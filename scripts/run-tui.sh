#!/usr/bin/env bash
# Launch DietCode / Hermes with the Herm (OpenTUI) TUI from this checkout.
# Syncs bun deps and rebuilds dist/ when sources or bun.lock change (e.g. after git pull).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TUI_DIR="$ROOT/herm-tui"
cd "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
elif [[ -f "$ROOT/venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/venv/bin/activate"
else
  echo "No .venv or venv — run: uv venv && source .venv/bin/activate && uv pip install -e '.[cli,pty]'" >&2
  exit 1
fi

export HERMES_AGENT_ROOT="$ROOT"
export HERMES_PYTHON_SRC_ROOT="$ROOT"

_bun() {
  if [[ -n "${HERMES_BUN:-}" && -x "${HERMES_BUN}" ]]; then
    echo "${HERMES_BUN}"
    return
  fi
  if command -v bun >/dev/null 2>&1; then
    command -v bun
    return
  fi
  if [[ -x "${HOME}/.bun/bin/bun" ]]; then
    echo "${HOME}/.bun/bin/bun"
    return
  fi
  echo "bun not found — install from https://bun.sh (or set HERMES_BUN=/path/to/bun)" >&2
  exit 1
}

_sync_herm_tui() {
  local bun="$(_bun)"
  local marker="$TUI_DIR/node_modules/@opentui/core/package.json"
  local dist="$TUI_DIR/dist/index.js"

  if [[ ! -f "$marker" ]] || { [[ -f "$TUI_DIR/bun.lock" ]] && [[ "$TUI_DIR/bun.lock" -nt "$marker" ]]; }; then
    echo "Installing TUI dependencies…" >&2
    (cd "$TUI_DIR" && "$bun" install)
  fi

  local need_build=0
  if [[ ! -f "$dist" ]]; then
    need_build=1
  else
    local f
    for f in package.json bun.lock tsconfig.json scripts/build.ts; do
      if [[ -f "$TUI_DIR/$f" && "$TUI_DIR/$f" -nt "$dist" ]]; then
        need_build=1
        break
      fi
    done
    if [[ "$need_build" == 0 && -d "$TUI_DIR/src" ]]; then
      while IFS= read -r -d '' f; do
        if [[ "$f" -nt "$dist" ]]; then
          need_build=1
          break
        fi
      done < <(find "$TUI_DIR/src" "$TUI_DIR/assets" -type f \( \
        -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.json' \
        \) -print0 2>/dev/null || true)
    fi
  fi

  if [[ "$need_build" == 1 ]]; then
    echo "Building herm-tui…" >&2
    (cd "$TUI_DIR" && "$bun" run build)
  fi
}

_sync_herm_tui
exec dietcode --tui "$@"
