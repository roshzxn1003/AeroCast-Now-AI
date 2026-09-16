"""
AeroCast-Now AI — Thread-Safe Alert Storage & Lifecycle Management (Phase 7)
===========================================================================
Manages active alert registration, intelligent deduplication, acknowledgment,
temporal expiration, and historical logging.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta

from alerts.alert_models import AlertItem, RiskLevel, AlertCategory


class AlertStore:
    """Thread-safe in-memory store for active and historical convective alerts."""

    def __init__(self, max_history: int = 200, dedup_window_minutes: int = 20) -> None:
        self._lock = threading.Lock()
        self._active_alerts: Dict[str, AlertItem] = {}
        self._history: List[AlertItem] = []
        self._max_history = max_history
        self._dedup_window_minutes = dedup_window_minutes

    def add_alert(self, alert: AlertItem) -> Tuple[AlertItem, bool]:
        """
        Registers an alert with deduplication.
        If a similar alert exists for the same station & category within the dedup window:
          - If severity escalated: registers new alert and supersedes previous.
          - If same or lower severity: updates the validity window without creating duplicate spam.
        Returns:
          (stored_alert, is_new_or_escalated)
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge_expired_locked(now)

            # Check for existing matching active alert
            for existing_id, existing in list(self._active_alerts.items()):
                if existing.station == alert.station and existing.category == alert.category:
                    # Severity escalation check
                    severity_order = {
                        RiskLevel.NORMAL: 0,
                        RiskLevel.LOW: 1,
                        RiskLevel.MODERATE: 2,
                        RiskLevel.HIGH: 3,
                        RiskLevel.SEVERE: 4,
                    }
                    existing_sev = severity_order.get(existing.risk_level, 0)
                    new_sev = severity_order.get(alert.risk_level, 0)

                    if new_sev > existing_sev:
                        # Escalation: Retire older alert to history and add new higher severity alert
                        self._history.insert(0, existing)
                        del self._active_alerts[existing_id]
                        break
                    else:
                        # Same or lower severity: update validity window & assessment, preserve alert_id
                        existing.valid_until = alert.valid_until
                        existing.risk_assessment = alert.risk_assessment
                        existing.actions = alert.actions
                        existing.impacts = alert.impacts
                        return existing, False

            # Add brand new alert
            self._active_alerts[alert.alert_id] = alert
            self._history.insert(0, alert)
            if len(self._history) > self._max_history:
                self._history = self._history[:self._max_history]

            return alert, True

    def get_active_alerts(
        self,
        station: Optional[str] = None,
        min_severity: Optional[RiskLevel] = None
    ) -> List[AlertItem]:
        """Returns non-expired active alerts matching filter criteria."""
        now = datetime.now(timezone.utc)
        severity_order = {
            RiskLevel.NORMAL: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MODERATE: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.SEVERE: 4,
        }
        min_order = severity_order.get(min_severity, 0) if min_severity else 0

        with self._lock:
            self._purge_expired_locked(now)
            results = []
            for alert in self._active_alerts.values():
                if station and alert.station != station:
                    continue
                if severity_order.get(alert.risk_level, 0) < min_order:
                    continue
                results.append(alert)
            return sorted(results, key=lambda a: severity_order.get(a.risk_level, 0), reverse=True)

    def get_alert_history(
        self,
        limit: int = 50,
        station: Optional[str] = None
    ) -> List[AlertItem]:
        """Returns historical alerts sorted newest first."""
        with self._lock:
            if not station:
                return list(self._history[:limit])
            filtered = [a for a in self._history if a.station == station]
            return filtered[:limit]

    def acknowledge_alert(self, alert_id: str) -> Optional[AlertItem]:
        """Marks an active alert as acknowledged by an operator."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.acknowledged = True
                alert.ack_timestamp = now.isoformat()
                return alert
            for alert in self._history:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    alert.ack_timestamp = now.isoformat()
                    return alert
            return None

    def get_alert_by_id(self, alert_id: str) -> Optional[AlertItem]:
        """Looks up an alert by ID."""
        with self._lock:
            if alert_id in self._active_alerts:
                return self._active_alerts[alert_id]
            for a in self._history:
                if a.alert_id == alert_id:
                    return a
            return None

    def clear(self) -> None:
        """Resets the store (primarily for unit tests)."""
        with self._lock:
            self._active_alerts.clear()
            self._history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Returns overview statistics of current alert store."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge_expired_locked(now)
            counts: Dict[str, int] = {}
            for a in self._active_alerts.values():
                k = a.risk_level.value if isinstance(a.risk_level, RiskLevel) else str(a.risk_level)
                counts[k] = counts.get(k, 0) + 1
            return {
                "active_count": len(self._active_alerts),
                "historical_count": len(self._history),
                "by_severity": counts,
            }

    def _purge_expired_locked(self, now: datetime) -> None:
        """Internal helper to drop expired active alerts."""
        to_delete = []
        for alert_id, alert in self._active_alerts.items():
            try:
                valid_until_dt = datetime.fromisoformat(alert.valid_until)
                if valid_until_dt.tzinfo is None:
                    valid_until_dt = valid_until_dt.replace(tzinfo=timezone.utc)
                if now > valid_until_dt:
                    to_delete.append(alert_id)
            except Exception:
                pass
        for aid in to_delete:
            del self._active_alerts[aid]
