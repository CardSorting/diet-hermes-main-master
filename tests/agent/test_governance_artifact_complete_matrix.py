"""Complete exempt-artifact catalog regression (policy v8+)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.governance_exemptions import (
    GOVERNANCE_POLICY_VERSION,
    governance_policy_summary,
    is_governance_artifact_path,
    is_governance_subject,
)
from tests.agent.governance_artifact_catalog import (
    COMPLETE_EXEMPT_CATALOG,
    MUST_REMAIN_GOVERNABLE_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Real files from this repo — behavioral smoke (skip if missing in sparse checkouts).
HERMES_REPO_ARTIFACT_SAMPLES = [
    "package.json",
    "pyproject.toml",
    "AGENTS.md",
    "README.md",
    "uv.lock",
    "herm-tui/package.json",
    "website/package.json",
    "docs/reports/dietcode-throughput-benchmark-results.md",
]


@pytest.mark.parametrize(
    "category,path",
    COMPLETE_EXEMPT_CATALOG,
    ids=lambda p: f"{p[0]}:{p[1][-48:]}",
)
def test_complete_exempt_catalog(category: str, path: str):
    assert is_governance_artifact_path(path) is True, f"{category}: {path}"
    assert is_governance_subject(path) is False, f"{category}: {path}"


@pytest.mark.parametrize("path", MUST_REMAIN_GOVERNABLE_CATALOG)
def test_complete_governable_catalog(path: str):
    assert is_governance_artifact_path(path) is False, path
    assert is_governance_subject(path) is True, path


@pytest.mark.parametrize("rel_path", HERMES_REPO_ARTIFACT_SAMPLES)
def test_hermes_repo_sample_artifacts_are_exempt(rel_path: str):
    full = REPO_ROOT / rel_path
    if not full.is_file():
        pytest.skip(f"missing sample: {rel_path}")
    assert is_governance_artifact_path(rel_path) is True
    assert is_governance_subject(rel_path) is False


def test_policy_version_at_least_8():
    assert GOVERNANCE_POLICY_VERSION >= 9


def test_governance_policy_summary_complete():
    summary = governance_policy_summary()
    assert summary["version"] >= 8
    assert summary["exempt_basenames"] >= 120
    assert summary["exempt_extensions"] >= 80
    assert summary["exempt_path_markers"] >= 50
    assert summary["compound_suffixes"] >= 5
    assert ".ts" in summary["source_extensions"]
