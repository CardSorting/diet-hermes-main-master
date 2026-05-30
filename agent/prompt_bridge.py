# -*- coding: utf-8 -*-
"""Generic plugin prompt-extension bridge — core stays plugin-name agnostic."""
from __future__ import annotations

from typing import AbstractSet, Callable, Optional


def resolve_plugin_prompt_guidance(
    builder_attr: str,
    valid_tool_names: AbstractSet[str],
) -> str:
    """Call a prompt builder registered on PluginManager by attribute name."""
    if not valid_tool_names:
        return ""
    try:
        from hermes_cli.plugins import get_plugin_manager

        pm = get_plugin_manager()
        builder: Optional[Callable[..., str]] = getattr(pm, builder_attr, None)
        if callable(builder):
            result = builder(valid_tool_names)
            return result if isinstance(result, str) else ""
    except Exception:
        pass
    return ""
