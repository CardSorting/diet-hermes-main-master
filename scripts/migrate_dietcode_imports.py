#!/usr/bin/env python3
"""One-shot import path migration for DietCode lib relocation."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REPLACEMENTS = [
    ("from tools.broccolidb_tools.", "from plugins.dietcode.lib.tools.broccolidb_tools."),
    ("import tools.broccolidb_tools.", "import plugins.dietcode.lib.tools.broccolidb_tools."),
    ("from tools.broccolidb_tools import", "from plugins.dietcode.lib.tools.broccolidb_tools import"),
    ("from tools.broccolidb import", "from plugins.dietcode.lib.tools.broccolidb import"),
    ("import tools.broccolidb", "import plugins.dietcode.lib.tools.broccolidb"),
    ("from tools.joyzoning_tools import", "from plugins.dietcode.lib.tools.joyzoning_tools import"),
    ("import tools.joyzoning_tools", "import plugins.dietcode.lib.tools.joyzoning_tools"),
    ("from tools.convergence_tools import", "from plugins.dietcode.lib.tools.convergence_tools import"),
    ("import tools.convergence_tools", "import plugins.dietcode.lib.tools.convergence_tools"),
    ("from tools.jsdp_harness_tools import", "from plugins.dietcode.lib.tools.jsdp_harness_tools import"),
    ("import tools.jsdp_harness_tools", "import plugins.dietcode.lib.tools.jsdp_harness_tools"),
    ("from tools.kanban_broccolidb_tools import", "from plugins.dietcode.lib.tools.kanban_broccolidb_tools import"),
    ("import tools.kanban_broccolidb_tools", "import plugins.dietcode.lib.tools.kanban_broccolidb_tools"),
    ("from tools.kanban_broccolidb_bridge import", "from plugins.dietcode.lib.tools.kanban_broccolidb_bridge import"),
    ("import tools.kanban_broccolidb_bridge", "import plugins.dietcode.lib.tools.kanban_broccolidb_bridge"),
    ("from agent.governance_exemptions import", "from plugins.dietcode.lib.agent.governance_exemptions import"),
    ("import agent.governance_exemptions", "import plugins.dietcode.lib.agent.governance_exemptions"),
    ("from agent.joy_zoning import", "from plugins.dietcode.lib.agent.joy_zoning import"),
    ("import agent.joy_zoning", "import plugins.dietcode.lib.agent.joy_zoning"),
    ("from agent.joyzoning.", "from plugins.dietcode.lib.agent.joyzoning."),
    ("import agent.joyzoning.", "import plugins.dietcode.lib.agent.joyzoning."),
    ("import agent.joyzoning as", "import plugins.dietcode.lib.agent.joyzoning as"),
    ("from agent.joyzoning import", "from plugins.dietcode.lib.agent.joyzoning import"),
    ("import agent.joyzoning", "import plugins.dietcode.lib.agent.joyzoning"),
]

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


def should_process(path: Path) -> bool:
    if path.suffix not in {".py", ".yml", ".yaml", ".md"}:
        return False
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return False
    if path.name == "migrate_dietcode_imports.py":
        return False
    return True


def migrate_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    for path in ROOT.rglob("*"):
        if path.is_file() and should_process(path):
            if migrate_file(path):
                changed.append(path.relative_to(ROOT))
    print(f"Updated {len(changed)} files")
    for p in sorted(changed)[:80]:
        print(f"  {p}")
    if len(changed) > 80:
        print(f"  ... and {len(changed) - 80} more")


if __name__ == "__main__":
    main()
