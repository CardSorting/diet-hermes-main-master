"""Regression: ~/.hermes/.env must not clobber TUI-pinned TERMINAL_CWD."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def agent_root(tmp_path: Path) -> Path:
    root = tmp_path / "hermes-agent"
    root.mkdir()
    (root / "herm-tui").mkdir()
    return root


def test_load_hermes_dotenv_preserves_pinned_cwd(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / ".env").write_text("TERMINAL_CWD=/stale/from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_CWD", "/real/project")
    monkeypatch.setenv("TERMINAL_CWD", "/real/project")
    monkeypatch.setenv("_HERMES_TUI_GATEWAY", "1")

    from hermes_cli.env_loader import load_hermes_dotenv

    load_hermes_dotenv(hermes_home=home)

    assert os.environ["TERMINAL_CWD"] == "/real/project"
    assert os.environ["HERMES_CWD"] == "/real/project"


def test_pin_dotenv_cli_chain_preserves_workspace(
    agent_root: Path, monkeypatch, tmp_path: Path
):
    """Simulate TUI gateway startup: pin → dotenv → lazy cli import."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / ".env").write_text("TERMINAL_CWD=/stale/from-dotenv\n", encoding="utf-8")

    bundle = agent_root / "herm-tui"
    monkeypatch.chdir(bundle)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("PWD", raising=False)

    from hermes_cli import tui_cwd as mod
    from hermes_cli.env_loader import load_hermes_dotenv

    mod.pin_launch_cwd(os.environ, str(project), checkout_root=agent_root)
    load_hermes_dotenv(hermes_home=home)
    assert os.environ["TERMINAL_CWD"] == str(project.resolve())

    from cli import load_cli_config

    cfg = load_cli_config()
    assert os.environ["TERMINAL_CWD"] == str(project.resolve())
    assert cfg["terminal"]["cwd"] == str(project.resolve())


def test_restore_pinned_after_manual_clobber(monkeypatch, tmp_path):
    """entry.py restore path heals a post-dotenv TERMINAL_CWD overwrite."""
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setenv("HERMES_CWD", str(project))
    monkeypatch.setenv("TERMINAL_CWD", str(project))

    pinned = str(project.resolve())
    from hermes_cli.tui_cwd import restore_pinned_launch_cwd, snapshot_pinned_launch_cwd

    snap = snapshot_pinned_launch_cwd()
    os.environ["TERMINAL_CWD"] = "/wrong"
    restore_pinned_launch_cwd(snap)
    assert os.environ["TERMINAL_CWD"] == pinned
    assert os.environ["HERMES_CWD"] == pinned
    assert os.environ["_HERMES_TUI_GATEWAY"] == "1"
