#!/usr/bin/env bash
# DietCode integration test runner — Python contract suite + BroccoliDB TypeScript tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "▶ DietCode Python tests"
scripts/run_tests.sh \
  tests/plugins/test_dietcode_plugin.py \
  tests/plugins/test_dietcode_audit.py \
  tests/plugins/test_dietcode_jsdp_hooks.py \
  tests/plugins/test_joyzoning_governance.py \
  tests/agent/test_joyzoning_runtime.py \
  tests/tools/test_kanban_broccolidb_tools.py

echo "▶ BroccoliDB TypeScript tests"
(
  cd broccolidb
  if [[ ! -d node_modules ]]; then
    npm ci
  fi
  npm run test:integration
)

echo "✅ DietCode integration tests passed"
