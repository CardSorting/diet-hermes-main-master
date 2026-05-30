"""Tests for autonomous jsdp tool."""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _reset_config_cache():
    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    from hermes_cli import config as hermes_config_mod

    cfg_mod._config_cache = None
    hermes_config_mod._LOAD_CONFIG_CACHE.clear()
    hermes_config_mod._RAW_CONFIG_CACHE.clear()
    yield
    cfg_mod._config_cache = None
    hermes_config_mod._LOAD_CONFIG_CACHE.clear()
    hermes_config_mod._RAW_CONFIG_CACHE.clear()


@pytest.fixture
def ws_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("DIETCODE_HOME", str(home))
    ws = tmp_path / "workspace"
    ws.mkdir()
    monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", str(ws))
    monkeypatch.chdir(ws)
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.joyzoning.jsdp_autonomous.probe_jz_cli",
        lambda: "/fake/jz",
    )
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.joyzoning.jsdp_harness_client.resolve_jz_executable",
        lambda: "/fake/jz",
    )
    yield ws


def test_jsdp_registered(ws_env):
    import plugins.dietcode.lib.tools.jsdp_harness_tools  # noqa: F401
    from tools.registry import registry

    assert "jsdp" in registry.get_tool_names_for_toolset("joyzoning")


def test_available_with_kanban_task(ws_env, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_auto001")
    from plugins.dietcode.lib.tools.jsdp_harness_tools import _jsdp_available

    assert _jsdp_available() is True


def test_status_without_harness(ws_env, monkeypatch):
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.joyzoning.jsdp_harness_client.resolve_jz_executable",
        lambda: "/fake/jz",
    )
    import plugins.dietcode.lib.tools.jsdp_harness_tools  # noqa: F401
    from plugins.dietcode.lib.tools.jsdp_harness_tools import jsdp

    raw = jsdp(action="guide")
    data = json.loads(raw)
    assert data["success"] is True
    assert data.get("phase") in ("start", "plan")
    assert "start" in (data.get("agent_next_call") or "")


def test_prepare_bootstrap_chain(ws_env, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(subcommand, *, workspace=None, timeout=120.0):
        calls.append(subcommand)
        if subcommand[0] == "init":
            (ws_env / ".jsdp").mkdir(exist_ok=True)
            (ws_env / ".jsdp" / "run.json").write_text('{"id":"r1","nodes":{}}')
            return {"ok": True}
        if subcommand[0] == "analyze":
            return {"ok": True}
        if subcommand[:2] == ["horizon", "export"]:
            return {"horizonContextPath": str(ws_env / ".jsdp/state/ctx.json")}
        if subcommand[:2] == ["horizon", "prompt"]:
            p = ws_env / ".jsdp/prompts/p.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# plan\n")
            return {"promptPath": str(p)}
        return {"ok": True}

    monkeypatch.setattr("plugins.dietcode.lib.agent.joyzoning.jsdp_harness_client.run_jsdp", fake_run)
    monkeypatch.setattr("plugins.dietcode.lib.agent.joyzoning.jsdp_autonomous.run_jsdp", fake_run)
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.joyzoning.jsdp_harness_client.resolve_jz_executable",
        lambda: "/fake/jz",
    )
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.joyzoning.jsdp_autonomous.probe_jz_cli",
        lambda: "/fake/jz",
    )

    import plugins.dietcode.lib.tools.jsdp_harness_tools  # noqa: F401
    from plugins.dietcode.lib.tools.jsdp_harness_tools import jsdp

    raw = jsdp(action="start", nodes=3)
    data = json.loads(raw)
    assert data.get("success") or data.get("bootstrap", {}).get("success"), raw
    assert data["bootstrap"]["initialized"] is True
    assert "planning_prompt_text" in data
    assert "init" in [c[0] for c in calls]


def test_commit_requires_json(ws_env, monkeypatch):
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.joyzoning.jsdp_harness_client.resolve_jz_executable",
        lambda: "/fake/jz",
    )
    import plugins.dietcode.lib.tools.jsdp_harness_tools  # noqa: F401
    from plugins.dietcode.lib.tools.jsdp_harness_tools import jsdp

    raw = jsdp(action="apply")
    assert "error" in raw.lower()


def test_legacy_export_alias_maps_to_start(ws_env, monkeypatch):
    """Legacy action names route to start/apply/advance/guide without breaking other tests."""
    from plugins.dietcode.lib.tools.jsdp_harness_tools import _LEGACY_MAP

    assert _LEGACY_MAP["export"] == "start"
    assert _LEGACY_MAP["commit"] == "apply"
    assert _LEGACY_MAP["status"] == "guide"
