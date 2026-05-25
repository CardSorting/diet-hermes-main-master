"""Resolve and pin the working directory for TUI / gateway sessions.

The Herm bundle runs with ``cwd`` set to ``herm-tui/`` inside the agent
checkout. Tooling, context files (AGENTS.md), path completion, and
``terminal`` must use the *user's* project directory — the shell cwd when
``hermes --tui`` / ``dietcode`` was invoked — not the bundle directory.

Environment contract (set by :func:`pin_launch_cwd` before spawning Herm):

- ``HERMES_CWD`` — launch workspace (Herm frontend → gateway child)
- ``TERMINAL_CWD`` — canonical cwd for tools and prompts (must match)
- ``_HERMES_TUI_GATEWAY=1`` — tells ``cli.load_cli_config()`` not to
  overwrite ``TERMINAL_CWD`` with ``os.getcwd()`` during lazy ``cli`` imports
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping

_CWD_PLACEHOLDERS = frozenset({".", "auto", "cwd"})
_TUI_GATEWAY_MARKER = "_HERMES_TUI_GATEWAY"
_PRESERVED_ENV_KEYS = frozenset({"HERMES_CWD", "TERMINAL_CWD"})


def _resolve_path(raw: str) -> Path | None:
    text = (raw or "").strip()
    if not text or text in _CWD_PLACEHOLDERS:
        return None
    try:
        path = Path(text).expanduser().resolve()
    except OSError:
        return None
    return path if path.is_dir() else None


def agent_root(agent_root: Path | None = None) -> Path:
    if agent_root is not None:
        return agent_root.resolve()
    return Path(__file__).resolve().parent.parent


def is_bundler_cwd(path: Path, root: Path | None = None) -> bool:
    """True when *path* is only the agent checkout or ``herm-tui/`` bundle."""
    base = agent_root(root)

    def _real(p: Path) -> Path | None:
        try:
            return Path(os.path.realpath(p))
        except OSError:
            try:
                return p.resolve()
            except OSError:
                return None

    resolved = _real(path)
    checkout = _real(base)
    bundle = _real(base / "herm-tui")
    if resolved is None or checkout is None or bundle is None:
        return False
    return resolved == checkout or resolved == bundle


def resolve_tui_launch_cwd(
    *,
    explicit: str | None = None,
    checkout_root: Path | None = None,
) -> str:
    """Return the directory tools and context files should use for this TUI run.

    Priority (non-explicit):

    When process cwd is **not** the bundle: ``getcwd`` → ``PWD`` → ``HERMES_CWD`` → ``TERMINAL_CWD``.

    When process cwd **is** the bundle (``herm-tui/``): ``PWD`` → ``HERMES_CWD`` →
    ``TERMINAL_CWD`` → ``getcwd`` — shell project dir beats stale exported env.
    """
    root = agent_root(checkout_root)

    if explicit:
        path = _resolve_path(explicit)
        if path is None:
            raise ValueError(f"Not a directory: {explicit}")
        return str(path)

    proc = Path.cwd().resolve()
    bundler = is_bundler_cwd(proc, root)

    ordered: list[str] = []
    pwd = (os.environ.get("PWD") or "").strip()
    hermes = (os.environ.get("HERMES_CWD") or "").strip()
    term = (os.environ.get("TERMINAL_CWD") or "").strip()
    if bundler:
        # Bun/herm-tui runs inside the bundle; shell PWD is the user's project.
        if pwd:
            ordered.append(pwd)
        if hermes:
            ordered.append(hermes)
        if term:
            ordered.append(term)
        ordered.append(str(proc))
    else:
        if not bundler:
            ordered.append(str(proc))
        if pwd:
            ordered.append(pwd)
        if hermes:
            ordered.append(hermes)
        if term:
            ordered.append(term)

    seen: set[str] = set()
    for raw in ordered:
        path = _resolve_path(raw)
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if bundler and is_bundler_cwd(path, root):
            continue
        return key

    return str(proc)


def pin_launch_cwd(
    env: MutableMapping[str, str],
    launch_cwd: str,
    *,
    checkout_root: Path | None = None,
) -> str:
    """Write launch cwd into *env* and mark the process as TUI-gateway pinned."""
    path = _resolve_path(launch_cwd)
    if path is None:
        raise ValueError(f"Not a directory: {launch_cwd}")
    key = str(path)
    env["HERMES_CWD"] = key
    env["TERMINAL_CWD"] = key
    env[_TUI_GATEWAY_MARKER] = "1"
    env.setdefault("HERMES_AGENT_ROOT", str(agent_root(checkout_root)))
    return key


def terminal_session_cwd() -> str:
    """Canonical session working directory (tools, @refs, context files)."""
    pinned = (os.environ.get("TERMINAL_CWD") or "").strip()
    if pinned and pinned not in _CWD_PLACEHOLDERS:
        path = _resolve_path(pinned)
        if path is not None:
            return str(path)
    hermes = (os.environ.get("HERMES_CWD") or "").strip()
    if hermes:
        path = _resolve_path(hermes)
        if path is not None:
            return str(path)
    checkout = os.environ.get("HERMES_AGENT_ROOT", "").strip()
    root = Path(checkout) if checkout else None
    return resolve_tui_launch_cwd(checkout_root=root)


def tui_gateway_pins_cwd() -> bool:
    """True when ``cli.load_cli_config`` must not rewrite ``TERMINAL_CWD``."""
    return os.environ.get(_TUI_GATEWAY_MARKER) == "1"


def snapshot_pinned_launch_cwd() -> str:
    """Capture launch cwd from env before dotenv / cli imports can rewrite it."""
    return (
        (os.environ.get("HERMES_CWD") or "").strip()
        or (os.environ.get("TERMINAL_CWD") or "").strip()
    )


def restore_pinned_launch_cwd(
    raw: str,
    *,
    checkout_root: Path | None = None,
) -> str | None:
    """Re-apply launch cwd after dotenv load (no-op when *raw* is empty/invalid)."""
    text = (raw or "").strip()
    if not text:
        return None
    return pin_launch_cwd(os.environ, text, checkout_root=checkout_root)


def preserved_workspace_env() -> dict[str, str]:
    """Return a copy of pinned workspace env keys (for dotenv load guards)."""
    if not tui_gateway_pins_cwd():
        return {}
    return {
        k: os.environ[k]
        for k in _PRESERVED_ENV_KEYS
        if (os.environ.get(k) or "").strip()
    }
