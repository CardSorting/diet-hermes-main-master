# -*- coding: utf-8 -*-
"""Seamless install and auto-enable tests for DietCode."""
from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

import pytest


@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def test_apply_seamless_defaults_merges_config(profile_env):
    home = profile_env
    cfg_path = home / "config.yaml"
    cfg_path.write_text("toolsets:\n  - hermes-cli\nplugins:\n  enabled: []\n")

    from plugins.dietcode.install import apply_seamless_defaults

    result = apply_seamless_defaults(save=True)
    assert result["ok"] is True
    assert "toolsets" in result["changed"]
    assert "plugins.enabled" in result["changed"]

    text = cfg_path.read_text()
    assert "dietcode" in text


def test_plugin_manifest_auto_enable(tmp_path):
    from hermes_cli.plugins import PluginManifest, _plugin_manifest_auto_enable

    plugin_dir = tmp_path / "dietcode"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text("name: dietcode\nauto_enable: true\n")
    manifest = PluginManifest(
        name="dietcode",
        path=str(plugin_dir),
        source="user",
        kind="standalone",
    )
    assert _plugin_manifest_auto_enable(manifest) is True

    (plugin_dir / "plugin.yaml").write_text("name: dietcode\n")
    assert _plugin_manifest_auto_enable(manifest) is False


def test_auto_enable_loads_user_plugin(tmp_path, monkeypatch):
    """Drag-and-drop with auto_enable: true loads without manual plugins.enabled."""
    home = tmp_path / ".hermes"
    dest = home / "plugins" / "dietcode"
    src = Path(__file__).resolve().parents[2] / "plugins" / "dietcode"

    def _ignore(_dir, names):
        skip = {"node_modules", "__pycache__", ".pytest_cache"}
        return [n for n in names if n in skip]

    shutil.copytree(src, dest, ignore=_ignore, dirs_exist_ok=True)
    (home / "config.yaml").write_text("plugins:\n  enabled: []\ntoolsets:\n  - hermes-cli\n")

    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    for key in list(sys.modules):
        if key.startswith("hermes_plugins") or key.startswith("plugins.dietcode"):
            del sys.modules[key]

    import hermes_cli.plugins as plugins_mod

    importlib.reload(plugins_mod)
    plugins_mod.discover_plugins(force=True)

    pm = plugins_mod.get_plugin_manager()
    loaded = pm._plugins.get("dietcode")
    assert loaded is not None, list(pm._plugins.keys())
    assert loaded.enabled is True, loaded.error

    cfg = (home / "config.yaml").read_text()
    assert "dietcode" in cfg
