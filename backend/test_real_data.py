"""
Unit & Integration Tests for Real Atmospheric Observation Ingestion Pipeline
=============================================================================
Verifies:
  1. IMD Doppler Weather Radar (DWR) station mapping and grid extraction
  2. INSAT-3D/3DR Geostationary Satellite Thermal IR decoding
  3. Real-time Blitzortung lightning density grid calculation
  4. RainViewer global radar tile fallback
  5. Multi-modal 4D spatio-temporal tensor assembly (4, 32, 32, 4)
  6. FastAPI REST endpoints for real data (/api/real/* and /api/nowcast)
"""

import unittest
import numpy as np
from PIL import Image

from real_data_service import (
    get_imd_station_code,
    decode_imd_radar_to_grids,
    decode_insat_to_tir_grid,
    calculate_real_lightning_grid,
    assemble_real_multimodal_tensor,
    fetch_rainviewer_metadata,
    IMD_STATION_MAP,
)
from observation_service import ingest_nowcast_multimodal_tensor
from fastapi.testclient import TestClient
from api_server import app


class TestRealDataIngestion(unittest.TestCase):
    """Test real observation ingestion functions."""

    def test_imd_station_mapping(self):
        """Verify proper station code normalization."""
        self.assertEqual(get_imd_station_code("Delhi NCR DWR (Palam/Mausam Bhawan)"), "delhi")
        self.assertEqual(get_imd_station_code("Mumbai DWR (Colaba/Veravali)"), "mum")
        self.assertEqual(get_imd_station_code("Kolkata DWR (Alipore)"), "kol")
        self.assertEqual(get_imd_station_code("Hyderabad DWR (Begumpet)"), "hyd")
        self.assertIn("delhi", IMD_STATION_MAP.values())

    def test_decode_imd_radar_to_grids(self):
        """Test decoding an IMD-like synthetic radar sweep image into dBZ and VIL."""
        # Create dummy 720x880 image with a simulated convective echo
        test_img = Image.new("RGB", (880, 720), (255, 255, 255))
        # Draw a red convective core (dBZ ~ 55) in sweep area
        for y in range(300, 360):
            for x in range(300, 360):
                test_img.putpixel((x, y), (255, 63, 0))

        import io
        buf = io.BytesIO()
        test_img.save(buf, format="GIF")
        image_bytes = buf.getvalue()

        dbz_grid, vil_grid, meta = decode_imd_radar_to_grids(image_bytes, target_grid_size=32)
        self.assertEqual(dbz_grid.shape, (32, 32))
        self.assertEqual(vil_grid.shape, (32, 32))
        self.assertGreater(meta["max_observed_dbz"], 0.0)
        self.assertEqual(meta["source"], "LIVE-IMD-DWR")

    def test_decode_insat_to_tir_grid(self):
        """Test decoding an INSAT-like IR image into brightness temperature."""
        test_img = Image.new("L", (1000, 1000), 128)
        # Put cold cloud top in center
        for y in range(450, 550):
            for x in range(450, 550):
                test_img.putpixel((x, y), 240)  # High grayscale = cold cloud top

        import io
        buf = io.BytesIO()
        test_img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        tir_grid, meta = decode_insat_to_tir_grid(
            image_bytes, station_lat=28.61, station_lon=77.21, target_grid_size=32
        )
        self.assertEqual(tir_grid.shape, (32, 32))
        self.assertEqual(meta["source"], "LIVE-INSAT-3D")
        self.assertLess(meta["min_observed_tir_c"], 0.0)

    def test_calculate_real_lightning_grid(self):
        """Test lightning strike aggregation into spatial density grid."""
        mock_strikes = [
            {"lat": 28.61, "lon": 77.21, "type": "CG"},
            {"lat": 28.62, "lon": 77.22, "type": "IC"},
            {"lat": 28.60, "lon": 77.20, "type": "CG"},
            {"lat": 13.08, "lon": 80.27, "type": "IC"},  # Outside Delhi domain
        ]

        density, rate, meta = calculate_real_lightning_grid(
            mock_strikes, station_lat=28.61, station_lon=77.21, target_grid_size=32
        )
        self.assertEqual(density.shape, (32, 32))
        self.assertEqual(meta["total_strikes_in_domain"], 3)
        self.assertGreater(rate, 0.0)

    def test_assemble_real_multimodal_tensor(self):
        """Test end-to-end multi-modal tensor assembly."""
        tensor, meta = assemble_real_multimodal_tensor(
            station_name="Delhi NCR DWR (Palam/Mausam Bhawan)",
            station_lat=28.61,
            station_lon=77.21,
            live_strikes=[],
            history_steps=4,
            grid_size=32
        )
        self.assertEqual(tensor.shape, (4, 32, 32, 4))
        self.assertEqual(meta["source"], "LIVE-MULTI-MODAL")
        self.assertIn("radar", meta)
        self.assertIn("satellite", meta)
        self.assertIn("lightning", meta)

    def test_ingest_multimodal_tensor_modes(self):
        """Test observation_service supports auto, live, and simulated modes."""
        # 1. Auto mode
        t_auto, m_auto = ingest_nowcast_multimodal_tensor(
            station_name="Delhi NCR DWR (Palam/Mausam Bhawan)",
            storm_mode="Severe Squall Line",
            data_mode="auto",
        )
        self.assertEqual(t_auto.shape, (4, 32, 32, 4))
        self.assertIn(m_auto["provenance"], ["LIVE-OBSERVATION", "HYBRID (Real INSAT-3D Satellite + Convective Scenario Core)"])

        # 2. Simulated mode
        t_sim, m_sim = ingest_nowcast_multimodal_tensor(
            station_name="Delhi NCR DWR (Palam/Mausam Bhawan)",
            storm_mode="Severe Squall Line",
            data_mode="simulated",
        )
        self.assertEqual(t_sim.shape, (4, 32, 32, 4))
        self.assertEqual(m_sim["provenance"], "SIMULATED")


class TestRealDataEndpoints(unittest.TestCase):
    """Test FastAPI REST endpoints for real data."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_real_status_endpoint(self):
        resp = self.client.get("/api/real/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sources", data)
        self.assertIn("imd_dwr_network", data["sources"])
        self.assertIn("insat_satellite", data["sources"])
        self.assertIn("blitzortung_ldn", data["sources"])

    def test_real_radar_endpoint(self):
        resp = self.client.get("/api/real/radar/delhi")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ["LIVE-IMD", "FALLBACK-RAINVIEWER"])

    def test_real_satellite_endpoint(self):
        resp = self.client.get("/api/real/satellite?station_lat=28.61&station_lon=77.21")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)

    def test_nowcast_with_real_data_mode(self):
        resp = self.client.get("/api/nowcast?station=Delhi%20NCR%20DWR%20(Palam/Mausam%20Bhawan)&data_mode=auto")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("data_note", data)
        self.assertIn("provenance", data)
        self.assertIn("real_metadata", data)


if __name__ == "__main__":
    unittest.main()
