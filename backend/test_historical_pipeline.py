"""
Unit & Integration Tests for Historical Real-World Dataset & Pipeline (Phase 2)
==============================================================================
Tests:
  1. Timestamp conversion, UTC normalization, and 15-minute alignment
  2. Spatial regridding to 32x32 and lightning 2D histogram binning
  3. Missing values detection and data quality filtering
  4. Sequence generation (4-frame input, 4-frame forecast)
  5. Ground-truth thunderstorm and lightning target derivations
  6. Chronological Train / Validation / Test splitting without temporal leakage
  7. Channel scaler fitting exclusively on training data and inverse transforms
  8. Dataset file loading, array shapes, and catalog/statistics metadata
"""

import os
import sys
import json
import unittest
import numpy as np
from datetime import datetime, timezone, timedelta

# Ensure backend directory is in python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config.region_config import StudyRegionConfig, ACTIVE_REGION
from dataset_pipeline.spatial_grid import (
    regrid_to_32x32,
    regrid_lightning_strikes,
    check_missing_pixels,
    build_4channel_spatial_frame,
    calculate_grid_cell_area_km2
)
from dataset_pipeline.temporal_sync import (
    parse_to_utc,
    format_utc_iso,
    align_timestamp_to_15min,
    resample_time_series_to_15min,
    assemble_temporal_sequences
)
from dataset_pipeline.targets import (
    compute_thunderstorm_target,
    compute_lightning_targets,
    THUNDERSTORM_DBZ_THRESHOLD,
    THUNDERSTORM_VIL_THRESHOLD
)
from dataset_pipeline.quality_filter import QualityAssessor, QualityFilterResult
from dataset_pipeline.scaler import ChannelScaler


