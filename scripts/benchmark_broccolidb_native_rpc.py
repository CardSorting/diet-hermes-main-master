#!/usr/bin/env python3
"""BroccoliDB native RPC throughput — before/after style measurements.

Compares:
  - Cold one-shot dispatch (HERMES_BROCCOLIDB_RPC=0 or run_oneshot_rpc each call)
  - Persistent RPC worker (warm_db_rpc + repeated run_db_rpc)

Usage:
    source .venv/bin/activate
    python scripts/benchmark_broccolidb_native_rpc.py
    python scripts/benchmark_broccolidb_native_rpc.py -o /tmp/broccolidb_bench.json
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

WT = str(Path(__file__).resolve().parents[1])
if WT not in sys.path:
    sys.path.insert(0, WT)


def _bench(label: str, fn: Callable[[], None], *, iterations: int = 7) -> dict[str, Any]:
    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "label": label,
        "iterations": iterations,
        "min_ms": round(times[0], 2),
        "median_ms": round(statistics.median(times), 2),
        "max_ms": round(times[-1], 2),
        "mean_ms": round(statistics.mean(times), 2),
    }


def _shutdown_gateway() -> None:
    from tools.broccolidb_tools.db_gateway import shutdown_gateway

    shutdown_gateway()


def _require_live() -> bool:
    from tools.broccolidb_tools.runner import check_requirements, resolve_broccolidb_db_path

    if not check_requirements():
        return False
    db = resolve_broccolidb_db_path()
    return bool(db and Path(db).is_file())


def run_benchmarks(*, iterations: int = 7) -> dict[str, Any]:
    from tools.broccolidb_tools.db_gateway import run_oneshot_rpc, shutdown_gateway
    from tools.broccolidb_tools.db_native import warm_db_rpc
    from tools.broccolidb_tools.runner import run_db_rpc

    meta: dict[str, Any] = {
        "iterations_per_case": iterations,
        "python": sys.version.split()[0],
        "node_hint": os.popen("node -v 2>/dev/null").read().strip(),
        "cwd": os.getcwd(),
    }
    rows: list[dict[str, Any]] = []

    if not _require_live():
        meta["live"] = False
        meta["error"] = "broccolidb.db or RPC modules not available"
        return {"meta": meta, "results": rows}

    meta["live"] = True
    from tools.broccolidb_tools.runner import resolve_broccolidb_db_path

    meta["db_path"] = resolve_broccolidb_db_path()

    # ── BEFORE analogue: fresh one-shot subprocess per call ──
    os.environ["HERMES_BROCCOLIDB_RPC"] = "0"
    _shutdown_gateway()

    rows.append(_bench(
        "oneshot: rpc_health",
        lambda: run_oneshot_rpc("rpc_health", timeout=60),
        iterations=iterations,
    ))
    rows.append(_bench(
        "oneshot: dashboard_snapshot",
        lambda: run_oneshot_rpc("dashboard_snapshot", timeout=90),
        iterations=iterations,
    ))
    rows.append(_bench(
        "oneshot: queue_status",
        lambda: run_oneshot_rpc("queue_status", timeout=60),
        iterations=iterations,
    ))
    rows.append(_bench(
        "oneshot: agent_invoke warm",
        lambda: run_oneshot_rpc(
            "agent_invoke",
            {"op": "warm", "args": {}, "flush": False},
            timeout=120,
        ),
        iterations=iterations,
    ))

    # ── AFTER: persistent worker ──
    os.environ["HERMES_BROCCOLIDB_RPC"] = "1"
    _shutdown_gateway()

    # First call includes worker spawn + ready handshake
    def _cold_worker_health() -> None:
        _shutdown_gateway()
        run_db_rpc("rpc_health", timeout=60)

    rows.append(_bench(
        "rpc (cold start): rpc_health [includes worker boot]",
        _cold_worker_health,
        iterations=3,
    ))

    warm_db_rpc(block=True)
    _shutdown_gateway()  # force reconnect once for fair warm series
    warm_db_rpc(block=True)

    rows.append(_bench(
        "rpc (warm): rpc_health",
        lambda: run_db_rpc("rpc_health", timeout=30),
        iterations=iterations,
    ))
    rows.append(_bench(
        "rpc (warm): dashboard_snapshot",
        lambda: run_db_rpc("dashboard_snapshot", timeout=90),
        iterations=iterations,
    ))
    rows.append(_bench(
        "rpc (warm): queue_status",
        lambda: run_db_rpc("queue_status", timeout=30),
        iterations=iterations,
    ))
    rows.append(_bench(
        "rpc (warm): agent_invoke warm",
        lambda: run_db_rpc(
            "agent_invoke",
            {"op": "warm", "args": {}, "flush": False},
            timeout=60,
        ),
        iterations=iterations,
    ))

    # Steady-state: second agent_invoke on same worker (AgentContext already loaded)
    run_db_rpc("agent_invoke", {"op": "warm", "args": {}, "flush": False}, timeout=60)
    rows.append(_bench(
        "rpc (warm): agent_invoke warm (repeat on hot worker)",
        lambda: run_db_rpc(
            "agent_invoke",
            {"op": "warm", "args": {}, "flush": False},
            timeout=30,
        ),
        iterations=iterations,
    ))

    _shutdown_gateway()
    return {"meta": meta, "results": rows}


def speedup_table(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = {r["label"]: r for r in results}
    pairs = [
        ("rpc_health", "oneshot: rpc_health", "rpc (warm): rpc_health"),
        ("dashboard_snapshot", "oneshot: dashboard_snapshot", "rpc (warm): dashboard_snapshot"),
        ("queue_status", "oneshot: queue_status", "rpc (warm): queue_status"),
        ("agent_warm", "oneshot: agent_invoke warm", "rpc (warm): agent_invoke warm"),
    ]
    out = []
    for name, cold_key, warm_key in pairs:
        cold = by_label.get(cold_key)
        warm = by_label.get(warm_key)
        if not cold or not warm:
            continue
        cm, wm = cold["median_ms"], warm["median_ms"]
        ratio = round(cm / wm, 2) if wm > 0 else None
        saved = round(cm - wm, 2)
        out.append({
            "operation": name,
            "before_median_ms": cm,
            "after_median_ms": wm,
            "median_saved_ms": saved,
            "speedup_x": ratio,
        })
    return out


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=Path, default=Path("/tmp/broccolidb_native_bench.json"))
    parser.add_argument("-n", "--iterations", type=int, default=7)
    args = parser.parse_args()

    payload = run_benchmarks(iterations=args.iterations)
    payload["speedup"] = speedup_table(payload.get("results", []))
    payload["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")

    print("BroccoliDB native RPC benchmark")
    print("=" * 72)
    for r in payload.get("results", []):
        print(
            f"{r['label']:<52} "
            f"min={r['min_ms']:>8.2f}  med={r['median_ms']:>8.2f}  max={r['max_ms']:>8.2f} ms"
        )
    print()
    print("Speedup (before=oneshot median / after=warm rpc median)")
    print("-" * 72)
    for s in payload.get("speedup", []):
        print(
            f"{s['operation']:<24} "
            f"{s['before_median_ms']:>9.2f} → {s['after_median_ms']:>9.2f} ms  "
            f"({s['speedup_x']}x faster, saved {s['median_saved_ms']:.0f} ms)"
        )
    print(f"\nJSON: {args.output}")
    return 0 if payload.get("meta", {}).get("live") else 1


if __name__ == "__main__":
    raise SystemExit(main())
