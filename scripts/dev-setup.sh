#!/usr/bin/env bash
# dev-setup.sh — verify Prometheus Agent from a FRESH CLONE in one command.
#
#   bash scripts/dev-setup.sh            # install + run all test suites
#   bash scripts/dev-setup.sh --no-test  # install only
#   bash scripts/dev-setup.sh --python-only / --node-only
#
# What this guarantees: following ONLY the README from an empty machine,
# this script exits 0 if and only if the repository installs from its
# lockfiles and its test suites pass. No provider API keys are needed —
# the suites are hermetic (tests/conftest.py scrubs credential env vars
# and isolates PROMETHEUS_HOME into a per-test tempdir).
#
# Prerequisites (the script checks and tells you exactly what's missing):
#   - Python 3.11+   - uv   - Node.js (version in .nvmrc)   - npm

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

RUN_TESTS=1
DO_PYTHON=1
DO_NODE=1
for arg in "$@"; do
  case "$arg" in
    --no-test) RUN_TESTS=0 ;;
    --python-only) DO_NODE=0 ;;
    --node-only) DO_PYTHON=0 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[1;34m[dev-setup]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[dev-setup] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ── Prerequisites ───────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || fail "python3 not found — install Python 3.11+"
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
log "python3 $PY_VER"

if ! command -v uv >/dev/null 2>&1; then
  fail "uv not found — install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
log "uv $(uv --version 2>/dev/null | head -1)"

if [ "$DO_NODE" = 1 ]; then
  command -v node >/dev/null 2>&1 || fail "node not found — install Node.js ($(cat .nvmrc 2>/dev/null || echo 'see .nvmrc'))"
  command -v npm >/dev/null 2>&1 || fail "npm not found"
  log "node $(node --version) / npm $(npm --version)"
fi

# ── Install from lockfiles ──────────────────────────────────────────────
if [ "$DO_PYTHON" = 1 ]; then
  log "installing Python dependencies (uv.lock, exact pins)..."
  uv sync --frozen --extra dev --extra messaging --extra anthropic
fi

if [ "$DO_NODE" = 1 ]; then
  log "installing Node dependencies (package-lock.json)..."
  npm ci
fi

[ "$RUN_TESTS" = 1 ] || { log "install complete (--no-test)."; exit 0; }

# ── Test suites ─────────────────────────────────────────────────────────
# Hermetic by design: no .env file and no provider credentials required.
if [ "$DO_PYTHON" = 1 ]; then
  log "running Python test suite (canonical per-file-isolation runner)..."
  bash scripts/run_tests.sh
fi

if [ "$DO_NODE" = 1 ]; then
  log "running Node workspace tests (vitest)..."
  npm run --ws test
fi

log "✅ fresh-clone verification passed: install + all test suites green."
