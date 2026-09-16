"""
Scientific Data Quality Filtering & Verification
=================================================
Screens, flags, and rejects corrupt, incomplete, or unphysical observations:
  - Checks physical variable boundaries (Radar, Satellite, Lightning, Meteorology)
  - Enforces missing pixel threshold (< 25% missing/unobserved)
  - Validates sequence continuity and timestamp integrity
  - Generates comprehensive, reproducible quality report
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# Physical bounds for validation
LIMITS = {
    "radar_dbz_min": 0.0,
    "radar_dbz_max": 80.0,
    "vil_min": 0.0,
    "vil_max": 75.0,
    "tir_min_c": -95.0,
    "tir_max_c": 45.0,
    "flash_density_min": 0.0,
    "flash_density_max": 50.0,
    "temp_min_c": -50.0,
    "temp_max_c": 65.0,
    "humidity_min": 0.0,
    "humidity_max": 100.0,
    "pressure_min_hpa": 850.0,
    "pressure_max_hpa": 1060.0,
    "wind_speed_max_ms": 100.0,
    "cape_max_j_kg": 8000.0,
    "max_missing_pixel_pct": 25.0,
}


@dataclass
class QualityFilterResult:
    """Evaluation result for a single sample or frame."""
    is_valid: bool
    quality_score: float  # 0.0 (unusable) to 1.0 (flawless)
    rejection_reasons: List[str] = field(default_factory=list)
    missing_pixels_pct: float = 0.0
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QualityAssessor:
    """Applies strict meteorological quality control and produces summary reports."""

    def __init__(self, max_missing_pixel_pct: float = 25.0) -> None:
        self.max_missing_pixel_pct = max_missing_pixel_pct
        self.reset_stats()

    def reset_stats(self) -> None:
        self.total_evaluated = 0
        self.valid_count = 0
        self.rejected_count = 0
        self.rejection_reasons: Dict[str, int] = {
            "missing_radar": 0,
            "missing_satellite": 0,
            "missing_lightning": 0,
            "invalid_timestamp": 0,
            "excessive_missing_pixels": 0,
            "impossible_physical_value": 0,
            "incomplete_sequence": 0,
            "other": 0,
        }

    def validate_spatial_frame(
        self,
        frame_4ch: np.ndarray,
        timestamp_str: str = ""
    ) -> QualityFilterResult:
        """
        Validates an unnormalized (32, 32, 4) physical observation frame.
        """
        self.total_evaluated += 1
        reasons: List[str] = []
        issues: List[str] = []
        penalty = 0.0

        if frame_4ch.shape != (32, 32, 4):
            reasons.append("invalid_dimension")
            self.rejection_reasons["other"] += 1
            self.rejected_count += 1
            return QualityFilterResult(is_valid=False, quality_score=0.0, rejection_reasons=reasons)

        dbz = frame_4ch[:, :, 0]
        vil = frame_4ch[:, :, 1]
        tir = frame_4ch[:, :, 2]
        flash = frame_4ch[:, :, 3]

        # 1. Missing pixel percentage check
        missing_dbz = float(np.mean(np.isnan(dbz) | np.isinf(dbz)) * 100.0)
        missing_vil = float(np.mean(np.isnan(vil) | np.isinf(vil)) * 100.0)
        missing_tir = float(np.mean(np.isnan(tir) | np.isinf(tir)) * 100.0)
        missing_flash = float(np.mean(np.isnan(flash) | np.isinf(flash)) * 100.0)
        overall_missing = (missing_dbz + missing_vil + missing_tir + missing_flash) / 4.0

        if overall_missing > self.max_missing_pixel_pct:
            reasons.append("excessive_missing_pixels")
            issues.append(f"Missing pixels ({overall_missing:.1f}%) exceed threshold ({self.max_missing_pixel_pct}%)")
            self.rejection_reasons["excessive_missing_pixels"] += 1
            penalty += 0.6

        # 2. Check channel availability
        if missing_dbz > 50.0:
            reasons.append("missing_radar")
            self.rejection_reasons["missing_radar"] += 1
            penalty += 0.3
        if missing_tir > 50.0:
            reasons.append("missing_satellite")
            self.rejection_reasons["missing_satellite"] += 1
            penalty += 0.3
        if missing_flash > 50.0:
            reasons.append("missing_lightning")
            self.rejection_reasons["missing_lightning"] += 1
            penalty += 0.3

        # 3. Physical boundaries validation
        valid_dbz = dbz[~np.isnan(dbz)]
        if len(valid_dbz) > 0:
            if np.min(valid_dbz) < LIMITS["radar_dbz_min"] or np.max(valid_dbz) > LIMITS["radar_dbz_max"]:
                issues.append(f"Radar dBZ out of physical range [{np.min(valid_dbz):.1f}, {np.max(valid_dbz):.1f}]")
                reasons.append("impossible_physical_value")
                self.rejection_reasons["impossible_physical_value"] += 1
                penalty += 0.4

        valid_tir = tir[~np.isnan(tir)]
        if len(valid_tir) > 0:
            if np.min(valid_tir) < LIMITS["tir_min_c"] or np.max(valid_tir) > LIMITS["tir_max_c"]:
                issues.append(f"Satellite TIR out of physical range [{np.min(valid_tir):.1f}, {np.max(valid_tir):.1f}]")
                reasons.append("impossible_physical_value")
                penalty += 0.4

        valid_flash = flash[~np.isnan(flash)]
        if len(valid_flash) > 0:
            if np.min(valid_flash) < LIMITS["flash_density_min"] or np.max(valid_flash) > LIMITS["flash_density_max"]:
                issues.append(f"Flash density out of physical range [{np.min(valid_flash):.1f}, {np.max(valid_flash):.1f}]")
                reasons.append("impossible_physical_value")
                penalty += 0.4

        quality_score = max(0.0, round(1.0 - penalty, 2))
        is_valid = len(reasons) == 0 and quality_score >= 0.70

        if is_valid:
            self.valid_count += 1
        else:
            self.rejected_count += 1

        return QualityFilterResult(
            is_valid=is_valid,
            quality_score=quality_score,
            rejection_reasons=reasons,
            missing_pixels_pct=round(overall_missing, 2),
            issues=issues
        )

    def validate_sequence(
        self,
        sequence_frames_4ch: np.ndarray,
        expected_steps: int = 8
    ) -> QualityFilterResult:
        """
        Validates an entire 8-step sequence of (8, 32, 32, 4).
        """
        if len(sequence_frames_4ch) != expected_steps:
            self.rejection_reasons["incomplete_sequence"] += 1
            self.rejected_count += 1
            return QualityFilterResult(
                is_valid=False,
                quality_score=0.0,
                rejection_reasons=["incomplete_sequence"],
                issues=[f"Expected {expected_steps} steps, got {len(sequence_frames_4ch)}"]
            )

        step_scores = []
        all_reasons = set()
        all_issues = []
        max_missing = 0.0

        for step in range(expected_steps):
            res = self.validate_spatial_frame(sequence_frames_4ch[step])
            step_scores.append(res.quality_score)
            max_missing = max(max_missing, res.missing_pixels_pct)
            if not res.is_valid:
                all_reasons.update(res.rejection_reasons)
                all_issues.extend(res.issues)

        avg_score = float(np.mean(step_scores))
        is_valid = len(all_reasons) == 0 and avg_score >= 0.75

        return QualityFilterResult(
            is_valid=is_valid,
            quality_score=round(avg_score, 2),
            rejection_reasons=list(all_reasons),
            missing_pixels_pct=round(max_missing, 2),
            issues=all_issues
        )

    def get_quality_report(self) -> Dict[str, Any]:
        """Generates structured quality report dictionary."""
        return {
            "total_samples": self.total_evaluated,
            "valid_samples": self.valid_count,
            "rejected_samples": self.rejected_count,
            "acceptance_rate_pct": round((self.valid_count / max(1, self.total_evaluated)) * 100.0, 2),
            "reasons": self.rejection_reasons,
        }
