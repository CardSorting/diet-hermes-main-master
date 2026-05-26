"""MemoryManager throughput: skip background prefetch without external provider."""

from unittest.mock import MagicMock

from agent.memory_manager import MemoryManager


def test_prefetch_all_skips_without_external_provider():
    mgr = MemoryManager()
    builtin = MagicMock()
    builtin.name = "builtin"
    builtin.prefetch = MagicMock(return_value="should not run")
    mgr.add_provider(builtin)

    assert mgr.prefetch_all("hello", session_id="s1") == ""
    builtin.prefetch.assert_not_called()


def test_queue_prefetch_all_skips_without_external_provider():
    mgr = MemoryManager()
    builtin = MagicMock()
    builtin.name = "builtin"
    builtin.queue_prefetch = MagicMock()
    mgr.add_provider(builtin)

    mgr.queue_prefetch_all("next turn", session_id="s1")

    builtin.queue_prefetch.assert_not_called()
    assert mgr.has_external_provider is False


def test_queue_prefetch_all_runs_for_external_provider():
    mgr = MemoryManager()
    external = MagicMock()
    external.name = "mem0"
    external.queue_prefetch = MagicMock()
    mgr.add_provider(external)

    mgr.queue_prefetch_all("next turn", session_id="s1")

    external.queue_prefetch.assert_called_once_with("next turn", session_id="s1")
    assert mgr.has_external_provider is True
