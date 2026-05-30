# -*- coding: utf-8 -*-
"""Optional JoyZoning layering facade — no-ops when DietCode is not installed."""
from __future__ import annotations

from typing import Any, Callable, Optional

_JZ: Any = None
_JZ_TRIED = False


def _joy_zoning():
    global _JZ, _JZ_TRIED
    if not _JZ_TRIED:
        _JZ_TRIED = True
        try:
            from plugins.dietcode.lib.agent import joy_zoning

            _JZ = joy_zoning
        except ImportError:
            _JZ = None
    return _JZ


def _call(name: str, default: Any, *args: Any, **kwargs: Any) -> Any:
    jz = _joy_zoning()
    if jz is None:
        return default() if callable(default) else default
    fn: Optional[Callable[..., Any]] = getattr(jz, name, None)
    if fn is None:
        return default() if callable(default) else default
    return fn(*args, **kwargs)


def get_path_layer(file_path: str) -> Optional[str]:
    return _call("get_path_layer", lambda: None, file_path)


def parse_layer_tag(content: str) -> Optional[str]:
    return _call("parse_layer_tag", lambda: None, content)


def generate_layer_comment(file_path: str, layer: str, content: str) -> Optional[str]:
    return _call("generate_layer_comment", lambda: None, file_path, layer, content)


def validate_joy_zoning(
    file_path: str,
    content: str,
    *,
    require_layer_tags: bool = False,
) -> Optional[dict[str, Any]]:
    return _call(
        "validate_joy_zoning",
        lambda: None,
        file_path,
        content,
        require_layer_tags=require_layer_tags,
    )
