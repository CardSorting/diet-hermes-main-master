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
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None


def test_config_loads_from_yaml(jz_env):
    (jz_env / "config.yaml").write_text(
        "joyzoning:\n"
        "  enabled: true\n"
        "  execution_journal: true\n"
        "  jsdp:\n"
        "    enabled: true\n"
        "    role: implementer\n"
    )
    _reset_config()
    from plugins.dietcode.lib.agent.joyzoning.config import get_joyzoning_config
    cfg = get_joyzoning_config()
    assert cfg.enabled is True
    assert cfg.execution_journal is True
    assert cfg.jsdp_enabled is True
    assert cfg.jsdp_role == "implementer"


def test_context_uses_scope_cluster(jz_env, monkeypatch):
    (jz_env / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    _reset_config()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_cluster1")
    monkeypatch.setenv("HERMES_SESSION_ID", "sess-cluster-1")
    from plugins.dietcode.lib.agent.joyzoning.scope_registry import register_scope_aliases
    from plugins.dietcode.lib.agent.joyzoning.workflow import build_operational_context

    register_scope_aliases("t_cluster1", "sess-cluster-1")
    ctx = build_operational_context()
    assert "sess-cluster-1" in ctx["scope_cluster"]
    assert "kanban_complete_allowed" in ctx
    assert "active_mutation" in ctx


def test_convergence_status_reports_cluster(jz_env, monkeypatch):
    (jz_env / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    _reset_config()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_statclus")
    import plugins.dietcode.lib.tools.convergence_tools  # noqa: F401
    from plugins.dietcode.lib.tools.convergence_tools import convergence_status

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
    monkeypatch.setenv("HERMES_SESSION_ID", "sess-sync-002")
    _reset_config()

    import plugins.dietcode.lib.tools.kanban_broccolidb_bridge as bridge
    from plugins.dietcode.lib.agent.joyzoning.scope_registry import expand_scope_cluster
    from plugins.dietcode.lib.tools.kanban_broccolidb_bridge import sync_on_worker_start

    monkeypatch.setattr(bridge, "auto_sync_enabled", lambda: True)
    monkeypatch.setattr(bridge, "schedule_sync", lambda *a, **k: None)
    sync_on_worker_start()
    assert "sess-sync-002" in expand_scope_cluster("t_sync002")


def test_inject_joyzoning_env_pins_kanban_scope(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    _reset_config()

    from hermes_cli import kanban_db as kb
    from hermes_cli.kanban_db import Task, _inject_joyzoning_env

    kb.init_db()
    with kb.connect() as conn:
        tid = kb.create_task(
            conn,
            title="worker task",
            body="work item",
        )
    task = Task(
        id=tid,
        title="worker task",
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
        idempotency_key=None,
    )
    env: dict = {}
    _inject_joyzoning_env(env, task, board="default")
    assert env["JOYZONING_SCOPE_ID"] == tid
    assert env["HERMES_KANBAN_TASK"] == tid
