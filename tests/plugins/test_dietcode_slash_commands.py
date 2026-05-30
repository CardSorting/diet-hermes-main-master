# -*- coding: utf-8 -*-
"""Slash command handler tests for DietCode consoles."""
from __future__ import annotations

from unittest.mock import patch


def test_joyzoning_help_without_broccolidb():
    from plugins.dietcode.slash_commands import _handle_joyzoning

    out = _handle_joyzoning("help")
    assert out is not None
    assert "/joyzoning" in out
    assert "check" in out.lower()


def test_joyzoning_check_rejects_path_traversal():
    from plugins.dietcode.slash_commands import _handle_joyzoning

    out = _handle_joyzoning("check ../../etc/passwd")
    assert out is not None
    assert "Invalid path" in out


def test_joyzoning_check_exempt_readme():
    from plugins.dietcode.slash_commands import _handle_joyzoning

    out = _handle_joyzoning("check README.md")
    assert out is not None
    assert "exempt" in out.lower()


def test_joyzoning_check_runs_gate_for_source_file():
    from plugins.dietcode.slash_commands import _handle_joyzoning

    with patch(
        "plugins.dietcode.slash_commands.run_governance_validation_gate",
        return_value={"success": True, "singleResults": []},
    ):
        out = _handle_joyzoning("check src/core/foo.ts")
    assert out is not None
    assert "compliant" in out.lower()


def test_broccolidb_help():
    from plugins.dietcode.slash_commands import _handle_broccolidb

    out = _handle_broccolidb("help")
    assert out is not None
    assert "broccolidb" in out.lower()


def test_broccoliq_help():
    from plugins.dietcode.slash_commands import _handle_broccoliq

    out = _handle_broccoliq("help")
    assert out is not None
    assert "broccoliq" in out.lower() or "queue" in out.lower()


def test_joyzoning_suggest_rejects_embed_injection():
    from plugins.dietcode.slash_commands import _handle_joyzoning

    out = _handle_joyzoning("suggest foo`bar")
    assert out is not None
    assert "Invalid path" in out
