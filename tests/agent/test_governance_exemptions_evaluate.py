"""evaluate_governance_transform — central governance hook decision."""

from __future__ import annotations

import json

from agent.governance_exemptions import (
    evaluate_governance_transform,
    is_governance_transform_result,
)


def test_evaluate_returns_none_for_exempt_only_write():
    out = evaluate_governance_transform(
        "write_file",
        {"path": "README.md", "content": "# hi"},
        json.dumps({"bytes_written": 3}),
        run_gate=lambda files: {"success": False, "singleResults": [{"file": "x", "errors": ["bad"]}]},
    )
    assert out is None


def test_evaluate_blocks_governed_ts():
    gate_called: list[str] = []

    def fake_gate(files):
        gate_called.extend(files)
        return {
            "success": False,
            "singleResults": [
                {"file": files[0], "layer": "domain", "errors": ["missing tag"]},
            ],
        }

    out = evaluate_governance_transform(
        "patch",
        {"path": "src/domain/x.ts", "patch": "@@\n+const a=1"},
        json.dumps({"success": True}),
        run_gate=fake_gate,
    )
    assert out is not None
    payload = json.loads(out)
    assert is_governance_transform_result(payload)
    assert payload["dirty_files"] == ["src/domain/x.ts"]
    assert gate_called == ["src/domain/x.ts"]
    assert json.loads(payload["original_result"])["success"] is True


def test_evaluate_lists_exempt_skipped_on_block():
    out = evaluate_governance_transform(
        "patch",
        {
            "mode": "patch",
            "patch": "*** Update File: README.md\n@@\n+x\n*** Update File: src/a.ts\n@@\n+y\n",
        },
        json.dumps({"success": True}),
        run_gate=lambda files: {
            "success": False,
            "singleResults": [{"file": "src/a.ts", "layer": "core", "errors": ["x"]}],
        },
    )
    assert out is not None
    payload = json.loads(out)
    assert "README.md" in payload.get("exempt_skipped", [])
    assert payload["dirty_files"] == ["src/a.ts"]
