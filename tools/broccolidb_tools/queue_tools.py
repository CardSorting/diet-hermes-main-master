"""
BroccoliQ Tools — Sharded queue, hive integrity, and swarm coordination.
"""
import json
from tools.registry import registry
from tools.broccolidb_tools.runner import check_requirements, run_ts_script


def broccolidb_queue_status(task_id: str = None) -> str:
    """Report SqliteQueue job counts grouped by status."""
    script = """
import { getDb, getActiveShards } from './infrastructure/db/Config.js';

const shards = getActiveShards().length ? getActiveShards() : ['main'];
const byStatus: Record<string, number> = {};
let total = 0;

for (const shardId of shards) {
  const db = await getDb(shardId);
  const rows = await db
    .selectFrom('queue_jobs')
    .select(['status'])
    .execute();
  for (const row of rows) {
    byStatus[row.status] = (byStatus[row.status] ?? 0) + 1;
    total += 1;
  }
}

console.log(JSON.stringify({ success: true, total, byStatus, shards }));
"""
    return run_ts_script(script)


def broccolidb_shard_status(task_id: str = None) -> str:
    """List active BroccoliQ database shards and connection health."""
    script = """
import { getActiveShards, getDb } from './infrastructure/db/Config.js';

const shards = getActiveShards();
const listed = shards.length ? shards : ['main'];
const detail = [];

for (const shardId of listed) {
  try {
    const db = await getDb(shardId);
    const probe = await db.selectFrom('queue_settings' as any).selectAll().limit(1).execute();
    detail.push({ shardId, healthy: true, probeRows: probe.length });
  } catch (e) {
    detail.push({ shardId, healthy: false, error: e instanceof Error ? e.message : String(e) });
  }
}

console.log(JSON.stringify({ success: true, shardCount: detail.length, shards: detail }));
"""
    return run_ts_script(script)


def broccolidb_hive_integrity(task_id: str = None) -> str:
    """Run a one-shot BroccoliQ IntegrityWorker audit across all shards."""
    script = """
import { IntegrityWorker } from './infrastructure/db/IntegrityWorker.js';
import { getActiveShards } from './infrastructure/db/Config.js';

const worker = new IntegrityWorker(600000);
await worker.runAudit();
const shards = getActiveShards();

console.log(JSON.stringify({
  success: true,
  message: 'Integrity audit complete',
  shards: shards.length ? shards : ['main'],
}));
"""
    return run_ts_script(script, timeout=120)


registry.register(
    name="broccolidb_queue_status",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_queue_status",
        "description": (
            "Report BroccoliQ SqliteQueue job counts by status (pending, processing, done, failed). "
            "Use before tuning background workers or diagnosing stuck jobs."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    handler=lambda args, **kw: broccolidb_queue_status(task_id=kw.get("task_id")),
    check_fn=check_requirements,
    emoji="📬",
)

registry.register(
    name="broccolidb_shard_status",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_shard_status",
        "description": (
            "List active BroccoliQ database shards and verify each shard connection is healthy. "
            "Use when scaling agent swarms or debugging SQLITE_BUSY contention."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    handler=lambda args, **kw: broccolidb_shard_status(task_id=kw.get("task_id")),
    check_fn=check_requirements,
    emoji="🧩",
)

registry.register(
    name="broccolidb_hive_integrity",
    toolset="broccolidb",
    schema={
        "name": "broccolidb_hive_integrity",
        "description": (
            "Run a BroccoliQ IntegrityWorker audit across all database shards. "
            "Checks physical SQLite integrity and logical orphan consistency."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    handler=lambda args, **kw: broccolidb_hive_integrity(task_id=kw.get("task_id")),
    check_fn=check_requirements,
    emoji="🛡️",
)
