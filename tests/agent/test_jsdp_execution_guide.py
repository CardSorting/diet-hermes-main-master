"""Phase clarity for autonomous JSDP."""
from __future__ import annotations

from plugins.dietcode.lib.agent.joyzoning.jsdp_execution_guide import JsdpPhase, determine_phase


def test_phase_setup_when_no_cli():
    g = determine_phase(cli_ok=False, harness_present=False)
    assert g["phase"] == JsdpPhase.SETUP_JOYZONING.value
    assert g["setup_required"] is True
    assert g["agent_next_call"] is None


def test_phase_start_without_harness():
    g = determine_phase(cli_ok=True, harness_present=False)
    assert g["phase"] == JsdpPhase.START.value
    assert g["agent_next_call"] == "jsdp(action='start')"


def test_phase_execute_when_next_suggested():
    g = determine_phase(
        cli_ok=True,
        harness_present=True,
        horizon={"suggestedAction": "jz jsdp next"},
    )
    assert g["phase"] == JsdpPhase.EXECUTE.value
