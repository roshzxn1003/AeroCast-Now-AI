"""
Host Resource & Environmental Telemetry Monitor for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability & Resource Protection.

Standard-library based telemetry monitor:
- CPU core count and system load average
- Process RSS memory via `resource` module
- System memory from /proc/meminfo
- Disk capacity and free bytes on /data partition
"""
from __future__ import annotations

import os
import shutil
import resource
from datetime import datetime, timezone
from typing import Dict, Any

from .logging import get_logger

logger = get_logger("aerocast.resource")


def _read_meminfo() -> Dict[str, float]:
    """Reads system total and available memory from /proc/meminfo if on Linux."""
    mem = {"total_mb": 4096.0, "available_mb": 2048.0, "used_pct": 50.0}
    try:
        if os.path.exists("/proc/meminfo"):
            values = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        values[k] = float(v)
            if "MemTotal" in values and "MemAvailable" in values:
                total_mb = values["MemTotal"] / 1024.0
                avail_mb = values["MemAvailable"] / 1024.0
                used_pct = round(((total_mb - avail_mb) / total_mb) * 100.0, 1)
                mem = {
                    "total_mb": round(total_mb, 1),
                    "available_mb": round(avail_mb, 1),
                    "used_pct": used_pct,
                }
    except Exception:
        pass
    return mem


class ResourceMonitor:
    """Tracks host resource health to prevent catastrophic OOM or disk-full crashes."""

    MEMORY_ALERT_THRESHOLD_PCT = 85.0
    DISK_ALERT_THRESHOLD_PCT = 90.0
    MIN_DISK_FREE_GB = 2.0

    @classmethod
    def get_resource_snapshot(cls) -> Dict[str, Any]:
        """Collects current CPU, memory, disk, and process telemetry using standard library."""
        # Process memory: Linux reports ru_maxrss in kilobytes
        usage = resource.getrusage(resource.RUSAGE_SELF)
        proc_mem_mb = round(usage.ru_maxrss / 1024.0, 2)

        # System memory
        sys_mem = _read_meminfo()
        sys_mem_pct = sys_mem["used_pct"]

        # Disk usage for data storage directory
        data_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/data"
        disk = shutil.disk_usage(data_dir if os.path.exists(data_dir) else "/")

        disk_total_gb = round(disk.total / (1024 ** 3), 2)
        disk_free_gb = round(disk.free / (1024 ** 3), 2)
        disk_used_pct = round((disk.used / disk.total) * 100.0, 1)

        # System load average (1m, 5m, 15m)
        load_avg = list(os.getloadavg()) if hasattr(os, "getloadavg") else [0.0, 0.0, 0.0]

        # Check for alert conditions
        is_mem_critical = sys_mem_pct >= cls.MEMORY_ALERT_THRESHOLD_PCT
        is_disk_critical = disk_used_pct >= cls.DISK_ALERT_THRESHOLD_PCT or disk_free_gb < cls.MIN_DISK_FREE_GB

        if is_mem_critical:
            logger.warning(
                f"Resource Alert: System memory at {sys_mem_pct}% (process RSS: {proc_mem_mb} MB)",
                extra={"event": "resource_memory_warning", "mem_pct": sys_mem_pct},
            )
        if is_disk_critical:
            logger.warning(
                f"Resource Alert: Disk usage at {disk_used_pct}% ({disk_free_gb} GB free)",
                extra={"event": "resource_disk_warning", "disk_pct": disk_used_pct},
            )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "CRITICAL" if (is_mem_critical or is_disk_critical) else "HEALTHY",
            "cpu": {
                "load_average_1m": round(load_avg[0], 2),
                "load_average_5m": round(load_avg[1], 2),
                "num_cores": os.cpu_count() or 1,
            },
            "memory": {
                "process_rss_mb": proc_mem_mb,
                "system_total_mb": sys_mem["total_mb"],
                "system_available_mb": sys_mem["available_mb"],
                "system_used_pct": sys_mem_pct,
                "is_critical": is_mem_critical,
            },
            "disk": {
                "total_gb": disk_total_gb,
                "free_gb": disk_free_gb,
                "used_pct": disk_used_pct,
                "is_critical": is_disk_critical,
            },
        }
