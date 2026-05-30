# -*- coding: utf-8 -*-
"""Thin facade from core Hermes to the optional DietCode plugin.

Core modules (``kanban_db``, gateway, CLI) import from here instead of
``plugins.dietcode.*`` directly so the dependency boundary stays explicit.
"""
from __future__ import annotations

import json
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_cli.kanban_db import Task


def joyzoning_completion_blocked_type() -> type[BaseException] | None:
    try:
        from plugins.dietcode.lib.agent.joyzoning.convergence_gate import (
            JoyZoningCompletionBlocked,
        )

        return JoyZoningCompletionBlocked
    except ImportError:
        return None


def assert_kanban_completion_allowed(task_id: str) -> None:
    """Raise when JoyZoning convergence policy blocks completion."""
    try:
        from plugins.dietcode.lib.agent.joyzoning.convergence_gate import (
            assert_kanban_completion_allowed as _assert,
        )

        _assert(task_id)
    except ImportError:
        return


def inject_joyzoning_worker_env(
    env: dict[str, Any],
    task: "Task",
    *,
    board: Optional[str] = None,
) -> None:
    """Pin JoyZoning scope ids for kanban worker subprocesses."""
    try:
        from plugins.dietcode.lib.agent.joyzoning.config import get_joyzoning_config
    except ImportError:
        return

    try:
        if not get_joyzoning_config().enabled:
            return
    except Exception:
        return

    env["JOYZONING_SCOPE_ID"] = task.id
    env["HERMES_KANBAN_TASK"] = task.id

    try:
        from plugins.dietcode.lib.agent.joyzoning.scope_registry import register_scope_aliases

        scopes = [task.id]
        if task.session_id:
            scopes.append(task.session_id)
        register_scope_aliases(*scopes)
    except Exception:
        pass


def inject_broccolidb_worker_env(env: dict[str, Any]) -> None:
    """Pin BroccoliDB paths for kanban workers when discoverable."""
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.runner import (
            resolve_broccolidb_db_path,
            resolve_broccolidb_root,
        )
        from plugins.dietcode.lib.tools.kanban_broccolidb_bridge import broccolidb_enabled
    except ImportError:
        return

    try:
        if not broccolidb_enabled():
            return
    except Exception:
        return

    root = resolve_broccolidb_root()
    if root:
        env["HERMES_BROCCOLIDB_ROOT"] = root
    db_path = resolve_broccolidb_db_path(root)
    if db_path:
        env["HERMES_BROCCOLIDB_DB"] = db_path


def run_joyzoning_doctor(*, scope_id: str | None = None) -> dict[str, Any]:
    """Run JoyZoning production checks (journal, scope env, JSDP harness)."""
    try:
        from plugins.dietcode.lib.agent.joyzoning.doctor import run_checks

        return run_checks(scope_id=scope_id)
    except ImportError:
        return {
            "ok": False,
            "success": False,
            "error": "DietCode plugin not installed",
            "checks": [],
            "recommendations": ["Install or enable plugins/dietcode"],
        }
    except Exception as exc:
        return {
            "ok": False,
            "success": False,
            "error": str(exc),
            "checks": [],
            "recommendations": [],
        }


def warn_if_dietcode_expected_but_missing() -> None:
    """Log when config expects DietCode but plugin registration failed."""
    import logging

    try:
        from plugins.dietcode.guard import dietcode_startup_expected, is_dietcode_plugin_registered
    except ImportError:
        return

    try:
        if dietcode_startup_expected() and not is_dietcode_plugin_registered():
            logging.getLogger(__name__).warning(
                "DietCode is enabled in config but the plugin did not register — "
                "run `/dietcode doctor` or check plugins.disabled / import errors"
            )
    except Exception:
        pass


# ─── BroccoliDB dashboard / RPC facade ───


def check_broccolidb_requirements() -> bool:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.runner import check_requirements

        return bool(check_requirements())
    except ImportError:
        return False


def resolve_broccolidb_root() -> str | None:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.runner import resolve_broccolidb_root as _resolve

        return _resolve()
    except ImportError:
        return None


def resolve_broccolidb_db_path(root: str | None = None) -> str | None:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.runner import resolve_broccolidb_db_path as _resolve

        return _resolve(root)
    except ImportError:
        return None


def broccolidb_rpc_available() -> bool:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import rpc_available

        return bool(rpc_available())
    except ImportError:
        return False


def broccolidb_rpc_version() -> str | None:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.db_native import RPC_VERSION

        return str(RPC_VERSION)
    except ImportError:
        return None


def warm_broccolidb_rpc(*, preload_agent: bool = False) -> None:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.db_native import warm_db_rpc

        warm_db_rpc(preload_agent=preload_agent)
    except ImportError:
        return
    except Exception:
        return


def run_broccolidb_rpc(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: int = 60,
) -> str:
    try:
        from plugins.dietcode.lib.tools.broccolidb_tools.runner import run_db_rpc

        return run_db_rpc(method, params, timeout=timeout)
    except ImportError:
        return '{"success": false, "error": "DietCode plugin not installed", "error_code": "PLUGIN_MISSING"}'
    except Exception as exc:
        return f'{{"success": false, "error": {json.dumps(str(exc))}, "error_code": "RPC_ERROR"}}'
