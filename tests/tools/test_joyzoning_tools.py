"""Tests for JoyZoning first-class primitive tool."""
from __future__ import annotations

import json

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
    monkeypatch.setenv("DIETCODE_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    import plugins.dietcode.lib.agent.joyzoning.journal as journal_mod

    cfg_mod._config_cache = None
    journal_mod._journal = None
    yield home
    cfg_mod._config_cache = None
    journal_mod._journal = None


def test_joyzoning_primitive_registered(jz_env):
    import plugins.dietcode.lib.tools.convergence_tools  # noqa: F401
    import plugins.dietcode.lib.tools.joyzoning_tools  # noqa: F401
    from tools.registry import registry

    names = registry.get_tool_names_for_toolset("joyzoning")
    assert "joyzoning" in names
    assert "mutation_record_patch" in names


def test_joyzoning_context_action(jz_env, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_ctxprim1")
    import plugins.dietcode.lib.tools.joyzoning_tools  # noqa: F401
    from plugins.dietcode.lib.tools.joyzoning_tools import joyzoning

    raw = joyzoning(action="context")
    data = json.loads(raw)
    assert data["success"] is True
    assert data["scope_id"] == "t_ctxprim1"
    assert "next_actions" in data
    assert data["authority"]["execution"] == "hermes"


def test_joyzoning_begin_and_patch(jz_env, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_prim002")
    import plugins.dietcode.lib.tools.joyzoning_tools  # noqa: F401
    from plugins.dietcode.lib.tools.joyzoning_tools import joyzoning

    started = json.loads(joyzoning(action="begin", goal="test feature"))
    assert started["success"] is True
    mid = started["mutation_id"]

    patched = json.loads(joyzoning(action="patch", mutation_id=mid, summary="edited files"))
    assert patched["success"] is True


def test_joyzoning_doctor(jz_env):
    import plugins.dietcode.lib.tools.joyzoning_tools  # noqa: F401
    from plugins.dietcode.lib.tools.joyzoning_tools import joyzoning

    raw = joyzoning(action="doctor")
    data = json.loads(raw)
    assert "checks" in data
    assert any(c["name"] == "journal_db" for c in data["checks"])


def test_joyzoning_doctor_action(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: true\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("DIETCODE_HOME", str(home))
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    import plugins.dietcode.lib.agent.joyzoning.journal as journal_mod

    cfg_mod._config_cache = None
    journal_mod._journal = None
    import plugins.dietcode.lib.tools.joyzoning_tools  # noqa: F401
    from plugins.dietcode.lib.tools.joyzoning_tools import joyzoning

    raw = joyzoning(action="doctor")
    data = json.loads(raw)
    assert data["success"] is True
    assert any(c["name"] == "joyzoning.enabled" for c in data["checks"])


def test_inject_joyzoning_env_sets_scope(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: true\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("DIETCODE_HOME", str(home))
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from hermes_cli.kanban_db import Task, _inject_joyzoning_env

    task = Task(
        id="t_inj001",
        title="t",
        body="",
        assignee="default",
        status="running",
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
        branch_name="joyzoning/card-t_inj001",
    )
    env: dict = {}
    _inject_joyzoning_env(env, task, board="default")
    assert env["JOYZONING_SCOPE_ID"] == "t_inj001"
    assert env["HERMES_KANBAN_TASK"] == "t_inj001"
