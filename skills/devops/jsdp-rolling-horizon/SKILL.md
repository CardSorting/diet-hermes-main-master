---
name: jsdp-rolling-horizon
description: Autonomous JSDP — jsdp(start|apply|advance|guide), zero operator setup.
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jsdp, joyzoning, autonomous]
    category: devops
    related_skills: [joyzoning-governed-work, kanban-worker]
---

# JSDP Autonomous Delivery

## Operators

Dispatch from JoyZoning. Run `jz task complete --yes` when satisfied. **No Hermes yaml.**

## Agents — four calls

| Call | When |
|------|------|
| `jsdp(action='start')` | First message in session |
| `jsdp(action='apply', proposal_json='…')` | After ≤5 horizon nodes (JSON) |
| `jsdp(action='advance')` | Execute/repair loop |
| `jsdp(action='guide')` | Read `phase`, `agent_next_call`, `operator_summary` |

Legacy names (`prepare`, `commit`, `step`, `status`) still work.

## Response fields (always read these)

- `phase` — where you are in the loop
- `agent_next_call` — exact next invocation
- `operator_summary` — plain English for the human
- `setup_required` — if true, human must install JoyZoning (not your job to fix config)

## Do not

- Configure Hermes paths
- Plan the whole project in one JSON blob
- Use twelve separate horizon CLI steps
