"""DietCode fork: throughput-oriented DEFAULT_CONFIG defaults."""

from hermes_cli.config import DEFAULT_CONFIG


def test_compression_threshold_defers_aux_summarization():
    assert DEFAULT_CONFIG["compression"]["threshold"] == 0.65


def test_background_review_nudges_disabled_by_default():
    assert DEFAULT_CONFIG["memory"]["nudge_interval"] == 0
    assert DEFAULT_CONFIG["skills"]["creation_nudge_interval"] == 0


def test_curator_and_joyzoning_off_by_default():
    assert DEFAULT_CONFIG["curator"]["enabled"] is False
    assert DEFAULT_CONFIG["joyzoning"]["enabled"] is False
    assert DEFAULT_CONFIG["joyzoning"]["execution_journal"] is False


def test_tui_tool_progress_emits_start_complete_only():
    assert DEFAULT_CONFIG["display"]["tool_progress"] == "new"
