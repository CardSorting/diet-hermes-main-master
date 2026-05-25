"""Production-hardening tests for JoyZoning integration."""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def jz_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    return home


def _reset_config():
    import agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None


def test_config_loads_tokens_from_yaml(jz_env):
    (jz_env / "config.yaml").write_text(
        "joyzoning:\n"
        "  enabled: true\n"
        "  control_plane:\n"
        "    url: http://127.0.0.1:9470\n"
        "    ingest_token: ingest-from-yaml\n"
        "    bridge_token: bridge-from-yaml\n"
    )
    _reset_config()
    from agent.joyzoning.config import get_joyzoning_config
    cfg = get_joyzoning_config()
    assert cfg.ingest_token == "ingest-from-yaml"
    assert cfg.habitat_bridge_token == "bridge-from-yaml"


def test_habitat_bridge_accepts_config_token(jz_env):
    (jz_env / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  control_plane:\n    bridge_token: cfg-bridge\n"
    )
    _reset_config()
    from agent.joyzoning.convergence import ConvergenceState, transition_convergence
    from agent.joyzoning.habitat_bridge import mark_operator_merge_accepted

    transition_convergence(
        ConvergenceState.READY_FOR_REVIEW,
        scope_id="t_cfgbridge",
        summary="review",
        force=True,
    )
    bad = mark_operator_merge_accepted("t_cfgbridge", token="wrong")
    assert bad["success"] is False
    ok = mark_operator_merge_accepted("t_cfgbridge", token="cfg-bridge")
    assert ok["success"] is True


def test_context_uses_scope_cluster(jz_env, monkeypatch):
    (jz_env / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    _reset_config()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_cluster1")
    monkeypatch.setenv("JOYZONING_HABITAT_TASK", "hab-guid-001")
    from agent.joyzoning.scope_registry import register_scope_aliases
    from agent.joyzoning.workflow import build_operational_context

    register_scope_aliases("t_cluster1", "hab-guid-001")
    ctx = build_operational_context()
    assert "hab-guid-001" in ctx["scope_cluster"]
    assert "kanban_complete_allowed" in ctx
    assert "active_mutation" in ctx


def test_convergence_status_reports_cluster(jz_env, monkeypatch):
    (jz_env / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    _reset_config()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_statclus")
    import tools.convergence_tools  # noqa: F401
    from tools.convergence_tools import convergence_status

    raw = convergence_status()
    data = json.loads(raw)
    assert data["scope_cluster"]
    assert "kanban_complete_allowed" in data


def test_sync_on_worker_start_always_registers_aliases(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_sync002")
    monkeypatch.setenv("JOYZONING_HABITAT_TASK", "hab-guid-002")
    _reset_config()

    import tools.kanban_broccolidb_bridge as bridge
    from agent.joyzoning.scope_registry import expand_scope_cluster
    from tools.kanban_broccolidb_bridge import sync_on_worker_start

    monkeypatch.setattr(bridge, "auto_sync_enabled", lambda: True)
    monkeypatch.setattr(bridge, "schedule_sync", lambda *a, **k: None)
    sync_on_worker_start()
    assert "hab-guid-002" in expand_scope_cluster("t_sync002")


def test_kanban_linkage_resolves_habitat_guid():
    from agent.joyzoning.kanban_linkage import (
        append_habitat_marker,
        habitat_idempotency_key,
        parse_idempotency_habitat,
        resolve_habitat_task_id,
    )

    guid = "550e8400-e29b-41d4-a716-446655440099"
    key = habitat_idempotency_key(guid)
    body = append_habitat_marker("Do the thing", guid)
    assert parse_idempotency_habitat(key) == guid.lower()
    assert resolve_habitat_task_id(idempotency_key=key) == guid.lower()
    assert resolve_habitat_task_id(body=body) == guid
    assert resolve_habitat_task_id(metadata={"habitat_task": guid}) == guid


def test_inject_joyzoning_env_from_idempotency(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    _reset_config()

    from agent.joyzoning.kanban_linkage import habitat_idempotency_key
    from hermes_cli import kanban_db as kb
    from hermes_cli.kanban_db import Task, _inject_joyzoning_env

    guid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    kb.init_db()
    with kb.connect() as conn:
        tid = kb.create_task(
            conn,
            title="linked",
            body="work item",
            idempotency_key=habitat_idempotency_key(guid),
        )
    task = Task(
        id=tid,
        title="linked",
        body="work item",
        assignee="default",
        status="ready",
        priority=0,
        created_by="test",
        created_at=0,
        started_at=None,
        completed_at=None,
        workspace_kind="path",
        workspace_path=str(tmp_path),
        claim_lock="lock",
        claim_expires=9999999999,
        tenant=None,
        idempotency_key=habitat_idempotency_key(guid),
    )
    env: dict = {}
    _inject_joyzoning_env(env, task, board="default")
    assert env["JOYZONING_SCOPE_ID"] == tid
    assert env["JOYZONING_HABITAT_TASK"] == guid.lower()
