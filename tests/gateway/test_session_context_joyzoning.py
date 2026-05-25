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
    )
    try:
        assert get_session_env("JOYZONING_HABITAT_TASK") == "hab-123"
        assert get_session_env("JOYZONING_SCOPE_ID") == "t_abc123"
        assert get_session_env("HERMES_KANBAN_TASK") == "t_abc123"
    finally:
        clear_joyzoning_run_vars(tokens)

    assert get_session_env("JOYZONING_HABITAT_TASK") == ""
