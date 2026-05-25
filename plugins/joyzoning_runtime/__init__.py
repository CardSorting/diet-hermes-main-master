# -*- coding: utf-8 -*-
"""JoyZoning runtime plugin — execution journal, convergence gates, habitat event stream."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _on_session_start(*, session_id: str = "", **_: Any) -> None:
    try:
        from agent.joyzoning.config import get_joyzoning_config, resolve_scope_id
        from agent.joyzoning.habitat_events import emit_habitat_event
        if not get_joyzoning_config().enabled:
            return
        from agent.joyzoning.config import _read_scope_env

        kanban_task = _read_scope_env("HERMES_KANBAN_TASK")
        habitat_task = _read_scope_env("JOYZONING_HABITAT_TASK")
        if kanban_task and habitat_task:
            from agent.joyzoning.scope_registry import register_scope_aliases
            register_scope_aliases(kanban_task, habitat_task)

        emit_habitat_event(
            "session.start",
            scope_id=resolve_scope_id(),
            session_id=session_id or _read_scope_env("HERMES_SESSION_ID"),
            payload={
                "jsdp_role": get_joyzoning_config().jsdp_role,
                "kanban_task": kanban_task or None,
                "habitat_task": habitat_task or None,
            },
        )
    except Exception as exc:
        logger.warning("joyzoning_runtime on_session_start: %s", exc)


def _on_session_end(*, session_id: str = "", **_: Any) -> None:
    try:
        from agent.joyzoning.config import _read_scope_env, get_joyzoning_config, resolve_scope_id
        from agent.joyzoning.habitat_events import emit_habitat_event
        if not get_joyzoning_config().enabled:
            return
        emit_habitat_event(
            "session.end",
            scope_id=resolve_scope_id(),
            session_id=session_id or _read_scope_env("HERMES_SESSION_ID"),
        )
    except Exception as exc:
        logger.warning("joyzoning_runtime on_session_end: %s", exc)


def _pre_tool_call(*, tool_name: str = "", args: Any = None, **_: Any) -> dict[str, str] | None:
    """Convergence gate — block kanban_complete until review/convergence (runtime authority)."""
    from agent.joyzoning.convergence_gate import pre_tool_call_block
    return pre_tool_call_block(tool_name=tool_name, args=args, fail_closed=True)


def _post_tool_call(
    *,
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    task_id: str = "",
    duration_ms: int = 0,
    **_: Any,
) -> None:
    try:
        from agent.joyzoning.config import get_joyzoning_config, resolve_scope_id
        from agent.joyzoning.habitat_events import emit_habitat_event
        if not get_joyzoning_config().enabled:
            return
        parsed = args if isinstance(args, dict) else {}
        scope = resolve_scope_id(parsed.get("task_id"))
        emit_habitat_event(
            "tool.complete",
            scope_id=scope,
            payload={
                "tool": tool_name,
                "task_id": task_id,
                "duration_ms": duration_ms,
                "success": isinstance(result, str) and "error" not in result[:200].lower(),
            },
        )
    except Exception as exc:
        logger.debug("joyzoning_runtime post_tool_call: %s", exc)


def register(ctx) -> None:
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("post_tool_call", _post_tool_call)
