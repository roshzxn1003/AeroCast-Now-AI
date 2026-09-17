"""
Async Multi-Cadence Ingestion Scheduler.
Phase 9 Operational Data Infrastructure.

Manages autonomous background ingestion cycles matched to natural atmospheric cadences:
  - Lightning: 60s cadence (near-real-time stroke accumulation)
  - Radar: 600s / 10m cadence (volume scans / mosaic updates)
  - Satellite: 900s / 15m cadence (geostationary rapid-scan dissemination)
  - NWP / Soundings: 3600s / 60m cadence (convective analysis updates)
Guarantees staggered query offsets (jitter), error containment, and persistent tracking.
"""
from __future__ import annotations

import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ingestion.provider_manager import provider_manager
from ingestion.raw_storage import raw_storage
from db.database import db_manager

logger = logging.getLogger("aerocast.ingestion.scheduler")

class CadenceTaskConfig:
    def __init__(self, domain: str, interval_sec: float, initial_delay_sec: float = 2.0):
        self.domain = domain
        self.interval_sec = interval_sec
        self.initial_delay_sec = initial_delay_sec
        self.is_running = False
        self.last_run_time: Optional[str] = None
        self.last_success: bool = False
        self.run_count: int = 0
        self.failure_count: int = 0


class IngestionScheduler:
    """
    Coordinates asynchronous polling loops for all active meteorological domains.
    """

    DEFAULT_LAT = 13.0827  # Chennai regional hub
    DEFAULT_LON = 80.2707

    def __init__(self):
        self.tasks: Dict[str, CadenceTaskConfig] = {
            "LIGHTNING": CadenceTaskConfig("LIGHTNING", interval_sec=60.0, initial_delay_sec=1.0),
            "RADAR": CadenceTaskConfig("RADAR", interval_sec=600.0, initial_delay_sec=3.0),
            "SATELLITE": CadenceTaskConfig("SATELLITE", interval_sec=900.0, initial_delay_sec=5.0),
            "NWP": CadenceTaskConfig("NWP", interval_sec=3600.0, initial_delay_sec=7.0),
        }
        self._running_tasks: List[asyncio.Task] = []
        self._is_active: bool = False

    async def start(self) -> None:
        """Starts background loops for all registered domains."""
        if self._is_active:
            return

        self._is_active = True
        for domain, cfg in self.tasks.items():
            task = asyncio.create_task(self._run_loop(cfg))
            self._running_tasks.append(task)
        logger.info("IngestionScheduler started with %d multi-cadence loops.", len(self.tasks))

    async def stop(self) -> None:
        """Cancels all active scheduler loops."""
        self._is_active = False
        for task in self._running_tasks:
            task.cancel()
        await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()
        logger.info("IngestionScheduler stopped cleanly.")

    async def _run_loop(self, cfg: CadenceTaskConfig) -> None:
        """Single loop running at fixed interval with jitter."""
        # Initial stagger delay
        await asyncio.sleep(cfg.initial_delay_sec)
        cfg.is_running = True

        while self._is_active:
            try:
                t0 = datetime.now(timezone.utc)
                cfg.run_count += 1
                cfg.last_run_time = t0.isoformat()

                # Execute domain fetch via provider manager
                obs_list, meta = await provider_manager.fetch_domain(
                    domain_name=cfg.domain,
                    lat=self.DEFAULT_LAT,
                    lon=self.DEFAULT_LON,
                )

                if obs_list:
                    cfg.last_success = True
                    # Persist observations to database
                    for obs in obs_list:
                        raw_storage.persist_canonical_observation(obs)
                else:
                    cfg.last_success = False
                    cfg.failure_count += 1

                # Update provider status in DB
                self._update_db_provider_status(cfg.domain)

            except asyncio.CancelledError:
                break
            except Exception as e:
                cfg.last_success = False
                cfg.failure_count += 1
                logger.warning("Scheduler cycle error for domain %s: %s", cfg.domain, e)

            # Sleep interval with ±5% random jitter to avoid lockstep bursts
            jitter = random.uniform(-0.05, 0.05) * cfg.interval_sec
            sleep_duration = max(5.0, cfg.interval_sec + jitter)
            try:
                await asyncio.sleep(sleep_duration)
            except asyncio.CancelledError:
                break

        cfg.is_running = False

    def _update_db_provider_status(self, domain_name: str) -> None:
        """Synchronizes in-memory circuit and adapter metrics into provider_status table."""
        try:
            sys_health = provider_manager.get_system_health()
            domain_info = sys_health["domains"].get(domain_name, {})
            now_utc = datetime.now(timezone.utc).isoformat()

            for key in ["primary", "secondary"]:
                p = domain_info.get(key)
                if not p:
                    continue

                prov_id = p["provider_id"]
                db_manager.execute(
                    """
                    INSERT INTO provider_status (
                        provider_id, name, source_type, state, consecutive_failures,
                        total_requests, total_failures, last_success_time, last_failure_time,
                        last_latency_ms, fallback_count, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider_id) DO UPDATE SET
                        state = excluded.state,
                        consecutive_failures = excluded.consecutive_failures,
                        total_requests = excluded.total_requests,
                        total_failures = excluded.total_failures,
                        last_success_time = excluded.last_success_time,
                        last_failure_time = excluded.last_failure_time,
                        last_latency_ms = excluded.last_latency_ms,
                        fallback_count = excluded.fallback_count,
                        updated_at = excluded.updated_at
                    """,
                    (
                        prov_id,
                        p["name"],
                        p["source_type"],
                        p["circuit"]["state"],
                        p["circuit"]["consecutive_failures"],
                        p["circuit"]["total_calls"],
                        p["circuit"]["total_failures"],
                        p["circuit"]["last_success_time"],
                        p["circuit"]["last_failure_time"],
                        p["last_latency_ms"],
                        domain_info.get("total_fallbacks", 0),
                        now_utc,
                    ),
                )
        except Exception as e:
            logger.debug("Failed updating provider_status in DB: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """Returns live scheduler metrics."""
        return {
            "is_active": self._is_active,
            "tasks": {
                name: {
                    "interval_sec": cfg.interval_sec,
                    "is_running": cfg.is_running,
                    "last_run_time": cfg.last_run_time,
                    "last_success": cfg.last_success,
                    "run_count": cfg.run_count,
                    "failure_count": cfg.failure_count,
                }
                for name, cfg in self.tasks.items()
            },
        }

ingestion_scheduler = IngestionScheduler()
