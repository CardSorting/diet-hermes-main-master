"""JoyZoning governance plugin — exempt paths, scoped gating, path extraction."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from plugins.dietcode.lib.agent.governance_exemptions import (
    extract_governance_tool_paths,
    invalidate_governance_path_cache,
    is_governance_artifact_path,
    is_governance_subject,
)
from plugins.dietcode.public import (
    _handle_joyzoning,
    _on_transform_tool_result,
    run_joyzoning_gate,
)


@pytest.fixture(autouse=True)
def _enable_governance_enforcement(monkeypatch):
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.governance_exemptions.is_governance_enforcement_enabled",
        lambda: True,
    )
    invalidate_governance_path_cache()
    yield
    invalidate_governance_path_cache()


@pytest.mark.parametrize(
    "path",
    [
        "package.json",
        "README.md",
        "docs/reports/benchmark.md",
        "prisma/schema.prisma",
        "db/migrations/001_init.sql",
        "package-lock.json",
        "tsconfig.json",
        "vite.config.ts",
        ".env.production",
    ],
)
def test_governance_artifact_paths_are_exempt(path: str):
    assert is_governance_artifact_path(path) is True
    assert is_governance_subject(path) is False


def test_governance_subject_accepts_layered_ts(tmp_path):
    src = tmp_path / "src" / "domain" / "foo.ts"
    src.parent.mkdir(parents=True)
    src.write_text("/** [LAYER: DOMAIN] */\nexport const x = 1;\n")
    assert is_governance_subject(str(src)) is True


def test_run_joyzoning_gate_skips_exempt_files(tmp_path):
    md = tmp_path / "README.md"
    md.write_text("# hello\n")
    gate = run_joyzoning_gate([str(md)])
    assert gate["success"] is True
    assert gate["singleResults"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/Users/me/Desktop/TypingJoy/package.json",
        "/Users/me/Desktop/TypingJoy/README.md",
        "/Users/me/Desktop/TypingJoy/docs/reports/typingjoy-agentic-benchmark.md",
    ],
)
def test_typingjoy_reported_false_positive_paths_are_exempt(path: str):
    assert is_governance_artifact_path(path) is True
    assert is_governance_subject(path) is False


def test_extract_tool_target_paths_v4a_patch():
    body = (
        "*** Update File: src/a.ts\n"
        "@@\n"
        "+x\n"
        "*** Add File: docs/readme.md\n"
        "+# hi\n"
    )
    paths = extract_governance_tool_paths("patch", {"mode": "patch", "patch": body})
    assert "src/a.ts" in paths
    assert "docs/readme.md" in paths


def test_extract_tool_target_paths_multi_replace():
    args = {
        "files": [
            {"path": "package.json"},
            {"path": "src/core/app.ts"},
        ],
    }
    paths = extract_governance_tool_paths("multi_replace_file_content", args)
    assert "package.json" in paths
    assert "src/core/app.ts" in paths


def test_transform_hook_does_not_block_readme_write(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("# old\n")

    dirty_ts = tmp_path / "src" / "bad.ts"
    dirty_ts.parent.mkdir(parents=True)
    dirty_ts.write_text("import x from '../ui/widget';\n")

    def fake_gate(files, **_kwargs):
        if any(f.endswith("bad.ts") for f in files):
            return {
                "success": False,
                "singleResults": [{"file": str(dirty_ts), "layer": "domain", "errors": ["violation"]}],
            }
        return {"success": True, "singleResults": []}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("plugins.dietcode.lib.agent.governance_exemptions.run_governance_validation_gate", fake_gate)

    blocked = _on_transform_tool_result(
        tool_name="write_file",
        args={"path": str(readme), "content": "# new\n"},
        result=json.dumps({"bytes_written": 6}),
    )
    assert blocked is None


def test_transform_hook_does_not_block_package_json_patch(tmp_path, monkeypatch):
    pkg = tmp_path / "package.json"
    pkg.write_text('{"name":"x"}\n')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.governance_exemptions.run_governance_validation_gate",
        lambda files, **_kwargs: {"success": False, "singleResults": [{"file": "x", "errors": ["x"]}]},
    )

    blocked = _on_transform_tool_result(
        tool_name="patch",
        args={"mode": "replace", "path": str(pkg), "old_string": "x", "new_string": "y"},
        result=json.dumps({"success": True}),
    )
    assert blocked is None


def test_transform_hook_blocks_governed_ts_with_violations(tmp_path, monkeypatch):
    ts_file = tmp_path / "src" / "domain" / "bad.ts"
    ts_file.parent.mkdir(parents=True)
    ts_file.write_text("const x = 1;\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.governance_exemptions.run_governance_validation_gate",
        lambda files, **_kwargs: {
            "success": False,
            "singleResults": [
                {
                    "file": str(ts_file),
                    "layer": "domain",
                    "errors": ["Missing mandatory [LAYER: TYPE] header tag."],
                },
            ],
        },
    )

    blocked = _on_transform_tool_result(
        tool_name="patch",
        args={"path": str(ts_file), "patch": "@@\n+/** [LAYER: DOMAIN] */\n"},
        result=json.dumps({"success": True}),
    )
    assert blocked is not None
    payload = json.loads(blocked)
    assert payload["success"] is False
    assert "GOVERNANCE FAULT" in payload["error"]


def test_mixed_patch_exempt_paths_not_in_verifier_on_governance_block():
    """Regression: README in a multi-file patch must not show as NOT modified."""
    from tests.run_agent.test_file_mutation_verifier import _bare_agent

    agent = _bare_agent()
    fault = "GOVERNANCE FAULT: JoyZoning Layering Violations Detected!"
    body = (
        "*** Update File: README.md\n@@\n+# x\n"
        "*** Update File: src/bad.ts\n@@\n+x\n"
    )
    agent._record_file_mutation_result(
        "patch",
        {"mode": "patch", "patch": body},
        json.dumps({"success": False, "error": fault}),
        is_error=True,
    )
    assert "README.md" not in agent._turn_failed_file_mutations
    assert "src/bad.ts" in agent._turn_failed_file_mutations


def test_transform_hook_v4a_only_gates_governable_files(tmp_path, monkeypatch):
    readme = tmp_path / "docs" / "note.md"
    readme.parent.mkdir(parents=True)
    ts_file = tmp_path / "src" / "app.ts"
    ts_file.parent.mkdir(parents=True)

    gated: list[str] = []

    def fake_gate(files, **_kwargs):
        gated.extend(files)
        return {"success": True, "singleResults": []}

    monkeypatch.setattr("plugins.dietcode.lib.agent.governance_exemptions.run_governance_validation_gate", fake_gate)

    body = (
        f"*** Update File: {ts_file}\n@@\n+x\n"
        f"*** Update File: {readme}\n@@\n+# t\n"
    )
    _on_transform_tool_result(
        tool_name="patch",
        args={"mode": "patch", "patch": body},
        result=json.dumps({"success": True}),
    )
    assert gated == [str(ts_file)]


def test_slash_check_reports_exempt(tmp_path):
    md = tmp_path / "README.md"
    md.write_text("# x\n")
    out = _handle_joyzoning(f"check {md}")
    assert out is not None
    assert "exempt" in out.lower()
    assert "README" in out or str(md) in out
