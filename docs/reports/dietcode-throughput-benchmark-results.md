# DietCode Throughput Benchmark — Test Results Report

| Field | Value |
| --- | --- |
| **Report ID** | `dietcode-throughput-2026-05-26b` |
| **Date (UTC)** | 2026-05-26 |
| **Repository commit** | `b85c99ddf` |
| **Branch** | `master` (working tree) |
| **Host OS** | Darwin 25.2.0 (arm64) |
| **Python** | 3.11.9 |
| **Benchmark harness** | `scripts/benchmark_dietcode_throughput.py` (full run) |
| **Benchmark artifact** | `docs/reports/dietcode-throughput-20260526.json` |
| **Pytest wrapper** | `scripts/run_tests.sh` (CI-parity, 4 workers) |

> **Architecture note (2026-05):** This report predates consolidation into `plugins/dietcode/`.
> References to `joyzoning_governance` mean the unified DietCode plugin’s governance hook
> (`plugins/dietcode/lib/runtime/governance_hooks.py`), not the removed legacy shim plugin.

---

This report documents DietCode throughput after the **JoyZoning plugin + governance hardening** pass and **agent-loop I/O** optimizations (deferred session persist, compression preflight off, light governance validation, mtime gate cache).

Two verification layers:

1. **Automated regression tests** — **47** pytest cases (config defaults, governance, session persist, BroccoliDB API, memory prefetch). **All passed** in 3.68 s.
2. **Manual throughput benchmark** — latency on TUI RPC batching, SessionDB writes, config load, memory/hook fast-paths, **JoyZoning governance transform hook**, path classification LRU, and BroccoliDB snapshot (when live).

**Key findings (this run):**

| Area | Result | Assessment |
| --- | --- | --- |
| TUI RPC batching | 10,000 deltas → **157** frames (−**98.4%**); **419k** events/s batched | Pass |
| SessionDB batched writes | **20,069 msg/s** vs **4,627 msg/s** single-row; **4.34×** speedup | Pass |
| Config load | Median **0.58 ms** (50 iterations) | Fast |
| Memory prefetch skip | Median **0.1 µs** (builtin-only) | Pass |
| `transform_tool_result` hook check | Median **0.2 µs** (`plugins/dietcode` registered) | Pass |
| Governance — tool error skip | Median **2.2 µs** (no gate / disk read) | Pass |
| Governance — cold light validate | Median **2.51 ms** per `write_file` | Acceptable on mutation path |
| Governance — mtime cache hit | Median **6.9 µs** (~**363×** vs cold) | Pass — repeat writes cheap |
| Path classification LRU | **~8.1M** classifications/s (30k paths / 3.7 ms) | Pass |
| BroccoliDB snapshot (live) | Median **8.58 ms** (warm RPC) | Baseline (environment-dependent) |

---

## 2. Scope

### 2.1 In scope

Optimizations and behavior covered by this benchmark and test suite:

| Category | Items |
| --- | --- |
| **TUI / session I/O** | `_EventBatcher`; `append_messages_batch`; `_CHECKPOINT_EVERY_N_WRITES = 200`; `agent.session_persist_incremental: false` + turn-end `_flush_deferred_session_persist` |
| **Compression** | `compression.threshold: 0.75`; `check_after_tools: false`; `preflight_enabled: false` |
| **Memory** | `cli_skip_background_prefetch` / `cli_skip_turn_prefetch`; `queue_prefetch_all` no-op without external provider |
| **Tool guardrails** | `warnings_enabled: false`; governance-fault fast path |
| **JoyZoning plugin** | Unified `plugins/dietcode` (`kind: standalone`); `governance.enabled: true`; `layer_tags_required: false`; `validation_mode: auto` → **light** (skips smell heuristics) |
| **Governance hot path** | Skip gate on failed tool JSON; in-memory `write_file` content; per-file mtime pass cache; path LRU (`resolve_governance_path_kind`) |
| **Plugins / hooks** | `has_hook_callbacks` before `invoke_hook` on `pre_tool_call` / `transform_tool_result` |
| **Dashboard** | `hermes_cli/dietcode_broccolidb.py` → `hermes_cli/dietcode_bridge.py` |

### 2.2 Out of scope

- End-to-end LLM provider latency (network-bound)
- Multi-process gateway contention under production load
- Full `validate_joy_zoning` **full** mode (smell + layering) on every write — use `validation_mode: full` only when needed
- Browser/CDP eval (`scripts/benchmark_browser_eval.py`)

