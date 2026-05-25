"""JoyZoning scope contextvars on API runs."""
from __future__ import annotations

from gateway.session_context import (
    clear_joyzoning_run_vars,
    get_session_env,
    set_joyzoning_run_vars,
)


def test_joyzoning_run_vars_are_task_local():
    tokens = set_joyzoning_run_vars(
        habitat_task="hab-123",
        scope_id="t_abc123",
        kanban_task="t_abc123",
        kanban_board="my-board",
        kanban_run_id="run-99",
        tenant="acme",
        session_id="sess-ctx-1",
    )
    try:
        assert get_session_env("JOYZONING_HABITAT_TASK") == "hab-123"
        assert get_session_env("JOYZONING_SCOPE_ID") == "t_abc123"
        assert get_session_env("HERMES_KANBAN_TASK") == "t_abc123"
        assert get_session_env("HERMES_KANBAN_BOARD") == "my-board"
        assert get_session_env("HERMES_KANBAN_RUN_ID") == "run-99"
        assert get_session_env("HERMES_TENANT") == "acme"
        assert get_session_env("HERMES_SESSION_ID") == "sess-ctx-1"
    finally:
        clear_joyzoning_run_vars(tokens)

    assert get_session_env("JOYZONING_HABITAT_TASK") == ""
    assert get_session_env("HERMES_KANBAN_BOARD") == ""


def test_scope_env_visible_to_bridge_helper(monkeypatch):
    """Bridge _scope_env() must read the same contextvars as get_session_env."""
    monkeypatch.setenv("HERMES_KANBAN_TASK", "from-env-should-not-win")
    tokens = set_joyzoning_run_vars(kanban_task="t_ctxbridge")
    try:
        from tools.kanban_broccolidb_bridge import _scope_env
        assert _scope_env("HERMES_KANBAN_TASK") == "t_ctxbridge"
    finally:
        clear_joyzoning_run_vars(tokens)
