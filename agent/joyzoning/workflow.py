"""JoyZoning workflow hints — what the agent should do next (Hermes authority)."""
from __future__ import annotations

from typing import Any, Optional

from agent.joyzoning.convergence import ConvergenceState
from agent.joyzoning.config import get_joyzoning_config, read_scope_env, resolve_scope_id


def _scope_bindings() -> dict[str, str]:
    keys = (
        "JOYZONING_HABITAT_TASK",
        "JOYZONING_SCOPE_ID",
        "HERMES_KANBAN_TASK",
        "HERMES_KANBAN_BOARD",
        "HERMES_KANBAN_RUN_ID",
        "HERMES_SESSION_ID",
    )
    out: dict[str, str] = {}
    for key in keys:
        val = read_scope_env(key)
        if val:
            out[key] = val
    return out


def recommended_next_actions(state: ConvergenceState) -> list[str]:
    """Human- and model-readable next steps for the governed mutation lifecycle."""
    if state == ConvergenceState.IDLE:
        return [
            "joyzoning(action='begin', goal='…') or mutation_begin(goal=…)",
            "If JSDP: joyzoning(action='role_context') first",
        ]
    if state == ConvergenceState.PROPOSED:
        return [
            "Implement the plan (patch/write tools)",
            "joyzoning(action='patch', mutation_id=…, summary='…') after substantive edits",
        ]
    if state == ConvergenceState.PATCHING:
        return [
            "Run verification (tests, lint)",
            "joyzoning(action='verify', mutation_id=…, report='…')",
        ]
    if state == ConvergenceState.VERIFYING:
        return [
            "joyzoning(action='request_review', summary='…')",
        ]
    if state == ConvergenceState.READY_FOR_REVIEW:
        return [
            "Stop — operator reviews in JoyZoning habitat (accept-merge)",
            "Do not kanban_complete until habitat marks converged",
        ]
    if state == ConvergenceState.CONVERGED:
        return [
            "kanban_complete(...) is allowed when review gate satisfied",
        ]
    if state == ConvergenceState.REJECTED:
        return [
            "joyzoning(action='begin', goal='…') to start a new mutation scope",
        ]
    return ["joyzoning(action='context') to refresh state"]


def _resolve_cluster(scope_id: str) -> tuple[ConvergenceState, str, list[str]]:
    from agent.joyzoning.convergence import get_convergence_state
    from agent.joyzoning.scope_registry import cluster_convergence_state, expand_scope_cluster

    cluster = expand_scope_cluster(scope_id)
    state, anchor = cluster_convergence_state(cluster)
    if state == ConvergenceState.IDLE and anchor:
        state = get_convergence_state(anchor)
    return state, anchor or scope_id, cluster


def build_operational_context(*, scope_id: str | None = None) -> dict[str, Any]:
    """Unified situational snapshot for the joyzoning primitive tool."""
    cfg = get_joyzoning_config()
    sid = resolve_scope_id(scope_id)
    state, anchor_scope, scope_cluster = _resolve_cluster(sid)
    bindings = _scope_bindings()

    cp_health: dict[str, Any] = {"configured": bool(cfg.control_plane_url)}
    habitat_context: dict[str, Any] | None = None
    habitat_manifest: dict[str, Any] | None = None

    if cfg.control_plane_url:
        from agent.joyzoning.control_plane_client import ControlPlaneClient
        client = ControlPlaneClient()
        cp_health = client.health()
        habitat_context = client.agent_context()
        if habitat_context.get("success") is not False and not habitat_context.get("error"):
            try:
                habitat_manifest = client.agent_manifest()
            except Exception as exc:
                habitat_manifest = {"success": False, "error": str(exc)}

    journal_row = None
    active_mutation: Optional[dict[str, Any]] = None
    journal_integrity: dict[str, Any] = {"success": True}
    try:
        from agent.joyzoning.journal import get_journal
        journal = get_journal()
        journal_row = journal.get_convergence(anchor_scope)
        active_mutation = journal.get_active_mutation(anchor_scope)
        journal_integrity = journal.integrity_check()
    except Exception as exc:
        journal_integrity = {"success": False, "error": str(exc)}

    gate_message = None
    try:
        from agent.joyzoning.convergence import require_review_before_complete
        gate_message = require_review_before_complete(anchor_scope)
    except Exception:
        pass

    return {
        "success": True,
        "scope_id": sid,
        "anchor_scope_id": anchor_scope,
        "scope_cluster": scope_cluster,
        "convergence_state": state.value,
        "kanban_complete_allowed": gate_message is None,
        "kanban_complete_block_reason": gate_message,
        "scope_bindings": bindings,
        "active_mutation": active_mutation,
        "config": {
            "enabled": cfg.enabled,
            "review_before_complete": cfg.review_before_complete,
            "control_plane_url": cfg.control_plane_url or None,
            "ingest_token_configured": bool(cfg.ingest_token),
            "bridge_token_configured": bool(cfg.habitat_bridge_token),
            "jsdp_enabled": cfg.jsdp_enabled,
            "jsdp_role": cfg.jsdp_role or None,
        },
        "control_plane": cp_health,
        "habitat_agent_context": habitat_context,
        "habitat_agent_manifest": habitat_manifest,
        "convergence_record": journal_row,
        "journal_integrity": journal_integrity,
        "next_actions": recommended_next_actions(state),
        "authority": {
            "execution": "hermes",
            "supervision": "joyzoning_habitat",
            "merge_gate": "habitat_operator",
        },
    }
