# Hermes native RPC (`infrastructure/hermes/`)

Persistent BroccoliDB/BroccoliQ worker used by Hermes Python tools. **Full before/after throughput documentation:** [`docs/broccolidb-native-execution-throughput.md`](../../../docs/broccolidb-native-execution-throughput.md).

## Quick reference

| File | Role |
|------|------|
| `hermes_rpc.ts` | Persistent stdin/stdout worker |
| `hermes_oneshot.ts` | Cold fallback: `tsx hermes_oneshot.ts <method> '<json-params>'` |
| `rpc_handlers.ts` | Canonical handlers (`dispatchRpc`) |
| `agent_session.ts` | Warm `AgentContext` singleton |
| `agent_invoke.ts` | Graph/kanban cognitive ops |
| `queue_metrics.ts` | SQL `GROUP BY` queue status |

## Local dev

```bash
cd broccolidb
export HERMES_BROCCOLIDB_DB=/path/to/broccolidb.db
echo '{"id":1,"method":"rpc_health","params":{}}' | npx tsx infrastructure/hermes/hermes_rpc.ts
```

Python: `from tools.broccolidb_tools.exec import run_db_rpc, warm_db_rpc`
