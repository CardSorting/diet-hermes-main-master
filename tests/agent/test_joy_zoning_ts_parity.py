# -*- coding: utf-8 -*-
"""Python ↔ TypeScript Joy-Zoning path-layer parity (fixed path matrix)."""
from __future__ import annotations

import json

import pytest

# Canonical paths both engines should classify identically (path-only, no content tag).
_PATH_LAYER_CASES: tuple[tuple[str, str], ...] = (
    ("src/domain/User.ts", "domain"),
    ("broccolidb/domain/models.ts", "domain"),
    ("src/core/engine.ts", "core"),
    ("broccolidb/core/mcp.ts", "core"),
    ("run_agent.py", "core"),
    ("agent/foo.py", "core"),
    ("src/infrastructure/db.ts", "infrastructure"),
    ("broccolidb/infrastructure/db/Config.ts", "infrastructure"),
    ("src/utils/helper.ts", "plumbing"),
    ("cli.py", "ui"),
    ("herm-tui/app.tsx", "ui"),
)


@pytest.mark.parametrize("file_path,expected", _PATH_LAYER_CASES)
def test_python_get_path_layer(file_path: str, expected: str):
    from plugins.dietcode.lib.agent.joy_zoning import get_path_layer

    assert get_path_layer(file_path) == expected


@pytest.mark.parametrize("file_path,expected", _PATH_LAYER_CASES)
def test_python_get_layer_matches_path_without_content(file_path: str, expected: str):
    from plugins.dietcode.lib.agent.joy_zoning import get_layer

    assert get_layer(file_path) == expected


def test_content_tag_overrides_path_layer():
    from plugins.dietcode.lib.agent.joy_zoning import get_layer

    content = "/** [LAYER: domain] */\nexport const x = 1;\n"
    assert get_layer("src/infrastructure/deep.ts", content=content) == "domain"


@pytest.mark.parametrize("file_path,expected", _PATH_LAYER_CASES)
def test_typescript_get_path_layer_matches_python(file_path: str, expected: str):
    from plugins.dietcode.lib.tools.broccolidb_tools.runner import check_requirements, run_standalone_script

    if not check_requirements():
        pytest.skip("BroccoliDB runtime not available")

    body = f"""
    const jz = await import('../utils/joy-zoning.js');
    const layer = jz.getPathLayer({json.dumps(file_path)});
    console.log(JSON.stringify({{ layer }}));
    """
    raw = run_standalone_script(body)
    data = json.loads(raw)
    if data.get("success") is False or (data.get("error") and "layer" not in data):
        pytest.fail(str(data))
    layer = data.get("layer")
    if layer is None and data.get("output"):
        layer = json.loads(data["output"]).get("layer")
    assert layer == expected
