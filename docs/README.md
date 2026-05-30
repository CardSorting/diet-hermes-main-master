# DietCode fork documentation

Hermes Agent upstream docs live at [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/). This directory holds **fork-specific** guides for BroccoliDB, throughput, and integrations shipped in this repository.

## BroccoliDB / BroccoliQ native RPC

| Document | Description |
|----------|-------------|
| [dietcode-plugin.md](./dietcode-plugin.md) | Unified plugin layout, core facades, config defaults, legacy shim policy |
| [broccolidb-native-execution-throughput.md](./broccolidb-native-execution-throughput.md) | Architecture (before/after), implementation passes, RPC protocol, configuration, fallback behavior |
| [broccolidb-throughput-benchmark-results.md](./broccolidb-throughput-benchmark-results.md) | Measured latencies: oneshot vs warm RPC, p50/p95, batch vs sequential, how to re-run benchmarks |

**Quick start (developers):**

```bash
source .venv/bin/activate
python -m pip install -e .
cd broccolidb && npm ci && npm rebuild better-sqlite3 && cd ..
python scripts/benchmark_broccolidb_native_rpc.py -n 9
```

**Python entry points:** `plugins/dietcode/lib/tools/broccolidb_tools/exec.py` (`run_db_rpc`, `run_agent_rpc`, `warm_db_rpc`). Dashboard and kanban use `hermes_cli/dietcode_bridge.py` — not direct plugin imports from core.

**TypeScript worker:** `broccolidb/infrastructure/hermes/hermes_rpc.ts` — see [broccolidb/infrastructure/hermes/README.md](../broccolidb/infrastructure/hermes/README.md).

## Related repo docs

- Root overview and install: [README.md](../README.md)
- Agent/contributor conventions: [AGENTS.md](../AGENTS.md)
