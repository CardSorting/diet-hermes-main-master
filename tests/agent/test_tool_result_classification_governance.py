"""Governance-aware file mutation result classification."""

from __future__ import annotations

import json

from agent.tool_result_classification import file_mutation_result_landed


def test_governance_block_preserves_landed_via_original_result():
    underlying = json.dumps({"bytes_written": 42})
    wrapped = json.dumps({
        "success": False,
        "error": "GOVERNANCE FAULT: JoyZoning Layering Violations Detected!",
        "original_result": underlying,
    })
    assert file_mutation_result_landed("write_file", wrapped) is True


def test_patch_landed_via_original_result():
    underlying = json.dumps({"success": True})
    wrapped = json.dumps({
        "error": "GOVERNANCE FAULT: blocked",
        "original_result": underlying,
    })
    assert file_mutation_result_landed("patch", wrapped) is True
