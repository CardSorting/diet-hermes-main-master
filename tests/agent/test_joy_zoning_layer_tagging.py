"""Regression: layer-tag auto-injection vs PGA validation must not disagree."""

from __future__ import annotations

import json

import pytest

from agent.joy_zoning import (
    generate_layer_comment,
    get_layer,
    get_path_layer,
    parse_layer_tag,
    validate_joy_zoning,
)
from agent.tool_guardrails import classify_tool_failure
from agent.governance_exemptions import is_governance_transform_result


def test_get_path_layer_recognizes_broccolidb_core():
    assert get_path_layer("broccolidb/core/policy/SpiderEngine.ts") == "core"


def test_spider_engine_tag_aligns_with_path_layer():
    from pathlib import Path

    p = "broccolidb/core/policy/SpiderEngine.ts"
    content = Path(p).read_text(encoding="utf-8", errors="ignore")
    assert parse_layer_tag(content) == "core"
    assert get_path_layer(p) == "core"
    result = validate_joy_zoning(p, content)
    assert result["success"] is True
    assert not any("Geographic Misalignment" in e for e in result.get("errors", []))


def test_auto_inject_uses_path_layer_not_content_heuristics():
    """React in src/domain must not get a UI tag that PGA would reject."""
    content = "import React from 'react'\nexport const Foo = () => null\n"
    path = "src/domain/Foo.tsx"
    assert get_layer(path, content) == "ui"
    assert get_path_layer(path) == "domain"
    injected = generate_layer_comment(path, get_path_layer(path), content)
    audit = validate_joy_zoning(path, injected)
    assert audit["success"] is True
    assert parse_layer_tag(injected) == "domain"


def test_governance_transform_counts_as_tool_failure_for_guardrails():
    underlying = json.dumps({"bytes_written": 10})
    wrapped = json.dumps({
        "success": False,
        "error": "GOVERNANCE FAULT: JoyZoning Layering Violations Detected!",
        "original_result": underlying,
    })
    assert is_governance_transform_result(json.loads(wrapped))
    failed, suffix = classify_tool_failure("write_file", wrapped)
    assert failed is True
    assert "governance" in suffix
