"""
AeroCast-Now AI — Alert & Risk Assessment Data Models (Phase 7)
==============================================================
Standardized data structures for explainable risk assessment,
sector-specific impact estimation, and decision-support action items.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta


class RiskLevel(str, Enum):
    """Standardized internal AI risk levels."""
    NORMAL = "NORMAL"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


class AlertCategory(str, Enum):
    """Operational meteorological alert categories."""
    THUNDERSTORM_SURGE = "THUNDERSTORM_SURGE"
    LIGHTNING_JUMP = "LIGHTNING_JUMP"
    RAPID_INTENSIFICATION = "RAPID_INTENSIFICATION"
    HAIL_HAZARD = "HAIL_HAZARD"
    ASSET_PROXIMITY = "ASSET_PROXIMITY"
    SEVERE_CONVECTION = "SEVERE_CONVECTION"


class ImpactSector(str, Enum):
    """Socio-economic & critical infrastructure sectors for impact prediction."""
    AVIATION = "AVIATION"
    POWER_GRID = "POWER_GRID"
    PUBLIC_SAFETY = "PUBLIC_SAFETY"
    AGRICULTURE = "AGRICULTURE"


RISK_COLOR_MAP = {
    RiskLevel.NORMAL: "#10b981",    # Emerald
    RiskLevel.LOW: "#38bdf8",       # Sky Blue
    RiskLevel.MODERATE: "#f59e0b",  # Amber
    RiskLevel.HIGH: "#f97316",      # Orange
    RiskLevel.SEVERE: "#ef4444",    # Crimson Red
}


@dataclass
class RiskComponent:
    """Individual explainable sub-score contributing to overall convective risk."""
    name: str
    weight: float
    raw_value: float
    unit: str
    normalized_score: float  # [0.0 - 100.0]
    weighted_score: float    # weight * normalized_score
    level: RiskLevel
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "weight": round(self.weight, 3),
            "raw_value": round(self.raw_value, 2),
            "unit": self.unit,
            "normalized_score": round(self.normalized_score, 1),
            "weighted_score": round(self.weighted_score, 2),
            "level": self.level.value if isinstance(self.level, RiskLevel) else str(self.level),
            "explanation": self.explanation,
        }


@dataclass
class RiskAssessment:
    """Comprehensive, fully transparent multi-factor convective risk assessment."""
    overall_score: float     # [0.0 - 100.0]
    risk_level: RiskLevel
    color: str
    components: List[RiskComponent]
    summary: str
    primary_driver: str
    is_alert_triggered: bool
    confidence_score: float  # [0.0 - 1.0]
    disclaimer: str = (
        "AeroCast-Now AI Decision-Support Guidance. Internal AI risk advisory only — "
        "not an official India Meteorological Department (IMD) warning."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 1),
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else str(self.risk_level),
            "color": self.color,
            "components": [c.to_dict() for c in self.components],
            "summary": self.summary,
            "primary_driver": self.primary_driver,
            "is_alert_triggered": self.is_alert_triggered,
            "confidence_score": round(self.confidence_score, 2),
            "disclaimer": self.disclaimer,
        }


@dataclass
class SectorImpact:
    """Domain-specific impact prediction."""
    sector: ImpactSector
    severity: RiskLevel
    headline: str
    hazards: List[str]
    affected_assets: List[str]
    onset_lead_time_min: int
    duration_min: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector": self.sector.value if isinstance(self.sector, ImpactSector) else str(self.sector),
            "severity": self.severity.value if isinstance(self.severity, RiskLevel) else str(self.severity),
            "headline": self.headline,
            "hazards": self.hazards,
            "affected_assets": self.affected_assets,
            "onset_lead_time_min": self.onset_lead_time_min,
            "duration_min": self.duration_min,
        }


@dataclass
class DecisionSupportAction:
    """Concrete operational mitigation guidance."""
    action_id: str
    sector: ImpactSector
    priority: str  # "IMMEDIATE", "PRECAUTIONARY", "STANDBY"
    action: str
    lead_time_min: int
    target_audience: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "sector": self.sector.value if isinstance(self.sector, ImpactSector) else str(self.sector),
            "priority": self.priority,
            "action": self.action,
            "lead_time_min": self.lead_time_min,
            "target_audience": self.target_audience,
        }


@dataclass
class AlertItem:
    """Actionable AI Alert Item with full contextual decision support."""
    alert_id: str
    timestamp: str
    station: str
    target_lat: float
    target_lon: float
    risk_level: RiskLevel
    category: AlertCategory
    headline: str
    description: str
    trigger_reason: str
    lead_time_min: int
    valid_until: str
    impacts: List[SectorImpact]
    actions: List[DecisionSupportAction]
    risk_assessment: RiskAssessment
    cell_id: Optional[str] = None
    acknowledged: bool = False
    ack_timestamp: Optional[str] = None
    disclaimer: str = (
        "AI Decision Support Advisory: Not an official IMD warning. "
        "Designed for operational situational awareness and preemptive risk management."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp,
            "station": self.station,
            "target_lat": round(self.target_lat, 4),
            "target_lon": round(self.target_lon, 4),
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else str(self.risk_level),
            "category": self.category.value if isinstance(self.category, AlertCategory) else str(self.category),
            "headline": self.headline,
            "description": self.description,
            "trigger_reason": self.trigger_reason,
            "lead_time_min": self.lead_time_min,
            "valid_until": self.valid_until,
            "cell_id": self.cell_id,
            "impacts": [imp.to_dict() for imp in self.impacts],
            "actions": [act.to_dict() for act in self.actions],
            "risk_assessment": self.risk_assessment.to_dict() if hasattr(self.risk_assessment, "to_dict") else self.risk_assessment,
            "acknowledged": self.acknowledged,
            "ack_timestamp": self.ack_timestamp,
            "disclaimer": self.disclaimer,
        }
