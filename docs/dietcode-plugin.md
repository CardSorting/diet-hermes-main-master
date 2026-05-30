# DietCode plugin architecture

Hermes upstream stays plugin-agnostic. This fork ships **one** integration bundle:
`plugins/dietcode/` (`kind: standalone`, enabled via `plugins.enabled: ["dietcode"]` in
`DEFAULT_CONFIG`).

Legacy split plugins (`joyzoning_governance`, `joyzoning_runtime`, `kanban_broccolidb`,
`jsdp_mutation`) and the Habitat control plane (`:9470`, `habitat_bridge`, etc.) were
removed. Do not reintroduce them.

---

## Install (drag-and-drop — standalone package)

Copy the **`dietcode/`** folder to `~/.hermes/plugins/dietcode/` (no pip required).
The plugin bootstraps `plugins.dietcode` imports when Hermes loads it as
`hermes_plugins.dietcode`.

**No manual YAML edits required:** `plugin.yaml` sets `auto_enable: true`, so Hermes
enables DietCode on first discovery and persists it to `plugins.enabled`. On register,
`install.py` also merges the `dietcode` toolset and governance defaults.

```bash
cp -R /path/to/dietcode-plugin/dietcode ~/.hermes/plugins/dietcode
python3 ~/.hermes/plugins/dietcode/install.py   # optional — also runs from install script
cd ~/.hermes/plugins/dietcode/broccolidb && npm ci
```

Or one step:

```bash
/path/to/dietcode-plugin/scripts/install-to-hermes.sh
```

Verify: `/dietcode doctor`

---

## Layout

```
plugins/dietcode/
├── plugin.yaml              # standalone, auto_enable: true (drag-and-drop)
├── install.py               # config merge + optional npm ci wizard
├── __init__.py              # register() + drag-and-drop namespace bootstrap
├── _bootstrap.py            # maps hermes_plugins.dietcode → plugins.dietcode
├── hooks.py                 # consolidated hook chains (fail-closed wrappers)
├── public.py                # stable exports for tests/extensions
├── health.py                # /dietcode status|doctor|tools
├── contracts.py + audit.py  # production contract + static scans
├── tools_loader.py          # deferred tool imports + EXPECTED_DIETCODE_TOOLS
├── paths.py                 # broccolidb root resolution (profile-safe)
├── broccolidb → ../../broccolidb   # symlink — single canonical TS tree
├── lib/
│   ├── runtime/             # kanban, joyzoning, governance, jsdp hooks
│   ├── agent/joyzoning/     # journal, convergence, scope registry (Hermes-native)
│   └── tools/               # broccolidb_*, kanban_broccolidb_*, joyzoning, jsdp
└── slash_commands.py        # /joyzoning, /broccolidb, /broccoliq
```

**BroccoliDB dedupe:** The only authoritative TypeScript tree is repo-root `broccolidb/`.
The plugin bundle is a symlink so npm ci / RPC version checks stay aligned. CI and
`/dietcode doctor` verify the symlink via `broccolidb_bundle_symlink_ok()`.

---

## Core facades (import boundary)

Core Hermes must not import `plugins.dietcode.*` except through these facades:

| Facade | Purpose |
|--------|---------|
| `hermes_cli/dietcode_bridge.py` | Kanban completion gates, worker env injection, JoyZoning doctor, BroccoliDB RPC helpers, startup warning |
| `hermes_cli/dietcode_broccolidb.py` | Dashboard health/snapshot (uses `dietcode_bridge` only) |
| `agent/governance_bridge.py` | Governance transform, exemptions, path classification |
| `agent/joy_zoning_bridge.py` | Layer tag injection / post-write validation in `file_tools` |
| `agent/prompt_bridge.py` | Plugin prompt guidance via `PluginManager` attribute |
| `tools/registry.py` | `DEFERRED_TOOL_MODULE_STEMS` only |

`plugins/dietcode/audit.py` scans `agent/`, `tools/`, `hermes_cli/`, `gateway/`, and
top-level entry points for forbidden direct imports.

---

## Configuration defaults (throughput fork)

| Key | Default | Meaning |
|-----|---------|---------|
| `plugins.enabled` | `["dietcode"]` | Load unified plugin |
| `joyzoning.enabled` | `false` | Journal + convergence lifecycle off |
| `joyzoning.governance.enabled` | `true` | Write/patch layering via transform hook |
| `joyzoning.governance.layer_tags_required` | `false` | Light validation; no mandatory `[LAYER:]` headers |
| `joyzoning.execution_journal` | `false` | Per-tool SQLite journal off |

Governance can run without full JoyZoning lifecycle. Enable `joyzoning.enabled` for
kanban convergence gates and journal tools.

---

## Operator commands

```bash
/dietcode doctor          # integration contract + symlink + layout checks
/dietcode status          # cached load report
hermes kanban joyzoning-doctor   # scope journal / JSDP checks (via dietcode_bridge)
```

Slash commands: `/joyzoning` (`/jz`), `/broccolidb` (`/bdb`), `/broccoliq` (`/bq`).

---

## JoyZoning flow (Hermes-native)

```
begin → patch → verify → request_review → convergence_mark_converged → kanban_complete
```

Runtime events append to the local journal only (`runtime_events.py`). Layer taxonomy
uses `RuntimeLayer.REPRESENTATION` (legacy alias `HABITAT`).

---

## Tests

```bash
scripts/run_tests.sh tests/plugins/test_dietcode*.py
scripts/run_tests.sh tests/hermes_cli/test_dietcode*.py
scripts/run_tests.sh tests/agent/test_joy_zoning*.py tests/agent/test_joyzoning*.py
```

Static audit: `tests/plugins/test_dietcode_audit.py` (forbidden imports, legacy shims absent).

CI: `.github/workflows/diet-integrations-check.yml` asserts legacy plugin dirs do not exist.

---

## Related docs

- [broccolidb-native-execution-throughput.md](./broccolidb-native-execution-throughput.md) — RPC worker
- [README.md](../README.md) — fork overview
- [AGENTS.md](../AGENTS.md) — contributor conventions
