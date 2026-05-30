# -*- coding: utf-8 -*-
"""Hook wrapper fail-closed behavior when enforcement is enabled."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_pre_tool_call_wrapper_blocks_when_handler_raises_and_joyzoning_enabled():
    from plugins.dietcode.hooks import _run_pre_tool_call

    cfg = MagicMock()
    cfg.enabled = True

    def _boom(**_kwargs):
        raise RuntimeError("journal offline")

    wrapped = _run_pre_tool_call((_boom,))
    with patch(
        "plugins.dietcode.lib.agent.joyzoning.config.get_joyzoning_config",
        return_value=cfg,
    ):
        block = wrapped(tool_name="kanban_complete", args={"task_id": "t_gate001"})

    assert isinstance(block, dict)
    assert block.get("action") == "block"
    assert "Convergence gate unavailable" in block.get("message", "")


def test_pre_tool_call_wrapper_fail_open_when_joyzoning_disabled():
    from plugins.dietcode.hooks import _run_pre_tool_call

    cfg = MagicMock()
    cfg.enabled = False

    def _boom(**_kwargs):
        raise RuntimeError("journal offline")

    wrapped = _run_pre_tool_call((_boom,))
    with patch(
        "plugins.dietcode.lib.agent.joyzoning.config.get_joyzoning_config",
        return_value=cfg,
    ):
        block = wrapped(tool_name="kanban_complete", args={"task_id": "t_gate002"})

    assert block is None


def test_transform_wrapper_returns_governance_fault_when_handler_raises():
    from plugins.dietcode.hooks import _run_transform

    def _boom(**_kwargs):
        raise RuntimeError("validator crash")

    wrapped = _run_transform((_boom,))
    with patch(
        "plugins.dietcode.lib.agent.governance_exemptions.is_governance_enforcement_enabled",
        return_value=True,
    ):
        out = wrapped(tool_name="write_file", args={"path": "x.ts"}, result='{"success": true}')

    assert isinstance(out, str)
    data = json.loads(out)
    assert data.get("success") is False
    assert "GOVERNANCE FAULT" in (data.get("error") or "")


def test_transform_wrapper_fail_open_when_governance_disabled():
    from plugins.dietcode.hooks import _run_transform

    def _boom(**_kwargs):
        raise RuntimeError("validator crash")

    wrapped = _run_transform((_boom,))
    with patch(
        "plugins.dietcode.lib.agent.governance_exemptions.is_governance_enforcement_enabled",
        return_value=False,
    ):
        out = wrapped(tool_name="write_file", args={"path": "x.ts"}, result='{"success": true}')

    assert out is None


def test_broccolidb_init_does_not_mutate_process_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    captured: dict = {}

    def _fake_interactive(*args, **kwargs):
        captured["extra_env"] = kwargs.get("extra_env")
        return '{"success": true}'

    with patch(
        "plugins.dietcode.lib.tools.broccolidb_tools.core_tools.run_cli_interactive",
        side_effect=_fake_interactive,
    ):
        from plugins.dietcode.lib.tools.broccolidb_tools.core_tools import broccolidb_init

        broccolidb_init(api_key="secret-key")

    assert "GEMINI_API_KEY" not in __import__("os").environ
    assert captured.get("extra_env") == {"GEMINI_API_KEY": "secret-key"}


def test_removed_habitat_modules_absent():
    from plugins.dietcode.audit import removed_habitat_modules_absent

    ok, present = removed_habitat_modules_absent()
    assert ok, present
