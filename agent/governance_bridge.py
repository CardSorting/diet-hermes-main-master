# -*- coding: utf-8 -*-
"""Optional DietCode governance facade — no-ops when the plugin is not installed."""
from __future__ import annotations

from typing import Any, Callable, Optional

_GOV: Any = None
_GOV_TRIED = False


def _governance():
    global _GOV, _GOV_TRIED
    if not _GOV_TRIED:
        _GOV_TRIED = True
        try:
            from plugins.dietcode.lib.agent import governance_exemptions

            _GOV = governance_exemptions
        except ImportError:
            _GOV = None
    return _GOV


def _call(name: str, default: Any, *args: Any, **kwargs: Any) -> Any:
    gov = _governance()
    if gov is None:
        return default() if callable(default) else default
    fn: Optional[Callable[..., Any]] = getattr(gov, name, None)
    if fn is None:
        return default() if callable(default) else default
    return fn(*args, **kwargs)


def parse_tool_result_payload(text: str) -> dict[str, Any]:
    gov = _governance()
    if gov is not None:
        return gov.parse_tool_result_payload(text)
    from utils import safe_json_loads

    parsed = safe_json_loads(text)
    return parsed if isinstance(parsed, dict) else {}


def is_governance_transform_result(data: Any) -> bool:
    return bool(_call("is_governance_transform_result", lambda: False, data))


def is_governance_fault_error(text: str) -> bool:
    return bool(_call("is_governance_fault_error", lambda: False, text))


def resolve_governance_path_kind(path: str) -> str:
    return str(_call("resolve_governance_path_kind", lambda: "exempt", path))


def is_governance_subject_content(path: str, content: str) -> bool:
    return bool(_call("is_governance_subject_content", lambda: False, path, content))


def is_governance_layer_tags_required() -> bool:
    return bool(_call("is_governance_layer_tags_required", lambda: False))


def is_governance_enforcement_enabled() -> bool:
    return bool(_call("is_governance_enforcement_enabled", lambda: False))


def find_recent_governance_fault_payload(messages: list) -> Optional[dict[str, Any]]:
    return _call("find_recent_governance_fault_payload", lambda: None, messages)


def format_governance_recovery_terminal_response(payload: dict[str, Any]) -> str:
    return str(
        _call(
            "format_governance_recovery_terminal_response",
            lambda: "Governance policy blocked a mutation. Follow recovery_plan in the tool result.",
            payload,
        )
    )


def looks_like_governance_suppression_response(text: str) -> bool:
    return bool(_call("looks_like_governance_suppression_response", lambda: False, text))