---

## 3. Methodology

### 3.1 Automated tests

```bash
scripts/run_tests.sh \
  tests/hermes_cli/test_dietcode_throughput_defaults.py \
  tests/hermes_cli/test_dietcode_broccolidb_api.py \
  tests/run_agent/test_cli_memory_background_prefetch.py \
  tests/run_agent/test_session_persist_deferred.py \
  tests/agent/test_governance_exemptions_evaluate.py \
  tests/agent/test_governance_layer_tags_optional.py \
  -q
```

Environment: hermetic (`HERMES_HOME` temp dir, credentials unset, `TZ=UTC`, `LANG=C.UTF-8`, 4 xdist workers).

### 3.2 Throughput benchmark

```bash
source .venv/bin/activate   # or: source venv/bin/activate
python scripts/benchmark_dietcode_throughput.py \
  -o docs/reports/dietcode-throughput-20260526.json
```

Parameters (full run):

| Parameter | Value |
| --- | --- |
| `message.delta` events | 10,000 |
| SessionDB messages (single / batch) | 2,000 each |
| Batch insert size | 50 rows per transaction |
| `load_config` iterations | 50 |
| Micro-benchmark iterations | 2,000 each (governance enforce / hooks) |
| Governance path classifications | 5,000 × 6 paths = 30,000 |
| TUI batch window | 25 ms (default) |
| Isolated `HERMES_HOME` | Minimal `config.yaml` with `joyzoning.governance` enabled + `validation_mode: light` |

Quick smoke:

```bash
python scripts/benchmark_dietcode_throughput.py --quick
```

Compare two JSON runs on the **same machine**:

```bash
python scripts/benchmark_dietcode_throughput.py -o /tmp/before.json
# apply changes
python scripts/benchmark_dietcode_throughput.py -o /tmp/after.json
python scripts/benchmark_dietcode_throughput.py --compare /tmp/before.json /tmp/after.json
```

---

## 4. Automated Test Results

### 4.1 Summary

| Metric | Value |
| --- | --- |
| **Total tests** | 47 |
| **Passed** | 47 |
| **Failed** | 0 |
| **Duration** | 3.68 s |

**Status: PASS**

### 4.2 Test inventory (representative)

#### `tests/hermes_cli/test_dietcode_throughput_defaults.py` (12 tests)

| Area | Default verified |
| --- | --- |
| Compression | `threshold == 0.75`, `check_after_tools == false`, `preflight_enabled == false` |
| Memory / skills nudges | `nudge_interval == 0`, `creation_nudge_interval == 0` |
| JoyZoning runtime | `joyzoning.enabled == false` (convergence/journal plugin path off) |
| **JoyZoning governance** | **`governance.enabled == true`**, `layer_tags_required == false`, `validation_mode == auto` |
| Session persist | `session_persist_incremental == false` |
| Guardrails / logging / LSP / timeouts | Throughput-oriented (see test file) |

#### Governance & session (additional suites in this run)

| Suite | Focus |
| --- | --- |
| `tests/agent/test_governance_exemptions_evaluate.py` | Transform hook, cache skip, tool-error skip, recovery payloads |
| `tests/agent/test_governance_layer_tags_optional.py` | Optional tags, light vs full validation |
| `tests/run_agent/test_session_persist_deferred.py` | Mid-turn skip DB; turn-end flush |
| `tests/run_agent/test_cli_memory_background_prefetch.py` | CLI prefetch skip |
| `tests/hermes_cli/test_dietcode_broccolidb_api.py` | Dashboard health/snapshot routes |

---

## 5. Throughput Benchmark Results

*Source: `docs/reports/dietcode-throughput-20260526.json` (`2026-05-26T19:28:38Z`).*

### 5.1 TUI gateway — RPC event batching

| Metric | Batched (25 ms) | Unbatched | Delta |
| --- | ---: | ---: | ---: |
| Events | 10,000 | 10,000 | — |
| Stdout frames | **157** | 10,000 | **−98.4%** |
| Wall time (ms) | 23.86 | 34.13 | −30.1% |
| Throughput | **419,182** events/s | — | — |

### 5.2 SessionDB — transcript writes

| Benchmark | Median (ms) | Throughput | Speedup |
| --- | ---: | ---: | ---: |
| `append_message` × 2,000 | **432.24** | 4,627 msg/s | 1.00× |
| `append_messages_batch` × 2,000 (batch=50) | **99.65** | **20,069 msg/s** | **4.34×** |

