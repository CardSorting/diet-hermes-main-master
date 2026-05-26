"""Deferred session persistence (DietCode throughput default)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _minimal_agent() -> AIAgent:
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
        )
    agent._session_persist_incremental = False
    agent._session_db = MagicMock()
    return agent


def test_persist_session_skips_db_and_log_when_not_incremental():
    agent = _minimal_agent()
    with (
        patch.object(agent, "_save_session_log") as mock_log,
        patch.object(agent, "_flush_messages_to_session_db") as mock_flush,
    ):
        agent._persist_session([{"role": "user", "content": "hello"}])
    mock_log.assert_not_called()
    mock_flush.assert_not_called()
    assert agent._session_messages == [{"role": "user", "content": "hello"}]


def test_persist_session_flushes_when_incremental_enabled():
    agent = _minimal_agent()
    agent._session_persist_incremental = True
    with (
        patch.object(agent, "_save_session_log") as mock_log,
        patch.object(agent, "_flush_messages_to_session_db") as mock_flush,
    ):
        agent._persist_session([{"role": "user", "content": "hello"}])
    mock_log.assert_called_once()
    mock_flush.assert_called_once()


def test_flush_deferred_session_persist_writes_at_turn_end():
    agent = _minimal_agent()
    agent._session_persist_incremental = False
    with (
        patch.object(agent, "_save_session_log") as mock_log,
        patch.object(agent, "_flush_messages_to_session_db") as mock_flush,
    ):
        agent._flush_deferred_session_persist(
            [{"role": "user", "content": "hello"}],
            conversation_history=[],
        )
    mock_log.assert_called_once()
    mock_flush.assert_called_once()
    assert agent._session_messages == [{"role": "user", "content": "hello"}]
