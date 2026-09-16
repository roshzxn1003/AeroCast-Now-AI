#!/usr/bin/env python3
"""
AeroCast-Now AI — Historical Dataset Builder Script
===================================================
Builds a real-world multi-modal training and validation dataset for the
thunderstorm & lightning nowcasting ConvLSTM model.

Usage:
  python scripts/build_dataset.py --region tamil_nadu
  python scripts/build_dataset.py --start 2024-05-01 --end 2024-05-31
  python scripts/build_dataset.py --min-lat 12.0 --max-lat 14.5 --min-lon 79.0 --max-lon 81.5
"""

import os
import sys
import argparse
import logging

# Ensure project root and backend are in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config.region_config import StudyRegionConfig
from dataset_pipeline.builder import DatasetBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("build_dataset")


REGION_PRESETS = {
    "tamil_nadu": {
        "name": "Tamil Nadu / Chennai",
        "min_lat": 12.0,
        "max_lat": 14.5,
        "min_lon": 79.0,
        "max_lon": 81.5,
    },
    "chennai": {
        "name": "Chennai Metropolitan Area",
        "min_lat": 12.5,
        "max_lat": 13.8,
        "min_lon": 79.6,
        "max_lon": 80.8,
    },
    "india_south": {
        "name": "South India Convective Corridor",
        "min_lat": 10.0,
        "max_lat": 16.0,
        "min_lon": 76.0,
        "max_lon": 82.0,
    }
}


def main():
    parser = argparse.ArgumentParser(
        description="Build Historical Real-World Dataset for AeroCast-Now AI Nowcasting Model"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="tamil_nadu",
        help="Region preset (tamil_nadu, chennai, india_south) or custom (default: tamil_nadu)"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2024-05-01",
        help="Start date YYYY-MM-DD for historical reanalysis (default: 2024-05-01)"
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-05-31",
        help="End date YYYY-MM-DD for historical reanalysis (default: 2024-05-31)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.path.join(ROOT_DIR, "data"),
        help="Base data directory (default: data)"
    )
    parser.add_argument("--min-lat", type=float, default=None, help="Custom min latitude")
    parser.add_argument("--max-lat", type=float, default=None, help="Custom max latitude")
    parser.add_argument("--min-lon", type=float, default=None, help="Custom min longitude")
    parser.add_argument("--max-lon", type=float, default=None, help="Custom max longitude")
    parser.add_argument(
        "--no-sevir",
        action="store_true",
        help="Disable SEVIR benchmark severe convective storm events"
    )

    args = parser.parse_args()

    # Determine region configuration
    preset = REGION_PRESETS.get(args.region.lower(), REGION_PRESETS["tamil_nadu"])
    min_lat = args.min_lat if args.min_lat is not None else preset["min_lat"]
    max_lat = args.max_lat if args.max_lat is not None else preset["max_lat"]
    min_lon = args.min_lon if args.min_lon is not None else preset["min_lon"]
    max_lon = args.max_lon if args.max_lon is not None else preset["max_lon"]

    region_config = StudyRegionConfig(
        name=preset["name"],
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        grid_size=32,
        temporal_resolution_min=15
    )

    print("\n" + "="*70)
    print("🌍 AEROCAST-NOW AI — HISTORICAL DATASET BUILDER (PHASE 2)")
    print("="*70)
    print(f"Study Region     : {region_config.name}")
    print(f"Bounding Box     : Lat [{region_config.min_lat}°, {region_config.max_lat}°], Lon [{region_config.min_lon}°, {region_config.max_lon}°]")
    print(f"Grid Size        : {region_config.grid_size} x {region_config.grid_size} cells")
    print(f"Date Range       : {args.start} to {args.end}")
    print(f"Target Cadence   : 15 minutes (UTC)")
    print(f"Output Directory : {args.data_dir}")
    print("="*70 + "\n")

    builder = DatasetBuilder(
        region=region_config,
        data_dir=args.data_dir,
        train_ratio=0.70,
        val_ratio=0.15,
        test_ratio=0.15
    )

    stats = builder.build(
        start_date=args.start,
        end_date=args.end,
        include_sevir=not args.no_sevir
    )

    print("\n" + "="*70)
    print("✅ DATASET BUILD COMPLETE!")
    print("="*70)
    print(f"Total Valid Sequences  : {stats['number_of_samples']}")
    print(f"  - Training Set       : {stats['train_samples']} (70%)")
    print(f"  - Validation Set     : {stats['val_samples']} (15%)")
    print(f"  - Test Set           : {stats['test_samples']} (15%)")
    print(f"Input Tensor Shape     : (N, {', '.join(map(str, stats['input_shape']))})")
    print(f"Target Tensor Shape    : (N, {', '.join(map(str, stats['target_shape']))})")
    print(f"Storm Samples          : {stats['storm_sample_count']} ({stats['storm_class_ratio']*100:.1f}%)")
    print(f"Non-Storm Samples      : {stats['non_storm_sample_count']}")
    print(f"Lightning Samples      : {stats['lightning_sample_count']}")
    print(f"Missing Data Pct       : {stats['missing_data_percentage']}%")
    print(f"Scaler Location        : {os.path.join(args.data_dir, 'processed', 'scaler.pkl')}")
    print(f"Dataset Location       : {os.path.join(args.data_dir, 'sequences', 'nowcasting_dataset.npz')}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
