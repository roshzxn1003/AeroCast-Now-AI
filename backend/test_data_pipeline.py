"""
Unit & Integration Tests for Real Data Ingestion & Preprocessing Pipeline
=========================================================================
Tests:
  1. DataConfig configuration & mode detection
  2. NormalizedObservation schema & DataQualityReport contracts
  3. Meteorological cleaning, range bounds, and quality score computation
  4. 15-minute time synchronization and alignment
  5. Physical channel normalization and inverse scaling
  6. Spatio-temporal 4D tensor sequence assembly (4, 32, 32, 4)
  7. Weather, radar, satellite, and lightning providers
  8. Standardized FastAPI REST endpoints (/api/data/*)
"""

import os
import unittest
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from config.data_config import DATA_CONFIG, DataConfig
from data_ingestion.base import DataQualityReport, NormalizedObservation
from preprocessing.cleaning import (
    validate_observation,
    clean_observation,
    TEMP_MIN_C,
    TEMP_MAX_C,
)
from preprocessing.interpolation import (
    align_to_15min_cadence,
    synchronize_time_series,
    interpolate_scalar_gap,
)
from preprocessing.normalization import (
    normalize_channels,
    denormalize_dbz,
    denormalize_vil,
    denormalize_tir,
    denormalize_flash,
)
from preprocessing.feature_engineering import (
    assemble_spatial_tensor_sequence,
    derive_thermodynamic_sounding,
)
from data_ingestion.lightning_ingest import BlitzortungLightningProvider
from data_ingestion.radar_ingest import IMDRadarProvider
from data_ingestion.satellite_ingest import INSATSatelliteProvider
from data_ingestion.weather_ingest import OpenMeteoWeatherProvider
from api_server import app


