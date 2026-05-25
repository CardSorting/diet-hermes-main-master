# -*- coding: utf-8 -*-
"""JSDP mutation provider plugin — transformation vocabulary, not execution authority."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _on_session_start(*, session_id: str = "", **_: Any) -> None:
    try:
        from agent.joyzoning.config import get_joyzoning_config, resolve_scope_id
        from agent.joyzoning.habitat_events import emit_habitat_event
        cfg = get_joyzoning_config()
        if not cfg.enabled or not cfg.jsdp_enabled:
            return
        if not cfg.jsdp_role:
            return
        emit_habitat_event(
            "jsdp.role_started",
            scope_id=resolve_scope_id(),
            session_id=session_id,
            payload={"role": cfg.jsdp_role, "chain_id": cfg.jsdp_chain_id},
        )
    except Exception as exc:
        logger.warning("jsdp_mutation on_session_start: %s", exc)


def register(ctx) -> None:
    ctx.register_hook("on_session_start", _on_session_start)
