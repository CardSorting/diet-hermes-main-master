"""Kanban ↔ JoyZoning habitat linkage (persistent, no schema migration)."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

# Machine-readable footer in task body (survives dashboard/API round-trips).
_HABITAT_MARKER_RE = re.compile(
    r"<!--\s*joyzoning:habitat=([0-9a-fA-F-]{36})\s*-->",
    re.IGNORECASE,
)
_IDEMPOTENCY_PREFIX = "jz:habitat:"


def habitat_idempotency_key(habitat_task_id: str) -> str:
    """Stable Hermes kanban idempotency key for a habitat card GUID."""
    return f"{_IDEMPOTENCY_PREFIX}{str(habitat_task_id).strip().lower()}"


def parse_idempotency_habitat(idempotency_key: Optional[str]) -> Optional[str]:
    if not idempotency_key:
        return None
    key = str(idempotency_key).strip()
    if key.lower().startswith(_IDEMPOTENCY_PREFIX):
        guid = key[len(_IDEMPOTENCY_PREFIX):].strip()
        if guid:
            return guid
    return None


def extract_habitat_from_body(body: Optional[str]) -> Optional[str]:
    if not body:
        return None
    match = _HABITAT_MARKER_RE.search(body)
    return match.group(1) if match else None


def append_habitat_marker(body: Optional[str], habitat_task_id: str) -> str:
    """Append or replace habitat marker footer in task body."""
    guid = str(habitat_task_id).strip()
    marker = f"<!-- joyzoning:habitat={guid} -->"
    if not body or not str(body).strip():
        return marker
    text = str(body)
    if _HABITAT_MARKER_RE.search(text):
        return _HABITAT_MARKER_RE.sub(marker, text)
    return f"{text.rstrip()}\n\n{marker}\n"


def extract_habitat_from_metadata(metadata: Any) -> Optional[str]:
    if not metadata:
        return None
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return None
    if not isinstance(metadata, dict):
        return None
    for key in (
        "habitat_task",
        "JOYZONING_HABITAT_TASK",
        "joyzoning_task_id",
        "habitatTaskId",
        "habitat_task_id",
    ):
        val = metadata.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return None


def resolve_habitat_task_id(
    *,
    body: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    metadata: Any = None,
) -> Optional[str]:
    """Resolve habitat GUID from any persisted Hermes kanban linkage field."""
    return (
        extract_habitat_from_metadata(metadata)
        or parse_idempotency_habitat(idempotency_key)
        or extract_habitat_from_body(body)
    )


def linkage_metadata(habitat_task_id: str, **extra: Any) -> dict[str, Any]:
    """Metadata dict for task_runs / handoffs."""
    meta: dict[str, Any] = {
        "habitat_task": str(habitat_task_id).strip(),
        "JOYZONING_HABITAT_TASK": str(habitat_task_id).strip(),
        "joyzoning_scope": str(habitat_task_id).strip(),
    }
    meta.update(extra)
    return meta