class TestDataPipeline(unittest.TestCase):
    """Complete test suite for Phase 1 Data Ingestion Architecture."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # --------------------------------------------------------------------------
    # 1. Configuration Tests
    # --------------------------------------------------------------------------
    def test_01_config_initialization(self):
        """Verify DataConfig paths, default mode, and directory creation."""
        cfg = DataConfig()
        self.assertIn(cfg.data_mode, ["simulation", "real", "hybrid"])
        self.assertTrue(os.path.exists(cfg.raw_data_dir))
        self.assertTrue(os.path.exists(cfg.processed_data_dir))
        self.assertEqual(cfg.grid_size, 32)
        self.assertEqual(cfg.time_steps_history, 4)

    # --------------------------------------------------------------------------
    # 2. Schema & Quality Tests
    # --------------------------------------------------------------------------
    def test_02_normalized_observation_schema(self):
        """Verify NormalizedObservation schema defaults and serialization."""
        obs = NormalizedObservation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            latitude=13.0827,
            longitude=80.2707,
            station_id="chennai_dwr",
            station_name="Chennai DWR",
            temperature_c=31.5,
            relative_humidity_pct=78.0,
            pressure_hpa=1008.2,
            wind_speed_ms=6.4,
            wind_direction_deg=110.0,
            rainfall_mm_h=2.5,
            cloud_cover_pct=85.0,
            cape_j_kg=2450.0,
            cin_j_kg=-45.0,
            lifted_index_c=-4.8,
            precipitable_water_mm=54.0,
            wind_shear_0_6km_kts=22.0,
        )
        data = obs.to_dict()
        self.assertEqual(data["station_id"], "chennai_dwr")
        self.assertEqual(data["temperature_c"], 31.5)
        self.assertEqual(data["cape_j_kg"], 2450.0)
        self.assertIn("quality", data)

    def test_03_quality_scoring_clean_data(self):
        """Verify high quality score for valid physical observation."""
        obs = NormalizedObservation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            latitude=28.61,
            longitude=77.21,
            station_id="delhi",
            station_name="Delhi NCR",
            temperature_c=28.0,
            relative_humidity_pct=65.0,
            pressure_hpa=1012.0,
            wind_speed_ms=4.5,
        )
        report = validate_observation(obs)
        self.assertTrue(report.valid)
        self.assertGreaterEqual(report.quality_score, 0.85)
        self.assertEqual(len(report.issues), 0)

    def test_04_quality_scoring_impossible_values(self):
        """Verify quality penalty and failure on impossible meteorological values."""
        bad_obs = NormalizedObservation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            latitude=28.61,
            longitude=77.21,
            station_id="delhi",
            station_name="Delhi NCR",
            temperature_c=85.0,        # Impossible temp
            relative_humidity_pct=150.0, # Impossible humidity
            pressure_hpa=500.0,         # Impossible surface pressure
            wind_speed_ms=250.0,        # Impossible wind speed
        )
        report = validate_observation(bad_obs)
        self.assertFalse(report.valid)
        self.assertLess(report.quality_score, 0.5)
        self.assertGreaterEqual(len(report.issues), 4)

    def test_05_stale_observation_detection(self):
        """Verify detection of observations older than TTL."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        stale_obs = NormalizedObservation(
            timestamp=old_time,
            latitude=28.61,
            longitude=77.21,
            station_id="delhi",
            station_name="Delhi NCR",
            temperature_c=25.0,
            relative_humidity_pct=50.0,
            pressure_hpa=1013.0,
            wind_speed_ms=3.0,
        )
        report = validate_observation(stale_obs, max_age_hours=3.0)
        self.assertTrue(report.is_stale)
        self.assertTrue(any("Stale observation" in issue for issue in report.issues))

    # --------------------------------------------------------------------------
    # 3. Time Synchronization Tests
    # --------------------------------------------------------------------------
    def test_06_time_cadence_alignment(self):
        """Verify alignment of observations to 15-minute intervals."""
        now = datetime.now(timezone.utc)
        self.assertEqual(align_to_15min_cadence(now, now), 3)  # T0
        self.assertEqual(align_to_15min_cadence(now - timedelta(minutes=15), now), 2)  # T-15m
        self.assertEqual(align_to_15min_cadence(now - timedelta(minutes=30), now), 1)  # T-30m
        self.assertEqual(align_to_15min_cadence(now - timedelta(minutes=45), now), 0)  # T-45m

    def test_07_synchronize_time_series(self):
        """Verify synchronization of multi-step sequence into 4 discrete slots."""
        now = datetime.now(timezone.utc)
        obs_list = [
            NormalizedObservation(timestamp=(now - timedelta(minutes=45)).isoformat(), latitude=13.0, longitude=80.0, station_id="s1", station_name="S1"),
            NormalizedObservation(timestamp=(now - timedelta(minutes=15)).isoformat(), latitude=13.0, longitude=80.0, station_id="s1", station_name="S1"),
            NormalizedObservation(timestamp=now.isoformat(), latitude=13.0, longitude=80.0, station_id="s1", station_name="S1"),
        ]
        slots = synchronize_time_series(obs_list, target_intervals=4, reference_dt=now)
        self.assertEqual(len(slots), 4)
        self.assertIsNotNone(slots[0])  # T-45m
        self.assertIsNone(slots[1])     # T-30m missing
        self.assertIsNotNone(slots[2])  # T-15m
        self.assertIsNotNone(slots[3])  # T0

    # --------------------------------------------------------------------------
    # 4. Normalization & Spatial Gridding Tests
    # --------------------------------------------------------------------------
    def test_08_channel_normalization_and_inversion(self):
        """Verify normalization bounds [0, 1] and accurate inversion."""
        dbz = np.array([[0.0, 37.5, 75.0]], dtype=np.float32)
        vil = np.array([[0.0, 32.5, 65.0]], dtype=np.float32)
        tir = np.array([[35.0, -25.0, -85.0]], dtype=np.float32)
        flash = np.array([[0.0, 12.5, 25.0]], dtype=np.float32)

        norm = normalize_channels(dbz, vil, tir, flash)
        self.assertEqual(norm.shape, (1, 3, 4))
        self.assertTrue(np.all(norm >= 0.0) and np.all(norm <= 1.0))

        # Check inversion accuracy
        restored_dbz = denormalize_dbz(norm[..., 0])
        np.testing.assert_allclose(restored_dbz, dbz, atol=1e-4)

        restored_tir = denormalize_tir(norm[..., 2])
        np.testing.assert_allclose(restored_tir, tir, atol=1e-4)

    def test_09_spatial_tensor_sequence_assembly(self):
        """Verify 4D spatio-temporal tensor assembly (4, 32, 32, 4)."""
        grid_size = 32
        dbz = np.zeros((grid_size, grid_size), dtype=np.float32)
        dbz[14:18, 14:18] = 52.0  # Convective core
        vil = dbz * 0.4
        tir = np.full((grid_size, grid_size), 22.0, dtype=np.float32)
        tir[14:18, 14:18] = -55.0  # Cold top
        flash = np.zeros((grid_size, grid_size), dtype=np.float32)
        flash[15, 15] = 18.0

        tensor = assemble_spatial_tensor_sequence(dbz, vil, tir, flash, history_steps=4)
        self.assertEqual(tensor.shape, (4, 32, 32, 4))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertTrue(np.all(tensor >= 0.0) and np.all(tensor <= 1.0))

    # --------------------------------------------------------------------------
    # 5. Lightning Density Grid Calculation
    # --------------------------------------------------------------------------
    def test_10_lightning_density_grid(self):
        """Verify conversion of discrete strikes to 32x32 density grid."""
        provider = BlitzortungLightningProvider()
        strikes = [
            {"lat": 13.08, "lon": 80.27, "type": "CG"},
            {"lat": 13.09, "lon": 80.28, "type": "IC"},
            {"lat": 13.07, "lon": 80.26, "type": "CG"},
        ]
        grid, rate, meta = provider.calculate_density_grid(
            strikes, center_lat=13.08, center_lon=80.27, grid_size=32, domain_radius_km=128.0
        )
        self.assertEqual(grid.shape, (32, 32))
        self.assertEqual(meta["total_strikes"], 3)
        self.assertGreater(rate, 0.0)
        self.assertGreater(np.max(grid), 0.0)

    # --------------------------------------------------------------------------
    # 6. REST API Endpoints Tests
    # --------------------------------------------------------------------------
    def test_11_api_data_status(self):
        """Verify GET /api/data/status responds with mode and provider health."""
        resp = self.client.get("/api/data/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("mode", data)
        self.assertIn("sources", data)
        self.assertIn("weather", data["sources"])
        self.assertIn("radar", data["sources"])
        self.assertIn("satellite", data["sources"])
        self.assertIn("lightning", data["sources"])
        self.assertIn("quality_score", data)

    def test_12_api_data_weather(self):
        """Verify GET /api/data/weather responds with normalized schema."""
        resp = self.client.get("/api/data/weather?station=Chennai DWR (Sriharikota/Port)")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["station_id"], "Chennai DWR (Sriharikota/Port)")
        self.assertIn("quality", data)

    def test_13_api_data_lightning(self):
        """Verify GET /api/data/lightning responds with flash density telemetry."""
        resp = self.client.get("/api/data/lightning?lat=13.08&lon=80.27&radius_km=200")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_strikes", data)
        self.assertIn("flash_rate_fpm", data)

    def test_14_api_data_radar(self):
        """Verify GET /api/data/radar responds with radar grid metadata."""
        resp = self.client.get("/api/data/radar?station=Delhi NCR DWR (Palam/Mausam Bhawan)")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("max_dbz", data)
        self.assertIn("metadata", data)

    def test_15_api_data_current(self):
        """Verify GET /api/data/current returns fully assembled station observation."""
        resp = self.client.get("/api/data/current?station=Chennai DWR (Sriharikota/Port)")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("station_id", data)
        self.assertIn("radar_max_dbz", data)
        self.assertIn("quality", data)
        self.assertTrue(data["quality"]["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
