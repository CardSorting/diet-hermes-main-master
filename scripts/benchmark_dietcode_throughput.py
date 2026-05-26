#!/usr/bin/env python3
"""DietCode throughput benchmark — manual regression harness.

Measures hot paths touched by DietCode throughput passes:
  - TUI gateway RPC event batching (message/reasoning deltas)
  - SessionDB transcript writes (single vs batched)
  - Config load latency
  - Memory background-prefetch skip (builtin-only)
  - Plugin hook fast-paths (pre_tool_call / transform_tool_result)
  - JoyZoning governance transform hook (skip-on-error, mtime cache, light validate)
  - Governance path classification LRU
  - BroccoliDB dashboard snapshot (optional, when live)

Not a pass/fail pytest — records numbers so you can compare before/after
a change or across machines. Saves JSON for diffing.

Usage:
    source .venv/bin/activate   # or: source venv/bin/activate
    python scripts/benchmark_dietcode_throughput.py
    python scripts/benchmark_dietcode_throughput.py --quick
    python scripts/benchmark_dietcode_throughput.py -o /tmp/before.json
    python scripts/benchmark_dietcode_throughput.py --compare before.json after.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock, patch

WT = str(Path(__file__).resolve().parents[1])


def bench(label: str, fn: Callable[[], None], *, iterations: int = 5) -> dict[str, Any]:
    """Return min/median/max ms over *iterations* runs."""
    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "label": label,
        "iterations": iterations,
        "min_ms": times[0],
        "median_ms": times[len(times) // 2],
        "max_ms": times[-1],
    }


def _setup_hermes_home() -> str:
    home = tempfile.mkdtemp(prefix="dietcode_bench_")
    os.environ["HERMES_HOME"] = home
    os.environ["HOME"] = home
    if WT not in sys.path:
        sys.path.insert(0, WT)
    # Minimal user config — benchmarks assume DietCode governance defaults.
    (Path(home) / "config.yaml").write_text(
        "joyzoning:\n"
        "  governance:\n"
        "    enabled: true\n"
        "    layer_tags_required: false\n"
        "    validation_mode: light\n",
        encoding="utf-8",
    )
    return home


def bench_tui_rpc_batching(*, n_events: int) -> list[dict[str, Any]]:
    """Compare stdout frame count: batched deltas vs per-event (batch disabled)."""
    results: list[dict[str, Any]] = []

    with patch.dict("sys.modules", {
        "hermes_constants": MagicMock(get_hermes_home=MagicMock(return_value="/tmp/hermes_bench")),
        "hermes_cli.env_loader": MagicMock(),
        "hermes_cli.banner": MagicMock(),
        "hermes_state": MagicMock(),
    }):
        import importlib

        mod = importlib.import_module("tui_gateway.server")
        sid = "bench-session"
        mod._sessions[sid] = {"session_key": sid}

        def _count_frames(batch_ms: float) -> tuple[int, float]:
            buf = io.StringIO()
            mod._real_stdout = buf
            mod._events._ms = batch_ms / 1000.0
            mod._events._buf.clear()
            mod._events._timers.clear()

            t0 = time.perf_counter()
            for i in range(n_events):
                mod._emit("message.delta", sid, {"text": f"chunk-{i}"})
            mod._events.flush(sid)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            lines = [ln for ln in buf.getvalue().strip().split("\n") if ln]
            return len(lines), elapsed_ms

        batched_frames, batched_ms = _count_frames(25.0)
        unbatched_frames, unbatched_ms = _count_frames(0.0)

        reduction = 0.0
        if unbatched_frames:
            reduction = round(100.0 * (1.0 - batched_frames / unbatched_frames), 1)

        results.append({
            "label": f"tui_rpc_frames ({n_events} message.delta)",
            "n_events": n_events,
            "batched_frames": batched_frames,
            "unbatched_frames": unbatched_frames,
            "frame_reduction_pct": reduction,
            "batched_elapsed_ms": round(batched_ms, 2),
            "unbatched_elapsed_ms": round(unbatched_ms, 2),
        })
        results.append({
            "label": f"tui_rpc_emit ({n_events} deltas, batched)",
            "median_ms": round(batched_ms, 3),
            "events_per_sec": round(n_events / (batched_ms / 1000.0), 0) if batched_ms else 0,
        })

        mod._sessions.clear()

    return results


def bench_sessiondb_writes(*, n_messages: int, batch_size: int) -> list[dict[str, Any]]:
    from hermes_state import SessionDB

    results: list[dict[str, Any]] = []
    db = SessionDB()
    sid_single = "bench-single"
    sid_batch = "bench-batch"
    db.create_session(sid_single, source="cli")
    db.create_session(sid_batch, source="cli")

    def single_writes():
        for i in range(n_messages):
            db.append_message(sid_single, "assistant", content=f"msg-{i}")

    def batch_writes():
        rows = [{"role": "assistant", "content": f"msg-{i}"} for i in range(batch_size)]
        written = 0
        while written < n_messages:
            chunk = rows[: min(batch_size, n_messages - written)]
            db.append_messages_batch(sid_batch, chunk)
            written += len(chunk)

    r_single = bench(f"sessiondb append_message x{n_messages}", single_writes, iterations=3)
    r_single["msgs_per_sec"] = round(n_messages / (r_single["median_ms"] / 1000.0), 0)
    results.append(r_single)

    r_batch = bench(
        f"sessiondb append_messages_batch x{n_messages} (size={batch_size})",
        batch_writes,
        iterations=3,
    )
    r_batch["msgs_per_sec"] = round(n_messages / (r_batch["median_ms"] / 1000.0), 0)
    speedup = r_single["median_ms"] / r_batch["median_ms"] if r_batch["median_ms"] else 0
    r_batch["speedup_vs_single"] = round(speedup, 2)
    results.append(r_batch)

    return results


def bench_load_config(*, iterations: int) -> dict[str, Any]:
    from hermes_cli.config import load_config

    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        load_config()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "label": f"load_config x{iterations}",
        "iterations": iterations,
        "min_ms": times[0],
        "median_ms": times[len(times) // 2],
        "max_ms": times[-1],
    }


def bench_memory_prefetch_skip(*, iterations: int) -> dict[str, Any]:
    """queue_prefetch_all should no-op quickly when only builtin memory is active."""
    from agent.memory_manager import MemoryManager

    mgr = MemoryManager()
    times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        mgr.queue_prefetch_all("next user turn about refactoring", session_id="bench")
        times_us.append((time.perf_counter() - t0) * 1_000_000)
    return {
        "label": "memory queue_prefetch_all (builtin-only skip)",
        "iterations": iterations,
        "median_us": round(statistics.median(times_us), 1),
        "max_us": round(max(times_us), 1),
    }


def bench_transform_tool_result_hook(*, iterations: int) -> dict[str, Any]:
    from hermes_cli.plugins import has_hook_callbacks

    import model_tools  # noqa: F401

    times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        has_hook_callbacks("transform_tool_result")
        times_us.append((time.perf_counter() - t0) * 1_000_000)

    return {
        "label": "transform_tool_result hook check",
        "iterations": iterations,
        "hooks_registered": has_hook_callbacks("transform_tool_result"),
        "median_us": round(statistics.median(times_us), 1),
        "max_us": round(max(times_us), 1),
    }


def bench_governance_path_classification(*, iterations: int) -> dict[str, Any]:
    from agent.governance_exemptions import (
        invalidate_governance_path_cache,
        resolve_governance_path_kind,
    )

    paths = [
        "README.md",
        "package.json",
        "src/domain/foo.ts",
        "src/infrastructure/db.ts",
        "docs/guide.md",
        "node_modules/foo/index.js",
    ]
    invalidate_governance_path_cache()

    def classify_loop():
        for _ in range(iterations):
            for p in paths:
                resolve_governance_path_kind(p)

    r = bench(
        f"governance resolve_path_kind x{iterations * len(paths)}",
        classify_loop,
        iterations=3,
    )
    r["paths_per_sec"] = round(
        (iterations * len(paths)) / (r["median_ms"] / 1000.0), 0
    )
    return r


def bench_governance_mutation_gate(*, iterations: int) -> list[dict[str, Any]]:
    """JoyZoning transform-hook hot paths (light validation, cache, failure skip)."""
    import json

    from agent.governance_exemptions import (
        enforce_governance_on_mutation,
        invalidate_governance_path_cache,
    )

    results: list[dict[str, Any]] = []
    work = Path(tempfile.mkdtemp(prefix="dietcode_gov_bench_"))
    src = work / "src" / "domain" / "bench.ts"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(
        "/** [LAYER: DOMAIN] */\nexport const benchValue = 1;\n",
        encoding="utf-8",
    )
    path = str(src)
    ok_args = {"path": path, "content": src.read_text(encoding="utf-8")}
    ok_result = json.dumps({"success": True, "bytes_written": 42})

    invalidate_governance_path_cache()

    # 1) Skip when tool already failed — no gate work.
    skip_times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        enforce_governance_on_mutation(
            "write_file",
            ok_args,
            json.dumps({"error": "permission denied"}),
        )
        skip_times_us.append((time.perf_counter() - t0) * 1_000_000)
    results.append({
        "label": "governance enforce (tool error skip)",
        "iterations": iterations,
        "median_us": round(statistics.median(skip_times_us), 1),
        "max_us": round(max(skip_times_us), 1),
    })

    # 2) First validate (cold) vs cached second call on same mtime.
    invalidate_governance_path_cache()
    cold_times: list[float] = []
    for _ in range(max(3, iterations // 50)):
        invalidate_governance_path_cache()
        t0 = time.perf_counter()
        enforce_governance_on_mutation("write_file", ok_args, ok_result)
        cold_times.append((time.perf_counter() - t0) * 1000)

    invalidate_governance_path_cache()
    enforce_governance_on_mutation("write_file", ok_args, ok_result)  # warm cache
    cache_times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        enforce_governance_on_mutation("write_file", ok_args, ok_result)
        cache_times_us.append((time.perf_counter() - t0) * 1_000_000)

    results.append({
        "label": "governance enforce (cold, light validate)",
        "iterations": len(cold_times),
        "median_ms": round(statistics.median(cold_times), 3),
        "max_ms": round(max(cold_times), 3),
    })
    results.append({
        "label": "governance enforce (mtime cache hit)",
        "iterations": iterations,
        "median_us": round(statistics.median(cache_times_us), 1),
        "max_us": round(max(cache_times_us), 1),
        "speedup_vs_cold": round(
            (statistics.median(cold_times) * 1000)
            / statistics.median(cache_times_us),
            1,
        )
        if cache_times_us
        else 0,
    })

    return results


def bench_pre_tool_hook_fastpath(*, iterations: int) -> dict[str, Any]:
    from hermes_cli.plugins import get_pre_tool_call_block_message, has_hook_callbacks

    # Warm plugin discovery (idempotent).
    import model_tools  # noqa: F401

    times_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        if has_hook_callbacks("pre_tool_call"):
            get_pre_tool_call_block_message("read_file", {"path": "/tmp/x"}, session_id="s")
        times_us.append((time.perf_counter() - t0) * 1_000_000)

    return {
        "label": "pre_tool_call hook check",
        "iterations": iterations,
        "hooks_registered": has_hook_callbacks("pre_tool_call"),
        "median_us": round(statistics.median(times_us), 1),
        "max_us": round(max(times_us), 1),
    }


def bench_broccolidb_snapshot() -> dict[str, Any] | None:
    try:
        from hermes_cli.dietcode_broccolidb import get_health, get_snapshot
    except ImportError:
        return None

    health = get_health()
    row: dict[str, Any] = {
        "label": "broccolidb get_health",
        "live": health.get("live"),
        "median_ms": None,
    }
    times: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        get_health()
        times.append((time.perf_counter() - t0) * 1000)
    row["median_ms"] = round(statistics.median(times), 2)

    if not health.get("live"):
        row["note"] = "snapshot skipped — broccolidb.db not live (run broccolidb_init)"
        return row

    from tools.broccolidb_tools.db_native import warm_db_rpc
    from tools.broccolidb_tools.runner import run_db_rpc

    warm_db_rpc(block=True)

    ping_times: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        run_db_rpc("rpc_health", timeout=15)
        ping_times.append((time.perf_counter() - t0) * 1000)

    snap_times: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        get_snapshot()
        snap_times.append((time.perf_counter() - t0) * 1000)
    return {
        "label": "broccolidb get_snapshot (live, warm RPC)",
        "live": True,
        "rpc_health_median_ms": round(statistics.median(ping_times), 2),
        "median_ms": round(statistics.median(snap_times), 2),
        "min_ms": round(min(snap_times), 2),
        "max_ms": round(max(snap_times), 2),
    }


def run_all(*, quick: bool) -> list[dict[str, Any]]:
    n_delta = 2_000 if quick else 10_000
    n_msgs = 500 if quick else 2_000
    batch_sz = 50

    results: list[dict[str, Any]] = []
    results.extend(bench_tui_rpc_batching(n_events=n_delta))
    results.extend(bench_sessiondb_writes(n_messages=n_msgs, batch_size=batch_sz))
    results.append(bench_load_config(iterations=30 if quick else 50))
    results.append(bench_memory_prefetch_skip(iterations=500 if quick else 2000))
    results.append(bench_pre_tool_hook_fastpath(iterations=500 if quick else 2000))
    results.append(bench_transform_tool_result_hook(iterations=500 if quick else 2000))
    gov_iters = 200 if quick else 2000
    results.extend(bench_governance_mutation_gate(iterations=gov_iters))
    results.append(
        bench_governance_path_classification(iterations=500 if quick else 5000)
    )

    broc = bench_broccolidb_snapshot()
    if broc:
        results.append(broc)
    return results


def print_table(results: list[dict[str, Any]]) -> None:
    print()
    print("=" * 72)
    print("DIETCODE THROUGHPUT BENCHMARK")
    print("=" * 72)
    for r in results:
        label = r.get("label", "?")
        if "batched_frames" in r:
            print(
                f"{label:<52} batched={r['batched_frames']} unbatched={r['unbatched_frames']} "
                f"(-{r['frame_reduction_pct']}%)"
            )
        elif "events_per_sec" in r:
            print(
                f"{label:<52} {r['median_ms']:>7.2f} ms  "
                f"{r['events_per_sec']:>10,.0f} events/s"
            )
        elif "msgs_per_sec" in r:
            extra = f"  speedup={r['speedup_vs_single']}x" if "speedup_vs_single" in r else ""
            print(
                f"{label:<52} {r['median_ms']:>7.2f} ms  "
                f"{r['msgs_per_sec']:>10,.0f} msg/s{extra}"
            )
        elif "median_us" in r and "median_ms" not in r:
            hooks = ""
            if "hooks_registered" in r:
                hooks = " (hooks on)" if r.get("hooks_registered") else " (fast-path)"
            extra = ""
            if "speedup_vs_cold" in r:
                extra = f"  ~{r['speedup_vs_cold']}x vs cold"
            print(f"{label:<52} {r['median_us']:>8.1f} us median{hooks}{extra}")
        elif "median_ms" in r and "min_ms" not in r:
            extra = ""
            if "speedup_vs_cold" in r:
                extra = f"  speedup={r['speedup_vs_cold']}x"
            print(f"{label:<52} {r['median_ms']:>7.3f} ms median{extra}")
        elif "median_ms" in r and "min_ms" in r:
            live = ""
            if "live" in r:
                live = f"  [{'live' if r['live'] else 'offline'}]"
            note = f"  {r['note']}" if r.get("note") else ""
            print(
                f"{label:<52} {r['min_ms']:>7.2f} {r['median_ms']:>7.2f} {r['max_ms']:>7.2f} ms"
                f"{live}{note}"
            )
        else:
            print(f"{label:<52} {r}")


def compare(before_path: Path, after_path: Path) -> None:
    before = {r["label"]: r for r in json.loads(before_path.read_text())}
    after = {r["label"]: r for r in json.loads(after_path.read_text())}
    labels = sorted(set(before) | set(after))

    print()
    print("=" * 72)
    print(f"COMPARE  {before_path.name}  →  {after_path.name}")
    print("=" * 72)
    print(f"{'Benchmark':<48} {'before':>10} {'after':>10} {'delta':>10}")
    print("-" * 72)

    for label in labels:
        b, a = before.get(label), after.get(label)
        if not b or not a:
            continue
        if "median_ms" in b and "median_ms" in a:
            bv, av = b["median_ms"], a["median_ms"]
            pct = ((av - bv) / bv * 100) if bv else 0
            sign = "+" if pct > 0 else ""
            print(f"{label:<48} {bv:>9.2f}ms {av:>9.2f}ms {sign}{pct:>8.1f}%")
        elif "batched_frames" in b and "batched_frames" in a:
            print(
                f"{label:<48} {b['batched_frames']:>10} {a['batched_frames']:>10} "
                f"  frames"
            )
        elif "msgs_per_sec" in b and "msgs_per_sec" in a:
            bv, av = b["msgs_per_sec"], a["msgs_per_sec"]
            pct = ((av - bv) / bv * 100) if bv else 0
            sign = "+" if pct > 0 else ""
            print(f"{label:<48} {bv:>10,.0f}/s {av:>10,.0f}/s {sign}{pct:>8.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Smaller N for a fast smoke run")
    parser.add_argument("-o", "--output", type=Path, default=Path("/tmp/dietcode_throughput_bench.json"))
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), type=Path)
    args = parser.parse_args()

    if args.compare:
        compare(args.compare[0], args.compare[1])
        return 0

    _setup_hermes_home()
    results = run_all(quick=args.quick)
    print_table(results)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "quick": args.quick,
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nResults saved to {args.output}")
    print("Re-run after changes, then:")
    print(f"  python scripts/benchmark_dietcode_throughput.py --compare before.json {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
