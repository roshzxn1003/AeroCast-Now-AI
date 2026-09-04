import os
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# Ensure reproducible results
np.random.seed(42)
tf.random.set_seed(42)

def generate_synthetic_weather_dataset(n_days=1825):
    """
    Generates 5 years of daily synthetic meteorological data (1825 days)
    with realistic physical correlations, seasonal waves, and stochastic weather noise.
    Features: [Temperature, Humidity, Wind_Speed, Pressure, Clouds]
    Target: Next-day Temperature
    """
    t = np.arange(n_days)
    
    # 1. Seasonal base temperature (sine cycle with yearly period of 365 days)
    seasonal_temp = 28.0 + 8.0 * np.sin(2 * np.pi * t / 365.0 - np.pi / 2)
    temp_noise = np.random.normal(0, 2.0, n_days)
    temperature = np.clip(seasonal_temp + temp_noise, 10.0, 48.0)
    
    # 2. Humidity negatively correlated with temperature + seasonal monsoon shift
    seasonal_humidity = 65.0 + 15.0 * np.sin(2 * np.pi * t / 365.0)
    humidity_noise = np.random.normal(0, 5.0, n_days)
    humidity = np.clip(seasonal_humidity - 0.4 * (temperature - 28.0) + humidity_noise, 20.0, 100.0)
    
    # 3. Pressure inversely related to temperature and humidity
    pressure = np.clip(1013.25 - 0.25 * (temperature - 25.0) + np.random.normal(0, 3.0, n_days), 980.0, 1035.0)
    
    # 4. Wind Speed with Rayleigh/Gamma-like variation
    wind_speed = np.clip(np.random.gamma(shape=3.0, scale=1.5, size=n_days) + 0.05 * np.abs(pressure - 1013.25), 0.5, 30.0)
    
    # 5. Cloud cover correlated with humidity
    cloud_noise = np.random.normal(0, 10.0, n_days)
    clouds = np.clip(0.8 * humidity + cloud_noise - 10.0, 0.0, 100.0)
    
    df = pd.DataFrame({
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "pressure": pressure,
        "clouds": clouds
    })
    
    return df

def create_sequences(data, sequence_length=7):
    """
    Converts 2D time series array (T, features) into (N, sequence_length, features)
    and target array y of next-day temperature (N, 1).
    """
    X, y = [], []
    for i in range(len(data) - sequence_length):
        X.append(data[i:i + sequence_length])
        y.append(data[i + sequence_length, 0]) # Target is next day's normalized temperature
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

def build_lstm_model(input_shape=(7, 5)):
    """
    Dual-layer LSTM with Dropout and Dense output.
    """
    model = models.Sequential([
        layers.Input(shape=input_shape),
        layers.LSTM(64, return_sequences=True),
        layers.Dropout(0.2),
        layers.LSTM(32, return_sequences=False),
        layers.Dropout(0.2),
        layers.Dense(16, activation='relu'),
        layers.Dense(1)
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
    return model

def main():
    os.makedirs("models", exist_ok=True)
    print("🌤️ Step 1: Generating 5-year meteorological time-series dataset...")
    df = generate_synthetic_weather_dataset(n_days=1825)
    print(f"Dataset generated with shape: {df.shape}")
    print(df.describe())
    
    # Scale features
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(df.values)
    
    # Save scaler
    joblib.dump(scaler, "models/scaler.pkl")
    # Also save scaling parameters in JSON format for easy inspection
    scaler_params = {
        "features": list(df.columns),
        "data_min": scaler.data_min_.tolist(),
        "data_max": scaler.data_max_.tolist(),
        "scale": scaler.scale_.tolist(),
        "min": scaler.min_.tolist()
    }
    with open("models/scaler_params.json", "w") as f:
        json.dump(scaler_params, f, indent=4)
    print("✅ Scaler saved to models/scaler.pkl and models/scaler_params.json")
    
    # Create 7-day sliding sequences
    X, y = create_sequences(scaled_data, sequence_length=7)
    print(f"Sequence Tensor Shape X: {X.shape}, Target Shape y: {y.shape}")
    
    # Train / Validation / Test split (70% train, 15% val, 15% test)
    n_samples = len(X)
    train_end = int(n_samples * 0.70)
    val_end = int(n_samples * 0.85)
    
    X_train, y_train = X[:train_end], y[:train_end]
    X_val, y_val = X[train_end:val_end], y[train_end:val_end]
    X_test, y_test = X[val_end:], y[val_end:]
    
    print(f"Train samples: {len(X_train)}, Val samples: {len(X_val)}, Test samples: {len(X_test)}")
    
    # Build model
    model = build_lstm_model(input_shape=(7, 5))
    model.summary()
    
    # Training callbacks
    early_stopping = callbacks.EarlyStopping(monitor='val_loss', patience=12, restore_best_weights=True)
    reduce_lr = callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-5)
    
    print("🧠 Step 2: Training LSTM Model...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=60,
        batch_size=32,
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )
    
    # Save trained model in standard Keras format
    model_path = "models/weather_lstm.keras"
    model.save(model_path)
    print(f"💾 Best model saved to {model_path}")
    
    # Evaluate model
    print("📊 Step 3: Evaluating model on test split...")
    y_pred_scaled = model.predict(X_test).flatten()
    
    # Unscale predictions to original °C temperature scale
    # Target is column 0 (Temperature)
    temp_min = scaler.data_min_[0]
    temp_max = scaler.data_max_[0]
    
    y_test_orig = y_test * (temp_max - temp_min) + temp_min
    y_pred_orig = y_pred_scaled * (temp_max - temp_min) + temp_min
    
    mse = mean_squared_error(y_test_orig, y_pred_orig)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test_orig, y_pred_orig)
    r2 = r2_score(y_test_orig, y_pred_orig)
    
    print(f"⭐ Test Results:")
    print(f" - RMSE: {rmse:.3f} °C")
    print(f" - MAE:  {mae:.3f} °C")
    print(f" - R² Score: {r2:.3f}")
    
    # Save training history & prediction plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Loss curve
    ax1.plot(history.history['loss'], label='Train Loss (MSE)')
    ax1.plot(history.history['val_loss'], label='Val Loss (MSE)')
    ax1.set_title('LSTM Model Convergence (Loss Curve)')
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Loss (MSE)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Actual vs Predicted (first 60 test days)
    plot_points = min(60, len(y_test_orig))
    ax2.plot(range(plot_points), y_test_orig[:plot_points], label='Actual Temp (°C)', color='blue', marker='o', markersize=4)
    ax2.plot(range(plot_points), y_pred_orig[:plot_points], label='LSTM Predicted Temp (°C)', color='red', linestyle='--', marker='x', markersize=4)
    ax2.set_title(f'Actual vs Predicted Test Sample (RMSE: {rmse:.2f}°C)')
    ax2.set_xlabel('Day Index')
    ax2.set_ylabel('Temperature (°C)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("models/training_performance.png", dpi=300)
    plt.close()
    print("📈 Performance plot saved to models/training_performance.png")
    
    # Save metadata summary
    metadata = {
        "model_file": model_path,
        "input_shape": [7, 5],
        "features": ["temperature", "humidity", "wind_speed", "pressure", "clouds"],
        "target": "next_day_temperature",
        "test_rmse_celsius": float(rmse),
        "test_mae_celsius": float(mae),
        "test_r2_score": float(r2),
        "training_samples": len(X_train),
        "validation_samples": len(X_val),
        "test_samples": len(X_test)
    }
    with open("models/model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=4)
    print("📋 Metadata written to models/model_metadata.json")

if __name__ == "__main__":
    main()