With `session_persist_incremental: false`, production agents should flush once per turn via `_flush_deferred_session_persist` (not per tool iteration).

### 5.3 Configuration and hook micro-paths

| Benchmark | Median | Unit | Notes |
| --- | ---: | --- | --- |
| `load_config` × 50 | **0.58** | ms | |
| `queue_prefetch_all` (builtin-only) | **0.1** | µs | No external memory provider |
| `pre_tool_call` hook check | **2.0** | µs | Hooks registered on bench host |
| `transform_tool_result` hook check | **0.2** | µs | `plugins/dietcode` governance hook active |

### 5.4 JoyZoning governance transform hook

Measured on a single governed `src/domain/bench.ts` with light validation (`validation_mode: light` in bench `HERMES_HOME`).

| Benchmark | Median | Unit | Notes |
| --- | ---: | --- | --- |
| Enforce — tool result already failed | **2.2** | µs | Parses JSON, returns before partition/gate |
| Enforce — cold (cache cleared) | **2.51** | ms | Full light validate + disk read if needed |
| Enforce — mtime cache hit | **6.9** | µs | **~363×** faster than cold on same file |
| `resolve_governance_path_kind` × 30,000 | **3.71** | ms | LRU classifier; **~8.1M** paths/s |

**Interpretation:** With the plugin **on**, repeat mutations to an unchanged file are effectively free at the Hermes layer. Cold validation remains ~2–5 ms per governed TS file (import rules + layering, no smell pass). Failed `write_file` / `patch` results do not trigger a gate.

### 5.5 BroccoliDB dashboard snapshot (live)

| Metric | Min (ms) | Median (ms) | Max (ms) |
| --- | ---: | ---: | ---: |
| `get_snapshot()` (warm RPC) | 8.36 | **8.58** | 11.47 |
| `rpc_health` | — | 1.06 | — |

**Status:** Live on benchmark host. Timings vary widely with subprocess warm-up and `broccolidb.db` size; treat as dashboard poll metric only (default 15 s), not agent hot path.

---

## 6. Configuration Defaults Verified

| Section | Key | Value | Rationale |
| --- | --- | --- | --- |
| `compression` | `threshold` | `0.75` | Fewer mid-turn aux summarizations |
| `compression` | `check_after_tools` | `false` | No O(n) token re-estimate after each tool batch |
| `compression` | `preflight_enabled` | `false` | No turn-start full-history token estimate |
| `compression` | `protect_last_n` | `25` | Smaller protected tail when compressing |
| `agent` | `session_persist_incremental` | `false` | Defer SQLite/JSON until turn end |
| `memory` | `cli_skip_background_prefetch` | `true` | Skip post-turn prefetch threads on CLI/TUI |
| `memory` | `cli_skip_turn_prefetch` | `true` | Skip turn-start external prefetch on CLI/TUI |
| `joyzoning` | `enabled` | `false` | Convergence/journal plugin path off |
| `joyzoning.governance` | `enabled` | **`true`** | **`plugins/dietcode` transform hook on** |
| `joyzoning.governance` | `layer_tags_required` | `false` | No mandatory `[LAYER: TYPE]` / PGA spirals |
| `joyzoning.governance` | `validation_mode` | `auto` | Light validate when tags optional |
| `tool_loop_guardrails` | `warnings_enabled` | `false` | Hot-path guardrail fingerprinting off |
| `curator` | `enabled` | `false` | No curator loop |
| `checkpoints` | `enabled` | `false` | No FS checkpoint overhead |
| `display` | `tool_progress` | `"new"` | `tool.start` / `tool.complete` only |
| `display` | `auto_title` / `file_mutation_verifier` | `false` | Skip auxiliary LLM calls |

SessionDB constant: `_CHECKPOINT_EVERY_N_WRITES = 200`.

---

## 7. Conclusions

1. **Regression tests pass** — 47 cases under CI-parity settings, including governance-on defaults and deferred session persistence.

2. **Batching remains the largest win** for Hermes-native I/O: TUI frames −98.4%; SessionDB **4.34×** on this host.

3. **JoyZoning can stay enabled** without dominating the tool loop: cache hits ~7 µs; failed tools ~2 µs; cold light validate ~2.5 ms per governed file.

4. **Do not disable the plugin for speed** — tune `validation_mode` (`light` / `auto`) and keep `layer_tags_required: false` unless you need strict tag enforcement.

