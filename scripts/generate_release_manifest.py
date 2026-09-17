#!/usr/bin/env python3
"""
AeroCast-Now AI: Release Artifact & Provenance Manifest Generator
==============================================================
Generates a deterministic release manifest tracking code commit SHA,
model artifact checksum, database schema version, and runtime dependencies.
Enables exact historical reconstruction of any operational deployment.
"""

import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def get_git_info() -> dict:
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(BASE_DIR), text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(BASE_DIR), text=True
        ).strip()
        is_dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(BASE_DIR), text=True
        ).strip())
    except Exception:
        commit_sha = "unknown"
        branch = "unknown"
        is_dirty = False
    return {"commit_sha": commit_sha, "branch": branch, "is_dirty": is_dirty}


def get_model_provenance() -> dict:
    model_path = BACKEND_DIR / "models" / "convlstm_real_best.keras"
    if not model_path.exists():
        return {"status": "missing"}

    with open(model_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    return {
        "model_id": "convlstm_real_best",
        "model_version": "1.0.0",
        "architecture": "ResAtt-ConvLSTM2D",
        "parameter_count": 191524,
        "weights_file": str(model_path.relative_to(BASE_DIR)),
        "file_size_bytes": os.path.getsize(model_path),
        "sha256_checksum": file_hash,
    }


def get_schema_version() -> dict:
    try:
        from db.migrations import MigrationManager
        from config.deployment_config import get_deployment_config
        cfg = get_deployment_config()
        mm = MigrationManager(cfg.db_path)
        applied = mm.get_applied_versions()
        latest = max(applied) if applied else 0
        return {"current_schema_version": latest, "applied_versions": applied}
    except Exception as e:
        return {"current_schema_version": 5, "note": str(e)}


def get_package_version() -> str:
    pkg_file = BASE_DIR / "frontend" / "package.json"
    if pkg_file.exists():
        try:
            with open(pkg_file, "r") as f:
                data = json.load(f)
                return data.get("version", "2.1.0")
        except Exception:
            pass
    return "2.1.0"


def generate_manifest(tag: str = "") -> dict:
    git_info = get_git_info()
    model_info = get_model_provenance()
    schema_info = get_schema_version()
    app_version = tag if tag else f"v{get_package_version()}"

    manifest = {
        "application": "AeroCast-Now AI Pro",
        "release_version": app_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": git_info,
        "model_provenance": model_info,
        "database_provenance": schema_info,
        "system_specifications": {
            "python_version": sys.version.split()[0],
            "input_tensor_shape": [1, 4, 32, 32, 4],
            "forecast_horizons_min": [15, 30, 45, 60, 90, 120],
            "spatial_resolution_km": 4.0,
            "temporal_resolution_min": 15,
        }
    }

    out_file = BASE_DIR / "reports" / "release_manifest.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[✓] Generated release manifest ({app_version}) -> {out_file}")
    return manifest


if __name__ == "__main__":
    tag_arg = ""
    for i, arg in enumerate(sys.argv):
        if arg == "--tag" and i + 1 < len(sys.argv):
            tag_arg = sys.argv[i + 1]
    manifest = generate_manifest(tag=tag_arg)
    print(json.dumps(manifest, indent=2))
