"""_tui_need_bun_install / _tui_need_rebuild: Herm TUI install and build freshness."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def main_mod():
    import hermes_cli.main as m

    return m


def _touch_opentui(root: Path) -> None:
    marker = root / "node_modules" / "@opentui" / "core" / "package.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}")


def _touch_tui_entry(root: Path) -> None:
    entry = root / "dist" / "index.js"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("console.log('tui')")


def test_need_install_when_opentui_missing(tmp_path: Path, main_mod) -> None:
    (tmp_path / "bun.lock").write_text("{}")
    assert main_mod._tui_need_bun_install(tmp_path) is True


def test_no_install_when_lock_older_than_marker(tmp_path: Path, main_mod) -> None:
    _touch_opentui(tmp_path)
    (tmp_path / "bun.lock").write_text("{}")
    os.utime(tmp_path / "bun.lock", (100, 100))
    os.utime(tmp_path / "node_modules" / "@opentui" / "core" / "package.json", (200, 200))
    assert main_mod._tui_need_bun_install(tmp_path) is False


def test_need_install_when_lock_newer_than_marker(tmp_path: Path, main_mod) -> None:
    _touch_opentui(tmp_path)
    (tmp_path / "bun.lock").write_text("{}")
    os.utime(tmp_path / "bun.lock", (200, 200))
    os.utime(tmp_path / "node_modules" / "@opentui" / "core" / "package.json", (100, 100))
    assert main_mod._tui_need_bun_install(tmp_path) is True


def test_no_install_without_lockfile_when_opentui_present(tmp_path: Path, main_mod) -> None:
    _touch_opentui(tmp_path)
    assert main_mod._tui_need_bun_install(tmp_path) is False


def test_no_install_prebuilt_bundle_mode(tmp_path: Path, main_mod) -> None:
    _touch_tui_entry(tmp_path)
    assert main_mod._tui_need_bun_install(tmp_path) is False


def test_need_rebuild_when_tui_bundle_missing(tmp_path: Path, main_mod) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.tsx").write_text("console.log('src')")

    assert main_mod._tui_need_rebuild(tmp_path) is True


def test_no_rebuild_when_tui_bundle_newer_than_inputs(tmp_path: Path, main_mod) -> None:
    _touch_tui_entry(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.tsx").write_text("console.log('src')")
    os.utime(src / "index.tsx", (100, 100))
    os.utime(tmp_path / "dist" / "index.js", (200, 200))

    assert main_mod._tui_need_rebuild(tmp_path) is False


def test_rebuild_when_tui_source_newer_than_bundle(tmp_path: Path, main_mod) -> None:
    _touch_tui_entry(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.tsx").write_text("console.log('src')")
    os.utime(tmp_path / "dist" / "index.js", (100, 100))
    os.utime(src / "index.tsx", (200, 200))

    assert main_mod._tui_need_rebuild(tmp_path) is True


def test_make_tui_argv_skips_build_only_on_termux_when_fresh(
    tmp_path: Path, main_mod, monkeypatch
) -> None:
    _touch_tui_entry(tmp_path)
    monkeypatch.setenv("TERMUX_VERSION", "1")
    monkeypatch.setattr(main_mod, "_tui_need_bun_install", lambda _root: False)
    monkeypatch.setattr(main_mod, "_tui_need_rebuild", lambda _root: False)
    monkeypatch.setattr(main_mod, "_bun_bin", lambda: "/bin/bun")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("fresh Termux TUI launch must not rebuild")

    monkeypatch.setattr(main_mod.subprocess, "run", fail_run)

    argv, cwd = main_mod._make_tui_argv(tmp_path, tui_dev=False)

    assert argv == ["/bin/bun", str(tmp_path / "dist" / "index.js")]
    assert cwd == tmp_path


def test_make_tui_argv_skips_build_when_bundle_is_fresh(
    tmp_path: Path, main_mod, monkeypatch
) -> None:
    _touch_tui_entry(tmp_path)
    monkeypatch.setattr(main_mod, "_tui_need_bun_install", lambda _root: False)
    monkeypatch.setattr(main_mod, "_tui_need_rebuild", lambda _root: False)
    monkeypatch.setattr(main_mod, "_bun_bin", lambda: "/bin/bun")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("fresh TUI launch must not rebuild")

    monkeypatch.setattr(main_mod.subprocess, "run", fail_run)

    argv, cwd = main_mod._make_tui_argv(tmp_path, tui_dev=False)

    assert argv == ["/bin/bun", str(tmp_path / "dist" / "index.js")]
    assert cwd == tmp_path
