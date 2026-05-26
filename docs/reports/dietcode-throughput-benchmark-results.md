# DietCode Throughput Benchmark — Test Results Report

| Field | Value |
| --- | --- |
| **Report ID** | `dietcode-throughput-2026-05-26` |
| **Date (UTC)** | 2026-05-26 |
| **Repository commit** | `74c0be5fe` |
| **Branch** | `master` |
| **Host OS** | Darwin 25.2.0 (arm64) |
| **Python** | 3.10.12 |
| **Benchmark harness** | `scripts/benchmark_dietcode_throughput.py` (full run) |
| **Pytest wrapper** | `scripts/run_tests.sh` (CI-parity, 4 workers) |

---

## 1. Executive Summary

This report documents verification of DietCode throughput optimizations across two complementary layers:

1. **Automated regression tests** — 23 pytest cases covering config defaults, BroccoliDB dashboard bridge, CLI memory prefetch skip, and web search timeout helpers. **All passed.**
2. **Manual throughput benchmark** — latency and throughput measurements on hot paths: TUI RPC event batching, SessionDB transcript writes, config load, memory prefetch fast-path, plugin hook checks, and live BroccoliDB dashboard snapshots.

**Key findings:**

| Area | Result | Assessment |
| --- | --- | --- |
| TUI RPC batching | 10,000 `message.delta` events → **157** stdout frames (vs 10,000 unbatched); **98.4%** frame reduction | Pass — batching effective |
| SessionDB batched writes | **20,355 msg/s** vs **2,570 msg/s** single-row; **7.92×** speedup | Pass — batch path dominant |
| Config load | Median **1.36 ms** (50 iterations) | Baseline recorded |
| Memory prefetch skip | Median **0.2 µs** (no external provider) | Pass — near-no-op fast path |
| BroccoliDB snapshot (live) | Median **470.52 ms** | Baseline recorded (I/O bound) |
| Config default tests | 11 tests, all assertions met | Pass |
| Integration tests | 12 additional tests (API + prefetch) | Pass |

---

## 2. Scope

### 2.1 In scope

Optimizations introduced in DietCode throughput passes (commits through `74c0be5fe`), including:

- TUI gateway `_EventBatcher` for high-frequency stream events
- SessionDB `append_messages_batch` and WAL checkpoint interval (`_CHECKPOINT_EVERY_N_WRITES = 200`)
- DietCode `DEFAULT_CONFIG` throughput-oriented defaults
- `memory.cli_skip_background_prefetch` on CLI/TUI
- `MemoryManager.queue_prefetch_all` no-op without external memory provider
- Plugin hook fast-paths (`has_hook_callbacks` before `invoke_hook`)
- BroccoliDB dashboard bridge (`hermes_cli/dietcode_broccolidb.py`)

### 2.2 Out of scope

- End-to-end LLM provider latency (network-bound)
- Multi-process gateway contention under production load
- Browser/CDP eval benchmarks (`scripts/benchmark_browser_eval.py`)

---

## 3. Methodology

### 3.1 Automated tests

```bash
scripts/run_tests.sh \
  tests/hermes_cli/test_dietcode_throughput_defaults.py \
  tests/hermes_cli/test_dietcode_broccolidb_api.py \
  tests/run_agent/test_cli_memory_background_prefetch.py \
  -q
```

Environment: hermetic (credential env vars unset, isolated `HERMES_HOME`, `TZ=UTC`, `LANG=C.UTF-8`, 4 xdist workers).

### 3.2 Throughput benchmark

```bash
source .venv/bin/activate
python scripts/benchmark_dietcode_throughput.py -o /tmp/dietcode_throughput_full.json
```

Parameters (full run):

| Parameter | Value |
| --- | --- |
| `message.delta` events | 10,000 |
| SessionDB messages (single / batch) | 2,000 each |
| Batch insert size | 50 rows per transaction |
| `load_config` iterations | 50 |
| Micro-benchmark iterations | 2,000 each |
| TUI batch window | 25 ms (`HERMES_TUI_RPC_BATCH_MS` default) |
| TUI batch max | 64 events (`HERMES_TUI_RPC_BATCH_MAX` default) |

