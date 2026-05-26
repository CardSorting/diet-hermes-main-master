"""Canonical JoyZoning governance exemption policy (agent.joy_zoning)."""

from __future__ import annotations

import pytest

from agent.governance_exemptions import (
    GOVERNANCE_POLICY_VERSION,
    _governance_path_context,
    enforce_governance_on_mutation,
    extract_and_partition_governance_paths,
    extract_governance_tool_paths,
    filter_governance_subjects,
    governance_skip_reason,
    invalidate_governance_path_cache,
    is_governance_artifact_path,
    is_governance_fault_error,
    is_governance_subject,
    iter_governance_subject_files,
    partition_governance_paths,
    resolve_governance_path_kind,
    run_governance_validation_gate,
)
from agent.joy_zoning import validate_joy_zoning


@pytest.mark.parametrize(
    "path",
    [
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "README.md",
        "docs/reports/benchmark.md",
        "CHANGELOG.MD",
        "prisma/schema.prisma",
        "db/migrations/001_init.sql",
        "src/db/migrations/2024_01.sql",
        "docker-compose.yml",
        ".env",
        ".env.local",
        "tsconfig.json",
        "vite.config.ts",
        "jest.config.js",
        "src/foo.d.ts",
        "src/components/Button.test.tsx",
        "src/utils/helper.spec.ts",
        "public/locales/en.json",
        "fixtures/users.sql",
        "node_modules/foo/index.js",
    ],
)
def test_artifact_paths_are_exempt(path: str):
    assert is_governance_artifact_path(path) is True
    assert is_governance_subject(path) is False
    assert governance_skip_reason(path) is not None


@pytest.mark.parametrize(
    "path",
    [
        "src/domain/UserService.ts",
        "src/core/orchestrator.ts",
        "lib/handler.js",
    ],
)
def test_layerable_source_paths_are_subjects(path: str):
    assert is_governance_artifact_path(path) is False
    assert is_governance_subject(path) is True


def test_validate_joy_zoning_skips_exempt_without_errors():
    result = validate_joy_zoning("README.md", "# Title\n")
    assert result["success"] is True
    assert result.get("skipped") is True
    assert result["errors"] == []


def test_governance_policy_version_is_positive():
    assert GOVERNANCE_POLICY_VERSION >= 16


def test_governance_path_context_caches_components():
    invalidate_governance_path_cache()
    ctx = _governance_path_context("src/domain/UserService.ts")
    assert ctx.kind == "subject"
    assert ctx.ext == ".ts"
    assert ctx.basename == "userservice.ts"


def test_resolve_governance_path_kind_classifier():
    assert resolve_governance_path_kind("README.md") == "exempt"
    assert resolve_governance_path_kind("src/domain/foo.ts") == "subject"
    # Non-exempt, non-TS/JS (unknown extension, not under exempt trees).
    assert resolve_governance_path_kind("src/misc/widget") == "ineligible"


def test_path_context_cache_is_stable():
    invalidate_governance_path_cache()
    assert _governance_path_context("package-lock.json").kind == "exempt"
    info1 = _governance_path_context.cache_info()
    assert _governance_path_context("package-lock.json").kind == "exempt"
    info2 = _governance_path_context.cache_info()
    assert info2.hits >= info1.hits


def test_run_governance_validation_gate_skips_exempt(tmp_path):
    ts_file = tmp_path / "src" / "domain" / "x.ts"
    ts_file.parent.mkdir(parents=True)
    ts_file.write_text("export const a = 1;\n", encoding="utf-8")
    gate = run_governance_validation_gate(
        ["README.md", str(ts_file)],
        validate=lambda _f, _c, **_: {"success": False, "errors": ["missing tag"]},
    )
    assert gate["success"] is False
    assert len(gate["singleResults"]) == 1
    assert gate["singleResults"][0]["file"] == str(ts_file)


def test_db_schema_paths_exempt_app_schema_folder_not():
    assert is_governance_artifact_path("db/schema/users.sql") is True
    assert is_governance_artifact_path("prisma/migrations/001.sql") is True
    # Bare /schema/ was removed — TS under src/.../schema/ stays governable.
    assert is_governance_artifact_path("src/validation/schema/resolver.ts") is False


def test_extract_paths_matches_partition_extractor():
    args = {"path": "README.md"}
    assert extract_governance_tool_paths("write_file", args) == ["README.md"]


def test_extract_and_partition_tool_paths():
    exempt, subjects = extract_and_partition_governance_paths(
        "patch",
        {
            "mode": "patch",
            "patch": (
                "*** Update File: README.md\n@@\n+x\n"
                "*** Update File: src/domain/foo.ts\n@@\n+y\n"
            ),
        },
    )
    assert "README.md" in exempt
    assert subjects == ["src/domain/foo.ts"]


def test_iter_governance_subject_files_yields_readable_subjects(tmp_path):
    ts_file = tmp_path / "src" / "app.ts"
    ts_file.parent.mkdir(parents=True)
    ts_file.write_text("export const x = 1;\n", encoding="utf-8")
    md = tmp_path / "README.md"
    md.write_text("# hi\n", encoding="utf-8")
    found = list(iter_governance_subject_files([str(md), str(ts_file)]))
    assert len(found) == 1
    assert found[0][0] == str(ts_file)


def test_partition_governance_paths_splits_exempt_and_subjects():
    exempt, subjects = partition_governance_paths([
        "README.md",
        "package.json",
        "src/domain/foo.ts",
        "src/domain/foo.ts",
    ])
    assert exempt == ["README.md", "package.json"]
    assert subjects == ["src/domain/foo.ts"]


def test_filter_governance_subjects_dedupes_and_preserves_order():
    paths = [
        "README.md",
        "src/a.ts",
        "package.json",
        "src/a.ts",
        "src/b.tsx",
    ]
    assert filter_governance_subjects(paths) == ["src/a.ts", "src/b.tsx"]


def test_governance_fault_marker_detection():
    assert is_governance_fault_error("GOVERNANCE FAULT: JoyZoning") is True
    assert is_governance_fault_error("patch failed") is False
