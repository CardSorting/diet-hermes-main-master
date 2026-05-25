"""Tests for kanban ↔ BroccoliQ orchestration (production-hardened)."""
from __future__ import annotations

import json
import time

import pytest


def _seed_broccolidb(tmp_path):
    root = tmp_path / "broccolidb"
    (root / "core").mkdir(parents=True)
    (root / "infrastructure" / "kanban").mkdir(parents=True)
    (root / "package.json").write_text('{"name":"broccolidb"}')
    for name in ("hive_sync.ts", "hive_drift.ts", "hive_board_intel.ts"):
        sync = root / "infrastructure" / "kanban" / name
        if not sync.is_file():
            sync.write_text(f"// test stub\nconsole.log(JSON.stringify({{success:true}}));\n")
    return root


def test_kanban_broccolidb_tools_hidden_without_kanban_env(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    import tools.kanban_broccolidb_tools  # noqa: F401
    from tools.registry import invalidate_check_fn_cache, registry
    from toolsets import resolve_toolset

    invalidate_check_fn_cache()
    schema = registry.get_definitions(set(resolve_toolset("hermes-cli")), quiet=True)
    names = {s["function"].get("name") for s in schema if "function" in s}
    bdb = {n for n in names if n and n.startswith("kanban_broccolidb_")}
    assert bdb == set()


def test_kanban_broccolidb_worker_tools_visible(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_fake123")
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    import tools.kanban_broccolidb_tools  # noqa: F401
    from tools.registry import invalidate_check_fn_cache, registry
    from toolsets import resolve_toolset

    invalidate_check_fn_cache()
    schema = registry.get_definitions(set(resolve_toolset("hermes-cli")), quiet=True)
    names = {s["function"].get("name") for s in schema if "function" in s}
    bdb = {n for n in names if n and n.startswith("kanban_broccolidb_")}
    assert bdb == {
        "kanban_broccolidb_context",
        "kanban_broccolidb_sync",
        "kanban_broccolidb_record",
    }


def test_kanban_broccolidb_orchestrator_sees_board_intel(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("toolsets:\n  - kanban\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    import tools.kanban_broccolidb_tools  # noqa: F401
    from tools.registry import invalidate_check_fn_cache, registry
    from toolsets import resolve_toolset

    invalidate_check_fn_cache()
    schema = registry.get_definitions(set(resolve_toolset("hermes-cli")), quiet=True)
    names = {s["function"].get("name") for s in schema if "function" in s}
    assert "kanban_broccolidb_board_intel" in names
    assert "kanban_broccolidb_drift" in names


def test_validate_task_id_rejects_garbage():
    from tools.kanban_broccolidb_bridge import validate_task_id

    assert validate_task_id("t_abc123") == "t_abc123"
    assert validate_task_id("not-a-task") is None
    assert validate_task_id("") is None
    assert validate_task_id(None) is None


def test_sync_task_payload_skips_without_broccolidb(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from tools.kanban_broccolidb_bridge import sync_task_payload

    raw = sync_task_payload({"task_id": "t_abc123", "title": "x", "status": "ready"})
    data = json.loads(raw)
    assert data.get("skipped") is True


def test_debounce_skips_rapid_heartbeats(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "kanban:\n  broccolidb:\n    sync_debounce_seconds: 60\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    from tools.kanban_broccolidb_bridge import BroccolidbKanbanConfig, sync_task_payload

    # Reset config cache
    import tools.kanban_broccolidb_bridge as bridge
    bridge.invalidate_config_cache()
    bridge._config_cache = BroccolidbKanbanConfig.load()
    bridge._config_cache_at = time.monotonic()
    bridge._last_sync_at["t_deb001"] = time.monotonic()

    raw = sync_task_payload({
        "task_id": "t_deb001",
        "title": "x",
        "status": "running",
        "event": "heartbeat",
    })
    data = json.loads(raw)
    assert data.get("skipped") is True
    assert data.get("reason") == "debounced"


def test_schedule_sync_force_for_complete_event(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_force01")

    import tools.kanban_broccolidb_bridge as bridge
    from tools.kanban_broccolidb_bridge import schedule_sync

    calls = []

    def _fake_sync(task_id, *, event="sync", board=None, force=False):
        calls.append({"task_id": task_id, "event": event, "force": force})

    monkeypatch.setattr(bridge, "sync_kanban_task_id", _fake_sync)
    monkeypatch.setattr(bridge, "broccolidb_available", lambda: True)
    bridge._config_cache = bridge.BroccolidbKanbanConfig(
        enabled=True, auto_sync=True, async_sync=False
    )
    bridge._config_cache_at = time.monotonic()

    schedule_sync("t_force01", event="complete")
    assert calls and calls[0]["force"] is True


def test_task_row_payload_omits_invalid_task_id():
    from tools.kanban_broccolidb_bridge import task_row_to_payload, validate_task_id

    payload = task_row_to_payload({"id": "not-valid", "title": "x", "status": "ready"})
    assert payload["task_id"] is None
    assert validate_task_id(payload["task_id"]) is None


def test_bridge_payload_includes_joyzoning_forensics(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("JOYZONING_HABITAT_TASK", "550e8400-e29b-41d4-a716-446655440000")
    monkeypatch.setenv("JOYZONING_SCOPE_ID", "t_forensic1")
    import agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None
    from agent.joyzoning.convergence import ConvergenceState, transition_convergence
    transition_convergence(ConvergenceState.PATCHING, scope_id="t_forensic1", summary="wip", force=True)

    from tools.kanban_broccolidb_bridge import task_row_to_payload

    payload = task_row_to_payload({
        "id": "t_forensic1",
        "title": "Forensic",
        "status": "running",
    }, event="heartbeat")
    assert payload["habitat_task"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["joyzoning_scope"] == "t_forensic1"
    assert payload["convergence_state"] == "patching"


def test_bridge_task_row_to_payload():
    from tools.kanban_broccolidb_bridge import task_row_to_payload

    payload = task_row_to_payload({
        "id": "t_abc123",
        "title": "Do thing",
        "body": "details",
        "assignee": "worker",
        "status": "running",
        "priority": 2,
    }, event="start")
    assert payload["task_id"] == "t_abc123"
    assert payload["event"] == "start"
    assert payload["shard_id"] == "kanban"
    assert "create" in payload["signal_events"]


def test_resolve_broccolidb_root_walks_workspace_parent(monkeypatch, tmp_path):
    root = _seed_broccolidb(tmp_path)
    ws = tmp_path / "kanban-ws" / "scratch"
    ws.mkdir(parents=True)
    monkeypatch.chdir(ws)
    monkeypatch.delenv("HERMES_BROCCOLIDB_ROOT", raising=False)

    from tools.broccolidb_tools.runner import resolve_broccolidb_root

    assert resolve_broccolidb_root() == str(root.resolve())


def test_plugin_registers_hooks():
    from plugins.kanban_broccolidb import register

    class _Ctx:
        def __init__(self):
            self.hooks = {}

        def register_hook(self, name, fn):
            self.hooks[name] = fn

    ctx = _Ctx()
    register(ctx)
    assert "on_session_start" in ctx.hooks
    assert "post_tool_call" in ctx.hooks


def test_force_sync_bypasses_debounce(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text(
        "kanban:\n  broccolidb:\n    sync_debounce_seconds: 3600\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    import tools.kanban_broccolidb_bridge as bridge
    from tools.kanban_broccolidb_bridge import BroccolidbKanbanConfig, sync_kanban_task_id

    bridge._config_cache = BroccolidbKanbanConfig.load()
    bridge._config_cache_at = time.monotonic()
    bridge._last_sync_at["t_force01"] = time.monotonic()

    calls = []

    def _fake_sync(payload):
        calls.append(payload)
        return json.dumps({"success": True, "task_id": payload["task_id"]})

    monkeypatch.setattr(
        "tools.broccolidb_tools.runner.run_hive_sync",
        _fake_sync,
    )

    class _Task:
        id = "t_force01"
        title = "x"
        body = ""
        assignee = "w"
        status = "running"
        priority = 0
        result = None
        created_at = 1
        started_at = None
        completed_at = None
        tenant = None
        current_run_id = None

    class _Conn:
        def close(self):
            pass

    import hermes_cli.kanban_db as kb
    monkeypatch.setattr(kb, "connect", lambda **_: _Conn())
    monkeypatch.setattr(kb, "get_task", lambda _c, tid: _Task() if tid == "t_force01" else None)

    raw = sync_kanban_task_id("t_force01", event="context", force=True)
    data = json.loads(raw)
    assert data.get("success") is True
    assert data.get("skipped") is not True
    assert len(calls) == 1


def test_compute_drift_reports_missing(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    class _Task:
        def __init__(self, tid, status):
            self.id = tid
            self.status = status

    class _Conn:
        def close(self):
            pass

    import hermes_cli.kanban_db as kb
    monkeypatch.setattr(kb, "connect", lambda **_: _Conn())
    monkeypatch.setattr(
        kb,
        "list_tasks",
        lambda _c, limit=200: [_Task("t_abc123", "ready"), _Task("t_def456", "running")],
    )

    def _fake_drift(payload):
        assert payload["task_ids"] == ["t_abc123", "t_def456"]
        return json.dumps({
            "success": True,
            "rows": [{"task_id": "t_abc123", "status": "ready"}],
        })

    monkeypatch.setattr(
        "tools.broccolidb_tools.runner.run_hive_drift",
        _fake_drift,
    )

    from tools.kanban_broccolidb_bridge import compute_drift

    report = compute_drift(limit=10)
    assert report["success"] is True
    assert report["missing_in_hive"] == ["t_def456"]
    assert report["in_sync"] is False


def test_task_row_serializes_dict_result():
    from tools.kanban_broccolidb_bridge import task_row_to_payload

    payload = task_row_to_payload({
        "id": "t_abc123",
        "title": "x",
        "status": "done",
        "result": {"summary": "ok", "tests": 14},
    })
    assert payload["result"] == '{"summary": "ok", "tests": 14}'


def test_broccolidb_available_caches_requirements(monkeypatch, tmp_path):
    import tools.kanban_broccolidb_bridge as bridge

    bridge.invalidate_config_cache()
    calls = {"n": 0}

    def _check():
        calls["n"] += 1
        return True

    monkeypatch.setattr(
        "tools.broccolidb_tools.runner.check_requirements",
        _check,
    )
    monkeypatch.setattr(bridge, "broccolidb_enabled", lambda: True)

    assert bridge.broccolidb_available() is True
    assert bridge.broccolidb_available() is True
    assert calls["n"] == 1

    bridge.invalidate_config_cache()
    assert bridge.broccolidb_available() is True
    assert calls["n"] == 2


def test_maybe_auto_sync_record_forces_sync(monkeypatch, tmp_path):
    import tools.kanban_broccolidb_bridge as bridge

    scheduled = []

    monkeypatch.setattr(bridge, "broccolidb_available", lambda: True)
    monkeypatch.setattr(
        bridge,
        "schedule_sync",
        lambda tid, *, event="sync", board=None, force=False: scheduled.append(
            {"task_id": tid, "event": event, "force": force}
        ),
    )
    bridge._config_cache = bridge.BroccolidbKanbanConfig(
        enabled=True, auto_sync=True, async_sync=False
    )
    bridge._config_cache_at = time.monotonic()
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_rec001")

    bridge.maybe_auto_sync_tool("kanban_broccolidb_record", {"task_id": "t_rec001"})
    assert scheduled == [{"task_id": "t_rec001", "event": "record", "force": True}]


def test_kanban_spawn_injects_broccolidb_env(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    _seed_broccolidb(tmp_path)
    monkeypatch.chdir(tmp_path)

    from hermes_cli.kanban_db import _inject_broccolidb_env

    env = {}
    _inject_broccolidb_env(env)
    assert "HERMES_BROCCOLIDB_ROOT" in env
