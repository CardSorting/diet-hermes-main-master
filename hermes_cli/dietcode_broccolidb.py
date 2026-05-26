"""
DietCode dashboard ↔ BroccoliDB bridge.

Exposes health checks and live hive/graph snapshots for the web dashboard.
Uses existing tools/broccolidb_tools/runner.py subprocess infrastructure.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger(__name__)

_SNAPSHOT_SCRIPT = "infrastructure/dashboard/snapshot.ts"
_PROPOSAL_ACTION_SCRIPT = """\
import { getActiveShards, getDb } from './infrastructure/db/Config.js';

const proposalId = process.env.DIETCODE_PROPOSAL_ID || '';
const action = (process.env.DIETCODE_PROPOSAL_ACTION || '').toLowerCase();

if (!proposalId || !['approve', 'deny'].includes(action)) {
  console.log(JSON.stringify({ success: false, error: 'Missing proposal id or invalid action' }));
  process.exit(1);
}

const shards = getActiveShards().length ? getActiveShards() : ['main'];
const shardId = shards.includes('kanban') ? 'kanban' : shards[0];
const db = await getDb(shardId);
const nextStatus = action === 'approve' ? 'approved' : 'rejected';

const row = await db
  .selectFrom('hive_healing_proposals')
  .selectAll()
  .where('id', '=', proposalId)
  .executeTakeFirst();

if (!row) {
  console.log(JSON.stringify({ success: false, error: 'Proposal not found' }));
  process.exit(1);
}

await db
  .updateTable('hive_healing_proposals')
  .set({ status: nextStatus, applied_at: action === 'approve' ? Date.now() : row.applied_at })
  .where('id', '=', proposalId)
  .execute();

console.log(JSON.stringify({ success: true, id: proposalId, status: nextStatus }));
"""


def _dietcode_dashboard_cfg() -> dict:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        dietcode = cfg.get("dietcode") if isinstance(cfg, dict) else {}
        dash = dietcode.get("dashboard") if isinstance(dietcode, dict) else {}
        return dash if isinstance(dash, dict) else {}
    except Exception:
        return {}


def dashboard_broccolidb_enabled() -> bool:
    """Whether the dashboard should attempt live BroccoliDB data."""
    dash = _dietcode_dashboard_cfg()
    return bool(dash.get("broccolidb_enabled", True))


def get_health() -> dict[str, Any]:
    """Connectivity probe — no subprocess when tree is missing."""
    from tools.broccolidb_tools.runner import (
        check_requirements,
        resolve_broccolidb_db_path,
        resolve_broccolidb_root,
    )

    root = resolve_broccolidb_root()
    db_path = resolve_broccolidb_db_path()
    db_exists = bool(db_path and Path(db_path).is_file())
    enabled = dashboard_broccolidb_enabled()

    return {
        "enabled": enabled,
        "available": check_requirements(),
        "root": root,
        "db_path": db_path,
        "db_exists": db_exists,
        "node_ok": shutil.which("npx") is not None,
        "live": enabled and check_requirements() and db_exists,
        "message": _health_message(enabled, check_requirements(), db_exists),
    }


def _health_message(enabled: bool, available: bool, db_exists: bool) -> str:
    if not enabled:
        return "BroccoliDB dashboard integration disabled in config (dietcode.dashboard.broccolidb_enabled)."
    if not available:
        return "BroccoliDB package not found in workspace — install broccolidb/ and run broccolidb_init."
    if not db_exists:
        return "broccolidb.db not found — run broccolidb_init from the project root."
    return "Connected to BroccoliDB."


def _parse_runner_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Invalid JSON from BroccoliDB: {exc}"}
    if not isinstance(data, dict):
        return {"success": False, "error": "BroccoliDB returned non-object JSON"}
    return data


def get_snapshot() -> dict[str, Any]:
    """Fetch live graph, sessions, proposals, queue, and audit rows."""
    health = get_health()
    if not health.get("live"):
        return {
            "success": False,
            "live": False,
            "health": health,
            "error": health.get("message") or "BroccoliDB unavailable",
        }

    from tools.broccolidb_tools.runner import resolve_broccolidb_root, run_ts_script

    root = resolve_broccolidb_root()
    if not root:
        return {"success": False, "live": False, "error": "BroccoliDB root not resolved"}

    script_path = Path(root) / _SNAPSHOT_SCRIPT
    if not script_path.is_file():
        return {
            "success": False,
            "live": False,
            "error": f"Missing dashboard script: {script_path.name}",
        }

    script = script_path.read_text(encoding="utf-8")
    raw = run_ts_script(script, timeout=45)
    data = _parse_runner_json(raw)
    data["live"] = bool(data.get("success"))
    data["health"] = health
    return data


def set_proposal_action(proposal_id: str, action: str) -> dict[str, Any]:
    """Approve or deny a hive_healing_proposals row."""
    health = get_health()
    if not health.get("live"):
        return {"success": False, "error": health.get("message") or "BroccoliDB unavailable"}

    action_lc = (action or "").strip().lower()
    if action_lc not in ("approve", "deny"):
        return {"success": False, "error": "action must be approve or deny"}

    pid = (proposal_id or "").strip()
    if not pid:
        return {"success": False, "error": "proposal_id required"}

    import os

    from tools.broccolidb_tools.runner import run_ts_script

    prev_id = os.environ.get("DIETCODE_PROPOSAL_ID")
    prev_action = os.environ.get("DIETCODE_PROPOSAL_ACTION")
    try:
        os.environ["DIETCODE_PROPOSAL_ID"] = pid
        os.environ["DIETCODE_PROPOSAL_ACTION"] = action_lc
        raw = run_ts_script(_PROPOSAL_ACTION_SCRIPT, timeout=30)
    finally:
        if prev_id is None:
            os.environ.pop("DIETCODE_PROPOSAL_ID", None)
        else:
            os.environ["DIETCODE_PROPOSAL_ID"] = prev_id
        if prev_action is None:
            os.environ.pop("DIETCODE_PROPOSAL_ACTION", None)
        else:
            os.environ["DIETCODE_PROPOSAL_ACTION"] = prev_action

    return _parse_runner_json(raw)
