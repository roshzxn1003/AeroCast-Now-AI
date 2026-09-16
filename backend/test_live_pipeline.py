"""
Unit and Integration Tests for Phase 5 Live Nowcasting Pipeline
===============================================================
Validates:
  1. Base & Specialized Observation Providers (Radar, Satellite, Lightning, Weather)
  2. Physical Sanity & Out-of-Bounds Validation (dBZ, VIL, TIR, Flash)
  3. Meteorological Freshness Auditing (Fresh, Delayed, Stale, Missing, Invalid)
  4. Rolling Observation Buffer & 15-min Temporal Synchronization
  5. Scientific Honesty & Zero Fabrication Enforcement in 'real' Mode
  6. Hybrid Warmup and Simulation Convective Pipelines
  7. ML Model Loading (Residual-Attention ConvLSTM2D) & Inference Service
  8. SCIT Storm Tracking, 2-Sigma Lightning Jump, and CAP Alert Generation
  9. FastAPI Endpoints (/api/live/nowcast and /api/live/status)
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from providers import (
    BaseObservationProvider,
    ProviderResult,
    ObservationQuality,
    RadarProvider,
    SatelliteProvider,
    LightningProvider,
    WeatherProvider,
    FRESH_THRESHOLD_MIN,
    DELAYED_THRESHOLD_MIN,
)
from live import (
    FreshnessTracker,
    StreamFreshness,
    PipelineFreshnessReport,
    ObservationManager,
    ObservationFrame,
    LiveNowcastPipeline,
)
from ml import (
    ModelLoader,
    PredictionPostprocessor,
    LiveInferenceService,
    grid_to_heatmap,
)
from fastapi.testclient import TestClient
from api_server import app, _live_pipeline, _live_inference_service


class TestObservationProviders(unittest.TestCase):
    """Unit tests for atmospheric observation providers."""

    def test_radar_provider_validation_valid(self):
        provider = RadarProvider()
        valid_data = {
            "dbz_grid": np.full((32, 32), 35.0, dtype=np.float32),
            "vil_grid": np.full((32, 32), 15.0, dtype=np.float32),
        }
        quality = provider.validate(valid_data)
        self.assertTrue(quality.valid)
        self.assertEqual(quality.quality_score, 1.0)
        self.assertFalse(quality.out_of_bounds)

    def test_radar_provider_validation_invalid_bounds(self):
        provider = RadarProvider()
        invalid_data = {
            "dbz_grid": np.full((32, 32), 85.0, dtype=np.float32),  # > 75.0
            "vil_grid": np.full((32, 32), -5.0, dtype=np.float32),  # < 0.0
        }
        quality = provider.validate(invalid_data)
        self.assertFalse(quality.valid)
        self.assertTrue(quality.out_of_bounds)
        self.assertGreater(len(quality.issues), 0)

    def test_radar_provider_validation_nan_inf(self):
        provider = RadarProvider()
        nan_grid = np.zeros((32, 32), dtype=np.float32)
        nan_grid[10, 10] = np.nan
        quality = provider.validate({
            "dbz_grid": nan_grid,
            "vil_grid": np.zeros((32, 32), dtype=np.float32),
        })
        self.assertFalse(quality.valid)
        self.assertTrue(any("NaN" in issue for issue in quality.issues))

    def test_satellite_provider_validation(self):
        provider = SatelliteProvider()
        valid_data = {"tir_grid": np.full((32, 32), -25.0, dtype=np.float32)}
        quality = provider.validate(valid_data)
        self.assertTrue(quality.valid)

        out_of_bounds = {"tir_grid": np.full((32, 32), -100.0, dtype=np.float32)}  # < -85.0
        quality_oob = provider.validate(out_of_bounds)
        self.assertFalse(quality_oob.valid)
        self.assertTrue(quality_oob.out_of_bounds)

    def test_lightning_provider_validation(self):
        provider = LightningProvider()
        valid_data = {
            "flash_density_grid": np.full((32, 32), 4.5, dtype=np.float32),
            "flash_rate_fpm": 12.0,
            "strike_count": 30,
        }
        quality = provider.validate(valid_data)
        self.assertTrue(quality.valid)

        invalid_data = {
            "flash_density_grid": np.full((32, 32), 35.0, dtype=np.float32),  # > 25.0
            "flash_rate_fpm": -2.0,  # negative
            "strike_count": 0,
        }
        quality_inv = provider.validate(invalid_data)
        self.assertFalse(quality_inv.valid)
        self.assertTrue(quality_inv.out_of_bounds)

    def test_weather_provider_validation(self):
        provider = WeatherProvider()
        valid_data = {
            "cape_j_kg": 2500.0,
            "cin_j_kg": -45.0,
            "relative_humidity_pct": 82.0,
            "temperature_c": 31.5,
            "pressure_hpa": 1008.0,
        }
        quality = provider.validate(valid_data)
        self.assertTrue(quality.valid)

        invalid_data = {
            "cape_j_kg": 9000.0,  # > 7000
            "relative_humidity_pct": 120.0,  # > 100
        }
        quality_inv = provider.validate(invalid_data)
        self.assertFalse(quality_inv.valid)


class TestFreshnessTracker(unittest.TestCase):
    """Unit tests for meteorological data latency and freshness classification."""

    def setUp(self):
        self.tracker = FreshnessTracker(fresh_threshold_min=20.0, delayed_threshold_min=60.0)

    def test_fresh_data(self):
        now = datetime.now(timezone.utc)
        obs_time = now - timedelta(minutes=10)
        status = self.tracker.compute_stream_status("radar", obs_time)
        self.assertEqual(status.status, "fresh")
        self.assertAlmostEqual(status.age_minutes, 10.0, delta=1.0)

    def test_delayed_data(self):
        now = datetime.now(timezone.utc)
        obs_time = now - timedelta(minutes=35)
        status = self.tracker.compute_stream_status("satellite", obs_time)
        self.assertEqual(status.status, "delayed")
        self.assertAlmostEqual(status.age_minutes, 35.0, delta=1.0)

    def test_stale_data(self):
        now = datetime.now(timezone.utc)
        obs_time = now - timedelta(minutes=90)
        status = self.tracker.compute_stream_status("radar", obs_time)
        self.assertEqual(status.status, "stale")
        self.assertAlmostEqual(status.age_minutes, 90.0, delta=1.0)

    def test_missing_data(self):
        status = self.tracker.compute_stream_status("lightning", None)
        self.assertEqual(status.status, "missing")

    def test_invalid_data(self):
        now = datetime.now(timezone.utc)
        status = self.tracker.compute_stream_status("radar", now, is_valid=False)
        self.assertEqual(status.status, "invalid")

    def test_pipeline_evaluation_all_fresh(self):
        now = datetime.now(timezone.utc)
        r_res = ProviderResult(True, {}, now - timedelta(minutes=5), 10.0, "MOCK", "fresh", 5.0, ObservationQuality(True))
        s_res = ProviderResult(True, {}, now - timedelta(minutes=10), 10.0, "MOCK", "fresh", 10.0, ObservationQuality(True))
        l_res = ProviderResult(True, {}, now - timedelta(minutes=2), 5.0, "MOCK", "fresh", 2.0, ObservationQuality(True))
        w_res = ProviderResult(True, {}, now - timedelta(minutes=15), 12.0, "MOCK", "fresh", 15.0, ObservationQuality(True))

        report = self.tracker.evaluate_pipeline(r_res, s_res, l_res, w_res)
        self.assertEqual(report.overall_status, "fresh")
        self.assertIn("radar", report.streams)
        self.assertIn("satellite", report.streams)


class TestObservationBufferManager(unittest.TestCase):
    """Unit tests for the rolling observation buffer and multi-modal synchronization."""

    def test_buffer_capacity_and_sequence_readiness(self):
        manager = ObservationManager(max_frames=4)
        self.assertFalse(manager.is_sequence_ready())
        self.assertEqual(manager.frame_count, 0)

        now = datetime.now(timezone.utc)
        for i in range(3):
            frame = np.zeros((32, 32, 4), dtype=np.float32)
            manager.add_frame(frame, now + timedelta(minutes=i * 15))
            self.assertFalse(manager.is_sequence_ready())

        # 4th frame makes it ready
        manager.add_frame(np.zeros((32, 32, 4), dtype=np.float32), now + timedelta(minutes=45))
        self.assertTrue(manager.is_sequence_ready())
        self.assertEqual(manager.frame_count, 4)

        # 5th frame rolls over FIFO
        manager.add_frame(np.ones((32, 32, 4), dtype=np.float32), now + timedelta(minutes=60))
        self.assertEqual(manager.frame_count, 4)
        tensor, timestamps, provenances = manager.get_sequence()
        self.assertEqual(tensor.shape, (4, 32, 32, 4))
        self.assertEqual(tensor[-1, 0, 0, 0], 1.0)

    def test_warmup_hybrid_sequence(self):
        manager = ObservationManager(max_frames=4)
        now = datetime.now(timezone.utc)
        latest_frame = np.full((32, 32, 4), 30.0, dtype=np.float32)

        tensor, timestamps, provenances = manager.warmup_hybrid_sequence(
            latest_frame=latest_frame,
            timestamp=now,
        )

        self.assertEqual(tensor.shape, (4, 32, 32, 4))
        self.assertEqual(len(timestamps), 4)
        self.assertEqual(provenances[-1], "LIVE")
        self.assertEqual(provenances[0], "HYBRID")
        self.assertTrue(manager.is_sequence_ready())

    def test_simulation_sequence(self):
        manager = ObservationManager(max_frames=4)
        tensor, timestamps, provenances = manager.get_simulation_sequence()

        self.assertEqual(tensor.shape, (4, 32, 32, 4))
        self.assertEqual(len(timestamps), 4)
        self.assertTrue(all(p == "SIMULATED" for p in provenances))
        self.assertTrue(manager.is_sequence_ready())


class TestMLInferenceService(unittest.TestCase):
    """Unit tests for model loading, scaler, and inference pipeline."""

    def test_model_loader_singleton(self):
        model, meta = ModelLoader.get_model()
        self.assertIsNotNone(model)
        self.assertEqual(model.count_params(), 191524)
        self.assertEqual(meta.get("active_mode"), "real")

        scaler = ModelLoader.get_scaler()
        self.assertIsNotNone(scaler)
        self.assertTrue(scaler.is_fitted)

    def test_live_inference_execution(self):
        inference_svc = LiveInferenceService(model_mode="real")
        seq = np.zeros((4, 32, 32, 4), dtype=np.float32)
        seq[..., 0] = 42.0  # Moderate thunderstorm core
        seq[..., 1] = 22.0
        seq[..., 2] = -45.0  # Cold cloud top
        seq[..., 3] = 8.0   # Lightning activity

        sounding = {
            "cape_j_kg": 2600.0,
            "cin_j_kg": -35.0,
            "lifted_index_c": -4.8,
            "wind_shear_0_6km_kts": 26.0,
            "precipitable_water_mm": 50.0,
        }

        res = inference_svc.run_prediction(
            sequence_physical=seq,
            sounding_params=sounding,
            station_name="Chennai DWR (Sriharikota/Port)",
            forecast_steps=4,
            provenance="LIVE_REAL_DATA",
            mode="real",
        )

        self.assertTrue(res["sequence_ready"])
        self.assertEqual(res["mode"], "real")
        self.assertIn("observation", res)
        self.assertIn("forecast", res)
        self.assertEqual(len(res["forecast"]), 4)
        self.assertIn("lightning_jump", res)
        self.assertIn("cap_bulletin", res)
        self.assertGreater(res["inference_time_ms"], 0.0)

        # Check forecast step metadata
        first_step = res["forecast"][0]
        self.assertEqual(first_step["lead_time_min"], 15)
        self.assertIn("cells", first_step)
        self.assertIn("max_dbz", first_step)

    def test_grid_to_heatmap(self):
        grid = np.zeros((32, 32), dtype=np.float32)
        grid[16, 16] = 55.0
        points = grid_to_heatmap(grid, downsample=2)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["x"], 16)
        self.assertEqual(points[0]["y"], 16)
        self.assertEqual(points[0]["v"], 55.0)


class TestFastAPIEndpoints(unittest.TestCase):
    """Integration tests for FastAPI REST endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_live_status_endpoint(self):
        res = self.client.get("/api/live/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "operational")
        self.assertEqual(data["active_model_mode"], "real")
        self.assertEqual(data["model_parameters"], 191524)
        self.assertTrue(data["scaler_fitted"])
        self.assertIn("buffer", data)
        self.assertIn("providers", data)

    def test_live_nowcast_simulation_mode(self):
        res = self.client.get("/api/live/nowcast?data_mode=simulation&forecast_steps=4")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["mode"], "simulation")
        self.assertEqual(data["provenance"], "SIMULATION")
        self.assertTrue(data["sequence_ready"])
        self.assertEqual(len(data["forecast"]), 4)
        self.assertIn("observation", data)
        self.assertIn("cap_bulletin", data)

    def test_live_nowcast_hybrid_mode(self):
        res = self.client.get("/api/live/nowcast?data_mode=hybrid&forecast_steps=4")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["mode"], "hybrid")
        self.assertTrue(data["sequence_ready"])
        self.assertEqual(len(data["forecast"]), 4)

    def test_live_nowcast_real_mode_zero_fabrication(self):
        # Clear buffer to verify real mode does NOT fabricate missing frames
        _live_pipeline.observation_manager.clear()
        res = self.client.get("/api/live/nowcast?data_mode=real&forecast_steps=4")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["mode"], "real")
        self.assertFalse(data["sequence_ready"])
        self.assertEqual(len(data["forecast"]), 0)
        self.assertIn("Awaiting frame accumulation", data["data_note"])

    def test_live_nowcast_invalid_station(self):
        res = self.client.get("/api/live/nowcast?station=NonExistentRadar")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