Each timed benchmark reports **min / median / max** over 3–5 iterations unless noted otherwise.

---

## 4. Automated Test Results

### 4.1 Summary

| Metric | Value |
| --- | --- |
| **Total tests** | 23 |
| **Passed** | 23 |
| **Failed** | 0 |
| **Skipped** | 0 |
| **Duration** | 2.15 s |

**Status: PASS**

### 4.2 Test inventory

#### `tests/hermes_cli/test_dietcode_throughput_defaults.py` (11 tests)

| Test | Assertion | Result |
| --- | --- | --- |
| `test_compression_threshold_defers_aux_summarization` | `compression.threshold == 0.65` | Pass |
| `test_background_review_nudges_disabled_by_default` | `memory.nudge_interval == 0`, `skills.creation_nudge_interval == 0` | Pass |
| `test_curator_and_joyzoning_off_by_default` | `curator.enabled`, `joyzoning.enabled`, `joyzoning.execution_journal` all `False` | Pass |
| `test_tui_tool_progress_emits_start_complete_only` | `display.tool_progress == "new"` | Pass |
| `test_aux_title_and_mutation_verifier_off_by_default` | `display.auto_title`, `display.file_mutation_verifier` both `False` | Pass |
| `test_tool_guardrails_and_compression_tuned_for_throughput` | `tool_loop_guardrails.warnings_enabled == False`, `compression.protect_last_n == 25` | Pass |
| `test_logging_and_model_catalog_quiet_by_default` | `logging.level == "WARNING"`, memory monitor off, model catalog off | Pass |
| `test_api_retries_and_lsp_tuned_for_throughput` | `agent.api_max_retries == 2`, `lsp.enabled == False` | Pass |
| `test_tool_timeout_defaults_tuned_for_throughput` | terminal 120s, browser command 25s, inactivity 90s, web search 45s | Pass |
| `test_memory_cli_skips_background_prefetch_by_default` | `memory.cli_skip_background_prefetch == True`, `checkpoints.enabled == False` | Pass |
| `test_dietcode_dashboard_broccolidb_enabled_by_default` | `dietcode.dashboard.broccolidb_enabled == True`, poll 15s | Pass |

#### `tests/hermes_cli/test_dietcode_broccolidb_api.py` (10 tests)

| Test | Description | Result |
| --- | --- | --- |
| `test_health_when_tree_missing` | Health probe when BroccoliDB tree absent | Pass |
| `test_health_live_when_db_exists` | Live flag when DB file present | Pass |
| `test_health_respects_config_disable` | `broccolidb_enabled: false` honored | Pass |
| `test_snapshot_skips_subprocess_when_not_live` | No subprocess when offline | Pass |
| `test_dietcode_health_route` | `GET /api/dietcode/health` | Pass |
| `test_dietcode_snapshot_route` | `GET /api/dietcode/snapshot` | Pass |
| `test_dietcode_proposal_action_route` | `POST /api/dietcode/proposals/{id}/action` | Pass |
| `test_dietcode_proposal_action_rejects_failure` | 400 on failed action | Pass |
| `test_get_web_search_timeout_seconds_default` | Default 45s | Pass |
| `test_get_web_search_timeout_seconds_clamps` | Upper bound 300s | Pass |

#### `tests/run_agent/test_cli_memory_background_prefetch.py` (2 tests)

| Test | Description | Result |
| --- | --- | --- |
| `test_mirror_turn_skips_background_prefetch_on_cli` | `queue_prefetch_all` not called when `cli_skip_background_prefetch` true | Pass |
| `test_mirror_turn_queues_prefetch_when_config_disabled` | Prefetch runs when config flag false | Pass |

---

## 5. Throughput Benchmark Results

### 5.1 TUI gateway — RPC event batching

Measures stdout frame count when emitting `message.delta` events to a registered TUI session.

| Metric | Batched (25 ms window) | Unbatched (`_ms = 0`) | Delta |
| --- | ---: | ---: | ---: |
| Events emitted | 10,000 | 10,000 | — |
| Stdout frames | **157** | 10,000 | **−98.4%** |
| Wall time (ms) | 30.20 | 46.05 | −34.4% |
| Throughput (events/s) | **331,110** | 217,155 | +52.5% |

