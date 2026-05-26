"""Shared helpers for classifying tool result payloads."""

from __future__ import annotations

import json
from typing import Any


FILE_MUTATING_TOOL_NAMES = frozenset({"write_file", "patch"})


def file_mutation_result_landed(tool_name: str, result: Any) -> bool:
    """Return True when a file mutation result proves the write landed."""
    if tool_name not in FILE_MUTATING_TOOL_NAMES or not isinstance(result, str):
        return False
    try:
        data = json.loads(result.strip())
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("error"):
        # Governance hook may replace the visible result while preserving the
        # underlying successful write in original_result.
        orig = data.get("original_result")
        if orig is not None:
            orig_str = orig if isinstance(orig, str) else json.dumps(orig)
            return file_mutation_result_landed(tool_name, orig_str)
        return False
    if tool_name == "write_file":
        return "bytes_written" in data
    if tool_name == "patch":
        return data.get("success") is True
    return False
