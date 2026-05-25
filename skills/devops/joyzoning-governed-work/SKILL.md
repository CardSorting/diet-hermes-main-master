---
name: joyzoning-governed-work
description: JoyZoning governed mutation lifecycle for Hermes workers.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [joyzoning, convergence, habitat, kanban, governance]
    category: devops
    related_skills: [kanban-worker, kanban-orchestrator]
---

# JoyZoning Governed Work

Use when Hermes runs under JoyZoning supervision (habitat :9470) or when
`joyzoning` tools are available. Hermes executes; habitat observes; operators
merge in the Watch/desktop UI.

## When to Use

- Kanban worker spawned with `JOYZONING_SCOPE_ID` / habitat-linked tasks
- JSDP delivery-chain roles (`JOYZONING_JSDP_ROLE` set)
- API runs with `metadata.JOYZONING_HABITAT_TASK` from habitat dispatch
- Long-horizon repo mutation with `.jsdp/` — pair with skill **`jsdp-rolling-horizon`** and tool **`jsdp_horizon`**

## Prerequisites

- `joyzoning.enabled: true` in config (default in diet-hermes)
- Optional: `joyzoning.control_plane.url: http://127.0.0.1:9470`
- Secrets in `config.yaml` under `joyzoning.control_plane` (`ingest_token`, `bridge_token`)
  or `.env`: `JOYZONING_INGEST_TOKEN`, `JOYZONING_HABITAT_BRIDGE_TOKEN`

## How to Run

1. `joyzoning(action='context')` — scope, convergence state, `next_actions`
2. `joyzoning(action='begin', goal='…')` — open mutation scope
3. Implement with `patch` / `write_file`; `joyzoning(action='patch', …)` after edits
4. `joyzoning(action='verify', mutation_id=…, report='…')`
5. `joyzoning(action='request_review', summary='…')` — stop here
6. Operator accept-merge in habitat (not in Hermes)
7. `kanban_complete(...)` — only after convergence allows

## Quick Reference

| Action | Tool |
|--------|------|
| Situation | `joyzoning(action='context')` |
| Health | `joyzoning(action='doctor')` |
| Start work | `joyzoning(action='begin', goal=…)` |
| After edits | `joyzoning(action='patch', mutation_id=…)` |
| Tests/checks | `joyzoning(action='verify', …)` |
| Hand off | `joyzoning(action='request_review', …)` |
| JSDP role | `joyzoning(action='role_context')` |
| Rolling horizon | `jsdp_horizon(action='export', nodes=3)` — see `jsdp-rolling-horizon` skill |

## Procedure

Combine with kanban worker flow: `kanban_show()` → `kanban_broccolidb_context()`
(if broccolidb present) → governed mutation lifecycle above →
`kanban_broccolidb_record()` → `kanban_complete()`.

## Pitfalls

- Do not call tools to self-mark CONVERGED when control plane is configured
- Do not `kanban_complete` before `request_review` + habitat merge
- Habitat UI “pet” state is not execution authority
- `convergence_status` is Hermes journal state, not Watch UI state

## Verification

- `joyzoning(action='context')` shows `convergence_state: ready_for_review` before stopping
- After habitat merge, `convergence_state: converged` then `kanban_complete` succeeds
- `joyzoning(action='doctor')` reports control plane healthy when :9470 is up
