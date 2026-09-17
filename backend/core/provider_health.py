"""
Provider Health & Readiness Probe Monitor.
Phase 8 Operational Platform — Measures Real Network Latency & Provider Availability.
"""
import time
import urllib.request
import urllib.error
import ssl
from typing import Dict, Any
from datetime import datetime, timezone
from db.database import get_db

class ProviderHealthMonitor:
    """Performs non-blocking HTTP/TCP health checks against real upstream data providers."""

    @staticmethod
    def check_sqlite() -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            db = get_db()
            db.fetch_one("SELECT 1")
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {"status": "HEALTHY", "latency_ms": latency_ms, "error": None}
        except Exception as e:
            return {"status": "UNHEALTHY", "latency_ms": None, "error": str(e)}

    @staticmethod
    def check_http_endpoint(url: str, timeout_sec: float = 3.0) -> Dict[str, Any]:
        t0 = time.perf_counter()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AeroCast-Now-HealthProbe/2.0"},
            method="HEAD",
        )
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as resp:
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                status_code = resp.getcode()
                is_healthy = 200 <= status_code < 400
                return {
                    "status": "HEALTHY" if is_healthy else "DEGRADED",
                    "http_status": status_code,
                    "latency_ms": latency_ms,
                    "error": None,
                }
        except urllib.error.HTTPError as he:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            # Even 403/405 indicates host is reachable
            return {
                "status": "DEGRADED" if he.code in (403, 405) else "UNHEALTHY",
                "http_status": he.code,
                "latency_ms": latency_ms,
                "error": f"HTTP {he.code}",
            }
        except Exception as e:
            return {
                "status": "UNHEALTHY",
                "http_status": None,
                "latency_ms": None,
                "error": str(e),
            }

    @classmethod
    def get_all_provider_health(cls) -> Dict[str, Any]:
        """Runs live health checks across all operational data providers."""
        now = datetime.now(timezone.utc).isoformat()
        db_health = cls.check_sqlite()
        open_meteo = cls.check_http_endpoint("https://api.open-meteo.com/v1/forecast?latitude=13.08&longitude=80.27&current=temperature_2m", timeout_sec=3.0)
        rainviewer = cls.check_http_endpoint("https://api.rainviewer.com/public/weather-maps.json", timeout_sec=3.0)
        mausam = cls.check_http_endpoint("https://mausam.imd.gov.in/Radar/caz_delhi.gif", timeout_sec=3.0)

        # Check Blitzortung status from live service
        from live_data_service import ldn_status
        blitz_status = ldn_status()

        overall = "HEALTHY"
        if open_meteo["status"] == "UNHEALTHY" and rainviewer["status"] == "UNHEALTHY":
            overall = "DEGRADED"
        if db_health["status"] == "UNHEALTHY":
            overall = "CRITICAL"

        return {
            "timestamp": now,
            "overall_status": overall,
            "providers": {
                "sqlite_store": db_health,
                "open_meteo_weather": open_meteo,
                "rainviewer_radar": rainviewer,
                "imd_mausam_dwr": mausam,
                "blitzortung_lightning": {
                    "status": "HEALTHY" if blitz_status.get("connected") else "STANDBY",
                    "connected": blitz_status.get("connected", False),
                    "buffered_strikes": blitz_status.get("buffered_strikes", 0),
                    "active_socket": blitz_status.get("active_host", "none"),
                },
            },
        }
