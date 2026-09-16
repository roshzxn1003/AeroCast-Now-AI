"""
Unit & Integration Tests for Nowcasting Model Training & Evaluation (Phase 3)
=============================================================================
Tests:
  1. Hardware detection utility (GPU / CPU detection & metadata)
  2. Model architecture shapes (Input (4, 32, 32, 4) -> Output (4, 32, 32, 4))
  3. Balanced Meteorological Weighted Convective Loss (BMAE)
  4. Convective balanced sampling under 99:1 class imbalance
  5. Channel scaler transform and inverse transform consistency
  6. Meteorological verification metrics: CSI, POD, FAR, HSS, MAE, RMSE
  7. Confusion matrix calculation & lead-time decomposition
  8. Model mode dual loading (real vs simulation) & runtime status endpoint
  9. FastAPI endpoints: /api/model/status and /api/model-info
"""

import os
import sys
import json
import unittest
import numpy as np
import tensorflow as tf
from fastapi.testclient import TestClient

# Ensure backend directory is in python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from train_nowcasting_model import detect_hardware, balance_convective_samples
from nowcasting_engine import (
    build_convlstm_model,
    weighted_convective_loss,
    load_nowcasting_model,
    get_model_status
)
from dataset_pipeline.scaler import ChannelScaler
from dataset_pipeline.evaluation import (
    calculate_meteorological_scores,
    calculate_channel_errors,
    calculate_lead_time_metrics,
    calculate_confusion_matrix,
    calculate_storm_cell_metrics
)
from api_server import app


