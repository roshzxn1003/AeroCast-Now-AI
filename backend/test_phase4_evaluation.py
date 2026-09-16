"""
Unit & Integration Tests for Real-World Evaluation & Storm Tracking (Phase 4)
=============================================================================
Tests:
  1. Haversine distance formula calculation
  2. Spatial grid to Latitude/Longitude coordinate projection
  3. Brier Score & Probability Calibration metrics
  4. Persistence Baseline evaluation across lead times (+15m to +60m)
  5. Lead-time specific Confusion Matrix generation
  6. SCIT storm tracking kinematics and centroid displacement error
  7. 2-Sigma Lightning Jump precursor verification
  8. Unseen test dataset loading, integrity, and shapes
  9. Real-data model checkpoint loading and inference pass
 10. Multi-model comparison interface (Real vs Synthetic baseline)
"""

import os
import sys
import unittest
import numpy as np
import tensorflow as tf

backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from dataset_pipeline.evaluation import (
    haversine_distance,
    grid_to_latlon,
    calculate_brier_score_and_calibration,
    evaluate_persistence_baseline,
    calculate_lead_time_confusion_matrices,
    evaluate_storm_location_and_tracking,
    evaluate_lightning_jump_performance,
    calculate_meteorological_scores
)
from nowcasting_engine import weighted_convective_loss