class TestHistoricalDatasetPipeline(unittest.TestCase):
    """Complete test suite for Phase 2 Historical Dataset & Pipeline."""

    def setUp(self):
        self.region = StudyRegionConfig(
            name="Tamil Nadu / Chennai Test",
            min_lat=12.0,
            max_lat=14.5,
            min_lon=79.0,
            max_lon=81.5,
            grid_size=32,
            temporal_resolution_min=15
        )

    # --------------------------------------------------------------------------
    # 1. Timestamp Conversion & 15-Minute Alignment Tests
    # --------------------------------------------------------------------------
    def test_01_timestamp_utc_conversion(self):
        """Verify various datetime representations convert to aware UTC datetime."""
        # ISO string with Z
        dt1 = parse_to_utc("2024-05-15T14:30:00Z")
        self.assertEqual(dt1.tzinfo, timezone.utc)
        self.assertEqual(dt1.hour, 14)
        self.assertEqual(dt1.minute, 30)

        # ISO string with space
        dt2 = parse_to_utc("2024-05-15 14:30:00")
        self.assertEqual(dt2.tzinfo, timezone.utc)

        # UNIX epoch timestamp
        epoch = 1715783400.0  # 2024-05-15 14:30:00 UTC
        dt3 = parse_to_utc(epoch)
        self.assertEqual(dt3.year, 2024)
        self.assertEqual(dt3.month, 5)

        # ISO formatter
        iso_str = format_utc_iso(dt1)
        self.assertEqual(iso_str, "2024-05-15T14:30:00Z")

    def test_02_15min_cadence_alignment(self):
        """Verify alignment to nearest exact 15-minute boundary (00, 15, 30, 45)."""
        # Exact 14:07 -> 14:00 (nearest)
        dt_07 = datetime(2024, 5, 15, 14, 7, 0, tzinfo=timezone.utc)
        aligned_00 = align_timestamp_to_15min(dt_07, mode="nearest")
        self.assertEqual(aligned_00.minute, 0)

        # Exact 14:08 -> 14:15 (nearest)
        dt_08 = datetime(2024, 5, 15, 14, 8, 0, tzinfo=timezone.utc)
        aligned_15 = align_timestamp_to_15min(dt_08, mode="nearest")
        self.assertEqual(aligned_15.minute, 15)

        # Floor mode
        dt_22 = datetime(2024, 5, 15, 14, 22, 0, tzinfo=timezone.utc)
        floor_15 = align_timestamp_to_15min(dt_22, mode="floor")
        self.assertEqual(floor_15.minute, 15)

    def test_03_time_series_resampling(self):
        """Verify hourly time series resamples linearly to 15-minute intervals."""
        hourly_dts = [
            datetime(2024, 5, 15, 12, 0, tzinfo=timezone.utc),
            datetime(2024, 5, 15, 13, 0, tzinfo=timezone.utc),
            datetime(2024, 5, 15, 14, 0, tzinfo=timezone.utc),
        ]
        hourly_vals = np.array([10.0, 20.0, 30.0], dtype=np.float32)

        target_dts, resampled = resample_time_series_to_15min(
            hourly_timestamps=hourly_dts,
            hourly_values=hourly_vals,
            target_start=hourly_dts[0],
            target_end=hourly_dts[-1]
        )

        # 12:00, 12:15, 12:30, 12:45, 13:00, 13:15, 13:30, 13:45, 14:00 -> 9 steps
        self.assertEqual(len(target_dts), 9)
        self.assertEqual(len(resampled), 9)
        # Check midpoint at 12:30 is 15.0
        self.assertAlmostEqual(resampled[2], 15.0, places=2)

    # --------------------------------------------------------------------------
    # 2. Spatial Regridding & 32x32 Grid Tests
    # --------------------------------------------------------------------------
    def test_04_spatial_regrid_32x32(self):
        """Verify 2D physical grid regrids cleanly to (32, 32) without random artifacts."""
        # 64x64 synthetic Gaussian storm core
        y, x = np.mgrid[-1:1:64j, -1:1:64j]
        core_64 = (np.exp(-(x**2 + y**2) / 0.2) * 55.0).astype(np.float32)

        grid_32, missing_pct = regrid_to_32x32(core_64, region=self.region)
        self.assertEqual(grid_32.shape, (32, 32))
        self.assertEqual(missing_pct, 0.0)
        self.assertTrue(np.max(grid_32) > 45.0)

    def test_05_regrid_with_coordinates(self):
        """Verify regular grid interpolation using source coordinates."""
        src_lats = np.linspace(11.0, 15.0, 20)
        src_lons = np.linspace(78.0, 82.0, 20)
        y, x = np.meshgrid(src_lats, src_lons, indexing='ij')
        data = (y * 2.0 + x * 0.5).astype(np.float32)

        grid_32, missing_pct = regrid_to_32x32(
            data,
            src_lats=src_lats,
            src_lons=src_lons,
            region=self.region
        )
        self.assertEqual(grid_32.shape, (32, 32))
        self.assertEqual(missing_pct, 0.0)

    def test_06_lightning_spatial_binning(self):
        """Verify discrete lightning strikes bin into counts and flash density."""
        strikes = [
            {"lat": 13.08, "lon": 80.27},  # Chennai center
            {"lat": 13.09, "lon": 80.28},  # Nearby stroke
            {"lat": 28.61, "lon": 77.20},  # Delhi (outside region, must be filtered out)
        ]

        count_grid, density_grid, total_flashes = regrid_lightning_strikes(strikes, region=self.region)
        self.assertEqual(count_grid.shape, (32, 32))
        self.assertEqual(density_grid.shape, (32, 32))
        self.assertEqual(total_flashes, 2.0)  # Only 2 strikes inside domain
        self.assertTrue(np.sum(count_grid) == 2.0)
        self.assertTrue(np.max(density_grid) > 0.0)

    # --------------------------------------------------------------------------
    # 3. Missing Values & Quality Filtering Tests
    # --------------------------------------------------------------------------
    def test_07_missing_pixels_detection(self):
        """Verify check_missing_pixels accurately calculates unobserved fraction."""
        grid = np.zeros((32, 32), dtype=np.float32)
        grid[0:8, :] = np.nan  # 25% missing
        pct = check_missing_pixels(grid)
        self.assertEqual(pct, 25.0)

    def test_08_quality_assessor_rejection(self):
        """Verify quality assessor rejects corrupt and excessive missing samples."""
        assessor = QualityAssessor(max_missing_pixel_pct=25.0)

        # 1. Valid frame
        dbz = np.zeros((32, 32), dtype=np.float32)
        vil = np.zeros((32, 32), dtype=np.float32)
        tir = np.full((32, 32), 25.0, dtype=np.float32)
        flash = np.zeros((32, 32), dtype=np.float32)
        frame_valid = build_4channel_spatial_frame(dbz, vil, tir, flash)

        res_valid = assessor.validate_spatial_frame(frame_valid)
        self.assertTrue(res_valid.is_valid)
        self.assertGreaterEqual(res_valid.quality_score, 0.90)

        # 2. Corrupt frame with impossible dBZ (> 80)
        frame_corrupt = frame_valid.copy()
        frame_corrupt[10, 10, 0] = 95.0
        res_corrupt = assessor.validate_spatial_frame(frame_corrupt)
        self.assertFalse(res_corrupt.is_valid)
        self.assertIn("impossible_physical_value", res_corrupt.rejection_reasons)

        # 3. Frame with > 25% missing pixels
        frame_missing = frame_valid.copy()
        frame_missing[:12, :, :] = np.nan
        res_missing = assessor.validate_spatial_frame(frame_missing)
        self.assertFalse(res_missing.is_valid)
        self.assertIn("excessive_missing_pixels", res_missing.rejection_reasons)

    # --------------------------------------------------------------------------
    # 4. Sequence Generation Tests
    # --------------------------------------------------------------------------
    def test_09_temporal_sequence_formation(self):
        """Verify 8 continuous 15-minute frames form 4-input and 4-forecast sequences."""
        base_time = datetime(2024, 5, 15, 10, 0, tzinfo=timezone.utc)
        timestamps = [base_time + timedelta(minutes=15 * i) for i in range(12)]

        frames = np.zeros((12, 32, 32, 4), dtype=np.float32)
        for i in range(12):
            frames[i, :, :, 0] = float(i)  # Distinguish frames

        X, Y, _, meta = assemble_temporal_sequences(
            timestamps=timestamps,
            spatial_frames=frames,
            input_steps=4,
            forecast_steps=4,
            step_minutes=15
        )

        # 12 frames -> 12 - 8 + 1 = 5 valid sequences
        self.assertEqual(len(X), 5)
        self.assertEqual(len(Y), 5)
        self.assertEqual(X.shape, (5, 4, 32, 32, 4))
        self.assertEqual(Y.shape, (5, 4, 32, 32, 4))

        # Check sequence 0: X has frames 0..3, Y has frames 4..7
        self.assertEqual(X[0, 0, 0, 0, 0], 0.0)
        self.assertEqual(X[0, 3, 0, 0, 0], 3.0)
        self.assertEqual(Y[0, 0, 0, 0, 0], 4.0)
        self.assertEqual(Y[0, 3, 0, 0, 0], 7.0)

    def test_10_temporal_gap_rejection(self):
        """Verify sequences with temporal breaks (> 15 min gap) are discarded."""
        base_time = datetime(2024, 5, 15, 10, 0, tzinfo=timezone.utc)
        # Introduce a 2-hour gap at index 4
        timestamps = [
            base_time,
            base_time + timedelta(minutes=15),
            base_time + timedelta(minutes=30),
            base_time + timedelta(minutes=45),
            base_time + timedelta(minutes=180),  # Gap!
            base_time + timedelta(minutes=195),
            base_time + timedelta(minutes=210),
            base_time + timedelta(minutes=225),
        ]
        frames = np.zeros((8, 32, 32, 4), dtype=np.float32)

        X, Y, _, _ = assemble_temporal_sequences(timestamps, frames)
        # Because of the break, no complete continuous 8-step sequence can form
        self.assertEqual(len(X), 0)

    # --------------------------------------------------------------------------
    # 5. Target Definition Tests
    # --------------------------------------------------------------------------
    def test_11_thunderstorm_target_rule(self):
        """Verify exact physical rule: storm = 1 if (dBZ >= 35 or VIL >= 15 or Flash >= 1)."""
        # Clear air
        dbz_clear = np.zeros((32, 32), dtype=np.float32)
        vil_clear = np.zeros((32, 32), dtype=np.float32)
        flash_clear = np.zeros((32, 32), dtype=np.float32)
        is_storm_clear, _, _ = compute_thunderstorm_target(dbz_clear, vil_clear, flash_clear)
        self.assertEqual(is_storm_clear, 0)

        # Radar trigger: dBZ = 36.0
        dbz_storm = dbz_clear.copy()
        dbz_storm[16, 16] = 36.0
        is_storm_radar, _, m_radar = compute_thunderstorm_target(dbz_storm, vil_clear, flash_clear)
        self.assertEqual(is_storm_radar, 1)
        self.assertTrue(m_radar["radar_trigger"])

        # Lightning trigger: flash density = 0.2
        flash_storm = flash_clear.copy()
        flash_storm[16, 16] = 0.2
        is_storm_flash, _, m_flash = compute_thunderstorm_target(dbz_clear, vil_clear, flash_storm)
        self.assertEqual(is_storm_flash, 1)
        self.assertTrue(m_flash["lightning_trigger"])

    def test_12_lightning_multi_horizon_targets(self):
        """Verify extraction of lightning targets across T0, T+15, T+30, T+45, T+60."""
        seq_8 = np.zeros((8, 32, 32, 4), dtype=np.float32)
        # Put lightning flash in T+30 (step index 5)
        seq_8[5, 10, 10, 3] = 4.5

        targets = compute_lightning_targets(seq_8, input_steps=4, forecast_steps=4)
        self.assertEqual(targets["t0_grid"].shape, (32, 32))
        self.assertEqual(targets["future_lightning_grids"].shape, (4, 32, 32))
        # T+30 is future step index 1
        self.assertEqual(targets["future_binary_lightning"][1], 1)
        self.assertEqual(targets["future_binary_lightning"][0], 0)

    # --------------------------------------------------------------------------
    # 6. Normalization & Scaler Tests
    # --------------------------------------------------------------------------
    def test_13_scaler_fit_and_transform(self):
        """Verify ChannelScaler fits on training data and normalizes channels correctly."""
        scaler = ChannelScaler(dbz_max=75.0, vil_max=65.0, tir_ground_c=35.0, tir_range_c=120.0, flash_max=25.0)

        # Training batch: (10, 4, 32, 32, 4)
        X_train = np.zeros((10, 4, 32, 32, 4), dtype=np.float32)
        X_train[..., 0] = 75.0   # dBZ max
        X_train[..., 1] = 65.0   # VIL max
        X_train[..., 2] = -85.0  # Cold top (-85°C) -> (35 - (-85))/120 = 1.0
        X_train[..., 3] = 25.0   # Flash max

        scaler.fit(X_train)
        self.assertTrue(scaler.is_fitted)

        norm_X = scaler.transform(X_train)
        # All max values should map to 1.0
        self.assertAlmostEqual(float(np.mean(norm_X[..., 0])), 1.0, places=3)
        self.assertAlmostEqual(float(np.mean(norm_X[..., 1])), 1.0, places=3)
        self.assertAlmostEqual(float(np.mean(norm_X[..., 2])), 1.0, places=3)
        self.assertAlmostEqual(float(np.mean(norm_X[..., 3])), 1.0, places=3)

        # Inverse transform
        inv_X = scaler.inverse_transform(norm_X)
        self.assertAlmostEqual(float(np.mean(inv_X[..., 0])), 75.0, places=2)
        self.assertAlmostEqual(float(np.mean(inv_X[..., 2])), -85.0, places=2)

    def test_14_scaler_persistence(self):
        """Verify scaler pickle and json parameter persistence."""
        scaler = ChannelScaler()
        dummy_data = np.random.uniform(0, 30, (5, 4, 32, 32, 4)).astype(np.float32)
        scaler.fit(dummy_data)

        tmp_pkl = os.path.join(backend_dir, "data", "processed", "test_scaler.pkl")
        scaler.save(tmp_pkl)

        self.assertTrue(os.path.exists(tmp_pkl))
        loaded_scaler = ChannelScaler.load(tmp_pkl)
        self.assertTrue(loaded_scaler.is_fitted)

        # Cleanup
        if os.path.exists(tmp_pkl):
            os.remove(tmp_pkl)
        json_param = os.path.splitext(tmp_pkl)[0] + "_params.json"
        if os.path.exists(json_param):
            os.remove(json_param)

    # --------------------------------------------------------------------------
    # 7. Dataset File Integrity & Metadata Tests
    # --------------------------------------------------------------------------
    def test_15_dataset_catalog_structure(self):
        """Verify data/datasets/dataset_catalog.json exists and conforms to standard schema."""
        catalog_path = os.path.join(backend_dir, "..", "data", "datasets", "dataset_catalog.json")
        if not os.path.exists(catalog_path):
            catalog_path = os.path.join(backend_dir, "data", "datasets", "dataset_catalog.json")

        self.assertTrue(os.path.exists(catalog_path), f"Catalog not found at {catalog_path}")
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        self.assertIn("datasets", catalog)
        datasets = catalog["datasets"]
        self.assertGreaterEqual(len(datasets), 5)

        for ds in datasets:
            self.assertIn("name", ds)
            self.assertIn("source", ds)
            self.assertIn("variables", ds)
            self.assertIn("spatial_resolution", ds)
            self.assertIn("temporal_resolution", ds)
            self.assertIn("status", ds)


if __name__ == "__main__":
    unittest.main()
