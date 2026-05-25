"""Kanban ↔ BroccoliQ first-class orchestration tools."""
from __future__ import annotations

import json

from tools.registry import registry, tool_error
from tools.kanban_tools import (
    _check_kanban_mode,
    _check_kanban_orchestrator_mode,
    _connect,
    _default_task_id,
    _enforce_worker_task_ownership,
    _require_orchestrator_tool,
)
from tools.kanban_broccolidb_bridge import (
    broccolidb_available,
    compute_drift,
    sync_kanban_task_id,
    validate_task_id,
)
from tools.broccolidb_tools.runner import (
    resolve_broccolidb_root,
    run_agent_context_script,
    run_hive_board_intel,
)


def _check_kanban_broccolidb_mode() -> bool:
    return _check_kanban_mode() and broccolidb_available()


def _check_kanban_broccolidb_orchestrator_mode() -> bool:
    return _check_kanban_orchestrator_mode() and broccolidb_available()


def _parse_sync_result(raw: str, *, context: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return tool_error(f"{context}: invalid JSON response")
    if not data.get("success") and not data.get("skipped"):
        err = data.get("error") or data.get("reason") or "unknown error"
        return tool_error(f"{context}: {err}")
    return raw


def kanban_broccolidb_context(task_id: str = None, sync_first: bool = True) -> str:
    tid = _default_task_id(task_id)
    if not validate_task_id(tid):
        return tool_error("task_id is required (or set HERMES_KANBAN_TASK in the env)")
    guard = _enforce_worker_task_ownership(tid)
    if guard:
        return guard

    if sync_first:
        sync_raw = sync_kanban_task_id(tid, event="context", force=True)
        parsed = json.loads(sync_raw)
        if not parsed.get("success") and not parsed.get("skipped"):
            return tool_error(f"pre-sync failed: {parsed.get('error', sync_raw)}")

    body = f"""
  const ctx = await context.getTaskContext({json.dumps(tid)});
  console.log(JSON.stringify({{
    success: true,
    taskId: {json.dumps(tid)},
    broccolidb_root: {json.dumps(resolve_broccolidb_root())},
    context: ctx,
  }}));
"""
    return run_agent_context_script(body)


def kanban_broccolidb_sync(task_id: str = None, event: str = "sync") -> str:
    tid = _default_task_id(task_id)
    if not validate_task_id(tid):
        return tool_error("task_id is required (or set HERMES_KANBAN_TASK in the env)")
    guard = _enforce_worker_task_ownership(tid)
    if guard:
        return guard
    raw = sync_kanban_task_id(tid, event=event or "sync", force=True)
    return _parse_sync_result(raw, context="kanban_broccolidb_sync")


def kanban_broccolidb_record(
    summary: str,
    task_id: str = None,
    tags: str = None,
    kb_type: str = "kanban_handoff",
) -> str:
    tid = _default_task_id(task_id)
    if not validate_task_id(tid):
        return tool_error("task_id is required (or set HERMES_KANBAN_TASK in the env)")
    guard = _enforce_worker_task_ownership(tid)
    if guard:
        return guard
    if not summary or not summary.strip():
        return tool_error("summary is required")

    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    tag_list.extend(["kanban", tid])
    kb_key = f"kanban_{tid}_{kb_type}"
    body = f"""
  const tags = {json.dumps(tag_list)};
  const kbId = await context.addKnowledge(
    {json.dumps(kb_key)},
    {json.dumps(kb_type)},
    {json.dumps(summary.strip())},
    {{ tags }}
  );
  console.log(JSON.stringify({{ success: true, kbId, taskId: {json.dumps(tid)} }}));
"""
    result = run_agent_context_script(body)
    sync_kanban_task_id(tid, event="record", force=True)
    return result


def kanban_broccolidb_board_intel(board: str = None, limit: int = 25) -> str:
    guard = _require_orchestrator_tool("kanban_broccolidb_board_intel")
    if guard:
        return guard

    lim = max(1, min(int(limit or 25), 100))
    try:
        kb_mod, conn = _connect(board=board)
        try:
            kb_mod.recompute_ready(conn)
            tasks = kb_mod.list_tasks(conn, limit=lim)
            by_status: dict[str, int] = {}
            for t in tasks:
                by_status[t.status] = by_status.get(t.status, 0) + 1
            board_summary = {
                "task_count": len(tasks),
                "by_status": by_status,
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status,
                        "assignee": t.assignee,
                        "priority": t.priority,
                    }
                    for t in tasks
                ],
            }
        finally:
            conn.close()
    except Exception as exc:
        return tool_error(f"kanban board read failed: {exc}")

    from tools.kanban_broccolidb_bridge import get_config
    cfg = get_config()
    raw = run_hive_board_intel({
        "shard_id": cfg.shard_id,
        "queue_limit": max(lim * 10, 100),
        "hive_limit": max(lim * 10, 100),
    })
    try:
        hive_metrics = json.loads(raw)
    except json.JSONDecodeError:
        hive_metrics = {"parse_error": raw[:500]}

    drift = compute_drift(board=board, limit=lim)

    return json.dumps({
        "success": True,
        "board": board_summary,
        "broccoliq": hive_metrics,
        "drift": drift,
    })


