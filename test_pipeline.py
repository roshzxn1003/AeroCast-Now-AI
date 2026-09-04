import os
import unittest
import numpy as np
import tensorflow as tf
import joblib

from weather_service import (
    CITY_COORDINATES,
    INDIAN_STATIONS,
    fetch_open_meteo_sequence,
    generate_mock_sequence,
    geocode_city,
    fetch_multi_station_sequences,
    load_trained_pipeline,
    predict_horizon,
    analyze_extreme_weather,
    format_temp
)

class TestWeatherAIPipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.model, cls.scaler, cls.metadata = load_trained_pipeline()
        
    def test_01_model_and_scaler_loaded(self):
        """Verify model weights and scaler artifacts exist and load correctly."""
        self.assertIsNotNone(self.model, "LSTM Model should not be None")
        self.assertIsNotNone(self.scaler, "MinMaxScaler should not be None")
        self.assertTrue(os.path.exists("models/weather_lstm.keras"), "Saved .keras model must exist")
        self.assertTrue(os.path.exists("models/scaler.pkl"), "Saved scaler.pkl must exist")
        
    def test_02_mock_sequence_generation(self):
        """Verify simulator generates valid (7, 5) shape within physical bounds."""
        seq, source, meta = generate_mock_sequence("Chennai")
        self.assertEqual(seq.shape, (7, 5), "Sequence shape must be (7, 5)")
        self.assertEqual(seq.dtype, np.float32, "Sequence dtype must be float32")
        # Physical bounds check
        self.assertTrue(np.all(seq[:, 0] >= -10) and np.all(seq[:, 0] <= 55), "Temp within [-10, 55]°C")
        self.assertTrue(np.all(seq[:, 1] >= 0) and np.all(seq[:, 1] <= 100), "Humidity within [0, 100]%")
        self.assertTrue(np.all(seq[:, 3] >= 900) and np.all(seq[:, 3] <= 1050), "Pressure within [900, 1050] hPa")
        
    def test_03_geocoding_and_open_meteo(self):
        """Verify geocoding coordinates and live satellite data extraction."""
        coords = geocode_city("Chennai")
        self.assertIsNotNone(coords)
        self.assertAlmostEqual(coords[0], 13.0827, places=2)
        
        seq, source, meta = fetch_open_meteo_sequence("Chennai")
        self.assertEqual(seq.shape, (7, 5))
        self.assertIn("Open-Meteo", source)
        
    def test_04_neural_inference_and_3day_lookahead(self):
        """Verify multi-step recurrent forecast produces 3 temperature values."""
        seq, _, _ = generate_mock_sequence("Chennai")
        forecast_3d = predict_horizon(self.model, self.scaler, seq, steps=3)
        self.assertEqual(len(forecast_3d), 3, "Must produce 3 forecast steps")
        for val in forecast_3d:
            self.assertIsInstance(val, float)
            self.assertTrue(10.0 <= val <= 50.0, f"Forecast {val}°C should be within reasonable bounds")
            
    def test_05_extreme_weather_anomaly_detector(self):
        """Verify cyclone and heatwave trigger rules."""
        storm_seq = np.array([
            [30, 80, 5, 1012, 50],
            [30, 80, 5, 1012, 50],
            [30, 80, 5, 1012, 50],
            [30, 80, 5, 1011, 50],
            [30, 82, 6, 1010, 60],
            [29, 85, 8, 1008, 70],
            [28, 90, 14, 1002, 95]  # Sharp drop -6 hPa & wind 14 m/s
        ], dtype=np.float32)
        
        alerts = analyze_extreme_weather(storm_seq, pred_temp=27.0)
        titles = [a["title"] for a in alerts]
        self.assertTrue(any("Cyclone" in t or "Low Pressure" in t for t in titles), "Must trigger cyclonic alert")

    def test_06_multi_station_concurrent_fetch(self):
        """Verify parallel multi-station retrieval across Indian stations."""
        sample_cities = ["Chennai", "Mumbai", "Delhi", "Bengaluru", "Kolkata"]
        results = fetch_multi_station_sequences(sample_cities, use_live=False)
        self.assertEqual(len(results), len(sample_cities))
        for city in sample_cities:
            self.assertIn(city, results)
            seq, src, meta = results[city]
            self.assertEqual(seq.shape, (7, 5))

    def test_07_unit_formatter(self):
        """Verify temperature unit conversion between Celsius and Fahrenheit."""
        self.assertEqual(format_temp(25.0, "Celsius (°C)"), "25.0 °C")
        self.assertEqual(format_temp(25.0, "Fahrenheit (°F)"), "77.0 °F")
        self.assertEqual(format_temp(0.0, "Fahrenheit (°F)"), "32.0 °F")

if __name__ == "__main__":
    unittest.main(verbosity=2)
