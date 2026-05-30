# -*- coding: utf-8 -*-
"""Import and runtime audit tests for DietCode production hardening."""
from __future__ import annotations


def test_runtime_layout_complete():
    from plugins.dietcode.audit import runtime_layout_ok

    ok, missing = runtime_layout_ok()
    assert ok, missing


def test_legacy_shim_directories_removed():
    from plugins.dietcode.audit import legacy_shim_dirs_absent

    ok, present = legacy_shim_dirs_absent()
    assert ok, present


def test_no_forbidden_diet_imports_in_core():
    from plugins.dietcode.audit import scan_forbidden_imports

    hits = scan_forbidden_imports()
    assert not hits, hits[:5]


def test_duplicate_diet_hooks_absent_when_registered():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.audit import duplicate_diet_hooks

    discover_plugins(force=True)
    ok, issues = duplicate_diet_hooks()
    assert ok, issues


def test_no_stale_integration_paths_in_fork_docs():
    from plugins.dietcode.audit import scan_stale_doc_paths

    hits = scan_stale_doc_paths()
    assert not hits, hits[:5]


def test_public_api_exports_governance_and_slash_handlers():
    from plugins.dietcode import public

    assert callable(public.run_joyzoning_gate)
    assert callable(public._on_transform_tool_result)
    assert callable(public._handle_joyzoning)
    assert callable(public._pre_tool_call)
    assert public._on_transform_tool_result is public.on_transform_tool_result


def test_audit_module_listed_in_contract_checks():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.contracts import validate_runtime_contract

    discover_plugins(force=True)
    report = validate_runtime_contract(strict=True)
    assert report.checks.get("runtime_layout_ok") is True
    assert report.checks.get("legacy_shim_dirs_absent") is True
    assert report.checks.get("no_duplicate_diet_hooks") is True


def test_contract_warns_when_governance_on_without_dietcode_toolset(monkeypatch):
    """Default hermes-cli toolsets should surface governance activation warning."""
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.contracts import validate_runtime_contract

    discover_plugins(force=True)
    report = validate_runtime_contract(strict=True)
    checks = report.checks
    if checks.get("plugin_registered") and checks.get("governance_config_enabled"):
        if not checks.get("dietcode_in_toolsets"):
            assert any(
                "dietcode is not in toolsets" in w for w in report.warnings
            ), report.warnings
