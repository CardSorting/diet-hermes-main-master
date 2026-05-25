"""JoyZoning emit_habitat_event fast path when journal and control plane are idle."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_joyzoning_singletons():
    import agent.joyzoning.config as cfg_mod
    from hermes_cli import config as hermes_config_mod

    cfg_mod._config_cache = None
    hermes_config_mod._LOAD_CONFIG_CACHE.clear()
    hermes_config_mod._RAW_CONFIG_CACHE.clear()
    yield
    cfg_mod._config_cache = None
    hermes_config_mod._LOAD_CONFIG_CACHE.clear()
    hermes_config_mod._RAW_CONFIG_CACHE.clear()


def test_emit_habitat_event_noops_when_enabled_but_no_sink(tmp_path, monkeypatch):
    home = tmp_path / ".dietcode"
    home.mkdir()
    (home / "config.yaml").write_text(
        "joyzoning:\n  enabled: true\n  execution_journal: false\n"
        "  control_plane:\n    url: \"\"\n"
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("DIETCODE_HOME", str(home))

    from agent.joyzoning.habitat_events import emit_habitat_event

    assert emit_habitat_event("tool.complete", scope_id="s1", payload={"tool": "x"}) is None
    assert not (home / "joyzoning" / "journal.db").exists()
