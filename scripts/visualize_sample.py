#!/usr/bin/env python3
"""
AeroCast-Now AI — Sample Data Visualization Utility
===================================================
Visualizes multi-modal physical channels (Radar Reflectivity, VIL, Satellite TIR,
Lightning Flash Density, Combined Convective Field) for a specific sample and timestep.

Usage:
  python scripts/visualize_sample.py --index 0
  python scripts/visualize_sample.py --index 5 --split val
  python scripts/visualize_sample.py --output data/metadata/sample_visualization.png
"""

import os
import sys
import argparse
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dataset_pipeline.scaler import ChannelScaler


def print_ascii_grid(grid: np.ndarray, title: str, unit: str):
    """Renders a small 16x16 ASCII visualization of a 32x32 field."""
    # Subsample 32x32 to 16x16
    sub = grid[::2, ::2]
    val_min, val_max = float(np.min(sub)), float(np.max(sub))
    chars = " .:-=+*#%@"

    print(f"\n--- {title} [{unit}] (Min: {val_min:.1f}, Max: {val_max:.1f}) ---")
    for r in range(sub.shape[0]):
        line = ""
        for c in range(sub.shape[1]):
            val = sub[r, c]
            if np.isnan(val):
                line += "?"
            elif val_max == val_min:
                line += "."
            else:
                idx = int(np.clip((val - val_min) / (val_max - val_min) * (len(chars) - 1), 0, len(chars) - 1))
                line += chars[idx]
        print(line)


