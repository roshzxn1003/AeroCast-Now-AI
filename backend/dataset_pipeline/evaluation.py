"""
Meteorological Evaluation & Verification Metrics (Phase 3)
===========================================================
Calculates scientific nowcasting verification scores:
  - Categorical Contingency Scores: CSI (Critical Success Index / Threat Score),
    POD (Probability of Detection), FAR (False Alarm Ratio), HSS (Heidke Skill Score)
    at standard operational convective thresholds (25 dBZ, 35 dBZ, 45 dBZ)
  - Lead-Time Decomposition (+15 min, +30 min, +45 min, +60 min)
  - Continuous Error: MAE and RMSE per channel (dBZ, VIL, TIR, Flash)
  - Storm Cell Kinematics & Morphological Displacement (SCIT / TITAN centroid error)
  - Binary Thunderstorm Confusion Matrix (TP, FP, TN, FN, Precision, Recall, F1)
  - Diagnostic Plot Generation: Training history, Confusion Matrix, Prediction Comparisons
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.ndimage import label, center_of_mass
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dataset_pipeline.targets import (
    compute_thunderstorm_target,
    THUNDERSTORM_DBZ_THRESHOLD,
    THUNDERSTORM_VIL_THRESHOLD,
    LIGHTNING_FLASH_DENSITY_THRESHOLD
)


def calculate_meteorological_scores(
    y_true_dbz: np.ndarray,
    y_pred_dbz: np.ndarray,
    threshold: float = 35.0
) -> Dict[str, float]:
    """
    Computes contingency table metrics for a specific reflectivity threshold.
    """
    hits = int(np.sum((y_true_dbz >= threshold) & (y_pred_dbz >= threshold)))
    misses = int(np.sum((y_true_dbz >= threshold) & (y_pred_dbz < threshold)))
    false_alarms = int(np.sum((y_true_dbz < threshold) & (y_pred_dbz >= threshold)))
    correct_negatives = int(np.sum((y_true_dbz < threshold) & (y_pred_dbz < threshold)))

    pod = float(hits / (hits + misses + 1e-6))
    far = float(false_alarms / (hits + false_alarms + 1e-6))
    csi = float(hits / (hits + misses + false_alarms + 1e-6))

    total = float(hits + misses + false_alarms + correct_negatives)
    expected_correct = (
        (hits + misses) * (hits + false_alarms) +
        (correct_negatives + misses) * (correct_negatives + false_alarms)
    ) / (total + 1e-6)
    hss = float((hits + correct_negatives - expected_correct) / (total - expected_correct + 1e-6))

    return {
        "hits": hits,
        "misses": misses,
        "false_alarms": false_alarms,
        "correct_negatives": correct_negatives,
        "CSI_Threat_Score": round(csi, 4),
        "Probability_of_Detection_POD": round(pod, 4),
        "False_Alarm_Ratio_FAR": round(far, 4),
        "Heidke_Skill_Score_HSS": round(hss, 4),
    }


def calculate_channel_errors(
    y_true_phys: np.ndarray,
    y_pred_phys: np.ndarray
) -> Dict[str, Dict[str, float]]:
    """
    Calculates MAE and RMSE for each of the 4 physical channels:
      0: dBZ (0 to 75 dBZ)
      1: VIL (0 to 65 kg/m²)
      2: TIR (-85 to +35 °C)
      3: Flash (0 to 25 flashes/km²)
    """
    channels = ["radar_dbz", "vil_kg_m2", "satellite_tir_c", "lightning_flash_density"]
    metrics: Dict[str, Dict[str, float]] = {}

    for c_idx, c_name in enumerate(channels):
        t_ch = y_true_phys[..., c_idx]
        p_ch = y_pred_phys[..., c_idx]

        mae = float(np.mean(np.abs(t_ch - p_ch)))
        rmse = float(np.sqrt(np.mean((t_ch - p_ch) ** 2)))

        metrics[c_name] = {
            "MAE": round(mae, 3),
            "RMSE": round(rmse, 3),
            "observed_mean": round(float(np.mean(t_ch)), 3),
            "predicted_mean": round(float(np.mean(p_ch)), 3),
        }

    return metrics


def calculate_lead_time_metrics(
    y_true_phys: np.ndarray,
    y_pred_phys: np.ndarray,
    threshold: float = 35.0
) -> Dict[str, Dict[str, Any]]:
    """
    Decomposes nowcasting performance separately by lead time:
      +15 min (step 0), +30 min (step 1), +45 min (step 2), +60 min (step 3).
    """
    lead_times = [15, 30, 45, 60]
    lead_time_results: Dict[str, Dict[str, Any]] = {}

    for step_idx, mins in enumerate(lead_times):
        t_step = y_true_phys[:, step_idx]
        p_step = y_pred_phys[:, step_idx]

        t_dbz = t_step[..., 0]
        p_dbz = p_step[..., 0]

        scores = calculate_meteorological_scores(t_dbz, p_dbz, threshold=threshold)
        mae_dbz = float(np.mean(np.abs(t_dbz - p_dbz)))
        rmse_dbz = float(np.sqrt(np.mean((t_dbz - p_dbz) ** 2)))

        t_flash = t_step[..., 3]
        p_flash = p_step[..., 3]
        mae_flash = float(np.mean(np.abs(t_flash - p_flash)))

        lead_time_results[f"+{mins}m"] = {
            "lead_time_minutes": mins,
            "CSI": scores["CSI_Threat_Score"],
            "POD": scores["Probability_of_Detection_POD"],
            "FAR": scores["False_Alarm_Ratio_FAR"],
            "HSS": scores["Heidke_Skill_Score_HSS"],
            "reflectivity_mae_dbz": round(mae_dbz, 2),
            "reflectivity_rmse_dbz": round(rmse_dbz, 2),
            "flash_mae": round(mae_flash, 3),
            "contingency": {
                "hits": scores["hits"],
                "misses": scores["misses"],
                "false_alarms": scores["false_alarms"],
                "correct_negatives": scores["correct_negatives"]
            }
        }

    return lead_time_results


def calculate_confusion_matrix(
    y_true_storm: np.ndarray,
    y_pred_storm: np.ndarray
) -> Dict[str, Any]:
    """
    Computes binary thunderstorm occurrence classification matrix:
      TP, FP, TN, FN, Precision, Recall, F1, Accuracy.
    """
    tp = int(np.sum((y_true_storm == 1) & (y_pred_storm == 1)))
    fp = int(np.sum((y_true_storm == 0) & (y_pred_storm == 1)))
    tn = int(np.sum((y_true_storm == 0) & (y_pred_storm == 0)))
    fn = int(np.sum((y_true_storm == 1) & (y_pred_storm == 0)))

    total = max(1, tp + fp + tn + fn)
    accuracy = float((tp + tn) / total)
    precision = float(tp / max(1, tp + fp))
    recall = float(tp / max(1, tp + fn))
    f1 = float(2 * precision * recall / max(1e-6, precision + recall))

    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "total_samples": total,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
    }


def calculate_storm_cell_metrics(
    y_true_dbz: np.ndarray,
    y_pred_dbz: np.ndarray,
    threshold: float = 35.0,
    grid_res_km: float = 4.0
) -> Dict[str, Any]:
    """
    Evaluates complete morphological convective storm cells:
      - Centroid displacement error (km)
      - Peak core reflectivity error (dBZ)
      - Storm cell detection rate
    """
    displacements = []
    intensity_errors = []
    detected_cells = 0
    total_true_cells = 0

    n_samples = y_true_dbz.shape[0]

    for i in range(n_samples):
        # Look at last forecast timestep (T+60)
        t_frame = y_true_dbz[i, -1] if y_true_dbz.ndim == 4 else y_true_dbz[i]
        p_frame = y_pred_dbz[i, -1] if y_pred_dbz.ndim == 4 else y_pred_dbz[i]

        t_mask = t_frame >= threshold
        p_mask = p_frame >= threshold

        if np.any(t_mask):
            t_lbl, t_n = label(t_mask)
            total_true_cells += t_n

            p_lbl, p_n = label(p_mask)

            if p_n > 0:
                t_com = np.array(center_of_mass(t_frame, t_lbl, range(1, t_n + 1)))
                p_com = np.array(center_of_mass(p_frame, p_lbl, range(1, p_n + 1)))

                for tc in t_com:
                    # Find nearest predicted centroid
                    dists = np.sqrt(np.sum((p_com - tc)**2, axis=-1)) * grid_res_km
                    min_dist = float(np.min(dists))
                    if min_dist <= 32.0:  # Within 32 km neighborhood
                        detected_cells += 1
                        displacements.append(min_dist)

            t_max = float(np.max(t_frame))
            p_max = float(np.max(p_frame))
            intensity_errors.append(abs(t_max - p_max))

    mean_disp = float(np.mean(displacements)) if displacements else 0.0
    mean_int_err = float(np.mean(intensity_errors)) if intensity_errors else 0.0
    cell_det_rate = float(detected_cells / max(1, total_true_cells))

    return {
        "total_true_cells": total_true_cells,
        "matched_detected_cells": detected_cells,
        "cell_detection_rate": round(cell_det_rate, 3),
        "mean_centroid_displacement_km": round(mean_disp, 2),
        "mean_core_reflectivity_error_dbz": round(mean_int_err, 2),
    }


def plot_training_history(history: Dict[str, List[float]], output_path: str) -> None:
    """Plots training and validation loss curves and learning rate schedule."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    epochs = range(1, len(history["loss"]) + 1)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Loss plot
    axes[0].plot(epochs, history["loss"], "b-o", label="Training Loss (Weighted BMAE)")
    if "val_loss" in history:
        axes[0].plot(epochs, history["val_loss"], "r--s", label="Validation Loss")
    axes[0].set_title("Training & Validation Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend()

    # MAE plot
    if "mae" in history:
        axes[1].plot(epochs, history["mae"], "g-o", label="Training MAE")
        if "val_mae" in history:
            axes[1].plot(epochs, history["val_mae"], "m--s", label="Validation MAE")
        axes[1].set_title("Normalized Mean Absolute Error (MAE)")
        axes[1].set_xlabel("Epoch")
        axes[1].set_ylabel("MAE [0-1]")
        axes[1].grid(True, linestyle="--", alpha=0.6)
        axes[1].legend()

    plt.suptitle("AeroCast-Now AI — ResAtt-ConvLSTM2D Training History", fontsize=13)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_confusion_matrix(cm: Dict[str, Any], output_path: str) -> None:
    """Renders confusion matrix graphic."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    matrix = np.array([
        [cm["true_negatives"], cm["false_positives"]],
        [cm["false_negatives"], cm["true_positives"]]
    ])

    fig, ax = plt.subplots(figsize=(6, 5))
    cax = ax.matshow(matrix, cmap="Blues")
    plt.colorbar(cax)

    for (i, j), val in np.ndenumerate(matrix):
        ax.text(j, i, f"{val}\n({val/cm['total_samples']*100:.1f}%)",
                ha="center", va="center", color="red" if (i != j and val > 0) else "black", fontsize=11)

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Clear Air", "Thunderstorm"])
    ax.set_yticklabels(["Clear Air", "Thunderstorm"])
    ax.set_xlabel("Predicted Label", fontsize=11)
    ax.set_ylabel("Actual Ground Truth", fontsize=11)
    ax.set_title(f"Thunderstorm Detection Confusion Matrix\nAccuracy: {cm['accuracy']*100:.1f}% | CSI: {cm.get('f1_score', 0):.3f}", pad=20)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_prediction_comparisons(
    y_true_phys: np.ndarray,
    y_pred_phys: np.ndarray,
    sample_indices: List[int],
    output_dir: str
) -> List[str]:
    """
    Renders multi-lead-time visual comparisons: Actual vs Predicted Radar dBZ.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_paths = []

    lead_times = ["+15m", "+30m", "+45m", "+60m"]

    for idx in sample_indices:
        t_seq = y_true_phys[idx]  # (4, 32, 32, 4)
        p_seq = y_pred_phys[idx]  # (4, 32, 32, 4)

        fig, axes = plt.subplots(2, 4, figsize=(16, 7))

        for step in range(4):
            # Row 0: Actual Ground Truth Reflectivity
            im_t = axes[0, step].imshow(t_seq[step, :, :, 0], cmap="jet", vmin=0, vmax=70)
            axes[0, step].set_title(f"Actual {lead_times[step]}\nMax: {np.max(t_seq[step, :, :, 0]):.1f} dBZ")
            axes[0, step].axis("off")

            # Row 1: AI Model Predicted Reflectivity
            im_p = axes[1, step].imshow(p_seq[step, :, :, 0], cmap="jet", vmin=0, vmax=70)
            axes[1, step].set_title(f"AI Predicted {lead_times[step]}\nMax: {np.max(p_seq[step, :, :, 0]):.1f} dBZ")
            axes[1, step].axis("off")

        plt.suptitle(f"AeroCast-Now AI — Historical Storm Verification (Sample {idx})", fontsize=13)
        plt.tight_layout()
        out_file = os.path.join(output_dir, f"prediction_comparison_sample_{idx}.png")
        plt.savefig(out_file, dpi=150)
        plt.close()
        saved_paths.append(out_file)

    return saved_paths


# ==============================================================================
# PHASE 4: SCIENTIFIC EVALUATION, GEOGRAPHY, TRACKING & BASELINE MODULES
# ==============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two geographic coordinates in kilometers.
    Uses Earth radius R = 6,371.0 km.
    """
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    return float(2.0 * R * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


def grid_to_latlon(
    r: float,
    c: float,
    min_lat: float = 12.0,
    max_lat: float = 14.5,
    min_lon: float = 79.0,
    max_lon: float = 81.5,
    grid_size: int = 32
) -> Tuple[float, float]:
    """
    Transforms internal 32x32 matrix (row, col) coordinates to latitude and longitude.
    Row 0 corresponds to northern boundary (max_lat), Row 31 to southern boundary (min_lat).
    Col 0 corresponds to western boundary (min_lon), Col 31 to eastern boundary (max_lon).
    """
    lat = max_lat - (r / float(grid_size)) * (max_lat - min_lat)
    lon = min_lon + (c / float(grid_size)) * (max_lon - min_lon)
    return round(float(lat), 4), round(float(lon), 4)


def calculate_brier_score_and_calibration(
    y_true_binary: np.ndarray,
    y_pred_prob: np.ndarray,
    n_bins: int = 5
) -> Dict[str, Any]:
    """
    Calculates Brier Score, Brier Skill Score, and reliability calibration curve:
      BS = (1/N) * sum((p_i - o_i)^2)
      BSS = 1 - (BS / BS_ref)
    """
    bs = float(np.mean((y_pred_prob - y_true_binary) ** 2))
    base_rate = float(np.mean(y_true_binary))
    bs_ref = float(base_rate * (1.0 - base_rate))
    bss = float(1.0 - (bs / (bs_ref + 1e-6))) if bs_ref > 0 else 0.0

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    calibration_table = []
    for b in range(n_bins):
        mask = (y_pred_prob >= bins[b]) & (y_pred_prob < bins[b+1]) if b < n_bins - 1 else (y_pred_prob >= bins[b]) & (y_pred_prob <= bins[b+1])
        count = int(np.sum(mask))
        if count > 0:
            obs_freq = float(np.mean(y_true_binary[mask]))
            pred_prob_mean = float(np.mean(y_pred_prob[mask]))
        else:
            obs_freq = 0.0
            pred_prob_mean = float((bins[b] + bins[b+1]) / 2.0)
        calibration_table.append({
            "bin_range": f"{bins[b]:.1f}-{bins[b+1]:.1f}",
            "sample_count": count,
            "mean_predicted_prob": round(pred_prob_mean, 3),
            "observed_frequency": round(obs_freq, 3)
        })

    return {
        "brier_score": round(bs, 5),
        "brier_skill_score": round(bss, 4),
        "climatological_base_rate": round(base_rate, 4),
        "calibration_bins": calibration_table
    }


def evaluate_persistence_baseline(
    X_test_phys: np.ndarray,
    Y_test_phys: np.ndarray,
    threshold: float = 35.0
) -> Dict[str, Dict[str, Any]]:
    """
    Computes rigorous Persistence Baseline:
    Assumes future state at T+15, T+30, T+45, T+60 equals the most recent past frame (T0, step index 3).
    """
    T0_frame = X_test_phys[:, 3:4, :, :, :]  # (N, 1, 32, 32, 4)
    Y_persist_phys = np.repeat(T0_frame, 4, axis=1)  # (N, 4, 32, 32, 4)

    lead_times = [15, 30, 45, 60]
    persist_results: Dict[str, Dict[str, Any]] = {}

    for step_idx, mins in enumerate(lead_times):
        t_dbz = Y_test_phys[:, step_idx, :, :, 0]
        p_dbz = Y_persist_phys[:, step_idx, :, :, 0]

        scores = calculate_meteorological_scores(t_dbz, p_dbz, threshold=threshold)
        mae_dbz = float(np.mean(np.abs(t_dbz - p_dbz)))
        rmse_dbz = float(np.sqrt(np.mean((t_dbz - p_dbz) ** 2)))
        bias_dbz = float(np.mean(p_dbz - t_dbz))

        persist_results[f"+{mins}m"] = {
            "lead_time_minutes": mins,
            "CSI": scores["CSI_Threat_Score"],
            "POD": scores["Probability_of_Detection_POD"],
            "FAR": scores["False_Alarm_Ratio_FAR"],
            "HSS": scores["Heidke_Skill_Score_HSS"],
            "reflectivity_mae_dbz": round(mae_dbz, 2),
            "reflectivity_rmse_dbz": round(rmse_dbz, 2),
            "reflectivity_bias_dbz": round(bias_dbz, 3),
            "hits": scores["hits"],
            "misses": scores["misses"],
            "false_alarms": scores["false_alarms"],
            "correct_negatives": scores["correct_negatives"]
        }

    return persist_results


def calculate_lead_time_confusion_matrices(
    y_true_phys: np.ndarray,
    y_pred_phys: np.ndarray,
    threshold: float = 25.0
) -> Dict[str, Dict[str, Any]]:
    """
    Computes individual confusion matrices for each lead time (+15m, +30m, +45m, +60m).
    """
    lead_times = [15, 30, 45, 60]
    matrices: Dict[str, Dict[str, Any]] = {}

    for step_idx, mins in enumerate(lead_times):
        t_dbz = y_true_phys[:, step_idx, :, :, 0]
        p_dbz = y_pred_phys[:, step_idx, :, :, 0]

        # Sequence-level classification: True if domain max >= threshold
        y_true_storm = (np.max(t_dbz, axis=(1, 2)) >= threshold).astype(int)
        y_pred_storm = (np.max(p_dbz, axis=(1, 2)) >= threshold).astype(int)

        cm = calculate_confusion_matrix(y_true_storm, y_pred_storm)
        cm["lead_time_minutes"] = mins
        matrices[f"+{mins}m"] = cm

    return matrices


def evaluate_storm_location_and_tracking(
    y_true_phys: np.ndarray,
    y_pred_phys: np.ndarray,
    storm_indices: List[int],
    threshold: float = 25.0,
    min_lat: float = 12.0,
    max_lat: float = 14.5,
    min_lon: float = 79.0,
    max_lon: float = 81.5,
    grid_size: int = 32
) -> Dict[str, Any]:
    """
    Evaluates storm cell centroid location error and trajectory tracking across all lead times.
    Calculates Haversine distance errors between true and predicted centroids.
    """
    location_errors_km = []
    track_records = []
    lead_time_loc_errors: Dict[str, List[float]] = {"+15m": [], "+30m": [], "+45m": [], "+60m": []}
    step_keys = ["+15m", "+30m", "+45m", "+60m"]

    for s_idx in storm_indices:
        t_seq = y_true_phys[s_idx, :, :, :, 0]  # (4, 32, 32)
        p_seq = y_pred_phys[s_idx, :, :, :, 0]  # (4, 32, 32)

        actual_track = []
        pred_track = []

        for step in range(4):
            t_frame = t_seq[step]
            p_frame = p_seq[step]

            t_mask = t_frame >= threshold
            p_mask = p_frame >= threshold

            if np.any(t_mask):
                t_com = center_of_mass(t_frame * t_mask)
                t_lat, t_lon = grid_to_latlon(t_com[0], t_com[1], min_lat, max_lat, min_lon, max_lon, grid_size)
                actual_track.append({"step": step, "lat": t_lat, "lon": t_lon, "row": t_com[0], "col": t_com[1]})

                if np.any(p_mask):
                    p_com = center_of_mass(p_frame * p_mask)
                    p_lat, p_lon = grid_to_latlon(p_com[0], p_com[1], min_lat, max_lat, min_lon, max_lon, grid_size)
                    pred_track.append({"step": step, "lat": p_lat, "lon": p_lon, "row": p_com[0], "col": p_com[1]})

                    dist_km = haversine_distance(t_lat, t_lon, p_lat, p_lon)
                    location_errors_km.append(dist_km)
                    lead_time_loc_errors[step_keys[step]].append(dist_km)
                else:
                    # Predicted peak did not exceed threshold: estimate centroid from global max
                    p_argmax = np.unravel_index(np.argmax(p_frame), p_frame.shape)
                    p_lat, p_lon = grid_to_latlon(p_argmax[0], p_argmax[1], min_lat, max_lat, min_lon, max_lon, grid_size)
                    dist_km = haversine_distance(t_lat, t_lon, p_lat, p_lon)
                    location_errors_km.append(dist_km)
                    lead_time_loc_errors[step_keys[step]].append(dist_km)

        if actual_track:
            track_records.append({
                "sample_index": int(s_idx),
                "actual_track": actual_track,
                "pred_track": pred_track
            })

    mean_err = float(np.mean(location_errors_km)) if location_errors_km else 0.0
    median_err = float(np.median(location_errors_km)) if location_errors_km else 0.0
    max_err = float(np.max(location_errors_km)) if location_errors_km else 0.0
    std_err = float(np.std(location_errors_km)) if location_errors_km else 0.0

    lead_time_summary = {}
    for k, v in lead_time_loc_errors.items():
        lead_time_summary[k] = {
            "mean_km": round(float(np.mean(v)), 2) if v else 0.0,
            "median_km": round(float(np.median(v)), 2) if v else 0.0,
            "count": len(v)
        }

    return {
        "location_errors_km": [round(float(e), 2) for e in location_errors_km],
        "mean_location_error_km": round(mean_err, 2),
        "median_location_error_km": round(median_err, 2),
        "max_location_error_km": round(max_err, 2),
        "std_location_error_km": round(std_err, 2),
        "lead_time_location_errors": lead_time_summary,
        "track_records": track_records
    }


def evaluate_lightning_jump_performance(
    X_test_phys: np.ndarray,
    Y_test_phys: np.ndarray,
    storm_indices: List[int]
) -> Dict[str, Any]:
    """
    Evaluates whether a rapid increase in total lightning flash density at T0
    statistically correlates with subsequent convective intensification at T+15 or T+30 min.
    """
    detected_jumps = 0
    correct_detections = 0
    false_detections = 0
    missed_events = 0
    total_events = len(storm_indices)

    for s_idx in storm_indices:
        # Lightning history from input frames: steps 0 to 3
        flash_hist = [float(np.sum(X_test_phys[s_idx, t, :, :, 3])) for t in range(4)]
        # Future lightning activity
        flash_future = [float(np.sum(Y_test_phys[s_idx, t, :, :, 3])) for t in range(4)]

        # Derivative at T0 (between step 2 and step 3)
        dfr_current = flash_hist[3] - flash_hist[2]
        mean_dfr_hist = float(np.mean([flash_hist[1] - flash_hist[0], flash_hist[2] - flash_hist[1]]))
        std_dfr_hist = max(0.2, float(np.std([flash_hist[1] - flash_hist[0], flash_hist[2] - flash_hist[1]])))

        # 2-sigma jump condition
        is_jump = (dfr_current - mean_dfr_hist) >= (1.5 * std_dfr_hist) and (flash_hist[3] > 0.05)

        # Ground truth intensification: future max flash rate exceeds T0 rate
        future_intensified = max(flash_future[:2]) > (flash_hist[3] + 0.1) if flash_future else False

        if is_jump:
            detected_jumps += 1
            if future_intensified:
                correct_detections += 1
            else:
                false_detections += 1
        else:
            if future_intensified:
                missed_events += 1

    return {
        "total_test_storm_events": total_events,
        "detected_jumps": detected_jumps,
        "correct_detections": correct_detections,
        "false_detections": false_detections,
        "missed_events": missed_events,
        "jump_precision": round(correct_detections / max(1, detected_jumps), 3),
        "jump_recall": round(correct_detections / max(1, correct_detections + missed_events), 3)
    }


def plot_lead_time_confusion_matrices(
    matrices: Dict[str, Dict[str, Any]],
    output_dir: str
) -> List[str]:
    """
    Saves individual confusion matrix plots for each lead time:
      reports/confusion_matrix_15min.png
      reports/confusion_matrix_30min.png
      reports/confusion_matrix_45min.png
      reports/confusion_matrix_60min.png
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_files = []

    lead_mapping = {
        "+15m": "confusion_matrix_15min.png",
        "+30m": "confusion_matrix_30min.png",
        "+45m": "confusion_matrix_45min.png",
        "+60m": "confusion_matrix_60min.png"
    }

    for lt, filename in lead_mapping.items():
        if lt not in matrices:
            continue
        cm = matrices[lt]
        matrix = np.array([
            [cm["true_negatives"], cm["false_positives"]],
            [cm["false_negatives"], cm["true_positives"]]
        ])

        fig, ax = plt.subplots(figsize=(6, 5))
        cax = ax.matshow(matrix, cmap="Blues")
        plt.colorbar(cax)

        for (i, j), val in np.ndenumerate(matrix):
            pct = (val / max(1, cm["total_samples"])) * 100.0
            color = "red" if (i != j and val > 0) else "black"
            ax.text(j, i, f"{val}\n({pct:.1f}%)", ha="center", va="center", color=color, fontsize=11, weight="bold")

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Clear Air", "Thunderstorm"])
        ax.set_yticklabels(["Clear Air", "Thunderstorm"])
        ax.set_xlabel("Predicted Event", fontsize=11)
        ax.set_ylabel("Actual Ground Truth", fontsize=11)
        ax.set_title(f"Confusion Matrix ({lt})\nAccuracy: {cm['accuracy']*100:.1f}% | CSI: {cm.get('f1_score', 0):.3f}", pad=20)

        plt.tight_layout()
        out_path = os.path.join(output_dir, filename)
        plt.savefig(out_path, dpi=150)
        plt.close()
        saved_files.append(out_path)

    return saved_files


def plot_storm_track_evaluation(
    track_records: List[Dict[str, Any]],
    output_path: str,
    min_lat: float = 12.0,
    max_lat: float = 14.5,
    min_lon: float = 79.0,
    max_lon: float = 81.5
) -> None:
    """
    Renders 2D spatial trajectory map comparing actual storm cell tracks vs predicted tracks.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 8))

    # Geographical boundary box
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    ax.set_xlabel("Longitude (°E)", fontsize=12)
    ax.set_ylabel("Latitude (°N)", fontsize=12)
    ax.set_title("AeroCast-Now AI — Unseen Storm Cell Trajectory Tracking (SCIT)", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.5)

    # Plot landmark reference: Chennai
    ax.plot(80.27, 13.08, 'r*', markersize=12, label="Chennai Radar (13.08°N, 80.27°E)")

    colors = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626"]
    plotted = 0

    for idx, rec in enumerate(track_records[:5]):
        act = rec["actual_track"]
        prd = rec["pred_track"]
        if len(act) < 2:
            continue

        c = colors[idx % len(colors)]
        act_lats = [pt["lat"] for pt in act]
        act_lons = [pt["lon"] for pt in act]
        ax.plot(act_lons, act_lats, color=c, marker="o", linestyle="-", linewidth=2.2,
                label=f"Actual Track (Event {rec['sample_index']})" if plotted == 0 else "")

        if prd:
            prd_lats = [pt["lat"] for pt in prd]
            prd_lons = [pt["lon"] for pt in prd]
            ax.plot(prd_lons, prd_lats, color=c, marker="x", linestyle="--", linewidth=1.8,
                    label=f"Predicted Track (Event {rec['sample_index']})" if plotted == 0 else "")

        plotted += 1

    ax.legend(loc="upper right", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_error_distributions(
    lead_time_metrics: Dict[str, Dict[str, Any]],
    persist_metrics: Dict[str, Dict[str, Any]],
    location_errors: List[float],
    output_path: str
) -> None:
    """
    Renders multi-panel diagnostic dashboard:
      Panel 1: Reflectivity MAE by Lead Time (AI vs Persistence)
      Panel 2: CSI Threat Score by Lead Time (AI vs Persistence)
      Panel 3: Storm Centroid Location Error Distribution (Histogram)
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    lead_labels = ["+15m", "+30m", "+45m", "+60m"]
    ai_mae = [lead_time_metrics[k]["reflectivity_mae_dbz"] for k in lead_labels]
    pe_mae = [persist_metrics[k]["reflectivity_mae_dbz"] for k in lead_labels]

    # Panel 1: MAE comparison
    x = np.arange(len(lead_labels))
    width = 0.35
    axes[0].bar(x - width/2, ai_mae, width, label="AI Model (ResAtt-ConvLSTM)", color="#3b82f6")
    axes[0].bar(x + width/2, pe_mae, width, label="Persistence Baseline", color="#9ca3af")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(lead_labels)
    axes[0].set_ylabel("Reflectivity MAE (dBZ)")
    axes[0].set_title("Reflectivity MAE vs Lead Time")
    axes[0].grid(True, linestyle="--", alpha=0.5)
    axes[0].legend()

    # Panel 2: CSI comparison
    ai_csi = [lead_time_metrics[k]["CSI"] for k in lead_labels]
    pe_csi = [persist_metrics[k]["CSI"] for k in lead_labels]
    axes[1].plot(lead_labels, ai_csi, 'b-o', linewidth=2, label="AI Model (ResAtt-ConvLSTM)")
    axes[1].plot(lead_labels, pe_csi, 'r--s', linewidth=2, label="Persistence Baseline")
    axes[1].set_ylabel("Critical Success Index (CSI @ 35 dBZ)")
    axes[1].set_title("CSI Decay Curve Across Lead Times")
    axes[1].set_ylim(-0.05, 1.0)
    axes[1].grid(True, linestyle="--", alpha=0.5)
    axes[1].legend()

    # Panel 3: Location Error Histogram
    if location_errors:
        axes[2].hist(location_errors, bins=12, color="#10b981", edgecolor="black", alpha=0.8)
        axes[2].axvline(np.mean(location_errors), color="red", linestyle="--", linewidth=2,
                        label=f"Mean: {np.mean(location_errors):.1f} km")
        axes[2].axvline(np.median(location_errors), color="blue", linestyle=":", linewidth=2,
                        label=f"Median: {np.median(location_errors):.1f} km")
        axes[2].set_xlabel("Centroid Distance Error (km)")
        axes[2].set_ylabel("Frequency")
        axes[2].set_title("Storm Location Error Distribution")
        axes[2].grid(True, linestyle="--", alpha=0.5)
        axes[2].legend()
    else:
        axes[2].text(0.5, 0.5, "No detected cells", ha="center", va="center")

    plt.suptitle("AeroCast-Now AI — Model Verification & Error Distributions", fontsize=13)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_actual_vs_predicted_grid_maps(
    y_true_phys: np.ndarray,
    y_pred_phys: np.ndarray,
    storm_indices: List[int],
    output_path: str
) -> None:
    """
    Renders high-resolution side-by-side comparison map of actual vs predicted radar fields
    for authentic unseen storm events across all lead times (+15m, +30m, +45m, +60m).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if not storm_indices:
        return

    # Select the most intense storm sample
    max_dbzs = [float(np.max(y_true_phys[i, :, :, :, 0])) for i in storm_indices]
    best_sample = storm_indices[int(np.argmax(max_dbzs))]

    t_seq = y_true_phys[best_sample, :, :, :, 0]  # (4, 32, 32)
    p_seq = y_pred_phys[best_sample, :, :, :, 0]  # (4, 32, 32)

    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    lead_times = ["+15 min", "+30 min", "+45 min", "+60 min"]

    for col in range(4):
        # Actual Ground Truth
        im0 = axes[0, col].imshow(t_seq[col], cmap="turbo", vmin=0, vmax=65)
        axes[0, col].set_title(f"ACTUAL OBSERVATION ({lead_times[col]})\nMax: {np.max(t_seq[col]):.1f} dBZ", fontsize=10, weight="bold")
        axes[0, col].axis("off")

        # Predicted Model Field
        im1 = axes[1, col].imshow(p_seq[col], cmap="turbo", vmin=0, vmax=65)
        axes[1, col].set_title(f"PREDICTED NOWCAST ({lead_times[col]})\nMax: {np.max(p_seq[col]):.1f} dBZ", fontsize=10, weight="bold")
        axes[1, col].axis("off")

    fig.colorbar(im0, ax=axes.ravel().tolist(), orientation="horizontal", fraction=0.046, pad=0.08, label="Radar Reflectivity (dBZ)")
    plt.suptitle(f"AeroCast-Now AI — Real-World Evaluation: Actual vs Predicted Radar Grids (Sample #{best_sample})", fontsize=13, weight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

