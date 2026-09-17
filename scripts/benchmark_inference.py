#!/usr/bin/env python3
"""
AeroCast-Now AI: Inference Latency, Memory & Hardware Benchmark
=============================================================
Measures exact inference latency, throughput, memory consumption,
and startup warmup duration on the current host platform.
Outputs structured JSON and human-readable metrics for Phase 12 documentation.
"""

import os
import sys
import time
import json
import resource
from pathlib import Path
import numpy as np

# Ensure backend directory is in sys.path
BASE_DIR = Path(__file__).parent.parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import tensorflow as tf


def get_process_memory_mb() -> float:
    """Returns current process RSS memory in megabytes."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except Exception:
        pass
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def run_benchmark(iterations: int = 50, batch_size: int = 1) -> dict:
    mem_initial_mb = get_process_memory_mb()


    # 1. Hardware Detection
    gpus = tf.config.list_physical_devices("GPU")
    hardware_type = "gpu" if gpus else "cpu"
    device_name = gpus[0].name if gpus else "CPU (AVX2/FMA vector instruction set)"

    # 2. Model Startup & Loading Benchmark
    start_load = time.perf_counter()
    from ml.model_manager import get_model_manager, weighted_convective_loss
    model_mgr = get_model_manager()
    load_time_ms = (time.perf_counter() - start_load) * 1000.0

    mem_after_load_mb = get_process_memory_mb()
    model_mem_delta_mb = mem_after_load_mb - mem_initial_mb

    model = model_mgr.model
    if model is None:
        raise RuntimeError("Failed to load production model.")

    # 3. Model Properties
    param_count = model.count_params()
    input_shape = list(model.input_shape) if hasattr(model, "input_shape") else [None, 4, 32, 32, 4]
    output_shape = list(model.output_shape) if hasattr(model, "output_shape") else [None, 4, 32, 32, 4]

    # 4. Warmup Execution
    synthetic_input = np.random.uniform(0.0, 1.0, size=(batch_size, 4, 32, 32, 4)).astype(np.float32)
    warmup_start = time.perf_counter()
    _ = model.predict(synthetic_input, verbose=0)
    warmup_time_ms = (time.perf_counter() - warmup_start) * 1000.0

    # 5. Repeated Inference Latency Measurements
    latencies_ms = []
    for _ in range(iterations):
        # Vary input slightly to avoid caching
        synthetic_input = np.random.uniform(0.0, 1.0, size=(batch_size, 4, 32, 32, 4)).astype(np.float32)
        t0 = time.perf_counter()
        _ = model(synthetic_input, training=False)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    mem_final_mb = get_process_memory_mb()

    # Compute Statistics
    latencies_arr = np.array(latencies_ms)
    mean_lat = float(np.mean(latencies_arr))
    median_lat = float(np.median(latencies_arr))
    p90_lat = float(np.percentile(latencies_arr, 90))
    p95_lat = float(np.percentile(latencies_arr, 95))
    p99_lat = float(np.percentile(latencies_arr, 99))
    min_lat = float(np.min(latencies_arr))
    max_lat = float(np.max(latencies_arr))
    std_lat = float(np.std(latencies_arr))
    throughput_fps = float(1000.0 / mean_lat) if mean_lat > 0 else 0.0

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": {
            "type": hardware_type,
            "device": device_name,
            "gpu_count": len(gpus),
            "cpu_threads": os.cpu_count(),
        },
        "model": {
            "model_id": model_mgr.model_id,
            "model_version": model_mgr.model_version,
            "parameter_count": param_count,
            "input_shape": input_shape,
            "output_shape": output_shape,
        },
        "timing_ms": {
            "load_time_ms": round(load_time_ms, 2),
            "warmup_time_ms": round(warmup_time_ms, 2),
            "total_startup_ms": round(load_time_ms + warmup_time_ms, 2),
            "inference_mean_ms": round(mean_lat, 2),
            "inference_median_ms": round(median_lat, 2),
            "inference_p90_ms": round(p90_lat, 2),
            "inference_p95_ms": round(p95_lat, 2),
            "inference_p99_ms": round(p99_lat, 2),
            "inference_min_ms": round(min_lat, 2),
            "inference_max_ms": round(max_lat, 2),
            "inference_std_ms": round(std_lat, 2),
        },
        "throughput": {
            "inferences_per_second": round(throughput_fps, 2),
            "iterations_tested": iterations,
            "batch_size": batch_size,
        },
        "memory_mb": {
            "initial_process_rss_mb": round(mem_initial_mb, 2),
            "after_model_load_rss_mb": round(mem_after_load_mb, 2),
            "model_delta_rss_mb": round(model_mem_delta_mb, 2),
            "final_rss_mb": round(mem_final_mb, 2),
        }
    }

    print("\n" + "=" * 64)
    print("⚡ AeroCast-Now AI: Inference Benchmark Results")
    print("=" * 64)
    print(f"Hardware:          {device_name} ({hardware_type.upper()})")
    print(f"Model ID / Ver:    {model_mgr.model_id} (v{model_mgr.model_version})")
    print(f"Parameters:        {param_count:,}")
    print(f"Model Load Time:   {load_time_ms:.2f} ms")
    print(f"Warmup Time:       {warmup_time_ms:.2f} ms")
    print(f"Inference Latency: {mean_lat:.2f} ms (p50: {median_lat:.2f} ms, p90: {p90_lat:.2f} ms, p99: {p99_lat:.2f} ms)")
    print(f"Throughput:        {throughput_fps:.2f} inferences/sec")
    print(f"Memory (Model RSS):+{model_mem_delta_mb:.2f} MB (Total: {mem_final_mb:.2f} MB)")
    print("=" * 64 + "\n")

    # Save to reports/
    report_file = BASE_DIR / "reports" / "inference_benchmark.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[✓] Benchmark metrics saved to: {report_file}")

    return results


if __name__ == "__main__":
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_benchmark(iterations=iters)