5. **LLM latency still dominates** end-to-end turn time; these numbers bound Hermes overhead only.

6. **Re-run after changes** and commit the JSON artifact next to this report for regression diffing.

---

## 8. Reproduction

### 8.1 Full benchmark + tests (recommended)

```bash
source .venv/bin/activate

scripts/run_tests.sh \
  tests/hermes_cli/test_dietcode_throughput_defaults.py \
  tests/hermes_cli/test_dietcode_broccolidb_api.py \
  tests/run_agent/test_cli_memory_background_prefetch.py \
  tests/run_agent/test_session_persist_deferred.py \
  tests/agent/test_governance_exemptions_evaluate.py \
  tests/agent/test_governance_layer_tags_optional.py \
  -q

python scripts/benchmark_dietcode_throughput.py \
  -o docs/reports/dietcode-throughput-$(date -u +%Y%m%d).json
```

### 8.2 Quick smoke (~5–10 s)

```bash
python scripts/benchmark_dietcode_throughput.py --quick
```

---

## Appendix A — Raw benchmark JSON

Captured at `2026-05-26T19:28:38Z` (`quick: false`). Canonical copy: `docs/reports/dietcode-throughput-20260526.json`.

```json
{
  "timestamp": "2026-05-26T19:28:38Z",
  "quick": false,
  "results": [
    {
      "label": "tui_rpc_frames (10000 message.delta)",
      "n_events": 10000,
      "batched_frames": 157,
      "unbatched_frames": 10000,
      "frame_reduction_pct": 98.4,
      "batched_elapsed_ms": 23.86,
      "unbatched_elapsed_ms": 34.13
    },
    {
      "label": "tui_rpc_emit (10000 deltas, batched)",
      "median_ms": 23.856,
      "events_per_sec": 419182.0
    },
    {
      "label": "sessiondb append_message x2000",
      "median_ms": 432.237,
      "msgs_per_sec": 4627.0
    },
    {
      "label": "sessiondb append_messages_batch x2000 (size=50)",
      "median_ms": 99.655,
      "msgs_per_sec": 20069.0,
      "speedup_vs_single": 4.34
    },
    {
      "label": "load_config x50",
      "median_ms": 0.581
    },
    {
      "label": "memory queue_prefetch_all (builtin-only skip)",
      "median_us": 0.1,
      "max_us": 1.0
    },
    {
      "label": "pre_tool_call hook check",
      "hooks_registered": true,
      "median_us": 2.0,
      "max_us": 3518.9
    },
    {
      "label": "transform_tool_result hook check",
      "hooks_registered": true,
      "median_us": 0.2,
      "max_us": 0.3
    },
    {
      "label": "governance enforce (tool error skip)",
      "median_us": 2.2,
      "max_us": 924.0
    },
    {
      "label": "governance enforce (cold, light validate)",
      "median_ms": 2.511,
      "max_ms": 5.082
    },
    {
      "label": "governance enforce (mtime cache hit)",
      "median_us": 6.9,
      "max_us": 92.0,
      "speedup_vs_cold": 363.1
    },
    {
      "label": "governance resolve_path_kind x30000",
      "median_ms": 3.706,
      "paths_per_sec": 8095617.0
    },
    {
      "label": "broccolidb get_snapshot (live, warm RPC)",
      "live": true,
      "rpc_health_median_ms": 1.06,
      "median_ms": 8.58,
      "min_ms": 8.36,
      "max_ms": 11.47
    }
  ]
}
```

---

## Appendix B — Related artifacts

| Artifact | Path |
| --- | --- |
| Benchmark script | `scripts/benchmark_dietcode_throughput.py` |
| Latest JSON output | `docs/reports/dietcode-throughput-20260526.json` |
| Config default tests | `tests/hermes_cli/test_dietcode_throughput_defaults.py` |
| Governance tests | `tests/agent/test_governance_exemptions_evaluate.py`, `tests/agent/test_governance_layer_tags_optional.py` |
| Session persist tests | `tests/run_agent/test_session_persist_deferred.py` |
| BroccoliDB API tests | `tests/hermes_cli/test_dietcode_broccolidb_api.py` |
| Memory prefetch tests | `tests/run_agent/test_cli_memory_background_prefetch.py` |

---

*Report generated from live runs on commit `b85c99ddf`. Absolute timings vary by hardware; use `--compare` on the same machine for before/after diffs.*
