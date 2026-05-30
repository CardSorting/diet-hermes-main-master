"""Tests for JoyZoning native runtime (Hermes authority, not habitat)."""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture(autouse=True)
def _reset_joyzoning_singletons():
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    import plugins.dietcode.lib.agent.joyzoning.journal as journal_mod
    from hermes_cli import config as hermes_config_mod

    cfg_mod._config_cache = None
    journal_mod._journal = None
    hermes_config_mod._LOAD_CONFIG_CACHE.clear()
    hermes_config_mod._RAW_CONFIG_CACHE.clear()
    yield
    cfg_mod._config_cache = None
    journal_mod._journal = None
    hermes_config_mod._LOAD_CONFIG_CACHE.clear()
    hermes_config_mod._RAW_CONFIG_CACHE.clear()


@pytest.fixture
def jz_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: true\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("DIETCODE_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    import plugins.dietcode.lib.agent.joyzoning.journal as journal_mod

    cfg_mod._config_cache = None
    journal_mod._journal = None
    yield home
    cfg_mod._config_cache = None
    journal_mod._journal = None


def test_convergence_transition_and_journal(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.convergence import ConvergenceState, get_convergence_state, transition_convergence
    from plugins.dietcode.lib.agent.joyzoning.journal import get_journal

    assert get_convergence_state("t_testscope1") == ConvergenceState.IDLE

    r1 = transition_convergence(ConvergenceState.PROPOSED, scope_id="t_testscope1", summary="plan")
    assert r1["success"] is True

    r1b = transition_convergence(ConvergenceState.PATCHING, scope_id="t_testscope1", summary="patch")
    assert r1b["success"] is True

    r2 = transition_convergence(ConvergenceState.READY_FOR_REVIEW, scope_id="t_testscope1", summary="review me")
    assert r2["success"] is True
    assert get_convergence_state("t_testscope1") == ConvergenceState.READY_FOR_REVIEW

    record = get_journal().get_convergence("t_testscope1")
    assert record is not None
    assert record["state"] == "ready_for_review"


def test_invalid_transition_rejected(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.convergence import ConvergenceState, transition_convergence

    r = transition_convergence(ConvergenceState.CONVERGED, scope_id="t_badtrans1", summary="skip")
    assert r["success"] is False


def test_require_review_blocks_complete(jz_env, monkeypatch):
    home = jz_env
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  convergence:\n    review_before_complete: true\n"
    )
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from plugins.dietcode.lib.agent.joyzoning.convergence import ConvergenceState, transition_convergence
    from plugins.dietcode.lib.agent.joyzoning.convergence import require_review_before_complete

    transition_convergence(ConvergenceState.PROPOSED, scope_id="t_block001", summary="x", force=True)
    msg = require_review_before_complete("t_block001")
    assert msg is not None
    assert "Convergence gate" in msg


def test_jsdp_handoff_validation(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.jsdp_protocol import validate_handoff_sections

    bad = validate_handoff_sections("just some text")
    assert bad["success"] is False
    assert len(bad["missing_sections"]) == 7

    good_text = "\n".join(
        f"## {s}\ncontent for {s}\n" for s in bad["required_sections"]
    )
    good = validate_handoff_sections(good_text)
    assert good["success"] is True


def test_mutation_lifecycle(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.mutation_lifecycle import begin_mutation, record_verification, request_review
    from plugins.dietcode.lib.agent.joyzoning.convergence import get_convergence_state, ConvergenceState

    started = begin_mutation("implement feature X", scope_id="t_mut001")
    assert started["success"] is True
    mid = started["mutation_id"]

    verified = record_verification(mid, report="tests pass", passed=True, scope_id="t_mut001")
    assert verified["success"] is True

    review = request_review("ready for operator", scope_id="t_mut001")
    assert review["success"] is True
    assert get_convergence_state("t_mut001") == ConvergenceState.READY_FOR_REVIEW


def test_habitat_events_tail_tool(jz_env, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_evt001")
    import plugins.dietcode.lib.tools.convergence_tools  # noqa: F401
    from plugins.dietcode.lib.tools.convergence_tools import habitat_events_tail

    from plugins.dietcode.lib.agent.joyzoning.habitat_events import emit_habitat_event
    emit_habitat_event("tool.complete", scope_id="t_evt001", payload={"tool": "test"})

    raw = habitat_events_tail(limit=10)
    data = json.loads(raw)
    assert data["success"] is True
    assert len(data["events"]) >= 1
    assert data["events"][0]["source"] == "hermes-runtime"


def test_register_from_scope_env_links_cluster(jz_env, monkeypatch):
    from plugins.dietcode.lib.agent.joyzoning.scope_registry import expand_scope_cluster, register_from_scope_env

    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_alias001")
    monkeypatch.setenv("JOYZONING_SCOPE_ID", "sess-alias-001")
    register_from_scope_env()
    cluster = expand_scope_cluster("t_alias001")
    assert "sess-alias-001" in cluster


def test_session_end_uses_scope_context(jz_env, monkeypatch):
    home = jz_env
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: true\n"
    )
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from gateway.session_context import clear_joyzoning_run_vars, set_joyzoning_run_vars
    from plugins.dietcode.public import _on_session_end

    tokens = set_joyzoning_run_vars(
        scope_id="t_end0001",
        kanban_task="t_end0001",
    )
    monkeypatch.setenv("HERMES_SESSION_ID", "should-not-win")
    try:
        _on_session_end()
        from plugins.dietcode.lib.agent.joyzoning.journal import get_journal
        end_rows = get_journal().list_events(limit=20, event_types=["session.end"])
        assert end_rows, "expected session.end journal row"
        assert end_rows[-1].get("scope_id") == "t_end0001"
    finally:
        clear_joyzoning_run_vars(tokens)


def test_habitat_events_session_id_from_contextvar(jz_env, monkeypatch):
    home = jz_env
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: true\n"
    )
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from gateway import session_context as sc
    from plugins.dietcode.lib.agent.joyzoning.habitat_events import emit_habitat_event

    monkeypatch.setenv("HERMES_SESSION_ID", "sess-from-env-should-lose")
    token = sc._SESSION_ID.set("sess-from-ctx")
    try:
        emit_habitat_event("tool.complete", scope_id="t_ctxsess1", payload={"tool": "x"})
        from plugins.dietcode.lib.agent.joyzoning.journal import get_journal
        rows = get_journal().list_events(limit=5, event_types=["tool.complete"])
        assert rows[-1]["session_id"] == "sess-from-ctx"
    finally:
        sc._SESSION_ID.reset(token)


def test_joyzoning_runtime_plugin_registers(jz_env):
    from plugins.dietcode.hooks import register_all_hooks

    class _Ctx:
        def __init__(self):
            self.hooks = {}

        def register_hook(self, name, fn):
            self.hooks[name] = fn

    ctx = _Ctx()
    register_all_hooks(ctx)
    assert "pre_tool_call" in ctx.hooks
    assert "on_session_start" in ctx.hooks


def test_pre_tool_call_blocks_kanban_complete(jz_env, monkeypatch):
    home = jz_env
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  convergence:\n    review_before_complete: true\n"
    )
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from plugins.dietcode.lib.agent.joyzoning.convergence import ConvergenceState, transition_convergence
    from plugins.dietcode.public import _pre_tool_call

    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_precmp01")
    transition_convergence(ConvergenceState.PATCHING, scope_id="t_precmp01", summary="wip", force=True)

    block = _pre_tool_call(tool_name="kanban_complete", args={"task_id": "t_precmp01"})
    assert isinstance(block, dict)
    assert block.get("action") == "block"
    assert "Convergence gate" in block.get("message", "")


def test_pre_tool_call_block_message_via_plugin_manager(jz_env, monkeypatch):
    home = jz_env
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  convergence:\n    review_before_complete: true\n"
    )
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from plugins.dietcode.lib.agent.joyzoning.convergence import ConvergenceState, transition_convergence
    from hermes_cli.plugins import discover_plugins, get_pre_tool_call_block_message

    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_hook001")
    transition_convergence(ConvergenceState.PATCHING, scope_id="t_hook001", summary="wip", force=True)

    discover_plugins(force=True)

    msg = get_pre_tool_call_block_message(
        tool_name="kanban_complete",
        args={"task_id": "t_hook001"},
    )
    assert msg is not None
    assert "Convergence gate" in msg


def test_request_review_requires_verify(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.mutation_lifecycle import begin_mutation, request_review

    begin_mutation("skip verify", scope_id="t_noverify")
    blocked = request_review("too early", scope_id="t_noverify")
    assert blocked["success"] is False
    assert blocked["error"] == "verify_required"


def test_scope_registry_links_aliases(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.scope_registry import expand_scope_cluster, register_scope_aliases

    register_scope_aliases("t_abc123", "sess-linked-001")
    cluster = expand_scope_cluster("t_abc123")
    assert "sess-linked-001" in cluster


def test_convergence_mark_converged_local(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.convergence import ConvergenceState, get_convergence_state, transition_convergence
    import plugins.dietcode.lib.tools.convergence_tools  # noqa: F401
    from plugins.dietcode.lib.tools.convergence_tools import convergence_mark_converged

    transition_convergence(ConvergenceState.READY_FOR_REVIEW, scope_id="t_selfauth", summary="review", force=True)
    raw = convergence_mark_converged(scope_id="t_selfauth")
    data = json.loads(raw)
    assert data.get("success") is True
    assert get_convergence_state("t_selfauth") == ConvergenceState.CONVERGED


def test_journal_integrity_check(jz_env):
    from plugins.dietcode.lib.agent.joyzoning.journal import get_journal

    check = get_journal().integrity_check()
    assert check["success"] is True


def test_broccolidb_sync_registers_scope_aliases_on_start(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: true\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_sync001")
    monkeypatch.setenv("JOYZONING_SCOPE_ID", "t_sync001")
    monkeypatch.setenv("HERMES_SESSION_ID", "sess-sync-001")
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    import plugins.dietcode.lib.tools.kanban_broccolidb_bridge as bridge
    from plugins.dietcode.lib.agent.joyzoning.scope_registry import expand_scope_cluster
    from plugins.dietcode.lib.tools.kanban_broccolidb_bridge import sync_on_worker_start

    monkeypatch.setattr(bridge, "auto_sync_enabled", lambda: True)
    monkeypatch.setattr(bridge, "schedule_sync", lambda *a, **k: None)
    sync_on_worker_start()
    cluster = expand_scope_cluster("t_sync001")
    assert "sess-sync-001" in cluster
