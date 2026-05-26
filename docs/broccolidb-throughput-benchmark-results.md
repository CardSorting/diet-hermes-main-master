# BroccoliDB Native RPC — Benchmark Results (Hard Numbers)

Companion to [broccolidb-native-execution-throughput.md](./broccolidb-native-execution-throughput.md) (architecture and implementation). Summarizes **what improved** after the native RPC worker, shared handlers, and production hardening passes.

**Headline:** oneshot subprocess calls sit at **~1 s p50**; a warm persistent worker serves the same operations at **~1–2 ms p50** (~**550–880×** faster for the cases below).

Measured on the Diet Hermes checkout with a live `broccolidb.db`. Reproduce with:

```bash
source .venv/bin/activate   # or: source venv/bin/activate
cd /path/to/diet-hermes-main-master
python scripts/benchmark_broccolidb_native_rpc.py -n 9 -o /tmp/broccolidb_bench.json
```

**Environment (2026-05-26 run):**

| | |
|---|---|
| Python | 3.11.9 |
| Node | v20.19.5 |
| DB | `broccolidb.db` at repo root |
| Iterations | 9 per case (3 for cold-worker restart) |
| Wall time (full harness) | ~41 s |

See also: [broccolidb-native-execution-throughput.md](./broccolidb-native-execution-throughput.md) for architecture.

---

## Executive summary

| Path | Typical latency (p50) | What dominates |
|------|----------------------|----------------|
| **Oneshot** (cold `tsx` per call) | **~950–1,000 ms** | Process spawn + module load + DB init |
| **RPC warm** (persistent worker) | **~1–2 ms** | JSON line + SQLite query |
| **RPC cold start** (new worker + first `getDb`) | **~1,100 ms** | Worker boot + schema self-heal (once per process) |

**Speedup (oneshot p50 → warm RPC p50):** roughly **550–880×** for the operations below.

Batching two methods in one RPC round-trip saves **Python↔worker overhead** but not much when each call is already sub-millisecond on a warm worker.

---

## Cold vs warm: oneshot vs persistent RPC

All times in **milliseconds**. **p50** = median; **p95** ≈ max for n=9 (see harness note).

### Oneshot (`HERMES_BROCCOLIDB_RPC=0`) — “before” analogue

Each row is a **new** `npx tsx infrastructure/hermes/hermes_oneshot.ts` process.

| Operation | min | p50 | p95≈max | mean |
|-----------|-----|-----|---------|------|
| `rpc_health` | 972 | **996** | 1,066 | 1,011 |
| `dashboard_snapshot` | 958 | **970** | 1,051 | 986 |
| `queue_status` | 950 | **955** | 973 | 957 |
| `agent_invoke` (`op=warm`) | 940 | **1,004** | 1,123 | 1,014 |

### Persistent RPC — warm worker

Worker already running; DB and (for agent) context warm.

| Operation | min | p50 | p95≈max | mean |
|-----------|-----|-----|---------|------|
| `rpc_health` | 1.14 | **1.22** | 2.06 | 1.38 |
| `dashboard_snapshot` | 1.41 | **1.74** | 2.29 | 1.78 |
| `queue_status` | 0.93 | **1.11** | 1.80 | 1.17 |
| `agent_invoke` (`op=warm`) | 0.90 | **1.14** | 4.69 | 1.54 |
| `agent_invoke` warm **repeat** (hot worker) | 0.91 | **0.94** | 1.58 | 1.06 |

### Persistent RPC — cold worker (includes boot)

`shutdown_gateway()` then `rpc_health` (new worker + first-request `getDb()` / schema log).

| | min | p50 | max |
|---|-----|-----|-----|
| Cold start `rpc_health` | 1,027 | **1,096** | 1,181 |

After the first RPC on a new worker, subsequent calls match the warm table above.

### Speedup table (p50)

| Operation | Oneshot p50 | Warm RPC p50 | Saved | Speedup |
|-------------|------------|--------------|-------|---------|
| `rpc_health` | 996 ms | 1.22 ms | ~995 ms | **817×** |
| `dashboard_snapshot` | 970 ms | 1.74 ms | ~969 ms | **558×** |
| `queue_status` | 955 ms | 1.11 ms | ~954 ms | **860×** |
| `agent_invoke` warm | 1,004 ms | 1.14 ms | ~1,003 ms | **881×** |

Raw JSON: `/tmp/broccolidb_bench.json` (or re-run harness with `-o`).

---

## Steady-state p50 / p95 (n=21, warm worker)

Supplementary micro-run on the same machine after one `warm_db_rpc()` (no per-iteration worker restart):

| Call | p50 | p95 |
|------|-----|-----|
| `rpc_health` | 0.22 ms | 0.39 ms |
| `queue_status` | 0.17 ms | 0.25 ms |

These are lower than the n=9 harness medians because the worker had been hot for many prior calls and the sample size is larger.

---

## Batch vs sequential (warm worker)

Two operations: `rpc_health` + `queue_status`.

| Pattern | p50 | p95 |
|---------|-----|-----|
| **2 sequential RPCs** (2 stdin lines, 2 responses) | 0.25 ms | 0.35 ms |
| **1 batch RPC** (`batch` with 2 sub-calls) | 0.25 ms | 0.54 ms |

**Interpretation:** On a warm worker, both patterns are **sub-millisecond**. Batching mainly helps when:

- You would otherwise pay **oneshot ~1 s** per call (Kanban board intel: 2–3 hive calls → one `run_db_rpc_batch`), or
- You want **one** Python round-trip for orchestration logic, not because SQLite is the bottleneck.

The `batch` handler runs sub-methods **sequentially** inside the worker (no parallel SQLite).

---

## What was *not* slow in this run

Spot-checks on a warm worker (single call):

| Method | Latency |
|--------|---------|
| `hive_integrity` | ~301 ms |
| `dashboard_snapshot` | ~1 ms |
| `agent_invoke` warm | ~3 ms |

---

## Why an ad-hoc benchmark script can “stall”

If you loop `shutdown_gateway()` + `run_db_rpc()` many times, **each iteration cold-starts a worker** and may run **schema self-heal** on first `getDb()` (~1 s+, occasionally longer). That looks like a hang but is repeated boot cost.

**Do instead:**

1. Use `scripts/benchmark_broccolidb_native_rpc.py` (finishes in ~40 s with n=9).
2. Call `warm_db_rpc(block=True)` once, then measure without shutting down the gateway between warm iterations.
3. Avoid `hive_integrity` in tight loops unless you intend to profile audits (~300 ms each).

---

## How to refresh these numbers

```bash
python scripts/benchmark_broccolidb_native_rpc.py -n 9 -o docs/broccolidb-bench-latest.json
```

The harness prints p50 and p95 columns and a speedup summary. Commit updated JSON only if you want to track regressions in-repo.

**Prerequisites:**

```bash
cd broccolidb && npm rebuild better-sqlite3   # if NODE_MODULE_VERSION errors
```

Ensure `broccolidb.db` exists and `HERMES_BROCCOLIDB_RPC=1` (default) for warm paths.
