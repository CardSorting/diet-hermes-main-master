# -*- coding: utf-8 -*-
"""Tests for drag-and-drop plugin namespace bootstrap."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _plugin_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "plugins" / "dietcode"


def test_drag_drop_bootstrap_aliases_plugins_dietcode():
    """Simulate Hermes loading ~/.hermes/plugins/dietcode as hermes_plugins.dietcode."""
    plugin_dir = _plugin_dir()
    init_file = plugin_dir / "__init__.py"
    assert init_file.is_file(), init_file

    for key in list(sys.modules):
        if key == "plugins" or key.startswith("plugins.dietcode") or key.startswith("hermes_plugins.dietcode"):
            del sys.modules[key]

    loaded_name = "hermes_plugins.dietcode"
    spec = importlib.util.spec_from_file_location(
        loaded_name,
        init_file,
        submodule_search_locations=[str(plugin_dir)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = loaded_name
    module.__path__ = [str(plugin_dir)]  # type: ignore[attr-defined]
    sys.modules[loaded_name] = module
    spec.loader.exec_module(module)

    assert "plugins.dietcode" in sys.modules
    assert sys.modules["plugins.dietcode"] is sys.modules[loaded_name]

    from plugins.dietcode.guard import is_dietcode_plugin_registered

    assert callable(is_dietcode_plugin_registered)
    assert callable(module.register)
