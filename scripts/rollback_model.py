#!/usr/bin/env python3
"""
AeroCast-Now AI: Independent Production Model Rollback Utility
============================================================
Allows operators to roll back an underperforming or drifting model
in production without redeploying the entire application stack.
Logs all rollback actions to the immutable model_actions audit ledger.
"""

import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def list_models():
    from ml.model_registry import ModelRegistry
    reg = ModelRegistry()
    models = reg.list_models()
    print("\n=== Registered Models in Database ===")
    for m in models:
        active_tag = " [ACTIVE PRODUCTION]" if m.get("is_active_production") else ""
        print(f"• ID: {m.get('model_id'):<22} Ver: {m.get('version'):<8} Stage: {str(m.get('stage')):<12} Arch: {m.get('architecture')}{active_tag}")
    print()


def execute_rollback(operator: str, rationale: str, target_version: str = ""):
    from ml.model_registry import ModelRegistry
    from ml.model_manager import get_model_manager

    reg = ModelRegistry()
    current_prod = reg.get_production_model()
    curr_str = f"{current_prod.get('model_id')} (v{current_prod.get('version')})" if current_prod else "None"
    print(f"[*] Current active production model: {curr_str}")
    print(f"[*] Initiating rollback by operator '{operator}'...")
    print(f"    Rationale: {rationale}")

    result = reg.rollback_production_model(
        operator_id=operator,
        rationale=rationale,
        target_version=target_version if target_version else None
    )

    if result.success:
        print(f"\n[✓] Rollback Succeeded!")
        print(f"    Message: {result.message}")
        print(f"    Active Model: {result.model_id} (v{result.version})")
        # Reload memory in ModelManager
        mm = get_model_manager()
        mm.load_active_production_model()
        print(f"    ModelManager hot-reloaded: {mm.model_id} (v{mm.model_version})")
    else:
        print(f"\n[!] Rollback Failed: {result.message}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "list":
        list_models()
    elif sys.argv[1] == "rollback":
        op = sys.argv[2] if len(sys.argv) > 2 else "ops_lead"
        rat = sys.argv[3] if len(sys.argv) > 3 else "Operational rollback via Phase 12 utility"
        ver = sys.argv[4] if len(sys.argv) > 4 else ""
        execute_rollback(operator=op, rationale=rat, target_version=ver)
    else:
        print("Usage:")
        print("  python scripts/rollback_model.py list")
        print("  python scripts/rollback_model.py rollback <operator_id> <rationale> [target_version]")
