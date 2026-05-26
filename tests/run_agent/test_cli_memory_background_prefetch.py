"""CLI/TUI skip queue_prefetch_all when memory.cli_skip_background_prefetch is true."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def agent_with_memory(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-test")
    from run_agent import AIAgent

    agent = object.__new__(AIAgent)
    agent.platform = "cli"
    agent.session_id = "sess-1"
    agent._memory_manager = MagicMock()
    agent._memory_manager.sync_all = MagicMock()
    agent._memory_manager.queue_prefetch_all = MagicMock()
    return agent


def test_mirror_turn_skips_background_prefetch_on_cli(agent_with_memory):
    with patch(
        "hermes_cli.config.cfg_get",
        return_value={"cli_skip_background_prefetch": True},
    ):
        agent_with_memory._sync_external_memory_for_turn(
            original_user_message="hello",
            final_response="world",
            interrupted=False,
        )

    agent_with_memory._memory_manager.sync_all.assert_called_once()
    agent_with_memory._memory_manager.queue_prefetch_all.assert_not_called()


def test_mirror_turn_queues_prefetch_when_config_disabled(agent_with_memory):
    with patch(
        "hermes_cli.config.cfg_get",
        return_value={"cli_skip_background_prefetch": False},
    ):
        agent_with_memory._sync_external_memory_for_turn(
            original_user_message="hello",
            final_response="world",
            interrupted=False,
        )

    agent_with_memory._memory_manager.queue_prefetch_all.assert_called_once()
