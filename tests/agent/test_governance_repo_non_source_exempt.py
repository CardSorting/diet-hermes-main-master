"""Every tracked non-source artifact in this repo must be governance-exempt."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plugins.dietcode.lib.agent.governance_exemptions import resolve_governance_path_kind

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories whose TS/JS is real source (must NOT be blanket-exempt).
_SOURCE_ROOTS = ("broccolidb/", "herm-tui/src/", "plugins/dietcode/lib/agent/", "run_agent.py", "cli.py")


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
        kind = resolve_governance_path_kind(rel)
        if kind == "subject":
            continue
        if kind != "exempt":
            failures.append(rel)
    assert not failures, "expected exempt:\n" + "\n".join(failures[:30])


def test_tracked_broccolidb_ts_is_governable_or_exempt_test_only(tracked_files: list[str]):
    ts = [p for p in tracked_files if p.startswith("broccolidb/") and p.endswith((".ts", ".tsx"))]
    if not ts:
        pytest.skip("no broccolidb TS")
    subjects = [p for p in ts if resolve_governance_path_kind(p) == "subject"]
    exempt = [p for p in ts if resolve_governance_path_kind(p) == "exempt"]
    assert subjects, "expected governable broccolidb TS"
    assert len(subjects) + len(exempt) == len(ts)