class TestPhase4Evaluation(unittest.TestCase):
    """Test suite for Phase 4 scientific evaluation and storm tracking."""

    def test_haversine_distance(self):
        """Test Haversine distance between known benchmark cities."""
        # Chennai: 13.0827°N, 80.2707°E
        # Bengaluru: 12.9716°N, 77.5946°E
        # Known great-circle distance is approximately 290 km
        dist = haversine_distance(13.0827, 80.2707, 12.9716, 77.5946)
        self.assertAlmostEqual(dist, 290.0, delta=10.0)

        # Distance to itself must be exactly 0.0
        self.assertAlmostEqual(haversine_distance(13.0, 80.0, 13.0, 80.0), 0.0, places=4)

    def test_grid_to_latlon(self):
        """Test mapping 32x32 grid indices to domain coordinates."""
        # Top-left corner (row 0, col 0) should be near max_lat (14.5°N) and min_lon (79.0°E)
        lat_tl, lon_tl = grid_to_latlon(0, 0, min_lat=12.0, max_lat=14.5, min_lon=79.0, max_lon=81.5, grid_size=32)
        self.assertEqual(lat_tl, 14.5)
        self.assertEqual(lon_tl, 79.0)

        # Bottom-right corner (row 32, col 32)
        lat_br, lon_br = grid_to_latlon(32, 32, min_lat=12.0, max_lat=14.5, min_lon=79.0, max_lon=81.5, grid_size=32)
        self.assertEqual(lat_br, 12.0)
        self.assertEqual(lon_br, 81.5)

    def test_brier_score_and_calibration(self):
        """Test Brier Score and calibration table output."""
        y_true = np.array([1, 1, 0, 0])
        # Perfect predictions
        perfect_res = calculate_brier_score_and_calibration(y_true, np.array([1.0, 1.0, 0.0, 0.0]))
        self.assertEqual(perfect_res["brier_score"], 0.0)
        self.assertEqual(perfect_res["brier_skill_score"], 1.0)

        # Worst predictions
        worst_res = calculate_brier_score_and_calibration(y_true, np.array([0.0, 0.0, 1.0, 1.0]))
        self.assertEqual(worst_res["brier_score"], 1.0)
        self.assertLess(worst_res["brier_skill_score"], 0.0)

    def test_persistence_baseline_evaluation(self):
        """Test persistence baseline produces metrics across all 4 lead times."""
        X_mock = np.zeros((10, 4, 32, 32, 4), dtype=np.float32)
        Y_mock = np.zeros((10, 4, 32, 32, 4), dtype=np.float32)

        # Put a 40 dBZ storm in frame 3 (T0) and keep it in Y_mock
        X_mock[:, 3, 10:15, 10:15, 0] = 40.0
        Y_mock[:, :, 10:15, 10:15, 0] = 40.0

        p_res = evaluate_persistence_baseline(X_mock, Y_mock, threshold=35.0)
        for lt in ["+15m", "+30m", "+45m", "+60m"]:
            self.assertIn(lt, p_res)
            self.assertIn("CSI", p_res[lt])
            self.assertIn("POD", p_res[lt])
            self.assertIn("reflectivity_mae_dbz", p_res[lt])
            # For stationary identical storm, persistence has perfect CSI = 1.0
            self.assertEqual(p_res[lt]["CSI"], 1.0)
            self.assertEqual(p_res[lt]["reflectivity_mae_dbz"], 0.0)

    def test_lead_time_confusion_matrices(self):
        """Test lead-time specific confusion matrices generation."""
        y_true = np.zeros((5, 4, 32, 32, 4), dtype=np.float32)
        y_pred = np.zeros((5, 4, 32, 32, 4), dtype=np.float32)

        y_true[0, 0, 10, 10, 0] = 40.0  # +15m storm
        y_pred[0, 0, 10, 10, 0] = 40.0  # +15m hit

        cms = calculate_lead_time_confusion_matrices(y_true, y_pred, threshold=25.0)
        self.assertIn("+15m", cms)
        self.assertIn("+30m", cms)
        self.assertIn("+45m", cms)
        self.assertIn("+60m", cms)
        self.assertEqual(cms["+15m"]["true_positives"], 1)

    def test_storm_tracking_kinematics(self):
        """Test storm cell tracking and centroid distance calculation."""
        y_true = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)
        y_pred = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)

        # Place storm at row 10, col 10 in true; row 10, col 11 in pred
        y_true[0, 0, 10, 10, 0] = 40.0
        y_pred[0, 0, 10, 11, 0] = 40.0

        res = evaluate_storm_location_and_tracking(y_true, y_pred, storm_indices=[0], threshold=25.0)
        self.assertIn("mean_location_error_km", res)
        self.assertIn("median_location_error_km", res)
        # 1 grid cell is approximately 4-8 km
        self.assertGreater(res["mean_location_error_km"], 0.0)
        self.assertLess(res["mean_location_error_km"], 20.0)

    def test_lightning_jump_performance(self):
        """Test lightning jump statistical surge detection on test events."""
        X_mock = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)
        Y_mock = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)

        # Steady low rate -> surge at step 3
        X_mock[0, 0, 0, 0, 3] = 0.1
        X_mock[0, 1, 0, 0, 3] = 0.1
        X_mock[0, 2, 0, 0, 3] = 0.1
        X_mock[0, 3, 0, 0, 3] = 10.0  # Massive jump
        Y_mock[0, 0, 0, 0, 3] = 15.0  # Intensified future

        res = evaluate_lightning_jump_performance(X_mock, Y_mock, storm_indices=[0])
        self.assertEqual(res["detected_jumps"], 1)
        self.assertEqual(res["correct_detections"], 1)

    def test_test_dataset_loading_and_integrity(self):
        """Verify unseen test dataset file structure and split sizes."""
        ds_path = os.path.join(root_dir, "data", "sequences", "nowcasting_dataset.npz")
        self.assertTrue(os.path.exists(ds_path), "Dataset nowcasting_dataset.npz must exist")

        ds = np.load(ds_path)
        self.assertIn("X_test", ds)
        self.assertIn("Y_test", ds)
        self.assertEqual(ds["X_test"].shape[1:], (4, 32, 32, 4))
        self.assertEqual(ds["Y_test"].shape[1:], (4, 32, 32, 4))
        self.assertGreaterEqual(ds["X_test"].shape[0], 2000)

    def test_model_loading_and_forward_pass(self):
        """Verify real trained model loads cleanly and performs forward pass."""
        model_path = os.path.join(backend_dir, "models", "convlstm_real_best.keras")
        self.assertTrue(os.path.exists(model_path), "convlstm_real_best.keras must exist")

        model = tf.keras.models.load_model(
            model_path,
            custom_objects={"weighted_convective_loss": weighted_convective_loss}
        )
        self.assertEqual(model.input_shape, (None, 4, 32, 32, 4))
        self.assertEqual(model.output_shape, (None, 4, 32, 32, 4))

        dummy = np.zeros((2, 4, 32, 32, 4), dtype=np.float32)
        pred = model.predict(dummy, verbose=0)
        self.assertEqual(pred.shape, (2, 4, 32, 32, 4))


if __name__ == "__main__":
    unittest.main()