def kanban_broccolidb_drift(board: str = None, limit: int = 200) -> str:
    guard = _require_orchestrator_tool("kanban_broccolidb_drift")
    if guard:
        return guard
    return json.dumps(compute_drift(board=board, limit=limit))


# ─── Schemas ───

registry.register(
    name="kanban_broccolidb_context",
    toolset="kanban",
    schema={
        "name": "kanban_broccolidb_context",
        "description": (
            "Load BroccoliDB epistemic context for a kanban task. Call after kanban_show(). "
            "Syncs kanban state to hive_tasks first unless sync_first=false."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "sync_first": {"type": "boolean", "default": True},
            },
        },
    },
    handler=lambda args, **kw: kanban_broccolidb_context(
        task_id=args.get("task_id"),
        sync_first=args.get("sync_first", True),
    ),
    check_fn=_check_kanban_broccolidb_mode,
    emoji="🧠",
)

registry.register(
    name="kanban_broccolidb_sync",
    toolset="kanban",
    schema={
        "name": "kanban_broccolidb_sync",
        "description": "Force-sync a kanban task into BroccoliQ hive_tasks (bypasses debounce).",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "event": {
                    "type": "string",
                    "enum": ["sync", "start", "heartbeat", "complete", "block", "create", "context", "record"],
                },
            },
        },
    },
    handler=lambda args, **kw: kanban_broccolidb_sync(
        task_id=args.get("task_id"),
        event=args.get("event", "sync"),
    ),
    check_fn=_check_kanban_broccolidb_mode,
    emoji="🔄",
)

registry.register(
    name="kanban_broccolidb_record",
    toolset="kanban",
    schema={
        "name": "kanban_broccolidb_record",
        "description": (
            "Record a durable handoff/decision in BroccoliDB before kanban_complete. "
            "Auto-syncs hive state after write."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "task_id": {"type": "string"},
                "tags": {"type": "string"},
                "kb_type": {"type": "string", "default": "kanban_handoff"},
            },
            "required": ["summary"],
        },
    },
    handler=lambda args, **kw: kanban_broccolidb_record(
        summary=args.get("summary", ""),
        task_id=args.get("task_id"),
        tags=args.get("tags"),
        kb_type=args.get("kb_type", "kanban_handoff"),
    ),
    check_fn=_check_kanban_broccolidb_mode,
    emoji="📓",
)

registry.register(
    name="kanban_broccolidb_board_intel",
    toolset="kanban",
    schema={
        "name": "kanban_broccolidb_board_intel",
        "description": (
            "Orchestrator-only: kanban board snapshot + BroccoliQ metrics + drift report."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "board": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
    },
    handler=lambda args, **kw: kanban_broccolidb_board_intel(
        board=args.get("board"),
        limit=args.get("limit", 25),
    ),
    check_fn=_check_kanban_broccolidb_orchestrator_mode,
    emoji="📊",
)

registry.register(
    name="kanban_broccolidb_drift",
    toolset="kanban",
    schema={
        "name": "kanban_broccolidb_drift",
        "description": (
            "Orchestrator-only: detect kanban vs hive_tasks mismatches (missing rows, status drift)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "board": {"type": "string"},
                "limit": {"type": "integer", "default": 200},
            },
        },
    },
    handler=lambda args, **kw: kanban_broccolidb_drift(
        board=args.get("board"),
        limit=args.get("limit", 200),
    ),
    check_fn=_check_kanban_broccolidb_orchestrator_mode,
    emoji="🔍",
)
