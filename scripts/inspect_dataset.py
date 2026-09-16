#!/usr/bin/env python3
"""
AeroCast-Now AI — Dataset Inspection Tool
=========================================
Inspects the built historical nowcasting dataset (.npz) and dataset statistics (.json),
displaying sample counts, shapes, class distributions, and data quality metrics.

Usage:
  python scripts/inspect_dataset.py
  python scripts/inspect_dataset.py --dataset-path data/sequences/nowcasting_dataset.npz
"""

import os
import sys
import json
import argparse
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Inspect AeroCast-Now Historical Nowcasting Dataset")
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=os.path.join(ROOT_DIR, "data", "sequences", "nowcasting_dataset.npz"),
        help="Path to nowcasting_dataset.npz"
    )
    parser.add_argument(
        "--stats-path",
        type=str,
        default=os.path.join(ROOT_DIR, "data", "metadata", "dataset_statistics.json"),
        help="Path to dataset_statistics.json"
    )
    args = parser.parse_args()

    if not os.path.exists(args.dataset_path):
        print(f"\n❌ Dataset file not found at: {args.dataset_path}")
        print("💡 Run the builder first: python scripts/build_dataset.py\n")
        sys.exit(1)

    # Load dataset
    data = np.load(args.dataset_path)
    X_train = data["X_train"]
    Y_train = data["Y_train"]
    X_val = data["X_val"]
    Y_val = data["Y_val"]
    X_test = data["X_test"]
    Y_test = data["Y_test"]

    storm_tr = data["storm_target_train"]
    storm_val = data["storm_target_val"]
    storm_te = data["storm_target_test"]

    lght_tr = data["lightning_target_train"]
    lght_val = data["lightning_target_val"]
    lght_te = data["lightning_target_test"]

    total_samples = len(X_train) + len(X_val) + len(X_test)
    total_storm = int(np.sum(storm_tr) + np.sum(storm_val) + np.sum(storm_te))
    total_non_storm = total_samples - total_storm
    total_lightning = int(np.sum(lght_tr > 0.05) + np.sum(lght_val > 0.05) + np.sum(lght_te > 0.05))

    stats = {}
    if os.path.exists(args.stats_path):
        try:
            with open(args.stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception:
            pass

    date_range_str = f"{stats.get('date_range', {}).get('start', 'N/A')} to {stats.get('date_range', {}).get('end', 'N/A')}"
    missing_pct = stats.get("missing_data_percentage", 0.0)
    region_info = stats.get("study_region", {}).get("name", "Configured Region")

    print("\n" + "="*50)
    print("       AEROCAST-NOW DATASET INSPECTION")
    print("="*50)
    print(f"Dataset Location : {args.dataset_path}")
    print(f"Study Region     : {region_info}")
    print(f"Date range       : {date_range_str}")
    print("-" * 50)
    print(f"Samples:")
    print(f"  Total          : {total_samples}")
    print(f"  Train          : {len(X_train)} ({len(X_train)/max(1, total_samples)*100:.1f}%)")
    print(f"  Validation     : {len(X_val)} ({len(X_val)/max(1, total_samples)*100:.1f}%)")
    print(f"  Test           : {len(X_test)} ({len(X_test)/max(1, total_samples)*100:.1f}%)")
    print("-" * 50)
    print(f"Spatial size     : {X_train.shape[2]} × {X_train.shape[3]}")
    print(f"Temporal frames  : {X_train.shape[1]} input frames -> {Y_train.shape[1]} forecast frames")
    print(f"Channels         : {X_train.shape[4]}")
    print("                   0: Radar dBZ [0-75 dBZ]")
    print("                   1: VIL [0-65 kg/m²]")
    print("                   2: Satellite TIR [-85 to +35 °C]")
    print("                   3: Lightning Flash Density [0-25 flashes/km²]")
    print("-" * 50)
    print(f"Input Shape      : (Batch, {X_train.shape[1]}, {X_train.shape[2]}, {X_train.shape[3]}, {X_train.shape[4]})")
    print(f"Target Shape     : (Batch, {Y_train.shape[1]}, {Y_train.shape[2]}, {Y_train.shape[3]}, {Y_train.shape[4]})")
    print("-" * 50)
    print(f"Missing data     : {missing_pct}%")
    print("-" * 50)
    print(f"Storm samples    : {total_storm} ({total_storm/max(1, total_samples)*100:.1f}%)")
    print(f"Non-storm samples: {total_non_storm} ({total_non_storm/max(1, total_samples)*100:.1f}%)")
    print(f"Lightning samples: {total_lightning} ({total_lightning/max(1, total_samples)*100:.1f}%)")
    print("-" * 50)
    print("Class Balance:")
    print(f"  Convective Storm Ratio : {total_storm/max(1, total_samples):.3f}")
    print(f"  Clear/Stratiform Ratio : {total_non_storm/max(1, total_samples):.3f}")
    print(f"  Lightning Activity     : {total_lightning/max(1, total_samples):.3f}")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