def main():
    parser = argparse.ArgumentParser(description="Visualize Multi-Modal Physical Channels of a Sample")
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=os.path.join(ROOT_DIR, "data", "sequences", "nowcasting_dataset.npz"),
        help="Path to nowcasting_dataset.npz"
    )
    parser.add_argument(
        "--scaler-path",
        type=str,
        default=os.path.join(ROOT_DIR, "data", "processed", "scaler.pkl"),
        help="Path to scaler.pkl"
    )
    parser.add_argument("--index", type=int, default=0, help="Sample index to inspect (default: 0)")
    parser.add_argument("--timestep", type=int, default=3, help="Timestep within sample (0-3 input, default 3=T0)")
    parser.add_argument("--split", type=str, default="train", choices=["train", "val", "test"], help="Dataset split")
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(ROOT_DIR, "data", "metadata", "sample_visualization.png"),
        help="Output image path"
    )
    parser.add_argument("--no-plot", action="store_true", help="Skip saving matplotlib PNG plot")
    args = parser.parse_args()

    if not os.path.exists(args.dataset_path):
        print(f"❌ Dataset file not found: {args.dataset_path}")
        print("💡 Run the builder first: python scripts/build_dataset.py")
        sys.exit(1)

    data = np.load(args.dataset_path)
    split_key = f"X_{args.split}"
    if split_key not in data:
        print(f"❌ Split {args.split} not found in dataset")
        sys.exit(1)

    X = data[split_key]
    n_samples = len(X)
    idx = max(0, min(args.index, n_samples - 1))
    t = max(0, min(args.timestep, X.shape[1] - 1))

    sample_tensor = X[idx, t]  # Shape (32, 32, 4) in [0, 1]

    # Inverse transform to restore authentic physical units
    scaler = None
    if os.path.exists(args.scaler_path):
        try:
            scaler = ChannelScaler.load(args.scaler_path)
        except Exception:
            scaler = ChannelScaler()
    else:
        scaler = ChannelScaler()

    physical_frame = scaler.inverse_transform(sample_tensor)

    dbz = physical_frame[:, :, 0]
    vil = physical_frame[:, :, 1]
    tir = physical_frame[:, :, 2]
    flash = physical_frame[:, :, 3]
    # Combined storm field: normalized composite
    combined = np.clip((dbz / 70.0) * 0.4 + (vil / 50.0) * 0.3 + (flash / 10.0) * 0.3, 0.0, 1.0)

    print("\n" + "="*60)
    print(f"🔍 SAMPLE VISUALIZATION: Index {idx} | Timestep {t} | Split '{args.split}'")
    print("="*60)
    print(f"Radar Reflectivity (dBZ) : Min {np.min(dbz):.1f} dBZ, Max {np.max(dbz):.1f} dBZ, Mean {np.mean(dbz):.1f} dBZ")
    print(f"Vert. Integ. Liquid (VIL): Min {np.min(vil):.1f} kg/m², Max {np.max(vil):.1f} kg/m², Mean {np.mean(vil):.1f} kg/m²")
    print(f"Satellite TIR BT         : Min {np.min(tir):.1f} °C, Max {np.max(tir):.1f} °C, Mean {np.mean(tir):.1f} °C")
    print(f"Lightning Flash Density  : Min {np.min(flash):.2f}, Max {np.max(flash):.2f}, Sum {np.sum(flash):.1f} flashes/km²")
    print(f"Convective Core Status   : {'⛈️ ACTIVE STORM CORE' if np.max(dbz) >= 35.0 or np.max(flash) > 0.1 else '🌤️ Clear / Stratiform'}")
    print("="*60)

    # ASCII Representations
    print_ascii_grid(dbz, "Channel 0: Radar Reflectivity", "dBZ")
    print_ascii_grid(vil, "Channel 1: Vertically Integrated Liquid", "kg/m²")
    print_ascii_grid(tir, "Channel 2: Satellite TIR Brightness Temp", "°C")
    print_ascii_grid(flash, "Channel 3: Lightning Flash Density", "flashes/km²")
    print_ascii_grid(combined, "Multi-Modal Combined Convective Storm Field", "[0-1]")

    if not args.no_plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            fig, axes = plt.subplots(1, 5, figsize=(20, 4))

            # Channel 0: Radar Reflectivity
            im0 = axes[0].imshow(dbz, cmap="pyart_NWSRef" if "pyart_NWSRef" in plt.colormaps() else "jet", vmin=0, vmax=70)
            axes[0].set_title(f"Radar Reflectivity\nMax: {np.max(dbz):.1f} dBZ")
            plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04, label="dBZ")

            # Channel 1: VIL
            im1 = axes[1].imshow(vil, cmap="Blues", vmin=0, vmax=60)
            axes[1].set_title(f"Vert. Integ. Liquid (VIL)\nMax: {np.max(vil):.1f} kg/m²")
            plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04, label="kg/m²")

            # Channel 2: Satellite TIR
            im2 = axes[2].imshow(tir, cmap="magma_r", vmin=-80, vmax=35)
            axes[2].set_title(f"Satellite TIR Temp\nMin: {np.min(tir):.1f} °C")
            plt.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.04, label="°C")

            # Channel 3: Lightning Flash Density
            im3 = axes[3].imshow(flash, cmap="YlOrRd", vmin=0, vmax=max(5.0, float(np.max(flash))))
            axes[3].set_title(f"Lightning Flash Density\nMax: {np.max(flash):.2f} f/km²")
            plt.colorbar(im3, ax=axes[3], fraction=0.046, pad=0.04, label="flashes/km²")

            # Combined Convective Field
            im4 = axes[4].imshow(combined, cmap="inferno", vmin=0, vmax=1.0)
            axes[4].set_title(f"Combined Storm Field\nSeverity: {np.max(combined):.2f}")
            plt.colorbar(im4, ax=axes[4], fraction=0.046, pad=0.04, label="Index [0-1]")

            for ax in axes:
                ax.set_xticks([0, 16, 31])
                ax.set_yticks([0, 16, 31])
                ax.grid(color="white", alpha=0.2, linestyle="--", linewidth=0.5)

            plt.suptitle(f"AeroCast-Now AI — Sample {idx} (Timestep {t}, Split: {args.split})", fontsize=14, y=1.03)
            plt.tight_layout()
            plt.savefig(args.output, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"\n🖼️ Multi-panel visualization plot saved to: {args.output}\n")
        except Exception as e:
            print(f"\n⚠️ Could not save matplotlib plot: {e}")


if __name__ == "__main__":
    main()
