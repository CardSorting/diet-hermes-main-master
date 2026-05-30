# -*- coding: utf-8 -*-
"""Tests for hermes_cli.dietcode_bridge facade."""
from __future__ import annotations


def test_inject_joyzoning_worker_env_pins_task(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    monkeypatch.setenv("HERMES_HOME", str(home))

    import plugins.dietcode.lib.agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None

    from hermes_cli.dietcode_bridge import inject_joyzoning_worker_env
    from hermes_cli.kanban_db import Task

    task = Task(
        id="t_bridge01",
        title="x",
        body="",
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
    inject_joyzoning_worker_env(env, task)
    assert env["HERMES_KANBAN_TASK"] == "t_bridge01"
    assert env["JOYZONING_SCOPE_ID"] == "t_bridge01"


def test_run_joyzoning_doctor_returns_checks():
    from hermes_cli.dietcode_bridge import run_joyzoning_doctor

    report = run_joyzoning_doctor(scope_id=None)
    assert "checks" in report
    assert isinstance(report["checks"], list)


def test_broccolidb_bundle_symlink_points_at_canonical_tree():
    from plugins.dietcode.audit import broccolidb_bundle_symlink_ok

    ok, detail = broccolidb_bundle_symlink_ok()
    assert ok, detail