**Interpretation:** Batching collapses thousands of per-delta JSON-RPC frames into O(batch_size) frames, reducing stdio pressure on the Ink ↔ Python bridge. Urgent events (`tool.start`, `tool.complete`, approvals) still bypass the buffer per `_EventBatcher.emit()`.

### 5.2 SessionDB — transcript writes

| Benchmark | Min (ms) | Median (ms) | Max (ms) | Throughput | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| `append_message` × 2,000 | 678.67 | **778.35** | 790.70 | 2,570 msg/s | 1.00× (baseline) |
| `append_messages_batch` × 2,000 (batch=50) | 93.38 | **98.26** | 106.34 | **20,355 msg/s** | **7.92×** |

**Interpretation:** Batched inserts amortize transaction and WAL checkpoint overhead. Production agent loops should prefer `append_messages_batch` where multiple messages are persisted in one turn.

### 5.3 Configuration and micro-paths

| Benchmark | Iterations | Min | Median | Max | Unit |
| --- | ---: | ---: | ---: | ---: | --- |
| `load_config` | 50 | 1.26 | **1.36** | 2.60 | ms |
| `queue_prefetch_all` (builtin-only) | 2,000 | — | **0.2** | 1.4 | µs |
| `pre_tool_call` hook check | 2,000 | — | **2.8** | 3,130.5 | µs |

**Notes:**

- `queue_prefetch_all` returns immediately when `has_external_provider` is false (DietCode default with builtin-only memory).
- `pre_tool_call` median is low; max spike (3.1 ms) reflects occasional plugin discovery/import on cold paths. `hooks_registered: true` on this host indicates at least one plugin registered `pre_tool_call`.

### 5.4 BroccoliDB dashboard snapshot (live)

| Metric | Min (ms) | Median (ms) | Max (ms) |
| --- | ---: | ---: | ---: |
| `get_snapshot()` | 463.86 | **470.52** | 658.63 |

**Status:** Live (`broccolidb.db` present, `npx` available).

**Interpretation:** Dominated by subprocess `npx tsx` + SQLite reads. Suitable for dashboard poll interval (default 15 s); not on the agent hot path.

---

## 6. Configuration Defaults Verified

The following `DEFAULT_CONFIG` keys are locked by automated tests and underpin the throughput profile:

| Section | Key | Value | Rationale |
| --- | --- | --- | --- |
| `compression` | `threshold` | `0.65` | Defer aux summarization |
| `compression` | `protect_last_n` | `25` | Smaller protected tail |
| `memory` | `nudge_interval` | `0` | No background review nudges |
| `memory` | `cli_skip_background_prefetch` | `true` | Skip post-turn prefetch on CLI/TUI |
| `skills` | `creation_nudge_interval` | `0` | No skill-creation nudges |
| `curator` | `enabled` | `false` | No curator loop |
| `joyzoning` | `enabled` | `false` | No joyzoning overhead |
| `display` | `tool_progress` | `"new"` | `tool.start` / `tool.complete` only |
| `display` | `auto_title` | `false` | Skip title LLM call |
| `display` | `file_mutation_verifier` | `false` | Skip verifier LLM call |
| `tool_loop_guardrails` | `warnings_enabled` | `false` | No guardrail warnings |
| `logging` | `level` | `"WARNING"` | Quieter logs |
| `model_catalog` | `enabled` | `false` | No remote catalog fetch |
| `agent` | `api_max_retries` | `2` | Faster failover |
| `lsp` | `enabled` | `false` | No LSP on write/patch |
| `terminal` | `timeout` | `120` | Fail hung shells sooner |
| `browser` | `command_timeout` | `25` | Faster CDP bail-out |
| `browser` | `inactivity_timeout` | `90` | Stale tab cleanup |
| `web` | `search_timeout_seconds` | `45` | Documented search cap |
| `checkpoints` | `enabled` | `false` | No FS checkpoint overhead |
| `dietcode.dashboard` | `broccolidb_enabled` | `true` | Live dashboard data |
| `dietcode.dashboard` | `poll_interval_seconds` | `15` | Reasonable poll cadence |

