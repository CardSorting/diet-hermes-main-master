"""JoyZoning runtime configuration (Hermes-owned, not habitat UI config)."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

_config_cache: Optional["JoyZoningConfig"] = None
_config_cache_at: float = 0.0
_CONFIG_TTL = 30.0


def _resolve_secret(yaml_val: str, env_key: str) -> str:
    """Config.yaml value wins; env is fallback (secrets stay in .env)."""
    if yaml_val and str(yaml_val).strip():
        return str(yaml_val).strip()
    return os.environ.get(env_key, "").strip()


@dataclass(frozen=True)
class JoyZoningConfig:
    enabled: bool = False
    execution_journal: bool = False
    journal_path: str = ""
    review_before_complete: bool = True
    control_plane_url: str = ""
    control_plane_observe_only: bool = True
    ingest_token: str = ""
    habitat_bridge_token: str = ""
    emit_habitat_events: bool = True
    jsdp_enabled: bool = False
    jsdp_role: str = ""
    jsdp_chain_id: str = ""
    jsdp_harness_enabled: bool = False
    jsdp_workspace_root: str = ""
    jsdp_jz_cli: str = ""
    scope_id: str = ""

    @classmethod
    def load(cls) -> "JoyZoningConfig":
        try:
            from hermes_cli.config import load_config
            raw = load_config().get("joyzoning", {})
            if not isinstance(raw, dict):
                raw = {}
            conv = raw.get("convergence", {})
            if not isinstance(conv, dict):
                conv = {}
            cp = raw.get("control_plane", {})
            if not isinstance(cp, dict):
                cp = {}
            jsdp = raw.get("jsdp", {})
            if not isinstance(jsdp, dict):
                jsdp = {}
            harness = jsdp.get("harness", {})
            if not isinstance(harness, dict):
                harness = {}
            cp_url = str(cp.get("url") or os.environ.get("JOYZONING_CONTROL_PLANE_URL", "")).strip()
            observe_only = bool(cp.get("observe_only", True))
            if cp_url and not observe_only:
                raise ValueError(
                    "joyzoning.control_plane.observe_only must be true when control_plane.url is set "
                    "(habitat is observe-only; Hermes journal remains canonical)."
                )
            return cls(
                enabled=bool(raw.get("enabled", False)),
                execution_journal=bool(raw.get("execution_journal", False)),
                journal_path=str(raw.get("journal_path") or "").strip(),
                review_before_complete=bool(conv.get("review_before_complete", True)),
                control_plane_url=cp_url,
                control_plane_observe_only=observe_only,
                ingest_token=_resolve_secret(
                    str(cp.get("ingest_token") or raw.get("ingest_token") or ""),
                    "JOYZONING_INGEST_TOKEN",
                ),
                habitat_bridge_token=_resolve_secret(
                    str(cp.get("bridge_token") or raw.get("habitat_bridge_token") or ""),
                    "JOYZONING_HABITAT_BRIDGE_TOKEN",
                ),
                emit_habitat_events=bool(raw.get("emit_habitat_events", True)),
                jsdp_enabled=bool(jsdp.get("enabled", False)),
                jsdp_role=str(jsdp.get("role") or os.environ.get("JOYZONING_JSDP_ROLE", "")).strip(),
                jsdp_chain_id=str(jsdp.get("chain_id") or os.environ.get("JOYZONING_JSDP_CHAIN_ID", "")).strip(),
                jsdp_harness_enabled=bool(
                    harness.get(
                        "enabled",
                        jsdp.get("harness_enabled", raw.get("enabled", False)),
                    )
                ),
                jsdp_workspace_root=str(
                    harness.get("workspace_root")
                    or os.environ.get("JOYZONING_WORKSPACE_ROOT", "")
                ).strip(),
                jsdp_jz_cli=str(
                    harness.get("jz_cli") or os.environ.get("JOYZONING_JZ_CLI", "")
                ).strip(),
                scope_id=str(raw.get("scope_id") or os.environ.get("JOYZONING_SCOPE_ID", "")).strip(),
            )
        except ValueError:
            raise
        except Exception:
            return cls(
                scope_id=os.environ.get("JOYZONING_SCOPE_ID", "").strip(),
                jsdp_role=os.environ.get("JOYZONING_JSDP_ROLE", "").strip(),
                jsdp_chain_id=os.environ.get("JOYZONING_JSDP_CHAIN_ID", "").strip(),
                jsdp_harness_enabled=os.environ.get("JOYZONING_JSDP_HARNESS", "").strip().lower()
                in ("1", "true", "yes"),
                jsdp_workspace_root=os.environ.get("JOYZONING_WORKSPACE_ROOT", "").strip(),
                jsdp_jz_cli=os.environ.get("JOYZONING_JZ_CLI", "").strip(),
                control_plane_url=os.environ.get("JOYZONING_CONTROL_PLANE_URL", "").strip(),
                ingest_token=os.environ.get("JOYZONING_INGEST_TOKEN", "").strip(),
                habitat_bridge_token=os.environ.get("JOYZONING_HABITAT_BRIDGE_TOKEN", "").strip(),
            )


def get_joyzoning_config() -> JoyZoningConfig:
    global _config_cache, _config_cache_at
    now = time.monotonic()
    if _config_cache is None or (now - _config_cache_at) > _CONFIG_TTL:
        _config_cache = JoyZoningConfig.load()
        _config_cache_at = now
    return _config_cache


def read_scope_env(key: str) -> str:
    """Gateway contextvars first, then process env (CLI / kanban dispatcher)."""
    try:
        from gateway.session_context import get_session_env
        val = get_session_env(key, "").strip()
        if val:
            return val
    except ImportError:
        pass
    return os.environ.get(key, "").strip()


def resolve_scope_id(explicit: Optional[str] = None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    cfg = get_joyzoning_config()
    if cfg.scope_id:
        return cfg.scope_id
    for key in (
        "HERMES_KANBAN_TASK",
        "JOYZONING_SCOPE_ID",
        "JOYZONING_HABITAT_TASK",
        "HERMES_SESSION_ID",
        "HERMES_KANBAN_RUN_ID",
    ):
        val = read_scope_env(key)
        if val:
            return val
    return "default"
