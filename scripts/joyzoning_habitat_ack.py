#!/usr/bin/env python3
"""CLI entry for JoyZoning control plane — mark Hermes convergence after operator accept-merge."""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes habitat accept-merge → CONVERGED bridge")
    parser.add_argument("--scope", required=True, help="Habitat task id (GUID)")
    parser.add_argument("--kanban-task", default="", help="Hermes kanban task id (t_…)")
    parser.add_argument("--hermes-session", default="", help="Hermes session id from managed run")
    parser.add_argument("--token", default="", help="JOYZONING_HABITAT_BRIDGE_TOKEN")
    parser.add_argument("--summary", default="", help="Optional merge summary")
    args = parser.parse_args()

    from agent.joyzoning.habitat_bridge import mark_operator_merge_accepted

    extra = []
    if args.kanban_task:
        extra.append(args.kanban_task)
    if args.hermes_session:
        extra.append(args.hermes_session)

    result = mark_operator_merge_accepted(
        args.scope,
        extra_scope_ids=extra,
        token=args.token or "",
        summary=args.summary or "",
    )
    print(json.dumps(result))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