SessionDB (code constant, not config): `_CHECKPOINT_EVERY_N_WRITES = 200`.

---

## 7. Conclusions

1. **Automated coverage passes.** All 23 targeted pytest cases pass under CI-parity conditions, confirming config defaults and integration contracts for BroccoliDB, memory prefetch, and web timeouts.

2. **Measured hot-path improvements are substantial** where batching applies:
   - TUI stream events: **98.4%** fewer RPC frames.
   - SessionDB writes: **7.92×** higher throughput with batch size 50.

3. **Fast-paths behave as designed.** Builtin-only memory prefetch and hook presence checks complete in microseconds at median.

4. **BroccoliDB snapshot latency is acceptable for dashboard polling** (~470 ms median) but should not be on the agent conversation critical path.

5. **Regression workflow:** Re-run the benchmark after changes and compare JSON artifacts:

   ```bash
   python scripts/benchmark_dietcode_throughput.py -o before.json
   # apply changes
   python scripts/benchmark_dietcode_throughput.py -o after.json
   python scripts/benchmark_dietcode_throughput.py --compare before.json after.json
   ```

---

## 8. Reproduction

### 8.1 Full benchmark + tests (recommended)

```bash
source .venv/bin/activate

scripts/run_tests.sh \
  tests/hermes_cli/test_dietcode_throughput_defaults.py \
  tests/hermes_cli/test_dietcode_broccolidb_api.py \
  tests/run_agent/test_cli_memory_background_prefetch.py \
  -q

python scripts/benchmark_dietcode_throughput.py \
  -o docs/reports/dietcode-throughput-$(date -u +%Y%m%d).json
```

### 8.2 Quick smoke (~5 s)

```bash
python scripts/benchmark_dietcode_throughput.py --quick
```

---

## Appendix A — Raw benchmark JSON

Captured at `2026-05-26T03:53:53Z` (`quick: false`):

```json
{
  "timestamp": "2026-05-26T03:53:53Z",
  "quick": false,
  "results": [
    {
      "label": "tui_rpc_frames (10000 message.delta)",
      "n_events": 10000,
      "batched_frames": 157,
      "unbatched_frames": 10000,
      "frame_reduction_pct": 98.4,
      "batched_elapsed_ms": 30.2,
      "unbatched_elapsed_ms": 46.05
    },
    {
      "label": "tui_rpc_emit (10000 deltas, batched)",
      "median_ms": 30.201,
      "events_per_sec": 331110.0
    },
    {
      "label": "sessiondb append_message x2000",
      "median_ms": 778.351,
      "msgs_per_sec": 2570.0
    },
    {
      "label": "sessiondb append_messages_batch x2000 (size=50)",
      "median_ms": 98.257,
      "msgs_per_sec": 20355.0,
      "speedup_vs_single": 7.92
    },
    {
      "label": "load_config x50",
      "median_ms": 1.357
    },
    {
      "label": "memory queue_prefetch_all (builtin-only skip)",
      "median_us": 0.2,
      "max_us": 1.4
    },
    {
      "label": "pre_tool_call hook check",
      "hooks_registered": true,
      "median_us": 2.8,
      "max_us": 3130.5
    },
    {
      "label": "broccolidb get_snapshot (live)",
      "live": true,
      "median_ms": 470.52,
      "min_ms": 463.86,
      "max_ms": 658.63
    }
  ]
}
```

---

## Appendix B — Related artifacts

| Artifact | Path |
| --- | --- |
| Benchmark script | `scripts/benchmark_dietcode_throughput.py` |
| Config default tests | `tests/hermes_cli/test_dietcode_throughput_defaults.py` |
| BroccoliDB API tests | `tests/hermes_cli/test_dietcode_broccolidb_api.py` |
| Memory prefetch tests | `tests/run_agent/test_cli_memory_background_prefetch.py` |
| Kanban scale benchmark (reference pattern) | `tests/stress/test_benchmarks.py` |

---

*Report generated from live runs on commit `74c0be5fe`. Absolute timings vary by hardware; use `--compare` for regression diffing on the same machine.*
