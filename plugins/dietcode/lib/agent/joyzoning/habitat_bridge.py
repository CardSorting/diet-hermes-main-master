"""Habitat → Hermes convergence bridge (operator accept-merge only).

JoyZoning calls this after git accept-merge so Hermes journal transitions to CONVERGED
and kanban_complete can proceed. Habitat never self-authorizes via observation ingest.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def mark_operator_merge_accepted(
    scope_id: str,
    *,
    extra_scope_ids: Optional[list[str]] = None,
    token: str = "",
    summary: str = "",
) -> dict[str, Any]:
    """Transition Hermes-owned convergence to CONVERGED after habitat accept-merge."""
    from agent.joyzoning.config import get_joyzoning_config
    cfg = get_joyzoning_config()
    expected = cfg.habitat_bridge_token or os.environ.get("JOYZONING_HABITAT_BRIDGE_TOKEN", "").strip()
    if expected and token != expected:
        return {"success": False, "error": "forbidden", "message": "Invalid habitat bridge token."}

    if not scope_id or not str(scope_id).strip():
        return {"success": False, "error": "invalid_scope", "message": "scope_id is required."}

    from agent.joyzoning.scope_registry import cluster_convergence_state, register_scope_aliases

    scopes: list[str] = []
    for raw in [scope_id, *(extra_scope_ids or [])]:
        if raw and str(raw).strip() and str(raw).strip() not in scopes:
            scopes.append(str(raw).strip())
    if not scopes:
        return {"success": False, "error": "invalid_scope", "message": "scope_id is required."}

    register_scope_aliases(*scopes)
    primary = scopes[0]

    from agent.joyzoning.config import get_joyzoning_config
    from agent.joyzoning.convergence import ConvergenceState, get_convergence_state, transition_convergence
    from agent.joyzoning.habitat_events import emit_habitat_event

    cfg = get_joyzoning_config()
    if not cfg.enabled:
        return {"success": True, "skipped": True, "reason": "joyzoning disabled"}

    cluster_state, cluster_scope = cluster_convergence_state(scopes)
    if cluster_state == ConvergenceState.CONVERGED:
        return {
            "success": True,
            "scope_id": primary,
            "state": "converged",
            "already": True,
            "scopes": scopes,
        }

    if cluster_state not in (ConvergenceState.READY_FOR_REVIEW, ConvergenceState.VERIFYING):
        return {
            "success": False,
            "error": "invalid_state",
            "message": (
                f"Cannot mark converged from habitat while state is '{cluster_state.value}' "
                f"(scope {cluster_scope}). Worker must reach ready_for_review first."
            ),
            "current_state": cluster_state.value,
            "scopes": scopes,
        }

    _, anchor = cluster_convergence_state(scopes)
    ordered = [anchor] + [s for s in scopes if s != anchor]
    results = []
    for sid in ordered:
        current = get_convergence_state(sid)
        if current == ConvergenceState.CONVERGED:
            results.append({"scope_id": sid, "already": True})
            continue
        if current not in (ConvergenceState.READY_FOR_REVIEW, ConvergenceState.VERIFYING):
            results.append({
                "scope_id": sid,
                "success": True,
                "skipped": True,
                "reason": f"no lifecycle at {current.value}",
            })
            continue
        r = transition_convergence(
            ConvergenceState.CONVERGED,
            scope_id=sid,
            summary=summary or "Operator accept-merge in JoyZoning habitat",
            metadata={"source": "habitat.operator.merge_accepted", "cluster": scopes},
        )
        results.append(r)

    emit_habitat_event(
        "habitat.operator.merge_accepted",
        scope_id=primary,
        payload={"summary": summary or "accept-merge", "scopes": scopes},
    )
    for sid in scopes:
        if get_convergence_state(sid) != ConvergenceState.CONVERGED:
            transition_convergence(
                ConvergenceState.CONVERGED,
                scope_id=sid,
                summary=summary or "Operator accept-merge in JoyZoning habitat",
                metadata={"source": "habitat.operator.merge_accepted", "cluster": scopes, "mirrored": True},
                force=True,
            )

    ok = all(get_convergence_state(s) == ConvergenceState.CONVERGED for s in scopes)
    return {
        "success": ok,
        "scope_id": primary,
        "state": "converged",
        "scopes": scopes,
        "transitions": results,
        "bridge": "habitat_accept_merge",
    }
