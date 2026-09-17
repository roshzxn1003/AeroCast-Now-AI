#!/usr/bin/env python3
"""
AeroCast-Now AI: Repeatable Load & Concurrency Test Suite
========================================================
Measures API throughput, latency percentiles, rate-limiting shedding,
and concurrency behavior across lightweight, dependency, and ML endpoints.
Saves structured benchmark reports to reports/load_test_results.json.
"""

import sys
import time
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

try:
    import httpx
except ImportError:
    print("[!] httpx required for load testing.")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent.resolve()


async def worker(
    client: httpx.AsyncClient,
    url: str,
    num_requests: int,
    results: List[float],
    status_codes: Dict[int, int],
    errors: List[str]
):
    for _ in range(num_requests):
        t0 = time.perf_counter()
        try:
            resp = await client.get(url, timeout=10.0)
            latency = (time.perf_counter() - t0) * 1000.0
            status_codes[resp.status_code] = status_codes.get(resp.status_code, 0) + 1
            results.append(latency)
        except Exception as e:
            errors.append(str(e))


async def run_load_scenario(
    base_url: str,
    endpoint: str,
    concurrency: int = 10,
    total_requests: int = 50,
    headers: Dict[str, str] = None
) -> Dict[str, Any]:
    url = f"{base_url}{endpoint}"
    reqs_per_worker = max(1, total_requests // concurrency)
    actual_total = reqs_per_worker * concurrency
    results: List[float] = []
    errors: List[str] = []
    status_codes: Dict[int, int] = {}

    print(f"[*] Scenario: {endpoint:<30} | Concurrency: {concurrency:<3} | Total Reqs: {actual_total}")
    
    t_start = time.perf_counter()
    async with httpx.AsyncClient(headers=headers or {}) as client:
        tasks = [
            asyncio.create_task(worker(client, url, reqs_per_worker, results, status_codes, errors))
            for _ in range(concurrency)
        ]
        await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - t_start

    arr = np.array(results) if results else np.array([0.0])
    mean_lat = float(np.mean(arr))
    p50_lat = float(np.median(arr))
    p90_lat = float(np.percentile(arr, 90))
    p99_lat = float(np.percentile(arr, 99))
    rps = len(results) / total_duration if total_duration > 0 else 0.0

    status_str = ", ".join(f"{code}: {count}" for code, count in sorted(status_codes.items()))
    print(f"    -> Throughput: {rps:.1f} req/s | Mean Latency: {mean_lat:.1f} ms | P90: {p90_lat:.1f} ms | Statuses: [{status_str}]")

    return {
        "endpoint": endpoint,
        "concurrency": concurrency,
        "total_requests": actual_total,
        "completed": len(results),
        "duration_seconds": round(total_duration, 2),
        "requests_per_second": round(rps, 2),
        "status_distribution": status_codes,
        "error_count": len(errors),
        "latencies_ms": {
            "mean": round(mean_lat, 2),
            "p50": round(p50_lat, 2),
            "p90": round(p90_lat, 2),
            "p99": round(p99_lat, 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
        }
    }


async def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    print("\n" + "=" * 64)
    print(f"⚡ AeroCast-Now AI: Executing Load & Stress Tests against {base_url}")
    print("=" * 64)

    scenarios = [
        # 1. High-concurrency Liveness Probe (bypasses rate limit by design)
        {"endpoint": "/health", "concurrency": 10, "total": 100},
        {"endpoint": "/health", "concurrency": 25, "total": 250},
        # 2. Dependency Readiness Probe
        {"endpoint": "/ready", "concurrency": 5, "total": 20},
        # 3. System Telemetry Endpoint
        {"endpoint": "/api/system/health", "concurrency": 5, "total": 20},
        # 4. Neural Nowcast Grid Inference (Rate limited to 30 req/min for compute)
        {"endpoint": "/api/radar-grid?channel=dbz", "concurrency": 2, "total": 10},
    ]

    scenario_results = []
    for sc in scenarios:
        res = await run_load_scenario(
            base_url=base_url,
            endpoint=sc["endpoint"],
            concurrency=sc["concurrency"],
            total_requests=sc["total"]
        )
        scenario_results.append(res)
        # Small delay between scenarios to let TCP sockets settle
        await asyncio.sleep(0.5)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target_url": base_url,
        "scenarios": scenario_results,
    }

    out_file = BASE_DIR / "reports" / "load_test_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    print("\n[✓] All load scenarios completed. Report saved to:")
    print(f"    {out_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
