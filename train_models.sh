#!/usr/bin/env bash
# ==============================================================================
# AeroCast-Now AI: Neural Nowcaster & Weather Model Training Runner
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${REPO_DIR}/venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Error: Virtual environment python not found at $VENV_PYTHON"
    exit 1
fi

export PYTHONPATH="${REPO_DIR}/backend:${PYTHONPATH}"

echo "================================================================================"
echo "⚡ AEROCAST-NOW AI: SPATIO-TEMPORAL NOWCASTER MODEL TRAINING PIPELINE"
echo "================================================================================"
echo "Python: $VENV_PYTHON"
echo "Backend: ${REPO_DIR}/backend"
echo "Target Model: ResAtt-ConvLSTM2D (4-Channel Radar + Satellite + Lightning)"
echo "================================================================================"

if [ "$1" == "--weather-lstm" ]; then
    echo "🌤️ Training 1D Meteorological Multi-Parameter LSTM..."
    "$VENV_PYTHON" "${REPO_DIR}/backend/train_model.py"
else
    echo "🌪️ Training Core Spatio-Temporal Nowcaster (ResAtt-ConvLSTM2D)..."
    "$VENV_PYTHON" "${REPO_DIR}/backend/train_nowcasting_model.py" "$@"
fi

echo "================================================================================"
echo "✅ Training pipeline completed successfully!"
echo "Artifacts generated in: ${REPO_DIR}/backend/models/"
echo "================================================================================"
