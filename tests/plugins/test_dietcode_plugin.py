# -*- coding: utf-8 -*-
"""Production-hardening tests for the unified DietCode plugin."""
from __future__ import annotations

import json

import pytest


def test_dietcode_plugin_loads_and_registers_tools():
    from hermes_cli.plugins import discover_plugins, get_plugin_manager

    discover_plugins(force=True)
    pm = get_plugin_manager()
    assert "dietcode" in pm._plugins, list(pm._plugins.keys())
    plugin = pm._plugins["dietcode"]
    assert plugin.enabled, getattr(plugin, "error", None)


def test_dietcode_toolset_includes_broccolidb_joyzoning_jsdp():
    from hermes_cli.plugins import discover_plugins
    from toolsets import resolve_toolset

    discover_plugins(force=True)
    tools = set(resolve_toolset("dietcode"))
    assert "broccolidb_init" in tools
    assert "joyzoning" in tools
    assert "mutation_record_patch" in tools
    assert "jsdp" in tools
    assert "jsdp_horizon" in tools
    assert "kanban_broccolidb_board_intel" in tools


def test_dietcode_registers_chained_hooks():
    from hermes_cli.plugins import discover_plugins, get_plugin_manager

    discover_plugins(force=True)
    pm = get_plugin_manager()
    hooks = pm._hooks
    start = [cb.__name__ for cb in hooks.get("on_session_start", [])]
    assert "dietcode_on_session_start" in start
    pre = [cb.__name__ for cb in hooks.get("pre_tool_call", [])]
    assert "dietcode_pre_tool_call" in pre
    transform = [cb.__name__ for cb in hooks.get("transform_tool_result", [])]
    assert "dietcode_transform_tool_result" in transform
    post = [cb.__name__ for cb in hooks.get("post_tool_call", [])]
    assert "dietcode_post_tool_call" in post


def test_legacy_shim_plugins_not_discovered():
    from hermes_cli.plugins import discover_plugins, get_plugin_manager

    discover_plugins(force=True)
    pm = get_plugin_manager()
    for key in ("joyzoning_runtime", "joyzoning_governance", "kanban_broccolidb", "jsdp_mutation"):
        assert key not in pm._plugins, f"legacy shim {key} should be removed"


def test_legacy_shim_directories_absent():
    from plugins.dietcode.audit import legacy_shim_dirs_absent

    ok, present = legacy_shim_dirs_absent()
    assert ok, present


def test_dietcode_slash_status_command():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.health import handle_dietcode_command

    discover_plugins(force=True)
    out = handle_dietcode_command("status")
    assert out is not None
    assert "DietCode integration status" in out
    assert "Tool modules loaded" in out


def test_dietcode_tools_json_subcommand():
    from plugins.dietcode.health import handle_dietcode_command

    out = handle_dietcode_command("tools")
    assert out is not None
    data = json.loads(out)
    assert "loaded" in data
    assert "registry_tools" in data


def test_load_report_tracks_expected_tools():
    from plugins.dietcode.tools_loader import EXPECTED_DIETCODE_TOOLS, get_load_report

    report = get_load_report(force=True)
    assert report.loaded
    assert not report.registry_missing, report.registry_missing
    assert EXPECTED_DIETCODE_TOOLS.issubset(set(report.registry_tools))


def test_hermes_cli_without_dietcode_toolset_excludes_broccolidb_tools():
    from tools.registry import registry
    from toolsets import resolve_toolset

    cli_tools = set(resolve_toolset("hermes-cli"))
    assert "broccolidb_init" not in cli_tools
    assert "joyzoning" not in cli_tools
    assert "jsdp" not in cli_tools
    # Registry may still contain tools (auto-discovery), but they must not ship in core toolset.
    if registry.get_tool_names_for_toolset("broccolidb"):
        assert "broccolidb_init" not in cli_tools


def test_dietcode_register_is_idempotent():
    from hermes_cli.plugins import PluginContext, PluginManager, discover_plugins, get_plugin_manager
    from plugins.dietcode import register as dietcode_register

    discover_plugins(force=True)
    pm = get_plugin_manager()
    before = len(pm._hooks.get("on_session_start", []))
    manifest = pm._plugins["dietcode"].manifest
    ctx = PluginContext(manifest, pm)
    dietcode_register(ctx)
    dietcode_register(ctx)
    after = len(pm._hooks.get("on_session_start", []))
    assert after == before


def test_private_tmp_pytest_paths_are_governable_subjects(tmp_path):
    """macOS pytest temps under /private/tmp/ must not match broad /tmp/ exempt rules."""
    from plugins.dietcode.lib.agent.governance_exemptions import (
        invalidate_governance_path_cache,
        is_governance_subject,
        resolve_governance_path_kind,
    )

    src = tmp_path / "src" / "app.ts"
    src.parent.mkdir(parents=True)
    src.write_text("export const x = 1;\n")
    invalidate_governance_path_cache()
    path = str(src)
    assert "/private/tmp/" in path or "/tmp/" in path
    assert resolve_governance_path_kind(path) == "subject"
    assert is_governance_subject(path) is True


