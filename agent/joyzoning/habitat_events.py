"""Habitat-compatible event stream — representational feed for JoyZoning observers."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from agent.joyzoning.boundaries import RuntimeLayer, layer_for_event
from agent.joyzoning.config import get_joyzoning_config, read_scope_env

logger = logging.getLogger(__name__)


def emit_habitat_event(
    event_type: str,
    *,
    scope_id: str = "",
    session_id: str = "",
    run_id: str = "",
    correlation_id: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Record operational event and optionally mirror to JoyZoning control plane (observe-only)."""
    cfg = get_joyzoning_config()
    if not cfg.enabled:
        return None
    will_journal = cfg.execution_journal
    will_mirror = bool(
        cfg.emit_habitat_events
        and cfg.control_plane_url
        and cfg.control_plane_observe_only
    )
    if not will_journal and not will_mirror:
        return None

    layer = layer_for_event(event_type)
    session_id = session_id or read_scope_env("HERMES_SESSION_ID")
    run_id = run_id or read_scope_env("HERMES_KANBAN_RUN_ID")

    event_id = None
    if cfg.execution_journal:
        from agent.joyzoning.journal import get_journal
        event_id = get_journal().append_event(
            event_type=event_type,
            layer=layer.value,
            scope_id=scope_id,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id,
            payload=payload,
        )

    if cfg.emit_habitat_events and cfg.control_plane_url and cfg.control_plane_observe_only:
        _mirror_to_control_plane(
            event_type=event_type,
            layer=layer,
            scope_id=scope_id,
            session_id=session_id,
            run_id=run_id,
            payload=payload or {},
        )

    return event_id


_mirror_executor: Optional[object] = None
_mirror_lock = threading.Lock()


def _mirror_executor_submit(fn) -> None:
    global _mirror_executor
    with _mirror_lock:
        if _mirror_executor is None:
            from concurrent.futures import ThreadPoolExecutor
            _mirror_executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="joyzoning-cp-mirror",
            )
        _mirror_executor.submit(fn)


def _mirror_to_control_plane(
    *,
    event_type: str,
    layer: RuntimeLayer,
    scope_id: str,
    session_id: str,
    run_id: str,
    payload: dict[str, Any],
) -> None:
    """Best-effort async mirror — habitat observes, does not authorize."""
    cfg = get_joyzoning_config()
    has_token = bool(cfg.ingest_token or __import__("os").environ.get("JOYZONING_INGEST_TOKEN", "").strip())
    if not has_token and cfg.control_plane_url:
        logger.debug(
            "habitat mirror skipped: ingest token not configured (set ingest_token in config)"
        )
        return

    def _send() -> None:
        try:
            from agent.joyzoning.control_plane_client import ControlPlaneClient
            result = ControlPlaneClient().emit_observation(
                event_type=event_type,
                layer=layer.value,
                scope_id=scope_id,
                session_id=session_id,
                run_id=run_id,
                payload=payload,
                timestamp=time.time(),
            )
            if result.get("success") is False and not result.get("skipped"):
                logger.warning(
                    "habitat observation mirror failed: %s",
                    result.get("error") or result,
                )
        except Exception as exc:
            logger.debug("habitat event mirror skipped: %s", exc)

    _mirror_executor_submit(_send)


def format_habitat_stream(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize journal rows for JoyZoning Watch / external consumers."""
    return [
        {
            "id": e.get("id"),
            "timestamp": e.get("timestamp"),
            "layer": e.get("layer"),
            "type": e.get("event_type"),
            "scopeId": e.get("scope_id"),
            "sessionId": e.get("session_id"),
            "runId": e.get("run_id"),
            "correlationId": e.get("correlation_id"),
            "payload": e.get("payload", {}),
            "source": "hermes-runtime",
        }
        for e in events
    ]
