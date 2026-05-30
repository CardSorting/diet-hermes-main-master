"""evaluate_governance_transform — central governance hook decision."""

from __future__ import annotations

import json

import pytest

from plugins.dietcode.lib.agent.governance_exemptions import (
    invalidate_governance_path_cache,
    enforce_governance_on_mutation,
    find_recent_governance_fault_payload,
    format_governance_recovery_terminal_response,
    is_governance_transform_result,
    looks_like_governance_suppression_response,
    parse_tool_result_payload,
    resolve_governance_validation_mode,
)


@pytest.fixture(autouse=True)
def _enable_governance_enforcement(monkeypatch):
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.governance_exemptions.is_governance_enforcement_enabled",
        lambda: True,
    )
    invalidate_governance_path_cache()
    yield
    invalidate_governance_path_cache()


def test_evaluate_returns_none_for_exempt_only_write():
    out = enforce_governance_on_mutation(
        "write_file",
        {"path": "README.md", "content": "# hi"},
        json.dumps({"bytes_written": 3}),
        run_gate=lambda files: {"success": False, "singleResults": [{"file": "x", "errors": ["bad"]}]},
    )
    assert out is None


def test_evaluate_blocks_governed_ts():
    gate_called: list[str] = []

    def fake_gate(files):
        gate_called.extend(files)
        return {
            "success": False,
            "singleResults": [
                {"file": files[0], "layer": "domain", "errors": ["missing tag"]},
            ],
        }

    out = enforce_governance_on_mutation(
        "patch",
        {"path": "src/domain/x.ts", "patch": "@@\n+const a=1"},
        json.dumps({"success": True}),
        run_gate=fake_gate,
    )
    assert out is not None
    payload = json.loads(out)
    assert is_governance_transform_result(payload)
    assert payload["dirty_files"] == ["src/domain/x.ts"]
    assert gate_called == ["src/domain/x.ts"]
    assert json.loads(payload["original_result"])["success"] is True


def test_evaluate_lists_exempt_skipped_on_block():
    out = enforce_governance_on_mutation(
        "patch",
        {
            "mode": "patch",
            "patch": "*** Update File: README.md\n@@\n+x\n*** Update File: src/a.ts\n@@\n+y\n",
        },
        json.dumps({"success": True}),
        run_gate=lambda files: {
            "success": False,
            "singleResults": [{"file": "src/a.ts", "layer": "core", "errors": ["x"]}],
        },
    )
    assert out is not None
    payload = json.loads(out)
    assert "README.md" in payload.get("exempt_skipped", [])
    assert payload["dirty_files"] == ["src/a.ts"]


def test_governance_recovery_plan_derives_import_queries():
    out = enforce_governance_on_mutation(
        "patch",
        {"path": "src/domain/x.ts", "patch": "@@\n+const a=1"},
        json.dumps({"success": True}),
        run_gate=lambda files: {
            "success": False,
            "singleResults": [
                {
                    "file": files[0],
                    "layer": "domain",
                    "errors": [
                        "DOMAIN layer in x.ts cannot import from ui (../ui/widget).",
                        "x.ts: Missing mandatory [LAYER: TYPE] header tag.",
                    ],
                }
            ],
        },
    )
    assert out is not None
    payload = json.loads(out)
    plan = payload.get("recovery_plan") or {}
    q1 = plan.get("search_files_phase1_queries") or []
    q2 = plan.get("search_files_phase2_queries") or []
    combined = plan.get("search_files_queries") or []
    assert "../ui/widget" in q1
    assert "from '../ui/widget'" in q1
    assert 'from "../ui/widget"' in q1
    assert "import '../ui/widget'" in q1
    assert "require('../ui/widget')" in q1
    # file-scoped hint (basename + spec)
    assert any(q.startswith("x.ts ../ui/widget") or q == "x.ts ../ui/widget" for q in q1)
    # phase2 carries anchors/snippets
    assert "[LAYER:" in q2
    assert combined[: len(q1)] == q1


def test_governance_fault_payload_uses_compact_model_error_and_detail():
    out = enforce_governance_on_mutation(
        "write_file",
        {"path": "src/domain/x.ts", "content": "x"},
        json.dumps({"bytes_written": 1}),
        run_gate=lambda files: {
            "success": False,
            "singleResults": [
                {"file": files[0], "layer": "domain", "errors": ["bad import"]},
            ],
        },
    )
    payload = json.loads(out)
    assert len(payload["error"]) < 1200
    assert "error_detail" in payload
    assert "====" in payload["error_detail"]
    assert payload.get("governance_fault") is True


def test_is_governance_transform_result_accepts_governance_fault_flag():
    assert is_governance_transform_result({"governance_fault": True, "error": "other"})


def test_find_recent_governance_fault_payload():
    wrapped = json.dumps({"governance_fault": True, "error": "GOVERNANCE FAULT: x"})
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "tool", "content": wrapped, "tool_call_id": "c1"},
    ]
    assert find_recent_governance_fault_payload(messages) is not None


def test_parse_tool_result_payload_with_appended_guardrail_guidance():
    base = json.dumps({"governance_fault": True, "error": "GOVERNANCE FAULT: x"})
    combined = base + "\n\n[Tool loop warning: governance_fault_warning; count=1; msg]"
    parsed = parse_tool_result_payload(combined)
    assert parsed is not None
    assert parsed.get("governance_fault") is True
    assert find_recent_governance_fault_payload(
        [{"role": "tool", "content": combined, "tool_call_id": "c1"}]
    ) is not None


def test_format_governance_recovery_terminal_response_includes_reads():
    text = format_governance_recovery_terminal_response(
        {
            "recovery_plan": {
                "read_file_targets": ["src/a.ts"],
                "search_files_phase1_queries": ["../ui/widget"],
            }
        }
    )
    assert "layering policy" in text
    assert "src/a.ts" in text
    assert "../ui/widget" in text


def test_looks_like_governance_suppression_response():
    assert looks_like_governance_suppression_response(
        "I apologize, but I cannot continue due to governance layer violations."
    )
    assert not looks_like_governance_suppression_response("Fixed the import in src/a.ts.")


def test_enforce_skips_when_tool_already_failed():
    gate_calls: list[list[str]] = []

    def fake_gate(files):
        gate_calls.append(list(files))
        return {"success": False, "singleResults": []}

    out = enforce_governance_on_mutation(
        "write_file",
        {"path": "src/domain/x.ts", "content": "export const x = 1;"},
        json.dumps({"error": "permission denied"}),
        run_gate=fake_gate,
    )
    assert out is None
    assert gate_calls == []


def test_gate_pass_cache_skips_repeat_validation(tmp_path):
    src = tmp_path / "src" / "domain" / "x.ts"
    src.parent.mkdir(parents=True)
    src.write_text("/** [LAYER: DOMAIN] */\nexport const x = 1;\n")
    path = str(src)
    gate_calls: list[list[str]] = []

    def fake_gate(files):
        gate_calls.append(list(files))
        return {"success": True}

    args = {"path": path, "content": src.read_text()}
    ok = json.dumps({"success": True})
    enforce_governance_on_mutation("write_file", args, ok, run_gate=fake_gate)
    enforce_governance_on_mutation("write_file", args, ok, run_gate=fake_gate)
    assert len(gate_calls) == 1


def test_resolve_validation_mode_auto_is_light_when_tags_optional(monkeypatch):
    monkeypatch.setattr(
        "plugins.dietcode.lib.agent.governance_exemptions.is_governance_layer_tags_required",
        lambda: False,
    )
    assert resolve_governance_validation_mode() == "light"
