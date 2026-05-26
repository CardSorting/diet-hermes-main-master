"""Validate governance exemptions against tracked files in this repository."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from agent.governance_exemptions import is_governance_artifact_path, is_governance_subject

REPO_ROOT = Path(__file__).resolve().parents[2]

# Tracked paths that must be exempt (non-layerable artifacts).
TRACKED_EXEMPT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("markdown", re.compile(r"\.(md|mdx|mdc)$", re.I)),
    ("json_manifest", re.compile(r"(^|/)package\.json$", re.I)),
    ("lockfile", re.compile(r"\.(lock|lockb|lock\.yaml)$|(-lock\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock)$", re.I)),
    ("python_packaging", re.compile(r"(^|/)(pyproject\.toml|requirements.*\.txt|setup\.py|MANIFEST\.in)$", re.I)),
    ("docker", re.compile(r"(^|/)Dockerfile(\.|$)|docker-compose\.(ya?ml)$", re.I)),
    ("github", re.compile(r"^\.github/", re.I)),
    ("yaml_ci", re.compile(r"\.(ya?ml)$", re.I)),
    ("env_template", re.compile(r"^\.env(\.|$)|\.envrc$", re.I)),
    ("assets", re.compile(r"\.(png|svg|ico|woff2?|gif|jpe?g|webp|avif)$", re.I)),
    ("skills", re.compile(r"(^|/)(optional-skills|skills)/.+/SKILL\.md$", re.I)),
]

# Tracked TS/JS under agent/ (app source) must remain governable when layer-tagged policy applies.
TRACKED_GOVERNABLE_SAMPLES = [
    "agent/governance_exemptions.py",
    "agent/joy_zoning.py",
    "run_agent.py",
    "cli.py",
]


def _git_ls_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git ls-files unavailable")
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def tracked_files() -> list[str]:
    return _git_ls_files()


@pytest.mark.parametrize("label,pattern", TRACKED_EXEMPT_PATTERNS)
def test_tracked_artifact_patterns_are_exempt(
    tracked_files: list[str], label: str, pattern: re.Pattern[str]
):
    matches = [p for p in tracked_files if pattern.search(p.replace("\\", "/"))]
    if not matches:
        pytest.skip(f"no tracked files for pattern {label}")
    failures = [p for p in matches if not is_governance_artifact_path(p)]
    assert not failures, f"{label}: not exempt: {failures[:8]}"


@pytest.mark.parametrize("rel_path", TRACKED_GOVERNABLE_SAMPLES)
def test_tracked_hermes_python_sources_not_auto_exempt(rel_path: str, tracked_files: list[str]):
    if rel_path not in tracked_files:
        pytest.skip(f"{rel_path} not in tree")
    # Python sources are exempt from layering (non-JS) — not governance subjects.
    assert is_governance_artifact_path(rel_path) is True
    assert is_governance_subject(rel_path) is False


def test_tracked_broccolidb_ts_sources_are_governable_or_exempt_by_path(tracked_files: list[str]):
    ts_files = [
        p for p in tracked_files
        if p.startswith("broccolidb/") and p.endswith((".ts", ".tsx", ".js", ".jsx"))
    ]
    if not ts_files:
        pytest.skip("no broccolidb TS tracked")
    governable = [p for p in ts_files if is_governance_subject(p)]
    assert governable, "expected some governable broccolidb TS sources"


def test_tracked_agent_json_descriptor_exempt(tracked_files: list[str]):
    targets = [p for p in tracked_files if p.endswith("agent.json")]
    for p in targets:
        assert is_governance_artifact_path(p) is True
