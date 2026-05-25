"""Soda-themed status lines for the DietCode fork (CLI / TUI / shared copy).

Parody tone only — no trademarked slogans. Used when the active skin is ``dietcode``.
"""

from __future__ import annotations

import random
from typing import Optional

# Bubble spinner frames (display-width 1)
FIZZ_SPINNER_FRAMES = ["·", "∘", "○", "◌", "◎", "◉", "●", "◉", "◎", "◌", "○", "∘"]

SODA_TAGLINES = (
    "Just for the diff of it.",
    "Break builds, not hearts.",
    "The pause that refreshes your CI.",
    "Live fizzfully. Ship responsibly.",
    "Zero-calorie diffs · maximum fizz.",
    "Crack open a fresh patch.",
)

SODA_WAKE_LINES = (
    "DietCode is carbonated and ready — pop the tab with /help.",
    "Shaker loaded. Pour a task when you're ready.",
    "Bubbles rising… type a message or /help.",
)

SODA_GOODBYE_LINES = (
    "Stay fizzy!",
    "Tab closed — see you on the next pour.",
    "Can's empty. Until the next diff!",
)

# Tool completion verbs (soda metaphor)
SODA_TOOL_VERBS: dict[str, tuple[str, str]] = {
    "terminal": ("🥤", "pouring"),
    "patch": ("🫧", "fizz-patch"),
    "read_file": ("📖", "sip-read"),
    "write_file": ("✍️", "pour-write"),
    "search_files": ("🔎", "bubble-search"),
    "web_search": ("🔍", "fizz-search"),
    "web_extract": ("📄", "strain-fetch"),
    "delegate_task": ("🧊", "shake-delegate"),
    "execute_code": ("🐍", "brew-exec"),
    "todo": ("📋", "cap-list"),
    "memory": ("🧠", "foam-store"),
}

SODA_DONE_SUFFIXES = (
    " — all fizzy",
    " — poured clean",
    " — zero spill",
    " — tab sealed",
)

SODA_FAIL_SUFFIXES = (
    " — flat line",
    " — spill detected",
    " — over the pour line",
)


def is_dietcode_skin(skin_name: Optional[str] = None) -> bool:
    if skin_name:
        return skin_name.strip().lower() == "dietcode"
    try:
        from hermes_cli.skin_engine import get_active_skin_name

        return get_active_skin_name() == "dietcode"
    except Exception:
        return False


def pick_soda_tagline() -> str:
    return random.choice(SODA_TAGLINES)


def pick_soda_wake() -> str:
    return random.choice(SODA_WAKE_LINES)


def pick_soda_goodbye() -> str:
    return random.choice(SODA_GOODBYE_LINES)


def soda_tool_verb(tool_name: str) -> tuple[str, str]:
    """Return (emoji, verb) for a tool, with generic soda fallback."""
    if tool_name in SODA_TOOL_VERBS:
        return SODA_TOOL_VERBS[tool_name]
    return ("🫧", tool_name.replace("_", "-")[:9])


def soda_done_suffix(failed: bool = False) -> str:
    return random.choice(SODA_FAIL_SUFFIXES if failed else SODA_DONE_SUFFIXES)


def resolve_fizz_spinner_frames() -> list[str]:
    """Custom frames from skin, else built-in fizz cycle."""
    try:
        from hermes_cli.skin_engine import get_active_skin

        skin = get_active_skin()
        if skin and skin.name == "dietcode":
            raw = skin.spinner.get("frames")
            if isinstance(raw, list) and raw:
                return [str(f) for f in raw]
    except Exception:
        pass
    return list(FIZZ_SPINNER_FRAMES)


def resolve_spinner_type(default: str = "dots") -> str:
    try:
        from hermes_cli.skin_engine import get_active_skin

        skin = get_active_skin()
        if skin:
            st = skin.spinner.get("type")
            if isinstance(st, str) and st.strip():
                return st.strip()
    except Exception:
        pass
    return default
