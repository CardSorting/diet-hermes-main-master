"""DietCode fork: interactive chat defaults to Ink TUI."""

import argparse
from unittest.mock import MagicMock

import pytest

from hermes_constants import (
    argv_requests_interactive_tui,
    interactive_tui_default_enabled,
    resolve_interactive_tui,
)


def test_interactive_tui_default_enabled_for_dietcode():
    assert interactive_tui_default_enabled() is True


def test_resolve_interactive_tui_defaults_on_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: True))
    monkeypatch.setattr("sys.stdout", MagicMock(isatty=lambda: True))
    args = argparse.Namespace(tui=False, query=None, quiet=False)
    assert resolve_interactive_tui(args) is True


def test_resolve_interactive_tui_classic_flag(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: True))
    monkeypatch.setattr("sys.stdout", MagicMock(isatty=lambda: True))
    args = argparse.Namespace(tui=False, query=None, quiet=False, classic=True)
    monkeypatch.setenv("HERMES_CLASSIC", "1")
    assert resolve_interactive_tui(args) is False


def test_resolve_interactive_tui_query_mode(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: True))
    monkeypatch.setattr("sys.stdout", MagicMock(isatty=lambda: True))
    args = argparse.Namespace(tui=False, query="hello", quiet=False)
    assert resolve_interactive_tui(args) is False


def test_resolve_interactive_tui_explicit_tui(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: False))
    args = argparse.Namespace(tui=True, query=None, quiet=False)
    assert resolve_interactive_tui(args) is True


def test_argv_requests_interactive_tui_bare_argv(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: True))
    monkeypatch.setattr("sys.stdout", MagicMock(isatty=lambda: True))
    assert argv_requests_interactive_tui([]) is True
    assert argv_requests_interactive_tui(["--classic"]) is False
    assert argv_requests_interactive_tui(["-q", "hi"]) is False


@pytest.mark.parametrize(
    "config_default,expected",
    [(True, True), (False, False)],
)
def test_resolve_interactive_tui_config_override(
    monkeypatch, tmp_path, config_default, expected
):
    home = tmp_path / ".dietcode"
    home.mkdir()
    (home / "config.yaml").write_text(
        f"display:\n  default_tui: {'true' if config_default else 'false'}\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("DIETCODE_HOME", str(home))
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: True))
    monkeypatch.setattr("sys.stdout", MagicMock(isatty=lambda: True))
    args = argparse.Namespace(tui=False, query=None, quiet=False)
    assert resolve_interactive_tui(args) is expected
