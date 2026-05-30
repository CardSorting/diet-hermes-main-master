# -*- coding: utf-8 -*-
"""Unit tests for JSDP runtime hooks."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_jsdp_on_session_start_emits_role_started():
    from plugins.dietcode.lib.runtime.jsdp_hooks import _on_session_start

    cfg = MagicMock()
    cfg.enabled = True
    cfg.jsdp_enabled = True
    cfg.jsdp_role = "implementer"
    cfg.jsdp_chain_id = "chain-42"

    with patch(
        "plugins.dietcode.lib.agent.joyzoning.config.get_joyzoning_config",
        return_value=cfg,
    ), patch(
        "plugins.dietcode.lib.agent.joyzoning.config.resolve_scope_id",
        return_value="scope-1",
    ), patch(
        "plugins.dietcode.lib.agent.joyzoning.runtime_events.emit_runtime_event",
    ) as emit:
        _on_session_start(session_id="sess-99")

    emit.assert_called_once()
    args, kwargs = emit.call_args
    assert args[0] == "jsdp.role_started"
    assert kwargs["session_id"] == "sess-99"
    assert kwargs["payload"]["role"] == "implementer"
    assert kwargs["payload"]["chain_id"] == "chain-42"


def test_jsdp_on_session_start_skips_when_role_unset():
    from plugins.dietcode.lib.runtime.jsdp_hooks import _on_session_start

    cfg = MagicMock()
    cfg.enabled = True
    cfg.jsdp_enabled = True
    cfg.jsdp_role = ""

    with patch(
        "plugins.dietcode.lib.agent.joyzoning.config.get_joyzoning_config",
        return_value=cfg,
    ), patch(
        "plugins.dietcode.lib.agent.joyzoning.runtime_events.emit_runtime_event",
    ) as emit:
        _on_session_start(session_id="sess-99")

    emit.assert_not_called()