def test_hermes_scratch_temp_paths_remain_exempt():
    from plugins.dietcode.lib.agent.governance_exemptions import (
        invalidate_governance_path_cache,
        resolve_governance_path_kind,
    )

    invalidate_governance_path_cache()
    assert resolve_governance_path_kind("/tmp/hermes-abc/session/foo.ts") == "exempt"



def test_deferred_tool_modules_excluded_from_builtin_discovery():
    from plugins.dietcode.tools_loader import DEFERRED_TOOL_MODULE_STEMS
    from tools.registry import _deferred_tool_module_stems

    assert _deferred_tool_module_stems() == DEFERRED_TOOL_MODULE_STEMS
    assert "broccolidb" in DEFERRED_TOOL_MODULE_STEMS
    assert "joyzoning_tools" in DEFERRED_TOOL_MODULE_STEMS


def test_dietcode_registry_populated_after_plugin_discovery():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.tools_loader import get_load_report

    discover_plugins(force=True)
    report = get_load_report(force=True)
    assert "plugins.dietcode.lib.tools.joyzoning_tools" in report.loaded
    assert not report.registry_missing, report.registry_missing


def test_build_dietcode_guidance_gates_on_tools():
    from plugins.dietcode.prompts import JOYZONING_GUIDANCE, build_dietcode_guidance

    assert build_dietcode_guidance(set()) == ""
    assert build_dietcode_guidance({"read_file"}) == ""
    guided = build_dietcode_guidance({"joyzoning", "patch"})
    assert JOYZONING_GUIDANCE in guided
    assert "JoyZoning governed work" in guided


def test_resolve_broccolidb_root_finds_plugin_bundle(tmp_path, monkeypatch):
    from hermes_cli.plugins import get_bundled_plugins_dir
    from plugins.dietcode.paths import is_valid_broccolidb_root, resolve_broccolidb_root

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HERMES_BROCCOLIDB_ROOT", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_WORKSPACE", raising=False)

    bundled = get_bundled_plugins_dir() / "dietcode" / "broccolidb"
    assert is_valid_broccolidb_root(bundled), bundled
    root = resolve_broccolidb_root()
    assert root is not None
    assert "broccolidb" in root


def test_dietcode_guidance_contract_for_joyzoning_toolset():
    from plugins.dietcode.prompts import JOYZONING_GUIDANCE, build_dietcode_guidance

    names = {"joyzoning", "mutation_record_patch", "jsdp", "kanban_broccolidb_context"}
    guidance = build_dietcode_guidance(names)
    assert guidance == JOYZONING_GUIDANCE
    assert "jsdp" in guidance.lower()
    assert "GOVERNANCE FAULT" in guidance


def test_prompt_bridge_uses_plugin_manager_builder():
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from agent.prompt_bridge import resolve_plugin_prompt_guidance

    discover_plugins(force=True)
    pm = get_plugin_manager()
    assert getattr(pm, "_dietcode_guidance_builder", None) is not None
    guidance = resolve_plugin_prompt_guidance(
        "_dietcode_guidance_builder",
        {"joyzoning"},
    )
    assert "JoyZoning governed work" in guidance


def test_runtime_contract_passes_when_plugin_loaded():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.contracts import validate_runtime_contract
    from plugins.dietcode.guard import dietcode_governance_hook_active

    discover_plugins(force=True)
    report = validate_runtime_contract(strict=True)
    assert report.ok, report.errors
    assert dietcode_governance_hook_active()


def test_doctor_surfaces_governance_hook_status():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.health import handle_dietcode_command

    discover_plugins(force=True)
    out = handle_dietcode_command("doctor")
    assert out is not None
    assert "Governance transform hook wired" in out


def test_doctor_surfaces_runtime_layout():
    from hermes_cli.plugins import discover_plugins
    from plugins.dietcode.health import handle_dietcode_command

    discover_plugins(force=True)
    out = handle_dietcode_command("doctor")
    assert out is not None
    assert "Runtime layout complete" in out


def test_hooks_import_from_dietcode_runtime_only():
    import inspect

    from plugins.dietcode import hooks

    src = inspect.getsource(hooks._ensure_handlers)
    assert "plugins.dietcode.lib.runtime" in src
    for legacy in (
        "plugins.joyzoning_governance",
        "plugins.joyzoning_runtime",
        "plugins.kanban_broccolidb",
        "plugins.jsdp_mutation",
    ):
        assert legacy not in src


def test_dietcode_layout_contract_files_exist():
    from hermes_cli.plugins import get_bundled_plugins_dir

    root = get_bundled_plugins_dir() / "dietcode"
    required = (
        "lib/runtime/governance_hooks.py",
        "lib/runtime/joyzoning_hooks.py",
        "lib/runtime/kanban_hooks.py",
        "lib/runtime/jsdp_hooks.py",
        "slash_commands.py",
        "lib/tools/broccolidb.py",
        "audit.py",
        "public.py",
    )
    for rel in required:
        assert (root / rel).is_file(), rel

