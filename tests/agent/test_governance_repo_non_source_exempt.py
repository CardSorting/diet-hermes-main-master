"""Every tracked non-source artifact in this repo must be governance-exempt."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent.governance_exemptions import is_governance_artifact_path, is_governance_subject

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories whose TS/JS is real source (must NOT be blanket-exempt).
_SOURCE_ROOTS = ("broccolidb/", "herm-tui/src/", "agent/", "run_agent.py", "cli.py")


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
    return [line.strip().replace("\\", "/") for line in out.stdout.splitlines() if line.strip()]


def _is_app_source(path: str) -> bool:
    if path.endswith((".ts", ".tsx", ".js", ".jsx")):
        if path.startswith(_SOURCE_ROOTS) or path in {"run_agent.py", "cli.py", "batch_runner.py"}:
            return True
        if path.startswith("herm-tui/src/"):
            return True
    return False


@pytest.fixture(scope="module")
def tracked_files() -> list[str]:
    return _git_ls_files()


def test_tracked_non_source_files_are_exempt(tracked_files: list[str]):
    failures: list[str] = []
    for rel in tracked_files:
        if _is_app_source(rel):
            continue
        if is_governance_subject(rel):
            continue
        if not is_governance_artifact_path(rel):
            failures.append(rel)
    assert not failures, "expected exempt:\n" + "\n".join(failures[:30])


def test_tracked_broccolidb_ts_is_governable_or_exempt_test_only(tracked_files: list[str]):
    ts = [p for p in tracked_files if p.startswith("broccolidb/") and p.endswith((".ts", ".tsx"))]
    if not ts:
        pytest.skip("no broccolidb TS")
    subjects = [p for p in ts if is_governance_subject(p)]
    exempt = [p for p in ts if is_governance_artifact_path(p)]
    assert subjects, "expected governable broccolidb TS"
    assert len(subjects) + len(exempt) == len(ts)
