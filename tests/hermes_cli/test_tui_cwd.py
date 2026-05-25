"""Tests for hermes_cli.tui_cwd — TUI workspace directory resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hermes_cli import tui_cwd as mod


@pytest.fixture
def agent_root(tmp_path: Path) -> Path:
    root = tmp_path / "hermes-agent"
    root.mkdir()
    (root / "herm-tui").mkdir()
    return root


def test_explicit_cwd_wins(agent_root: Path, monkeypatch):
    project = agent_root.parent / "my-app"
    project.mkdir()
    monkeypatch.chdir(agent_root / "herm-tui")
    assert mod.resolve_tui_launch_cwd(explicit=str(project), checkout_root=agent_root) == str(
        project.resolve()
    )


def test_prefers_pwd_over_bundler_getcwd(agent_root: Path, monkeypatch):
    project = agent_root.parent / "client"
    project.mkdir()
    monkeypatch.chdir(agent_root / "herm-tui")
    monkeypatch.setenv("PWD", str(project))
    monkeypatch.delenv("HERMES_CWD", raising=False)
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    assert mod.resolve_tui_launch_cwd(checkout_root=agent_root) == str(project.resolve())


def test_prefers_fresh_getcwd_over_stale_hermes_cwd(agent_root: Path, monkeypatch):
    project = agent_root.parent / "client"
    stale = agent_root.parent / "stale"
    project.mkdir()
    stale.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("HERMES_CWD", str(stale))
    assert mod.resolve_tui_launch_cwd(checkout_root=agent_root) == str(project.resolve())


def test_pwd_beats_hermes_cwd_when_in_bundler(agent_root: Path, monkeypatch):
    project = agent_root.parent / "client"
    stale = agent_root.parent / "stale"
    project.mkdir()
    stale.mkdir()
    monkeypatch.chdir(agent_root / "herm-tui")
    monkeypatch.setenv("PWD", str(project))
    monkeypatch.setenv("HERMES_CWD", str(stale))
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    assert mod.resolve_tui_launch_cwd(checkout_root=agent_root) == str(project.resolve())


def test_hermes_cwd_used_when_process_in_bundler(agent_root: Path, monkeypatch):
    project = agent_root.parent / "client"
    project.mkdir()
    monkeypatch.chdir(agent_root / "herm-tui")
    monkeypatch.setenv("HERMES_CWD", str(project))
    monkeypatch.delenv("PWD", raising=False)
    assert mod.resolve_tui_launch_cwd(checkout_root=agent_root) == str(project.resolve())


def test_skips_stale_terminal_cwd_placeholder(agent_root: Path, monkeypatch):
    project = agent_root.parent / "client"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("TERMINAL_CWD", ".")
    assert mod.resolve_tui_launch_cwd(checkout_root=agent_root) == str(project.resolve())


def test_invalid_explicit_raises(agent_root: Path):
    with pytest.raises(ValueError, match="Not a directory"):
        mod.resolve_tui_launch_cwd(explicit="/no/such/path", checkout_root=agent_root)


def test_pin_launch_cwd_sets_marker(agent_root: Path, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    env: dict[str, str] = {}
    pinned = mod.pin_launch_cwd(env, str(project), checkout_root=agent_root)
    assert pinned == str(project.resolve())
    assert env["HERMES_CWD"] == pinned
    assert env["TERMINAL_CWD"] == pinned
    assert env["_HERMES_TUI_GATEWAY"] == "1"


def test_is_bundler_cwd(agent_root: Path):
    assert mod.is_bundler_cwd(agent_root, agent_root)
    assert mod.is_bundler_cwd(agent_root / "herm-tui", agent_root)
    assert not mod.is_bundler_cwd(agent_root.parent / "other", agent_root)


class TestLoadCliConfigRespectsTuiGateway:
    """cli.load_cli_config must not clobber pinned TERMINAL_CWD."""

    def test_tui_gateway_marker_skips_terminal_cwd_bridge(self, monkeypatch):
        monkeypatch.setenv("TERMINAL_CWD", "/pinned/project")
        monkeypatch.setenv("_HERMES_TUI_GATEWAY", "1")
        monkeypatch.chdir("/tmp")

        from cli import load_cli_config

        load_cli_config()
        assert os.environ["TERMINAL_CWD"] == "/pinned/project"

    def test_terminal_config_cwd_uses_session_not_bundle(
        self, agent_root: Path, monkeypatch, tmp_path: Path
    ):
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(agent_root / "herm-tui")
        monkeypatch.setenv("TERMINAL_CWD", str(project))
        monkeypatch.setenv("HERMES_CWD", str(project))
        monkeypatch.setenv("_HERMES_TUI_GATEWAY", "1")

        from cli import load_cli_config

        cfg = load_cli_config()
        assert cfg["terminal"]["cwd"] == str(project.resolve())
