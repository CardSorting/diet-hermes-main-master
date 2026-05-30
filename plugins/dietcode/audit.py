# -*- coding: utf-8 -*-
"""Static and runtime audit helpers for DietCode production hardening."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Removed legacy shim plugin directories (must not reappear under plugins/).
REMOVED_LEGACY_PLUGIN_DIRS: frozenset[str] = frozenset({
    "joyzoning_governance",
    "joyzoning_runtime",
    "kanban_broccolidb",
    "jsdp_mutation",
})

# Diet runtime must not live under core Hermes paths (plugin-only surface).
FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "from tools.broccolidb",
    "from tools.joyzoning",
    "from tools.convergence",
    "from tools.jsdp_harness",
    "from tools.kanban_broccolidb",
    "from agent.joyzoning",
    "from agent.governance_exemptions",
    "import tools.broccolidb",
    "import agent.joyzoning",
    "from plugins.joyzoning_governance",
    "from plugins.joyzoning_runtime",
    "from plugins.kanban_broccolidb",
    "from plugins.jsdp_mutation",
    "import plugins.joyzoning_governance",
    "import plugins.joyzoning_runtime",
    "import plugins.kanban_broccolidb",
    "import plugins.jsdp_mutation",
)

# Paths allowed to reference old import strings (migration tooling only).
_IMPORT_AUDIT_ALLOWLIST: frozenset[str] = frozenset({
    "scripts/migrate_dietcode_imports.py",
})

_REQUIRED_RUNTIME_FILES: tuple[str, ...] = (
    "lib/runtime/governance_hooks.py",
    "lib/runtime/joyzoning_hooks.py",
    "lib/runtime/kanban_hooks.py",
    "lib/runtime/jsdp_hooks.py",
    "slash_commands.py",
    "lib/tools/broccolidb.py",
    "hooks.py",
    "contracts.py",
    "health.py",
    "guard.py",
    "tools_loader.py",
    "audit.py",
    "public.py",
)


def dietcode_plugin_root() -> Path:
    return Path(__file__).resolve().parent


def plugins_root() -> Path:
    return dietcode_plugin_root().parent


def runtime_layout_ok() -> tuple[bool, list[str]]:
    """Return (ok, missing relative paths) for canonical DietCode layout."""
    root = dietcode_plugin_root()
    missing = [rel for rel in _REQUIRED_RUNTIME_FILES if not (root / rel).is_file()]
    return not missing, missing


def legacy_shim_dirs_absent() -> tuple[bool, list[str]]:
    """Return (ok, present legacy directory names) — shims must be fully removed."""
    present = sorted(
        name
        for name in REMOVED_LEGACY_PLUGIN_DIRS
        if (plugins_root() / name).exists()
    )
    return not present, present


def scan_forbidden_imports(
    *,
    roots: Iterable[Path] | None = None,
    extensions: frozenset[str] = frozenset({".py"}),
) -> list[tuple[str, int, str]]:
    """Scan Python sources for deprecated diet import paths.

    Returns list of (relative_path, line_number, line_text).
    """
    if roots is None:
        repo = dietcode_plugin_root().parents[1]
        roots = (
            repo / "agent",
            repo / "tools",
            repo / "hermes_cli",
            repo / "gateway",
            repo / "plugins",
            repo / "tests",
            repo / "run_agent.py",
            repo / "cli.py",
            repo / "model_tools.py",
            repo / "batch_runner.py",
        )

    hits: list[tuple[str, int, str]] = []
    repo_root = dietcode_plugin_root().parents[1]

    def _scan_file(path: Path) -> None:
        rel = path.relative_to(repo_root).as_posix()
        if rel in _IMPORT_AUDIT_ALLOWLIST:
            return
        if rel.startswith("plugins/dietcode/"):
            return
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for prefix in FORBIDDEN_IMPORT_PREFIXES:
                if prefix in stripped:
                    hits.append((rel, i, stripped))
                    break

    for root in roots:
        if root.is_file() and root.suffix in extensions:
            _scan_file(root)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in extensions:
                continue
            if "plugins/dietcode" in path.as_posix():
                continue
            _scan_file(path)

    return hits


# Stale path markers that must not appear in fork integration docs (post-plugin migration).
STALE_DOC_PATH_MARKERS: tuple[str, ...] = (
    "tools/broccolidb.py",
    "tools/broccolidb_tools/",
    "tools.broccolidb_tools.",
    "plugins/joyzoning_governance",
    "plugins/kanban_broccolidb",
    "plugins/joyzoning_runtime",
    "plugins/jsdp_mutation",
)

_DOC_SCAN_PATHS: tuple[str, ...] = (
    "README.md",
    "docs/README.md",
    "docs/broccolidb-native-execution-throughput.md",
)


def scan_stale_doc_paths() -> list[tuple[str, int, str]]:
    """Return stale integration path references in key fork docs."""
    repo = dietcode_plugin_root().parents[1]
    hits: list[tuple[str, int, str]] = []
    for rel in _DOC_SCAN_PATHS:
        path = repo / rel
        if not path.is_file():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "plugins/dietcode/lib/tools/" in line:
                continue
            if "plugins.dietcode.lib.tools." in line:
                continue
            for marker in STALE_DOC_PATH_MARKERS:
                if marker in line:
                    hits.append((rel, i, line.strip()))
                    break
    return hits


def duplicate_diet_hooks() -> tuple[bool, list[str]]:
    """Detect duplicate non-dietcode transform/pre_tool hooks when dietcode is active."""
    try:
        from hermes_cli.plugins import get_plugin_manager
        from plugins.dietcode.guard import is_dietcode_plugin_registered

        if not is_dietcode_plugin_registered():
            return True, []

        pm = get_plugin_manager()
        issues: list[str] = []
        for hook_name in ("transform_tool_result", "pre_tool_call"):
            callbacks = pm._hooks.get(hook_name, [])
            non_diet = [
                getattr(cb, "__name__", repr(cb))
                for cb in callbacks
                if not getattr(cb, "__name__", "").startswith("dietcode_")
            ]
            if non_diet:
                issues.append(f"{hook_name}: non-dietcode callbacks {non_diet}")
        return not issues, issues
    except Exception as exc:
        return False, [f"hook audit failed: {exc}"]
