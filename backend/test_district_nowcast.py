"""
Unit & Integration Tests for District-Level AI Nowcasting Engine
================================================================
Verifies:
  1. District gazetteer loading (734 Indian districts)
  2. Nearest radar station mapping & spatial projection
  3. AI nowcasting timeline (+15m to +120m) calculation
  4. Multi-sector impact scoring (Aviation, Power Grid, Agriculture, Urban)
  5. 2-Sigma Lightning Jump precursor detection
  6. Multilingual advisory generation (English & Hindi)
  7. FastAPI REST endpoints (/api/v1/districts/*)
"""

import unittest
from fastapi.testclient import TestClient
from api_server import app
from district_nowcast_service import (
    load_districts_gazetteer,
    find_district_by_query,
    find_nearest_radar_station,
    project_district_to_radar_pixel,
    classify_threat_level,
    compute_convective_impacts,
    generate_district_nowcast,
    get_national_district_summary,
)


class TestDistrictNowcastEngine(unittest.TestCase):
    """Test district-level nowcasting domain logic."""

    def test_gazetteer_loading(self):
        """Verify that all 734 Indian districts are parsed and indexed."""
        districts = load_districts_gazetteer()
        self.assertGreaterEqual(len(districts), 700)
        
        # Verify schema
        sample = districts[0]
        self.assertIn("id", sample)
        self.assertIn("name", sample)
        self.assertIn("state", sample)
        self.assertIn("lat", sample)
        self.assertIn("lon", sample)

    def test_find_district_by_query(self):
        """Test fuzzy and slug lookups for districts."""
        d1 = find_district_by_query("Chennai")
        self.assertIsNotNone(d1)
        self.assertEqual(d1["name"], "Chennai")
        self.assertEqual(d1["state"], "Tamil Nadu")

        d2 = find_district_by_query("new delhi")
        self.assertIsNotNone(d2)
        self.assertIn("Delhi", d2["name"])

        d3 = find_district_by_query("palamau")
        self.assertIsNotNone(d3)

    def test_nearest_radar_station(self):
        """Verify mapping from district to nearest DWR radar station."""
        # Chennai coordinates
        st_name, st_info, dist = find_nearest_radar_station(13.08, 80.27)
        self.assertIn("Chennai", st_name)
        self.assertLess(dist, 50.0)

        # Mumbai coordinates
        st_name_m, _, dist_m = find_nearest_radar_station(19.07, 72.87)
        self.assertIn("Mumbai", st_name_m)
        self.assertLess(dist_m, 50.0)

    def test_threat_classification(self):
        """Verify convective threat thresholds and colors."""
        level, color = classify_threat_level(max_dbz=58.0, max_vil=40.0, min_tir=-65.0, flash_rate=45.0)
        self.assertEqual(level, "EXTREME")
        self.assertEqual(color, "#a855f7")

        level_clear, _ = classify_threat_level(max_dbz=10.0, max_vil=0.0, min_tir=20.0, flash_rate=0.0)
        self.assertEqual(level_clear, "CLEAR")

    def test_convective_impacts(self):
        """Test calculation of multi-sector risk metrics."""
        impacts = compute_convective_impacts(max_dbz=52.0, max_vil=28.0, flash_rate=22.0, shear_kts=30.0)
        self.assertGreater(impacts["rain_intensity_mm_h"], 10.0)
        self.assertGreater(impacts["hail_probability_pct"], 30)
        self.assertGreater(impacts["estimated_wind_gust_kmh"], 70.0)
        self.assertTrue(impacts["aviation"]["llws_alert"])

    def test_end_to_end_district_nowcast(self):
        """Test full AI nowcast synthesis for a district."""
        res = generate_district_nowcast("Chennai", storm_mode="Severe Squall Line", data_mode="auto")
        self.assertIn("district", res)
        self.assertIn("current_observation", res)
        self.assertIn("nowcast_timeline", res)
        self.assertEqual(len(res["nowcast_timeline"]), 6)
        self.assertIn("lightning_jump_alert", res)
        self.assertIn("sector_impacts", res)
        self.assertIn("cap_v1_2_bulletin", res)
        self.assertIn("advisory", res)
        self.assertIn("en", res["advisory"])
        self.assertIn("hi", res["advisory"])


class TestDistrictAPIEndpoints(unittest.TestCase):
    """Test FastAPI REST endpoints for district nowcasts."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_districts_summary_endpoint(self):
        resp = self.client.get("/api/v1/districts/summary?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_districts_indexed", data)
        self.assertIn("warning_summary", data)
        self.assertIn("districts", data)

    def test_districts_search_endpoint(self):
        resp = self.client.get("/api/v1/districts/search?q=Bengaluru")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["count"], 0)

    def test_district_state_endpoint(self):
        resp = self.client.get("/api/v1/districts/state/kerala")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["state"], "Kerala")
        self.assertGreater(data["count"], 10)

    def test_district_nowcast_endpoint(self):
        resp = self.client.get("/api/v1/districts/nowcast/lucknow?storm_mode=Severe%20Squall%20Line")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["district"]["name"], "Lucknow")
        self.assertIn("nowcast_timeline", data)
        self.assertEqual(len(data["nowcast_timeline"]), 6)

    def test_state_report_endpoint_tamil_nadu(self):
        resp = self.client.get("/api/v1/reports/state/tamil-nadu")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["state"], "Tamil Nadu")
        self.assertEqual(len(data["districts"]), 38)
        self.assertIn("summary", data)
        self.assertIn("sector_impacts", data)
        self.assertIn("aviation", data["sector_impacts"])
        self.assertGreaterEqual(len(data["sector_impacts"]["aviation"]), 4)
        self.assertIn("advisory", data)
        self.assertIn("en", data["advisory"])
        self.assertIn("ta", data["advisory"])
        self.assertIn("hi", data["advisory"])
        self.assertIn("cap_bulletin", data)


if __name__ == "__main__":
    unittest.main()

