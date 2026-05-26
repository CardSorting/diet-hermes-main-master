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


def test_aux_title_and_mutation_verifier_off_by_default():
    assert DEFAULT_CONFIG["display"]["auto_title"] is False
    assert DEFAULT_CONFIG["display"]["file_mutation_verifier"] is False


def test_tool_guardrails_and_compression_tuned_for_throughput():
    assert DEFAULT_CONFIG["tool_loop_guardrails"]["warnings_enabled"] is False
    assert DEFAULT_CONFIG["compression"]["protect_last_n"] == 25


def test_logging_and_model_catalog_quiet_by_default():
    assert DEFAULT_CONFIG["logging"]["level"] == "WARNING"
    assert DEFAULT_CONFIG["logging"]["memory_monitor"]["enabled"] is False
    assert DEFAULT_CONFIG["model_catalog"]["enabled"] is False
