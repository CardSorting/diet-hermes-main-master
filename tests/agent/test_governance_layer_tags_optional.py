"""Layer tags are optional unless joyzoning.governance.layer_tags_required is true."""

from __future__ import annotations

import json

import pytest

import agent.governance_exemptions as governance_exemptions
from agent.joy_zoning import validate_joy_zoning


@pytest.fixture
def layer_tags_optional(monkeypatch):
    monkeypatch.setattr(
        "agent.governance_exemptions.is_governance_layer_tags_required",
        lambda: False,
    )
    monkeypatch.setattr(
        "tools.file_tools._should_auto_inject_layer_tags",
        lambda: False,
    )
    governance_exemptions.invalidate_governance_path_cache()
    yield
    governance_exemptions.invalidate_governance_path_cache()


@pytest.fixture
def layer_tags_required(monkeypatch):
    monkeypatch.setattr(
        "agent.governance_exemptions.is_governance_layer_tags_required",
        lambda: True,
    )
    monkeypatch.setattr(
        "tools.file_tools._should_auto_inject_layer_tags",
        lambda: True,
    )
    governance_exemptions.invalidate_governance_path_cache()
    yield
    governance_exemptions.invalidate_governance_path_cache()


def test_layer_tags_optional_by_default_in_config():
    from hermes_cli.config import DEFAULT_CONFIG

    gov = DEFAULT_CONFIG["joyzoning"]["governance"]
    assert gov.get("enabled") is True
    assert gov.get("layer_tags_required") is False
    assert gov.get("validation_mode") == "auto"


def test_governance_enforcement_disabled_skips_mutation_gate(monkeypatch):
    monkeypatch.setattr(
        "agent.governance_exemptions.is_governance_enforcement_enabled",
        lambda: False,
    )
    governance_exemptions.invalidate_governance_path_cache()
    from agent.governance_exemptions import enforce_governance_on_mutation

    out = enforce_governance_on_mutation(
        "write_file",
        {"path": "src/domain/x.ts", "content": "x"},
        json.dumps({"bytes_written": 1}),
        run_gate=lambda files: {
            "success": False,
            "singleResults": [{"file": files[0], "errors": ["bad"]}],
        },
    )
    assert out is None


def test_light_validation_skips_smell_heuristics(layer_tags_optional):
  """validation_mode=light keeps import rules but not class-count / any-type smells."""
  content = (
      "export class A {}\nexport class B {}\nexport class C {}\n"
      "export class D {}\n"
  )
  full = validate_joy_zoning(
      "src/domain/x.ts", content, require_layer_tags=False, validation_mode="full"
  )
  light = validate_joy_zoning(
      "src/domain/x.ts", content, require_layer_tags=False, validation_mode="light"
  )
  assert full["success"] is False
  assert any("Multiple classes" in e for e in full.get("errors", []))
  assert light["success"] is True


def test_validate_passes_without_layer_tag_when_optional(layer_tags_optional):
    assert governance_exemptions.is_governance_layer_tags_required() is False
    content = "export const x = 1;\n"
    result = validate_joy_zoning("src/domain/x.ts", content, require_layer_tags=False)
    assert result["success"] is True
    assert not any("Missing mandatory" in e for e in result.get("errors", []))


def test_validate_requires_tag_when_config_enabled(layer_tags_required):
    assert governance_exemptions.is_governance_layer_tags_required() is True
    content = "export const x = 1;\n"
    result = validate_joy_zoning("src/domain/x.ts", content, require_layer_tags=True)
    assert result["success"] is False
    assert any("Missing mandatory" in e for e in result.get("errors", []))


def test_write_file_tool_result_has_no_joyzoning_hint_when_optional(
    layer_tags_optional, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    ts = tmp_path / "src" / "domain" / "x.ts"
    ts.parent.mkdir(parents=True)
    ts.write_text("export const x = 1;\n")

    from tools.file_tools import write_file_tool

    out = json.loads(write_file_tool(str(ts.relative_to(tmp_path)), "export const y = 2;\n"))
    assert "_hint" not in out
    assert "JoyZoning" not in json.dumps(out)
