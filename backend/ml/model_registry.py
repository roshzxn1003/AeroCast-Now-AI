"""
Model Registry, Promotion Gates, Artifact Integrity & Rollback System.
Phase 10 Operational Platform — Manages Machine Learning Lifecycles & Auditability.
"""
from __future__ import annotations

import os
import sys
import json
import uuid
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from db.database import get_db

class ModelStage(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


@dataclass
class ModelIdentity:
    """Scientific model identity specification."""
    model_id: str
    model_version: str
    model_family: str = "ResAtt-ConvLSTM2D"
    architecture_version: str = "2.0.0"
    training_dataset_version: str = "2026.09.001"
    feature_pipeline_version: str = "1.0.0"
    preprocessing_version: str = "1.0.0"
    training_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    code_version: str = "git-phase10"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionResult:
    success: bool
    message: str
    previous_model_id: Optional[str] = None
    promoted_model_id: Optional[str] = None
    gate_checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    """Manages model artifacts, promotions, rollbacks, artifact security, and lifecycle auditability."""

    def __init__(self, base_models_dir: Optional[str] = None):
        if base_models_dir is None:
            base_models_dir = str(Path(__file__).parent.parent / "models")
        self.models_dir = Path(base_models_dir)
        self.staging_dir = self.models_dir / "staging"
        self.production_dir = self.models_dir / "production"
        self.archive_dir = self.models_dir / "archive"

        # Ensure directory structure exists
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.production_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        self.db = get_db()
        self._sync_existing_models()

    def _sync_existing_models(self):
        """Discovers existing .keras models on disk and registers them in SQLite if absent."""
        existing = self.db.fetch_all("SELECT model_id FROM model_registry")
        existing_ids = {r["model_id"] for r in existing}

        candidate_models = [
            ("convlstm_real_best", "models/convlstm_real_best.keras", "1.0.0", "real"),
            ("convlstm_nowcaster", "models/convlstm_nowcaster.keras", "0.9.0", "simulation"),
            ("weather_lstm", "models/weather_lstm.keras", "0.1.0", "weather"),
        ]

        for model_id, rel_path, version, mode in candidate_models:
            full_path = Path(__file__).parent.parent / rel_path
            if full_path.exists() and model_id not in existing_ids:
                hasher = hashlib.sha256()
                with open(full_path, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                model_hash = hasher.hexdigest()

                # Load metadata if exists
                meta_file = self.models_dir / (
                    "model_metadata_real.json" if "real" in model_id else "model_metadata.json"
                )
                metrics = {}
                limitations = ["Requires GPU for < 200ms latency", "Domain restricted to Tamil Nadu / South India"]
                if meta_file.exists():
                    try:
                        with open(meta_file, "r") as mf:
                            metrics = json.load(mf)
                    except Exception:
                        pass

                is_prod = 1 if model_id == "convlstm_real_best" else 0
                stage = ModelStage.PRODUCTION.value if is_prod else ModelStage.STAGING.value
                now_utc = datetime.now(timezone.utc).isoformat()

                self.db.execute(
                    """
                    INSERT INTO model_registry (
                        model_id, model_name, version, stage, architecture,
                        dataset_version, feature_version, weights_path, model_hash,
                        created_at, promoted_at, promoted_by, metrics_json,
                        limitations_json, is_active_production
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        model_id,
                        version,
                        stage,
                        "ResAtt-ConvLSTM2D" if "convlstm" in model_id else "1D-LSTM",
                        "2026.09.001",
                        "1.0.0",
                        str(full_path),
                        model_hash,
                        now_utc,
                        now_utc if is_prod else None,
                        "system_init" if is_prod else None,
                        json.dumps(metrics),
                        json.dumps(limitations),
                        is_prod,
                    ),
                )

                # Track in model_artifacts table
                self.record_artifact(
                    model_id=model_id,
                    version=version,
                    file_path=str(full_path),
                    file_hash=model_hash,
                    file_size=full_path.stat().st_size,
                    status="VALID",
                )

    def record_artifact(
        self,
        model_id: str,
        version: str,
        file_path: str,
        file_hash: str,
        file_size: int,
        status: str = "VALID",
    ) -> None:
        """Records artifact integrity in model_artifacts table."""
        now_utc = datetime.now(timezone.utc).isoformat()
        art_id = f"ART-{uuid.uuid4().hex[:10].upper()}"
        try:
            self.db.execute(
                """
                INSERT OR REPLACE INTO model_artifacts (
                    artifact_id, model_id, version, file_path, file_hash,
                    file_size_bytes, framework_version, python_version,
                    created_at, verified_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    art_id,
                    model_id,
                    version,
                    file_path,
                    file_hash,
                    file_size,
                    "TensorFlow 2.18+",
                    sys.version.split()[0],
                    now_utc,
                    now_utc,
                    status,
                ),
            )
        except Exception:
            pass

    def verify_artifact_integrity(self, model_id: str) -> Tuple[bool, str, str]:
        """
        Verifies that model weights file exists and that computed SHA-256 matches
        the immutable hash stored in the model registry.
        Returns: (is_valid, registered_hash, computed_hash)
        """
        model = self.db.fetch_one("SELECT * FROM model_registry WHERE model_id = ?", (model_id,))
        if not model:
            return False, "", "MODEL_NOT_FOUND"

        weights_path = Path(model["weights_path"])
        reg_hash = model["model_hash"]

        if not weights_path.exists():
            self.record_artifact(model_id, model["version"], str(weights_path), reg_hash, 0, status="MISSING")
            return False, reg_hash, "FILE_MISSING"

        hasher = hashlib.sha256()
        with open(weights_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()

        is_valid = (actual_hash == reg_hash)
        status = "VALID" if is_valid else "CORRUPT"

        self.record_artifact(
            model_id=model_id,
            version=model["version"],
            file_path=str(weights_path),
            file_hash=actual_hash,
            file_size=weights_path.stat().st_size,
            status=status,
        )

        return is_valid, reg_hash, actual_hash

    def get_production_model(self) -> Optional[Dict[str, Any]]:
        """Returns metadata of currently active production model."""
        return self.db.fetch_one(
            "SELECT * FROM model_registry WHERE is_active_production = 1 LIMIT 1"
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """Lists all registered models across all stages."""
        return self.db.fetch_all("SELECT * FROM model_registry ORDER BY id DESC")

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves metadata of a specific model by ID."""
        return self.db.fetch_one("SELECT * FROM model_registry WHERE model_id = ?", (model_id,))

    def register_candidate_model(
        self,
        model_id: str,
        version: str,
        weights_path: str,
        architecture: str,
        dataset_version: str,
        feature_version: str,
        metrics: Dict[str, Any],
        limitations: List[str],
        stage: ModelStage = ModelStage.CANDIDATE,
    ) -> Dict[str, Any]:
        """Registers a newly trained candidate model into CANDIDATE or STAGING."""
        hasher = hashlib.sha256()
        with open(weights_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        model_hash = hasher.hexdigest()

        # Copy weights to staging directory
        staged_path = self.staging_dir / f"{model_id}_{version}.keras"
        shutil.copy2(weights_path, staged_path)

        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT OR REPLACE INTO model_registry (
                model_id, model_name, version, stage, architecture,
                dataset_version, feature_version, weights_path, model_hash,
                created_at, metrics_json, limitations_json, is_active_production
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                model_id,
                model_id,
                version,
                stage.value,
                architecture,
                dataset_version,
                feature_version,
                str(staged_path),
                model_hash,
                now,
                json.dumps(metrics),
                json.dumps(limitations),
            ),
        )

        # Record action
        self.record_action(
            action_type="REGISTER",
            model_id=model_id,
            version=version,
            actor="training_pipeline",
            reason="Candidate model registered after training",
            previous_state=None,
            new_state=stage.value,
            details={"weights_path": str(staged_path), "model_hash": model_hash},
        )

        return self.db.fetch_one("SELECT * FROM model_registry WHERE model_id = ?", (model_id,))

    def promote_to_production(
        self,
        model_id: str,
        promoted_by: str,
        force: bool = False,
        min_csi: float = 0.25,
        min_pod: float = 0.35,
        require_baseline_outperformance: bool = True,
    ) -> PromotionResult:
        """
        Promotes a candidate model to PRODUCTION after verifying quality gates and integrity.
        Archives the existing production model for instant rollback capability.
        """
        candidate = self.db.fetch_one(
            "SELECT * FROM model_registry WHERE model_id = ?", (model_id,)
        )
        if not candidate:
            return PromotionResult(success=False, message=f"Model {model_id} not found")

        current_prod = self.get_production_model()

        # 1. Verify artifact integrity before promotion
        is_intact, reg_hash, actual_hash = self.verify_artifact_integrity(model_id)
        if not is_intact:
            return PromotionResult(
                success=False,
                message=f"Model artifact integrity check failed! Registered: {reg_hash}, Actual: {actual_hash}",
                gate_checks={"artifact_integrity": False},
            )

        # 2. Evaluation Gate Checks
        metrics = json.loads(candidate.get("metrics_json") or "{}")
        csi_35 = metrics.get("csi_35", metrics.get("contingency", {}).get("35dBZ", {}).get("CSI", 0.0))
        pod_35 = metrics.get("pod_35", metrics.get("contingency", {}).get("35dBZ", {}).get("POD", 0.0))
        far_35 = metrics.get("far_35", metrics.get("contingency", {}).get("35dBZ", {}).get("FAR", 1.0))

        # Check vs persistence baseline if present in metrics
        persistence_csi = metrics.get("baseline_persistence_csi", 0.15)
        outperforms_baseline = csi_35 > persistence_csi if require_baseline_outperformance else True

        gate_checks = {
            "artifact_integrity": True,
            "csi_gate": csi_35 >= min_csi,
            "pod_gate": pod_35 >= min_pod,
            "far_gate": far_35 <= 0.65,
            "baseline_check": outperforms_baseline,
            "weights_exist": Path(candidate["weights_path"]).exists(),
        }

        if not force and not all(gate_checks.values()):
            failed_gates = [k for k, v in gate_checks.items() if not v]
            return PromotionResult(
                success=False,
                message=(
                    f"Model {model_id} failed promotion gates: {failed_gates}. "
                    f"CSI={csi_35:.3f} (req >= {min_csi}), POD={pod_35:.3f} (req >= {min_pod}). "
                    "Promotion rejected without manual operator override."
                ),
                gate_checks=gate_checks,
            )

        now = datetime.now(timezone.utc).isoformat()

        # 3. Archive current production model
        if current_prod:
            prev_id = current_prod["model_id"]
            archive_path = self.archive_dir / f"{prev_id}_{current_prod['version']}.keras"
            if Path(current_prod["weights_path"]).exists():
                shutil.copy2(current_prod["weights_path"], archive_path)

            self.db.execute(
                """
                UPDATE model_registry
                SET stage = ?, is_active_production = 0, weights_path = ?
                WHERE model_id = ?
                """,
                (ModelStage.RETIRED.value, str(archive_path), prev_id),
            )
            self.record_action(
                action_type="RETIRE",
                model_id=prev_id,
                version=current_prod["version"],
                actor=promoted_by,
                reason=f"Superseded by {model_id}",
                previous_state=ModelStage.PRODUCTION.value,
                new_state=ModelStage.RETIRED.value,
            )
        else:
            prev_id = None

        # 4. Copy candidate weights to production directory
        prod_path = self.production_dir / f"{model_id}_{candidate['version']}.keras"
        shutil.copy2(candidate["weights_path"], prod_path)

        # 5. Promote candidate
        self.db.execute(
            """
            UPDATE model_registry
            SET stage = ?, is_active_production = 1, weights_path = ?,
                promoted_at = ?, promoted_by = ?
            WHERE model_id = ?
            """,
            (ModelStage.PRODUCTION.value, str(prod_path), now, promoted_by, model_id),
        )

        # 6. Record action
        self.record_action(
            action_type="PROMOTE",
            model_id=model_id,
            version=candidate["version"],
            actor=promoted_by,
            reason=f"Promoted to PRODUCTION (forced={force})",
            previous_state=candidate["stage"],
            new_state=ModelStage.PRODUCTION.value,
            details={"previous_model": prev_id, "gate_checks": gate_checks},
        )

        return PromotionResult(
            success=True,
            message=f"Model {model_id} successfully promoted to PRODUCTION",
            previous_model_id=prev_id,
            promoted_model_id=model_id,
            gate_checks=gate_checks,
        )

    def rollback_production_model(
        self,
        target_model_id: Optional[str] = None,
        operator: str = "operator",
        reason: str = "Operational performance degradation",
    ) -> PromotionResult:
        """
        Rolls back production to a specified retired/archived model, or to the most recently retired model.
        """
        current_prod = self.get_production_model()
        if not current_prod:
            return PromotionResult(success=False, message="No active production model found to rollback from.")

        # Find target model
        if target_model_id:
            target = self.db.fetch_one(
                "SELECT * FROM model_registry WHERE model_id = ?", (target_model_id,)
            )
        else:
            target = self.db.fetch_one(
                """
                SELECT * FROM model_registry
                WHERE stage = ? AND model_id != ?
                ORDER BY id DESC LIMIT 1
                """,
                (ModelStage.RETIRED.value, current_prod["model_id"]),
            )

        if not target:
            return PromotionResult(success=False, message="No suitable candidate model found for rollback.")

        target_weights = Path(target["weights_path"])
        if not target_weights.exists():
            return PromotionResult(
                success=False, message=f"Rollback target weights not found at {target_weights}"
            )

        now = datetime.now(timezone.utc).isoformat()
        prev_id = current_prod["model_id"]
        target_id = target["model_id"]

        # 1. Demote current model to RETIRED
        self.db.execute(
            """
            UPDATE model_registry
            SET stage = ?, is_active_production = 0
            WHERE model_id = ?
            """,
            (ModelStage.RETIRED.value, prev_id),
        )

        # 2. Promote target model back to PRODUCTION
        prod_path = self.production_dir / f"{target_id}_{target['version']}.keras"
        shutil.copy2(str(target_weights), prod_path)

        self.db.execute(
            """
            UPDATE model_registry
            SET stage = ?, is_active_production = 1, weights_path = ?,
                promoted_at = ?, promoted_by = ?
            WHERE model_id = ?
            """,
            (ModelStage.PRODUCTION.value, str(prod_path), now, operator, target_id),
        )

        # 3. Record action
        self.record_action(
            action_type="ROLLBACK",
            model_id=target_id,
            version=target["version"],
            actor=operator,
            reason=reason,
            previous_state=target["stage"],
            new_state=ModelStage.PRODUCTION.value,
            details={"demoted_model": prev_id, "reason": reason},
        )

        return PromotionResult(
            success=True,
            message=f"Rolled back production from {prev_id} to {target_id}",
            previous_model_id=prev_id,
            promoted_model_id=target_id,
            gate_checks={"weights_exist": True, "rollback": True},
        )

    def record_action(
        self,
        action_type: str,
        model_id: str,
        version: str,
        actor: str,
        reason: str,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Writes an audit trail record into model_actions table."""
        action_id = f"ACT-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        try:
            self.db.execute(
                """
                INSERT INTO model_actions (
                    action_id, timestamp, action_type, model_id, version,
                    actor, reason, previous_state, new_state, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    now,
                    action_type,
                    model_id,
                    version,
                    actor,
                    reason,
                    previous_state,
                    new_state,
                    json.dumps(details or {}),
                ),
            )
        except Exception:
            pass

    def get_actions(self, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves audit trail actions."""
        if model_id:
            return self.db.fetch_all(
                "SELECT * FROM model_actions WHERE model_id = ? ORDER BY timestamp DESC LIMIT 100",
                (model_id,),
            )
        return self.db.fetch_all("SELECT * FROM model_actions ORDER BY timestamp DESC LIMIT 100")