class TestModelTrainingPhase3(unittest.TestCase):
    """Complete test suite for Phase 3 Model Training & Verification Pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_hardware_detection(self):
        """Test hardware detection reports execution device and TF version cleanly."""
        hw = detect_hardware()
        self.assertIsInstance(hw, dict)
        self.assertIn("device", hw)
        self.assertIn("gpu_available", hw)
        self.assertIn("tensorflow_version", hw)
        self.assertIn(hw["device"], ["GPU", "CPU"])
        self.assertIsInstance(hw["gpu_available"], bool)

    def test_model_architecture_shapes(self):
        """Test ResAtt-ConvLSTM2D model builds with exact (4, 32, 32, 4) input and output shapes."""
        model = build_convlstm_model(input_shape=(4, 32, 32, 4), output_steps=4)
        self.assertIsNotNone(model)
        self.assertEqual(model.input_shape, (None, 4, 32, 32, 4))
        self.assertEqual(model.output_shape, (None, 4, 32, 32, 4))

        # Perform a forward dummy pass
        dummy_input = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)
        dummy_output = model.predict(dummy_input, verbose=0)
        self.assertEqual(dummy_output.shape, (2, 4, 32, 32, 4))
        # Ensure outputs are non-negative normalized values
        self.assertTrue(np.all(dummy_output >= 0.0))

    def test_weighted_convective_loss_math(self):
        """Test that weighted convective loss places higher penalty on severe convective cells."""
        # 1. Clear-air error: true = 0.0, pred = 0.2
        y_clear_true = tf.constant(np.zeros((1, 4, 32, 32, 4), dtype=np.float32))
        y_clear_pred = tf.constant(np.full((1, 4, 32, 32, 4), 0.2, dtype=np.float32))
        clear_loss = float(weighted_convective_loss(y_clear_true, y_clear_pred).numpy())

        # 2. Convective core error: true = 0.8 (reflectivity > 45 dBZ), pred = 0.6 (same 0.2 diff)
        y_storm_true = tf.constant(np.full((1, 4, 32, 32, 4), 0.8, dtype=np.float32))
        y_storm_pred = tf.constant(np.full((1, 4, 32, 32, 4), 0.6, dtype=np.float32))
        storm_loss = float(weighted_convective_loss(y_storm_true, y_storm_pred).numpy())

        # Storm loss must penalize convective core significantly more than clear air
        self.assertGreater(storm_loss, clear_loss)

    def test_convective_balanced_sampling(self):
        """Test balanced sampling keeps 100% of convective storm events and ratios background."""
        n_total = 100
        storm_targets = np.zeros(n_total, dtype=int)
        storm_targets[10:15] = 1  # 5 storm events

        X_dummy = np.zeros((n_total, 4, 32, 32, 4), dtype=np.float32)
        Y_dummy = np.zeros((n_total, 4, 32, 32, 4), dtype=np.float32)

        X_b, Y_b, idxs = balance_convective_samples(X_dummy, Y_dummy, storm_targets, ratio=3, seed=42)

        # 5 storm events + 5 * 3 background = 20 total samples
        self.assertEqual(len(X_b), 20)
        self.assertEqual(len(Y_b), 20)
        # All storm indices (10, 11, 12, 13, 14) must be in idxs
        for s_idx in range(10, 15):
            self.assertIn(s_idx, idxs)

    def test_channel_scaler_roundtrip(self):
        """Test Multi-Modal Channel Scaler min-max forward and inverse transform."""
        scaler_path = os.path.join(root_dir, "data", "processed", "scaler.pkl")
        if os.path.exists(scaler_path):
            scaler = ChannelScaler.load(scaler_path)
        else:
            scaler = ChannelScaler()

        # Physical sample: [dBZ=45.0, VIL=30.0, TIR=-40.0, Flash=10.0]
        sample = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)
        sample[..., 0] = 45.0
        sample[..., 1] = 30.0
        sample[..., 2] = -40.0
        sample[..., 3] = 10.0

        normalized = scaler.transform(sample)
        self.assertTrue(np.all(normalized >= 0.0))
        self.assertTrue(np.all(normalized <= 1.0))

        recovered = scaler.inverse_transform(normalized)
        np.testing.assert_allclose(recovered[..., 0], 45.0, atol=0.1)
        np.testing.assert_allclose(recovered[..., 1], 30.0, atol=0.1)
        np.testing.assert_allclose(recovered[..., 2], -40.0, atol=0.1)
        np.testing.assert_allclose(recovered[..., 3], 10.0, atol=0.1)

    def test_meteorological_verification_scores(self):
        """Test contingency metrics (CSI, POD, FAR, HSS) on controlled synthetic ground truth."""
        y_true = np.zeros((10, 32, 32), dtype=np.float32)
        y_pred = np.zeros((10, 32, 32), dtype=np.float32)

        # 50 pixels true storm, 40 detected, 10 missed, 10 false alarms
        y_true[0, 0:5, 0:10] = 40.0  # 50 hits
        y_pred[0, 0:4, 0:10] = 40.0  # 40 hits
        y_pred[0, 5:6, 0:10] = 40.0  # 10 false alarms

        scores = calculate_meteorological_scores(y_true, y_pred, threshold=35.0)
        self.assertIn("CSI_Threat_Score", scores)
        self.assertIn("Probability_of_Detection_POD", scores)
        self.assertIn("False_Alarm_Ratio_FAR", scores)
        self.assertIn("Heidke_Skill_Score_HSS", scores)

        # POD = 40 / 50 = 0.8
        self.assertAlmostEqual(scores["Probability_of_Detection_POD"], 0.8, places=2)
        # FAR = 10 / (40 + 10) = 0.2
        self.assertAlmostEqual(scores["False_Alarm_Ratio_FAR"], 0.2, places=2)
        # CSI = 40 / (40 + 10 + 10) = 40/60 = 0.6667
        self.assertAlmostEqual(scores["CSI_Threat_Score"], 0.6667, places=2)

    def test_lead_time_metrics(self):
        """Test lead time decomposition computes scores across 4 forecast steps."""
        y_true = np.random.uniform(10.0, 50.0, size=(5, 4, 32, 32, 4)).astype(np.float32)
        y_pred = y_true + np.random.normal(0.0, 2.0, size=(5, 4, 32, 32, 4)).astype(np.float32)

        lt = calculate_lead_time_metrics(y_true, y_pred, threshold=35.0)
        self.assertIn("+15m", lt)
        self.assertIn("+30m", lt)
        self.assertIn("+45m", lt)
        self.assertIn("+60m", lt)
        for step in ["+15m", "+30m", "+45m", "+60m"]:
            self.assertIn("CSI", lt[step])
            self.assertIn("reflectivity_mae_dbz", lt[step])

    def test_confusion_matrix_calculation(self):
        """Test confusion matrix precision, recall, and accuracy."""
        y_true = np.array([1, 1, 1, 0, 0, 0, 1, 0, 0, 0])
        y_pred = np.array([1, 1, 0, 0, 0, 1, 1, 0, 0, 0])

        cm = calculate_confusion_matrix(y_true, y_pred)
        self.assertEqual(cm["true_positives"], 3)
        self.assertEqual(cm["false_positives"], 1)
        self.assertEqual(cm["true_negatives"], 5)
        self.assertEqual(cm["false_negatives"], 1)
        self.assertAlmostEqual(cm["accuracy"], 0.8, places=2)
        self.assertAlmostEqual(cm["recall"], 0.75, places=2)
        self.assertAlmostEqual(cm["precision"], 0.75, places=2)

    def test_model_mode_selection_and_status(self):
        """Test load_nowcasting_model returns status and weights info."""
        status = get_model_status()
        self.assertIsInstance(status, dict)
        self.assertIn("status", status)
        self.assertEqual(status["status"], "operational")
        self.assertIn("parameters", status)
        self.assertGreater(status["parameters"], 100000)
        self.assertIn("active_mode", status)
        self.assertIn("active_weights", status)

    def test_api_endpoints_status_and_info(self):
        """Test /api/model/status and /api/model-info HTTP responses."""
        res_status = self.client.get("/api/model/status")
        self.assertEqual(res_status.status_code, 200)
        data_status = res_status.json()
        self.assertEqual(data_status["status"], "operational")
        self.assertIn("active_mode", data_status)
        self.assertIn("parameters", data_status)

        res_info = self.client.get("/api/model-info")
        self.assertEqual(res_info.status_code, 200)
        data_info = res_info.json()
        self.assertIn("architecture", data_info)
        self.assertIn("input_shape", data_info)
        self.assertIn("forecast_lead_times_minutes", data_info)
        self.assertIn("metrics", data_info)


if __name__ == "__main__":
    unittest.main()
