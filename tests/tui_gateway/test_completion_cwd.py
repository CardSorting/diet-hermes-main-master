"""Path completion must anchor relative queries to TERMINAL_CWD."""

from __future__ import annotations

import os

import pytest


def test_completion_search_dir_uses_session_root(monkeypatch, tmp_path):
    session = tmp_path / "workspace"
    session.mkdir()
    sub = session / "src"
    sub.mkdir()
    (sub / "main.py").write_text("", encoding="utf-8")

    bundle = tmp_path / "herm-tui-bundle"
    bundle.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(session))
    monkeypatch.chdir(bundle)

    from tui_gateway.server import _completion_search_dir

    search_dir, match = _completion_search_dir("src/")
    assert os.path.normpath(search_dir) == os.path.normpath(str(sub))
    assert match == ""
    assert os.path.isdir(search_dir)
