"""Canonical JoyZoning governance exemption policy (agent.joy_zoning)."""

from __future__ import annotations

import pytest

from agent.governance_exemptions import (
    GOVERNANCE_POLICY_VERSION,
    filter_governance_subjects,
    governance_skip_reason,
    is_governance_artifact_path,
    is_governance_fault_error,
    is_governance_subject,
    partition_governance_paths,
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
    assert GOVERNANCE_POLICY_VERSION >= 10


def test_db_schema_paths_exempt_app_schema_folder_not():
    assert is_governance_artifact_path("db/schema/users.sql") is True
    assert is_governance_artifact_path("prisma/migrations/001.sql") is True
    # Bare /schema/ was removed — TS under src/.../schema/ stays governable.
    assert is_governance_artifact_path("src/validation/schema/resolver.ts") is False


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
