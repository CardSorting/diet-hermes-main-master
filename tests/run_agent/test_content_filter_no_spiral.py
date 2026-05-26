"""Regression: finish_reason=content_filter must not trigger retry spirals."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _mock_response(content: str, finish_reason: str):
    msg = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def test_content_filter_returns_terminal_response_without_retries():
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("hermes_cli.config.load_config", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            max_iterations=10,
        )
    agent.client = MagicMock()
    agent._cached_system_prompt = "You are helpful."
    agent._use_prompt_caching = False
    agent.tool_delay = 0
    agent.compression_enabled = False
    agent.save_trajectories = False

    agent.client.chat.completions.create.side_effect = [
        _mock_response(content="", finish_reason="content_filter"),
    ]

    with (
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("do something that gets filtered")

    assert result["api_calls"] == 1
    assert result["turn_exit_reason"] == "content_filter"
    assert "content filter" in result["final_response"].lower()

