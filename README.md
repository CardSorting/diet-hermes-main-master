<p align="center">
  <img src="assets/banner.png" alt="DietCode — Hermes Agent fork" width="100%">
</p>

# DietCode Agent

<p align="center">
  <a href="https://github.com/NousResearch/hermes-agent"><img src="https://img.shields.io/badge/Upstream-Hermes%20Agent-FFD700?style=for-the-badge" alt="Upstream: Hermes Agent"></a>
  <a href="https://hermes-agent.nousresearch.com/docs/"><img src="https://img.shields.io/badge/Hermes%20Docs-nousresearch.com-CD7F32?style=for-the-badge" alt="Hermes documentation"></a>
  <a href="https://github.com/NousResearch/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://nousresearch.com"><img src="https://img.shields.io/badge/Origin-Nous%20Research-blueviolet?style=for-the-badge" alt="Origin: Nous Research"></a>
</p>

**DietCode** is a specialized fork of [**Hermes Agent**](https://github.com/NousResearch/hermes-agent) by [Nous Research](https://nousresearch.com) — the self-improving, tool-calling AI agent with CLI, TUI, messaging gateway, skills, memory, and scheduled jobs. This repository adds **BroccoliDB**, **JoyZoning governance**, **Kanban ↔ BroccoliQ orchestration**, and a **DietCode control-plane** UI on top of that core.

Use **`dietcode`** as the primary CLI (a **`hermes`** alias remains for compatibility). Data lives under **`~/.dietcode`**, separate from a vanilla **`~/.hermes`** install, so you can run both side by side.

> **Upstream:** Feature behavior, architecture, and most user guides are documented at [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/). Where those docs say `hermes`, use `dietcode` in this fork unless noted otherwise.

---

## Quick start (this repository)

Clone this repo and run the local setup script (recommended for diet-hermes development):

```bash
git clone <your-diet-hermes-remote> diet-hermes
cd diet-hermes
./setup-hermes.sh          # uv/venv, deps, symlinks dietcode + hermes
dietcode setup             # wizard — API keys, model, tools
dietcode                   # interactive CLI (cola-themed dietcode skin)
```

Optional surfaces:

```bash
dietcode --tui             # Herm TUI (OpenTUI) — auto syncs/builds herm-tui/
./scripts/run-tui.sh       # same, from repo root (recommended after git pull)
dietcode dashboard          # web dashboard — DietCode route at /dietcode
dietcode gateway            # messaging gateway (Telegram, Discord, …)
dietcode doctor             # diagnostics
dietcode update             # update this checkout
```

Reload your shell if `dietcode` is not found: `source ~/.bashrc` (or `~/.zshrc`). The installer links both `~/.local/bin/dietcode` and `~/.local/bin/hermes` to the same entry point.

### Herm TUI (every run)

From this repo — **no manual `bun install` / `bun run build` after `git pull`**. The launcher syncs deps and rebuilds only when `herm-tui/` or `bun.lock` changed:

```bash
cd /path/to/diet-hermes-main-master
./scripts/run-tui.sh              # production
./scripts/run-tui.sh -c           # resume last session
./scripts/run-tui.sh --dev        # hot reload
```

Same behavior via `dietcode --tui` if this checkout is your active install (`source .venv/bin/activate` first).

**Once per machine:** [Bun](https://bun.sh) on your `PATH` (or `export HERMES_BUN=~/.bun/bin/bun`). Use a real terminal tab (Terminal, iTerm, or Cursor’s integrated terminal).

### DietCode vs vanilla Hermes

| | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | **This fork (DietCode)** |
|---|---|---|
| CLI command | `hermes` | **`dietcode`** (also `hermes` alias) |
| Data directory | `~/.hermes` | **`~/.dietcode`** |
| Home env var | `HERMES_HOME` | **`DIETCODE_HOME`** (mirrored to `HERMES_HOME` in code) |
| Default CLI skin | Hermes gold | **`dietcode`** cola theme |
| Extra integrations | — | BroccoliDB, JoyZoning, Kanban bridge, DietCode UI |

Internal Python package names (`hermes_cli`, `hermes_constants`, etc.) stay aligned with upstream on purpose so `git merge upstream/main` stays tractable.

---

## What this fork adds

### DietCode control plane (web)

A reviewer-friendly dashboard for bounded, approval-gated code changes:

- Route: **`/dietcode`** in the embedded dashboard (`dietcode dashboard`)
- Components: `web/src/components/dietcode/` — session workflow, quality tab, activity log, carbonation UI
- Plain-language copy and soda-parody branding (not upstream Hermes chrome)

### BroccoliDB + BroccoliQ

| Layer | Paths |
|-------|--------|
| TypeScript engine | `broccolidb/` (includes vendored **BroccoliQ** queue/hive under `broccolidb/infrastructure/`) |
| Python tools | `tools/broccolidb.py`, `tools/broccolidb_tools/` |
| Toolset | `broccolidb` in `toolsets.py` |

### JoyZoning governance

Policy and workflow hooks for governed agent runs: `plugins/joyzoning_governance/`, CLI helper `scripts/joy_check.py`.

### Kanban ↔ BroccoliQ

| Layer | Paths |
|-------|--------|
| Plugin | `plugins/kanban_broccolidb/` |
| Tools | `tools/kanban_broccolidb_tools.py`, `tools/kanban_broccolidb_bridge.py` |

### CLI / TUI branding

- Built-in skin **`dietcode`** in `hermes_cli/skin_engine.py` (default in `hermes_cli/config.py`)
- Shared soda callbacks: `hermes_cli/soda_callbacks.py`, `web/src/components/dietcode/sodaCallbacks.ts`
- TUI is Herm (OpenTUI) in `herm-tui/`; gateway skin flows through `tui_gateway` → Herm theme
- User-facing command strings flow through `get_cli_command()` / `cli_usage()` / `format_cli_reference()` in `hermes_constants.py`

---

## Inherited from Hermes Agent

Everything below comes from **upstream Hermes** unless this README’s fork sections say otherwise. Full detail lives in [Nous Research’s documentation](https://hermes-agent.nousresearch.com/docs/).

| Capability | Summary |
|------------|---------|
| **Models** | OpenRouter, Anthropic, OpenAI, Nous Portal, and many more — `dietcode model` |
| **Terminal UI** | Classic CLI + `dietcode --tui` (Herm / OpenTUI), slash commands, streaming tools |
| **Messaging** | `dietcode gateway` — Telegram, Discord, Slack, WhatsApp, Signal, email, … |
| **Tools** | 40+ built-in tools, toolsets, MCP servers — `dietcode tools` |
| **Skills** | Procedural memory, hub install, agent-created skills |
| **Memory** | Pluggable providers (honcho, mem0, …), session search |
| **Cron** | Scheduled jobs with platform delivery — `dietcode cron` |
| **Delegation** | Subagents, parallel workers, isolated terminals |
| **Backends** | Local, Docker, SSH, Modal, Daytona, Singularity, Vercel Sandbox |

Switch models with **`dietcode model`** — same provider ecosystem as upstream, no code fork required for inference.

### CLI vs messaging (command cheat sheet)

| Action | CLI / TUI | Messaging (after `dietcode gateway`) |
|--------|-----------|--------------------------------------|
| Start chatting | `dietcode`, `./scripts/run-tui.sh`, or `dietcode --tui` | Message your bot |
| Fresh session | `/new` or `/reset` | `/new` or `/reset` |
| Change model | `/model [provider:model]` | `/model …` |
| Skills | `/skills` or `/<skill-name>` | `/<skill-name>` |
| Interrupt | `Ctrl+C` or new message | `/stop` or new message |

Upstream references: [CLI guide](https://hermes-agent.nousresearch.com/docs/user-guide/cli), [Messaging gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging).

### Documentation map (upstream)

| Topic | Link |
|-------|------|
| Quickstart | [hermes-agent.nousresearch.com/docs/getting-started/quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) |
| Configuration | [Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools & toolsets | [Tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) |
| Skills | [Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) |
| Architecture | [Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture) |
| CLI reference | [CLI commands](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) (substitute `dietcode` for `hermes`) |

---

## Install from upstream script (optional)

You can still use Nous Research’s public installer for a **vanilla Hermes** tree; for **this fork**, prefer `./setup-hermes.sh` in your clone.

<details>
<summary>Vanilla Hermes one-liner (upstream repo)</summary>

```bash
# Installs NousResearch/hermes-agent — not diet-hermes integrations
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Windows (beta), Termux, and WSL notes: see [upstream README](https://github.com/NousResearch/hermes-agent/blob/main/README.md) and [Termux guide](https://hermes-agent.nousresearch.com/docs/getting-started/termux).

</details>

---

## Migrating from OpenClaw

Same upstream flow; use **`dietcode`** instead of `hermes`:

```bash
dietcode claw migrate              # interactive migration
dietcode claw migrate --dry-run    # preview only
```

Imported data lands under **`~/.dietcode/`** (e.g. skills → `~/.dietcode/skills/openclaw-imports/`). See `dietcode claw migrate --help` and the `openclaw-migration` skill.

---

## Syncing upstream Hermes

**Do not deploy** artifacts built only from `NousResearch/hermes-agent` into diet-hermes infrastructure. Pull upstream **into this repo**, re-apply the fork overlay, then build and deploy from here.

```bash
git remote add upstream https://github.com/NousResearch/hermes-agent.git   # once
git fetch upstream main
git tag diet-integrations-$(date +%Y-%m-%d)   # backup before sync

# Merge or cherry-pick integration paths, then re-apply overlay files:
git checkout diet-integrations-<date> -- \
  broccolidb/ tools/broccolidb.py tools/broccolidb_tools/ \
  plugins/joyzoning_governance/ plugins/kanban_broccolidb/ \
  tools/kanban_broccolidb_tools.py tools/kanban_broccolidb_bridge.py \
  scripts/joy_check.py web/src/components/dietcode/ web/src/pages/DietCodePage.tsx

# Re-merge toolsets.py broccolidb entries and web/src/App.tsx /dietcode route if conflicts
cd broccolidb && npm ci && cd ..
python -c "from tools.registry import discover_builtin_tools, registry; discover_builtin_tools(); assert len(registry.get_tool_names_for_toolset('broccolidb')) >= 20"
```

### Fork overlay after every `git merge upstream/main`

Re-apply when merge conflicts touch these files:

| File | What to restore |
|------|-----------------|
| `hermes_constants.py` | `DietCode fork` block: `PRODUCT_CLI_COMMAND`, `cli_usage()`, `format_cli_reference()` |
| `hermes_bootstrap.py` | `ensure_default_home_env()` on import |
| `pyproject.toml` | `[project.scripts]` — `dietcode`, `dietcode-agent`, `dietcode-acp` (+ `hermes*` aliases) |
| `hermes_cli/_parser.py` | `get_cli_command()` + `_build_epilogue()` |
| `hermes_cli/config.py` | default `display.skin: dietcode` |
| `hermes_cli/skin_engine.py` | `dietcode` built-in skin |
| `hermes_cli/relaunch.py` | PATH: `dietcode` then `hermes` |
| `hermes_cli/config.py` | `recommended_update_command()` → `dietcode update` |
| `gateway/run.py` | `_resolve_hermes_bin()` prefers `dietcode` |
| `hermes_cli/tips.py` | `format_cli_reference` on tips |
| `setup-hermes.sh` | `DIETCODE_HOME`, symlinks `dietcode` + `hermes` |
| `web/src/App.tsx` | `/dietcode` route and nav |
| `README.md` | This fork-oriented README |

CI: `.github/workflows/diet-integrations-check.yml` guards integration paths on PRs.

---

## Developing this fork

```bash
git clone <your-diet-hermes-remote> diet-hermes
cd diet-hermes
./setup-hermes.sh
dietcode doctor
scripts/run_tests.sh                    # full suite (CI-parity wrapper)
scripts/run_tests.sh tests/hermes_cli/test_cli_command_overlay.py -q
```

Manual equivalent:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[all,dev]"
cd broccolidb && npm ci && cd ..
cd web && npm ci && npm run build && cd ..
scripts/run_tests.sh
```

Agent and contributor conventions for the Hermes codebase: see **`AGENTS.md`** in this tree (same upstream layout; profile paths use `get_hermes_home()` / `display_hermes_home()` which resolve to `~/.dietcode` here).

---

## Community & upstream

- **Hermes Agent (origin):** [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **Docs:** [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)
- **Discord:** [Nous Research](https://discord.gg/NousResearch)
- **Skills standard:** [agentskills.io](https://agentskills.io)

Community bridges and tools listed in the upstream README (e.g. computer-use-linux, HermesClaw) apply to the Hermes core this fork tracks.

---

## License

MIT — see [LICENSE](LICENSE).

**Hermes Agent** is built by [Nous Research](https://nousresearch.com). **DietCode** is a downstream fork that retains that origin and adds the integrations and branding described above.
