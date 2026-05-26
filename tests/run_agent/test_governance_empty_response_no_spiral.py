"""Regression: empty responses after governance must not trigger retry spirals."""

from __future__ import annotations

import json
from unittest.mock import patch

from tests.run_agent.test_tool_call_guardrail_runtime import (
    _make_agent,
    _mock_response,
    _mock_tool_call,
)


def test_empty_after_governance_block_terminates_without_empty_retries():
    agent = _make_agent("write_file", max_iterations=10)
    args = {"path": "src/domain/x.ts", "content": "x"}
    governance_wrapped = json.dumps(
        {
            "success": False,
            "governance_fault": True,
            "error": "GOVERNANCE FAULT: blocked",
            "recovery_plan": {"read_file_targets": ["src/domain/x.ts"]},
        }
    )

    agent.client.chat.completions.create.side_effect = [
        _mock_response(
            content="",
            finish_reason="tool_calls",
            tool_calls=[_mock_tool_call("write_file", json.dumps(args), "call_w")],
        ),
        _mock_response(content="", finish_reason="stop"),
        _mock_response(content="", finish_reason="stop"),
        _mock_response(content="", finish_reason="stop"),
    ]

    with (
        patch("run_agent.handle_function_call", return_value=governance_wrapped),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("patch domain file")

    assert result["api_calls"] <= 2
    assert result["turn_exit_reason"] == "governance_recovery_needed"
    assert "layering policy" in result["final_response"].lower()


def test_refusal_text_after_governance_block_terminates_without_spiral():
    agent = _make_agent("write_file", max_iterations=10)
    args = {"path": "src/domain/x.ts", "content": "x"}
    governance_wrapped = json.dumps(
        {
            "success": False,
            "governance_fault": True,
            "error": "GOVERNANCE FAULT: blocked",
            "recovery_plan": {
                "read_file_targets": ["src/domain/x.ts"],
                "search_files_phase2_queries": ["[LAYER:"],
            },
        }
    )

    agent.client.chat.completions.create.side_effect = [
        _mock_response(
            content="",
            finish_reason="tool_calls",
            tool_calls=[_mock_tool_call("write_file", json.dumps(args), "call_w")],
        ),
        _mock_response(
            content="I'm sorry, but I cannot continue due to governance layer violations.",
            finish_reason="stop",
        ),
    ]

    with (
        patch("run_agent.handle_function_call", return_value=governance_wrapped),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("patch domain file")

    assert result["api_calls"] == 2
    assert result["turn_exit_reason"] == "governance_recovery_needed"
    assert "layering policy" in result["final_response"].lower()
    assert "read first" in result["final_response"].lower()
    assert "src/domain/x.ts" in result["final_response"]
