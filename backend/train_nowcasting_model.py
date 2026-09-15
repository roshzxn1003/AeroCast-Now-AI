import os
import sys
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from sklearn.model_selection import train_test_split

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from observation_service import generate_convective_storm_field, GRID_SIZE
from nowcasting_engine import build_convlstm_model, weighted_convective_loss

# Set random seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)

def generate_multimodal_training_dataset(n_sequences: int = 160, grid_size: int = GRID_SIZE):
    """
    Synthesizes multi-modal spatio-temporal sequences of thunderstorm convective lifecycles.
    Each sample contains:
    - X: 4 input timesteps (-45 min to 0 min) with 4 channels [dBZ, VIL, TIR, Flash]
    - Y: 4 target timesteps (+15 min to +60 min) with 4 channels
    """
    storm_types = ["Severe Squall Line", "Supercell Thunderstorm", "Multi-Cell Cluster"]
    
    X_list, Y_list = [], []
    
    print(f"🌪️ Generating {n_sequences} multi-modal convective storm sequences (8 timesteps each)...")
    
    for seq_idx in range(n_sequences):
        mode = storm_types[seq_idx % len(storm_types)]
        seed = 1000 + seq_idx * 23
        
        sequence_frames = []
        # Total 8 consecutive timesteps: 4 input (0..3) and 4 forecast (4..7)
        for t in range(8):
            dbz, vil, tir, flash = generate_convective_storm_field(t, storm_mode=mode, grid_size=grid_size, seed=seed)
            
            # Normalize to [0, 1]
            norm_dbz = np.clip(dbz / 75.0, 0.0, 1.0)
            norm_vil = np.clip(vil / 65.0, 0.0, 1.0)
            norm_tir = np.clip((35.0 - tir) / 120.0, 0.0, 1.0)
            norm_flash = np.clip(flash / 25.0, 0.0, 1.0)
            
            frame_4ch = np.stack([norm_dbz, norm_vil, norm_tir, norm_flash], axis=-1)
            sequence_frames.append(frame_4ch)
            
        seq_arr = np.array(sequence_frames, dtype=np.float32)  # Shape (8, 32, 32, 4)
        X_list.append(seq_arr[0:4])  # Input: 4 steps
        Y_list.append(seq_arr[4:8])  # Target: 4 steps
        
    X = np.array(X_list, dtype=np.float32)
    Y = np.array(Y_list, dtype=np.float32)
    return X, Y

def calculate_meteorological_scores(y_true_dbz: np.ndarray, y_pred_dbz: np.ndarray, threshold: float = 35.0):
    """
    Computes standard meteorological verification metrics:
    - CSI (Critical Success Index / Threat Score)
    - POD (Probability of Detection / Hit Rate)
    - FAR (False Alarm Ratio)
    - HSS (Heidke Skill Score)
    """
    hits = np.sum((y_true_dbz >= threshold) & (y_pred_dbz >= threshold))
    misses = np.sum((y_true_dbz >= threshold) & (y_pred_dbz < threshold))
    false_alarms = np.sum((y_true_dbz < threshold) & (y_pred_dbz >= threshold))
    correct_negatives = np.sum((y_true_dbz < threshold) & (y_pred_dbz < threshold))
    
    pod = float(hits / (hits + misses + 1e-6))
    far = float(false_alarms / (hits + false_alarms + 1e-6))
    csi = float(hits / (hits + misses + false_alarms + 1e-6))
    
    total = float(hits + misses + false_alarms + correct_negatives)
    expected_correct = ((hits + misses) * (hits + false_alarms) + (correct_negatives + misses) * (correct_negatives + false_alarms)) / (total + 1e-6)
    hss = float((hits + correct_negatives - expected_correct) / (total - expected_correct + 1e-6))
    
    return csi, pod, far, hss

