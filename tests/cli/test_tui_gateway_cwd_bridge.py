"""Regression: load_cli_config must not rewrite TERMINAL_CWD in TUI gateway children."""


import os

import pytest


@pytest.fixture
def _isolate(monkeypatch, tmp_path):
    project = tmp_path / "user-project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("TERMINAL_CWD", str(project))
    monkeypatch.setenv("_HERMES_TUI_GATEWAY", "1")
    return project


def test_load_cli_config_preserves_pinned_cwd(_isolate, monkeypatch):
    from cli import load_cli_config

    load_cli_config()
    assert os.environ["TERMINAL_CWD"] == str(_isolate)
