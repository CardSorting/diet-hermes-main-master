---
name: joyzoning-governed-work
description: JoyZoning governed mutation lifecycle for Hermes workers.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [joyzoning, convergence, kanban, governance]
    category: devops
    related_skills: [kanban-worker, kanban-orchestrator]
---

# JoyZoning Governed Work

Use when `joyzoning` tools are available on a kanban worker or governed API run.
Hermes owns execution state; operators review out-of-band before complete.

## When to Use

- Kanban worker spawned with `JOYZONING_SCOPE_ID` / `HERMES_KANBAN_TASK`
- JSDP delivery-chain roles (`JOYZONING_JSDP_ROLE` set)
- Long-horizon repo mutation with `.jsdp/` — pair with skill **`jsdp-rolling-horizon`** and tool **`jsdp`**

## Prerequisites

- `joyzoning.enabled: true` in config (required for lifecycle tools; off in upstream defaults)
- `dietcode` in `toolsets` (exposes joyzoning / broccolidb tools to the agent)

## How to Run

1. `joyzoning(action='context')` — scope, convergence state, `next_actions`
2. `joyzoning(action='begin', goal='…')` — open mutation scope
3. Implement with `patch` / `write_file`; `joyzoning(action='patch', …)` after edits
4. `joyzoning(action='verify', mutation_id=…, report='…')`
5. `joyzoning(action='request_review', summary='…')` — stop here
6. Operator calls `convergence_mark_converged(...)` after review
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
| Mark converged | `convergence_mark_converged(...)` |
| JSDP role | `joyzoning(action='role_context')` |
| Rolling horizon | `jsdp(action='start')` — see `jsdp-rolling-horizon` skill |

## Procedure

Combine with kanban worker flow: `kanban_show()` → `kanban_broccolidb_context()`
(if broccolidb present) → governed mutation lifecycle above →
`kanban_broccolidb_record()` → `kanban_complete()`.

## Pitfalls

- Layer governance applies to governable `.ts`/`.js` source only — not `.md`,
  `package.json`, SQL/migrations, or other non-layerable artifacts
- Do not `kanban_complete` before `request_review` + `convergence_mark_converged`
- `convergence_status` is Hermes journal state

## Verification

- `joyzoning(action='context')` shows `convergence_state: ready_for_review` before stopping
- After `convergence_mark_converged`, `convergence_state: converged` then `kanban_complete` succeeds
- `joyzoning(action='doctor')` reports journal and scope env healthy
