# -*- coding: utf-8 -*-
"""Tests for agent.joy_zoning_bridge facade."""
from __future__ import annotations


def test_get_path_layer_delegates_when_plugin_present():
    from agent.joy_zoning_bridge import get_path_layer

    assert get_path_layer("cli.py") == "ui"
    assert get_path_layer("broccolidb/core/mcp.ts") == "core"


def test_bridge_returns_none_when_plugin_unavailable(monkeypatch):
    import agent.joy_zoning_bridge as bridge

    monkeypatch.setattr(bridge, "_JZ", None)
    monkeypatch.setattr(bridge, "_JZ_TRIED", True)

    assert bridge.get_path_layer("cli.py") is None
    assert bridge.parse_layer_tag("/** [LAYER: core] */") is None
    assert bridge.validate_joy_zoning("x.py", "pass", require_layer_tags=True) is None
