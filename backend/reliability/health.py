"""
Operational Health Probes & Component Diagnostics for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability, Security & Observability.

Endpoints:
- /health: Lightweight liveness probe (process responsiveness).
- /ready: Readiness probe with component dependency check.
- /live: Kubernetes liveness probe.
- /api/system/health: Comprehensive engineering health breakdown across all components.
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from fastapi.responses import JSONResponse

from db.database import get_db
from core.provider_health import ProviderHealthMonitor


class ReadinessState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"
    FAILED = "FAILED"
    MAINTENANCE = "MAINTENANCE"


class ComponentHealthEngine:
    """Evaluates granular health across all platform architectural failure domains."""

    @staticmethod
    def check_database() -> Tuple[ReadinessState, Dict[str, Any]]:
        db = get_db()
        try:
            row = db.fetch_one("SELECT 1 as alive")
            if row and row.get("alive") == 1:
                return ReadinessState.HEALTHY, {"status": "CONNECTED", "engine": "SQLite WAL"}
            return ReadinessState.NOT_READY, {"status": "UNRESPONSIVE"}
        except Exception as e:
            return ReadinessState.FAILED, {"status": "ERROR", "error": str(e)}

    @staticmethod
    def check_storage() -> Tuple[ReadinessState, Dict[str, Any]]:
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / "data"
        models_dir = base_dir / "models"
        
        try:
            data_ok = data_dir.exists() and os.access(str(data_dir), os.W_OK)
            models_ok = models_dir.exists() and os.access(str(models_dir), os.R_OK)
            
            if data_ok and models_ok:
                return ReadinessState.HEALTHY, {"data_dir": "READ_WRITE", "models_dir": "READABLE"}
            return ReadinessState.DEGRADED, {"data_dir": str(data_ok), "models_dir": str(models_ok)}
        except Exception as e:
            return ReadinessState.FAILED, {"error": str(e)}

    @staticmethod
    def check_model() -> Tuple[ReadinessState, Dict[str, Any]]:
        from ml.model_manager import get_model_manager
        mm = get_model_manager()
        status = mm.status
        is_ready = (status == "ready")
        
        if is_ready:
            return ReadinessState.HEALTHY, {
                "status": "READY",
                "model_id": mm.model_id,
                "version": mm.model_version,
                "architecture": getattr(mm, "architecture_version", "2.0.0"),
            }
        elif status == "degraded":
            return ReadinessState.DEGRADED, {"status": "DEGRADED", "model_id": mm.model_id}
        else:
            return ReadinessState.NOT_READY, {"status": status, "model_id": mm.model_id}

    @staticmethod
    def check_providers() -> Tuple[ReadinessState, Dict[str, Any]]:
        health_data = ProviderHealthMonitor.get_all_provider_health()
        providers = health_data.get("providers", {})
        if not providers:
            return ReadinessState.HEALTHY, {"providers_tracked": 0}

        unhealthy = [
            k for k, v in providers.items()
            if isinstance(v, dict) and v.get("status") in ("UNHEALTHY", "DEGRADED", "FAILED")
        ]
        if not unhealthy:
            return ReadinessState.HEALTHY, {"healthy_count": len(providers), "unhealthy_count": 0}
        elif len(unhealthy) < len(providers):
            return ReadinessState.DEGRADED, {
                "healthy_count": len(providers) - len(unhealthy),
                "unhealthy_count": len(unhealthy),
                "degraded_providers": unhealthy,
            }
        else:
            return ReadinessState.FAILED, {"all_providers_failing": True}

    @classmethod
    def get_full_health(cls) -> Dict[str, Any]:
        """Returns non-compressed component-level operational health breakdown."""
        db_state, db_info = cls.check_database()
        storage_state, storage_info = cls.check_storage()
        model_state, model_info = cls.check_model()
        prov_state, prov_info = cls.check_providers()

        # Overall platform state resolution:
        # Critical dependencies: Database and Model. If either is NOT_READY/FAILED => NOT_READY/FAILED.
        # If providers are degraded => DEGRADED.
        if db_state in (ReadinessState.NOT_READY, ReadinessState.FAILED) or model_state in (ReadinessState.NOT_READY, ReadinessState.FAILED):
            overall = ReadinessState.NOT_READY
        elif prov_state == ReadinessState.DEGRADED or storage_state == ReadinessState.DEGRADED:
            overall = ReadinessState.DEGRADED
        else:
            overall = ReadinessState.HEALTHY

        return {
            "overall_status": overall.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "database": {"state": db_state.value, **db_info},
                "storage": {"state": storage_state.value, **storage_info},
                "model": {"state": model_state.value, **model_info},
                "providers": {"state": prov_state.value, **prov_info},
            },
        }


def make_health_response():
    """Generates /health probe response."""
    return {"status": "HEALTHY", "timestamp": datetime.now(timezone.utc).isoformat()}


def make_live_response():
    """Generates /live probe response."""
    return {"status": "ALIVE", "timestamp": datetime.now(timezone.utc).isoformat()}


def make_ready_response():
    """Generates /ready probe response with HTTP status code reflecting service readiness."""
    health = ComponentHealthEngine.get_full_health()
    overall = health["overall_status"]
    
    # 200 OK for HEALTHY and DEGRADED (operational but with some non-critical alerts)
    # 503 Service Unavailable for NOT_READY and FAILED
    status_code = 200 if overall in (ReadinessState.HEALTHY.value, ReadinessState.DEGRADED.value) else 503
    return JSONResponse(status_code=status_code, content=health)
