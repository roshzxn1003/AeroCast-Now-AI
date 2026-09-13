import os
import unittest
import numpy as np
import pandas as pd
import tensorflow as tf

from observation_service import (
    RADAR_STATIONS,
    ingest_nowcast_multimodal_tensor,
    generate_convective_storm_field,
    generate_lightning_jump_timeseries
)
from nowcasting_engine import (
    build_convlstm_model,
    predict_nowcast_sequence,
    identify_and_track_storm_cells,
    detect_lightning_jump,
    generate_cap_bulletin
)

class TestThunderstormNowcastingPipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.model = build_convlstm_model(input_shape=(4, 32, 32, 4), output_steps=4)
        
    def test_01_multimodal_tensor_generation(self):
        """Verify multi-modal spatio-temporal tensor has correct 4D shape and bounds."""
        tensor, meta = ingest_nowcast_multimodal_tensor("Chennai DWR (Sriharikota/Port)", "Severe Squall Line")
        self.assertEqual(tensor.shape, (4, 32, 32, 4), "Tensor shape must be (4, 32, 32, 4)")
        self.assertEqual(tensor.dtype, np.float32)
        # All normalized channels must be within [0, 1]
        self.assertTrue(np.all(tensor >= 0.0) and np.all(tensor <= 1.0), "Normalized values must be in [0, 1]")
        
    def test_02_sounding_parameters_physical_bounds(self):
        """Verify atmospheric sounding thermodynamic indices are physically consistent."""
        _, meta = ingest_nowcast_multimodal_tensor("Kolkata DWR (Alipore)")
        sounding = meta["sounding"]
        
        self.assertTrue(1000.0 <= sounding["CAPE_J_kg"] <= 5000.0, "CAPE should be in convective range [1000, 5000] J/kg")
        self.assertTrue(-200.0 <= sounding["CIN_J_kg"] <= 0.0, "CIN should be in range [-200, 0] J/kg")
        self.assertTrue(5.0 <= sounding["Deep_Layer_Shear_0_6km_kts"] <= 60.0, "Deep layer shear within [5, 60] kts")
        self.assertTrue(-15.0 <= sounding["Lifted_Index_C"] <= 2.0, "Lifted index must indicate instability")
        
    def test_03_storm_cell_tracking_scit(self):
        """Verify Storm Cell Identification and Tracking (SCIT) identifies cores and trajectories."""
        dbz, vil, _, _ = generate_convective_storm_field(3, "Severe Squall Line")
        cells = identify_and_track_storm_cells(dbz, vil, dbz_threshold=40.0)
        
        self.assertGreater(len(cells), 0, "Must detect at least 1 convective storm cell in squall line")
        first_cell = cells[0]
        self.assertIn("cell_id", first_cell)
        self.assertGreaterEqual(first_cell["max_dbz"], 40.0, "Max dBZ must be >= threshold")
        self.assertIn("projected_15min", first_cell)
        self.assertIn("projected_30min", first_cell)
        self.assertIn("projected_60min", first_cell)
        
    def test_04_lightning_jump_2sigma_detection(self):
        """Verify 2-sigma Lightning Jump algorithm triggers early warning on flash rate surges."""
        jump_df = generate_lightning_jump_timeseries(duration_mins=75, interval_mins=5, has_jump=True)
        jump_result = detect_lightning_jump(jump_df, sigma_threshold=2.0)
        
        self.assertTrue(jump_result["jump_detected"], "Must flag jump_detected = True on surge sequence")
        self.assertEqual(jump_result["threat_level"], "LEVEL 2 (IMMEDIATE PRECAUTION)")
        self.assertTrue(15 <= jump_result["estimated_lead_time_min"] <= 45, "Lead time must be within 15-45 minutes")
        
    def test_05_lightning_jump_normal_state(self):
        """Verify Lightning Jump algorithm returns NORMAL for steady baseline flash rates."""
        normal_df = generate_lightning_jump_timeseries(duration_mins=75, interval_mins=5, has_jump=False)
        normal_result = detect_lightning_jump(normal_df, sigma_threshold=2.0)
        
        self.assertFalse(normal_result["jump_detected"], "Must not flag jump for stable rate")
        self.assertIn(normal_result["threat_level"], ["NORMAL", "LEVEL 1 (MONITORING)"])
        
    def test_06_convlstm_forward_inference(self):
        """Verify Spatio-Temporal ConvLSTM rollout produces 6 future time steps (+15 to +120 min)."""
        dummy_input = np.random.uniform(0.0, 1.0, (4, 32, 32, 4)).astype(np.float32)
        forecast = predict_nowcast_sequence(self.model, dummy_input, total_forecast_steps=6)
        
        self.assertEqual(forecast.shape, (6, 32, 32, 4), "Forecast shape must be (6, 32, 32, 4)")
        self.assertTrue(np.all(forecast >= 0.0) and np.all(forecast <= 1.0))
        
    def test_07_cap_bulletin_generation(self):
        """Verify standard Common Alerting Protocol (CAP v1.2) JSON output compliance."""
        _, meta = ingest_nowcast_multimodal_tensor("Chennai DWR (Sriharikota/Port)")
        cells = [{"cell_id": "CELL-01", "max_dbz": 54.0, "severity": "INTENSE THUNDERSTORM"}]
        jump_info = {"jump_detected": True, "message": "Lightning jump active", "status": "CRITICAL"}
        
        cap_doc = generate_cap_bulletin("Chennai DWR (Sriharikota/Port)", cells, jump_info, meta["sounding"])
        self.assertIn("identifier", cap_doc)
        self.assertIn("info", cap_doc)
        self.assertEqual(cap_doc["info"]["eventCode"], "THUNDERSTORM_LIGHTNING_01")
        self.assertEqual(cap_doc["info"]["severity"], "Severe")
        self.assertEqual(cap_doc["info"]["urgency"], "Immediate")

if __name__ == "__main__":
    unittest.main(verbosity=2)