def main():
    parser = argparse.ArgumentParser(description="Train Spatio-Temporal ResAtt-ConvLSTM2D Model for AeroCast-Now")
    parser.add_argument("--epochs", type=int, default=18, help="Number of training epochs (default: 18)")
    parser.add_argument("--samples", type=int, default=160, help="Number of multi-modal sequences (default: 160)")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size (default: 8)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output models directory (default: backend/models)")
    args = parser.parse_args()

    models_dir = args.output_dir or os.path.join(backend_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # 1. Generate convective training dataset
    X, Y = generate_multimodal_training_dataset(n_sequences=args.samples, grid_size=GRID_SIZE)
    print(f"Dataset generated: X shape = {X.shape}, Y shape = {Y.shape}")
    
    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42)
    print(f"Training set: {X_train.shape[0]} sequences | Validation set: {X_test.shape[0]} sequences")
    
    # 2. Build Upgraded ResAtt-ConvLSTM2D Model
    print("🧠 Building Spatio-Temporal Residual-Attention ConvLSTM2D (ResAtt-ConvLSTM2D)...")
    model = build_convlstm_model(input_shape=(4, 32, 32, 4), output_steps=4)
    model.summary()
    
    # 3. Train Model with learning rate schedule
    epochs = args.epochs
    batch_size = args.batch_size
    print(f"🚀 Training ResAtt-ConvLSTM2D for {epochs} epochs with Weighted Balanced Convective Loss...")
    
    lr_callback = tf.keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.6,
        patience=3,
        min_lr=1e-5,
        verbose=1
    )
    
    history = model.fit(
        X_train, Y_train,
        validation_data=(X_test, Y_test),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[lr_callback],
        verbose=1
    )
    
    # 4. Save Upgraded Model Checkpoint
    model_save_path = os.path.join(models_dir, "convlstm_nowcaster.keras")
    model.save(model_save_path)
    print(f"✅ Saved trained ResAtt-ConvLSTM model to {model_save_path}")
    
    # 5. Evaluate Meteorological Scores
    Y_pred = model.predict(X_test, verbose=0)
    
    # Denormalize dBZ channel (Channel 0: [0, 1] -> [0, 75 dBZ])
    y_test_dbz = Y_test[:, :, :, :, 0] * 75.0
    y_pred_dbz = Y_pred[:, :, :, :, 0] * 75.0
    
    csi_25, pod_25, far_25, hss_25 = calculate_meteorological_scores(y_test_dbz, y_pred_dbz, threshold=25.0)
    csi_35, pod_35, far_35, hss_35 = calculate_meteorological_scores(y_test_dbz, y_pred_dbz, threshold=35.0)
    csi_45, pod_45, far_45, hss_45 = calculate_meteorological_scores(y_test_dbz, y_pred_dbz, threshold=45.0)
    
    mae_dbz = float(np.mean(np.abs(y_test_dbz - y_pred_dbz)))
    rmse_dbz = float(np.sqrt(np.mean((y_test_dbz - y_pred_dbz)**2)))
    
    metadata = {
        "model_architecture": "Residual-Attention ConvLSTM2D (ResAtt-ConvLSTM2D)",
        "total_parameters": int(model.count_params()),
        "input_shape": [4, 32, 32, 4],
        "output_shape": [4, 32, 32, 4],
        "channels": [
            "Radar Reflectivity (dBZ)",
            "Vertically Integrated Liquid (kg/m²)",
            "INSAT-3D TIR Brightness Temp (°C)",
            "Lightning Flash Density (flashes/km²)"
        ],
        "forecast_lead_times_minutes": [15, 30, 45, 60, 90, 120],
        "metrics_threshold_25dBZ": {
            "CSI_Threat_Score": round(csi_25, 3),
            "Probability_of_Detection_POD": round(pod_25, 3),
            "False_Alarm_Ratio_FAR": round(far_25, 3),
            "Heidke_Skill_Score_HSS": round(hss_25, 3)
        },
        "metrics_threshold_35dBZ": {
            "CSI_Threat_Score": round(csi_35, 3),
            "Probability_of_Detection_POD": round(pod_35, 3),
            "False_Alarm_Ratio_FAR": round(far_35, 3),
            "Heidke_Skill_Score_HSS": round(hss_35, 3)
        },
        "metrics_threshold_45dBZ": {
            "CSI_Threat_Score": round(csi_45, 3),
            "Probability_of_Detection_POD": round(pod_45, 3),
            "False_Alarm_Ratio_FAR": round(far_45, 3),
            "Heidke_Skill_Score_HSS": round(hss_45, 3)
        },
        "reflectivity_mae_dbz": round(mae_dbz, 2),
        "reflectivity_rmse_dbz": round(rmse_dbz, 2),
        "training_epochs": epochs,
        "training_samples": int(X_train.shape[0]),
        "validation_samples": int(X_test.shape[0])
    }
    
    meta_path = os.path.join(models_dir, "model_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=4)
        
    print("📊 Evaluation Metrics (Threshold = 35 dBZ):")
    print(f"   • CSI (Threat Score) : {csi_35:.3f}")
    print(f"   • POD (Detection Rate): {pod_35:.3f}")
    print(f"   • FAR (False Alarm)  : {far_35:.3f}")
    print(f"   • HSS (Skill Score)  : {hss_35:.3f}")
    print(f"   • Reflectivity MAE   : {mae_dbz:.2f} dBZ")
    print(f"   • Reflectivity RMSE  : {rmse_dbz:.2f} dBZ")
    
    # 6. Generate Diagnostic Plots
    plt.figure(figsize=(14, 6))
    
    # Subplot 1: Loss Curve
    plt.subplot(1, 2, 1)
    plt.plot(history.history['loss'], label='Train Convective Loss', color='#38bdf8', linewidth=2.5)
    plt.plot(history.history['val_loss'], label='Val Convective Loss', color='#4ade80', linewidth=2.5, linestyle='--')
    plt.title('ResAtt-ConvLSTM2D Loss Convergence', fontsize=12, fontweight='bold')
    plt.xlabel('Epoch', fontsize=11)
    plt.ylabel('Weighted Convective Loss', fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=10)
    
    # Subplot 2: Metric Verification Matrix
    plt.subplot(1, 2, 2)
    metrics_labels = ['CSI (25dBZ)', 'POD (25dBZ)', 'CSI (35dBZ)', 'POD (35dBZ)', 'HSS (35dBZ)', 'CSI (45dBZ)']
    metrics_vals = [csi_25, pod_25, csi_35, pod_35, max(0.0, hss_35), csi_45]
    colors = ['#38bdf8', '#4ade80', '#fb923c', '#f87171', '#a78bfa', '#ef4444']
    
    bars = plt.bar(metrics_labels, metrics_vals, color=colors, alpha=0.85, edgecolor='white', linewidth=1.2)
    plt.ylim(0, 1.15)
    plt.title('Meteorological Skill Verification Matrix', fontsize=12, fontweight='bold')
    plt.ylabel('Score (0.0 to 1.0)', fontsize=11)
    plt.xticks(rotation=25, ha='right', fontsize=9.5)
    plt.grid(axis='y', alpha=0.3)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.02, f"{yval:.2f}", ha='center', va='bottom', fontsize=9, fontweight='bold')
        
    plt.tight_layout()
    plot_path = os.path.join(models_dir, "training_performance.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"📈 Saved diagnostic training plot to {plot_path}")

if __name__ == "__main__":
    main()
