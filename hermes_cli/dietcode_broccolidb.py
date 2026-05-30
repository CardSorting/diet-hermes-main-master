"""
DietCode dashboard ↔ BroccoliDB bridge.

Exposes health checks and live hive/graph snapshots for the web dashboard.
Plugin imports are isolated in ``hermes_cli.dietcode_bridge``.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from hermes_cli.dietcode_bridge import (
    broccolidb_rpc_available,
    broccolidb_rpc_version,
    check_broccolidb_requirements,
    resolve_broccolidb_db_path,
    resolve_broccolidb_root,
    run_broccolidb_rpc,
    warm_broccolidb_rpc,
)

_log = logging.getLogger(__name__)


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
    root = resolve_broccolidb_root()
    db_path = resolve_broccolidb_db_path()
    db_exists = bool(db_path and Path(db_path).is_file())
    enabled = dashboard_broccolidb_enabled()
    available = check_broccolidb_requirements()
    live = enabled and available and db_exists
    rpc_ok = broccolidb_rpc_available()

    if live and rpc_ok and dash_warm_rpc_enabled():
        warm_broccolidb_rpc(preload_agent=dash_preload_agent_enabled())

    rpc_version = broccolidb_rpc_version()

    return {
        "enabled": enabled,
        "available": available,
        "root": root,
        "db_path": db_path,
        "db_exists": db_exists,
        "node_ok": shutil.which("npx") is not None,
        "rpc_available": rpc_ok,
        "rpc_version": rpc_version if rpc_ok else None,
        "live": live,
        "message": _health_message(enabled, available, db_exists),
    }


def dash_warm_rpc_enabled() -> bool:
    dash = _dietcode_dashboard_cfg()
    return bool(dash.get("warm_rpc", True))


def dash_preload_agent_enabled() -> bool:
    dash = _dietcode_dashboard_cfg()
    return bool(dash.get("preload_agent_context", False))


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

    raw = run_broccolidb_rpc("dashboard_snapshot", timeout=45)
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

    raw = run_broccolidb_rpc(
        "proposal_action",
        {"proposalId": pid, "action": action_lc},
        timeout=30,
    )
    return _parse_runner_json(raw)
