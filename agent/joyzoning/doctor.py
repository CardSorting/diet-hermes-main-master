"""JoyZoning production health checks — shared by tool and CLI."""
from __future__ import annotations

from typing import Any, Optional


def run_checks(*, scope_id: Optional[str] = None) -> dict[str, Any]:
    from agent.joyzoning.config import get_joyzoning_config, resolve_scope_id
    from agent.joyzoning.convergence import get_convergence_state
    from agent.joyzoning.journal import get_journal
    from agent.joyzoning.workflow import _resolve_cluster

    cfg = get_joyzoning_config()
    sid = resolve_scope_id(scope_id)
    state, anchor, cluster = _resolve_cluster(sid)
    checks: list[dict[str, Any]] = []

    def _check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    _check("joyzoning.enabled", cfg.enabled)
    _check("execution_journal", cfg.execution_journal)

    try:
        journal = get_journal()
        journal.get_convergence(anchor)
        integrity = journal.integrity_check()
        _check("journal_db", True, "readable")
        _check("journal_integrity", integrity.get("success") is True, str(integrity))
    except Exception as exc:
        _check("journal_db", False, str(exc))
        _check("journal_integrity", False, str(exc))

    _check("convergence_state", True, f"{state.value} (anchor={anchor}, cluster={len(cluster)})")

    if cfg.control_plane_url:
        try:
            from agent.joyzoning.control_plane_client import ControlPlaneClient
            client = ControlPlaneClient()
            health = client.health()
            reachable = health.get("success") is True and not health.get("skipped")
            _check("control_plane_health", reachable, str(health)[:400])
            ctx = client.agent_context()
            ctx_ok = ctx.get("success") is not False and not ctx.get("error")
            _check("control_plane_agent_context", ctx_ok, str(ctx.get("error") or "ok")[:200])
        except Exception as exc:
            _check("control_plane", False, str(exc))
    else:
        _check("control_plane", True, "not configured (local-only mode)")

    _check(
        "ingest_token_set",
        bool(cfg.ingest_token) or not cfg.control_plane_url,
        "joyzoning.control_plane.ingest_token or JOYZONING_INGEST_TOKEN",
    )
    _check(
        "bridge_token_set",
        bool(cfg.habitat_bridge_token) or not cfg.control_plane_url,
        "joyzoning.control_plane.bridge_token or JOYZONING_HABITAT_BRIDGE_TOKEN",
    )

    try:
        from agent.joyzoning.config import read_scope_env
        in_worker = bool(
            read_scope_env("HERMES_KANBAN_RUN_ID") or read_scope_env("HERMES_KANBAN_TASK")
        )
        has_kanban = bool(read_scope_env("HERMES_KANBAN_TASK"))
        has_habitat = bool(read_scope_env("JOYZONING_HABITAT_TASK"))
        _check(
            "scope_env_kanban",
            has_kanban or not in_worker,
            read_scope_env("HERMES_KANBAN_TASK") or ("unset" if not in_worker else "missing in worker"),
        )
        _check(
            "scope_env_habitat",
            has_habitat or not cfg.control_plane_url or not in_worker,
            read_scope_env("JOYZONING_HABITAT_TASK") or (
                "unset" if not in_worker else "missing habitat linkage in worker"
            ),
        )
    except Exception as exc:
        _check("scope_env", False, str(exc))

    ok = all(c["ok"] for c in checks)
    recommendations: list[str] = []
    if not cfg.enabled:
        recommendations.append("Set joyzoning.enabled: true in config.yaml")
    if cfg.enabled and cfg.control_plane_url and not cfg.ingest_token:
        recommendations.append(
            "Set joyzoning.control_plane.ingest_token (or JOYZONING_INGEST_TOKEN) "
            "to match JoyZoning ControlPlane:InternalToken"
        )
    if cfg.enabled and cfg.control_plane_url and not cfg.habitat_bridge_token:
        recommendations.append(
            "Set joyzoning.control_plane.bridge_token (or JOYZONING_HABITAT_BRIDGE_TOKEN) "
            "for habitat accept-merge → CONVERGED"
        )
    if cfg.enabled and not cfg.control_plane_url:
        recommendations.append(
            "Optional: joyzoning.control_plane.url http://127.0.0.1:9470 for habitat supervision"
        )
    for chk in checks:
        if not chk.get("ok"):
            recommendations.append(f"Fix: {chk.get('name')} — {chk.get('detail', '')}")

    return {
        "success": ok,
        "ok": ok,
        "scope_id": sid,
        "anchor_scope_id": anchor,
        "scope_cluster": cluster,
        "convergence_state": state.value,
        "checks": checks,
        "recommendations": recommendations,
    }
