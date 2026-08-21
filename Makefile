# Prometheus Agent — developer entry points.
#
# Thin wrappers over the canonical tooling so a fresh clone has ONE
# obvious way to install, test, and lint:
#
#   make setup   # install Python + Node dependencies from lockfiles
#   make test    # run the full Python + Node test suites
#   make lint    # ruff (Python) + eslint/prettier checks (Node)
#   make check   # everything CI runs, in order
#
# Python deps come from uv.lock (exact pins); Node deps come from
# package-lock.json. No network account/API key is required to run the
# test suites — they are hermetic (tests/conftest.py scrubs credential
# env vars and isolates PROMETHEUS_HOME per test).

UV ?= uv
PYTHON_EXTRAS ?= --extra dev --extra messaging --extra anthropic
JOBS ?= 4

.PHONY: setup setup-python setup-node test test-python test-node lint check env-check clean

setup: setup-python setup-node  ## Install everything from lockfiles

setup-python:
	$(UV) sync --frozen $(PYTHON_EXTRAS)

setup-node:
	npm ci

test: test-python test-node  ## Run all test suites

test-python:  ## Canonical Python runner (per-file subprocess isolation)
	bash scripts/run_tests.sh -j $(JOBS)

test-node:  ## vitest across all npm workspaces
	npm run --ws test

lint:  ## ruff + eslint/prettier + env-example sync gate
	$(UV) run ruff check .
	$(UV) run python scripts/sync_env_example.py --check
	npm run check

env-check:
	$(UV) run python scripts/sync_env_example.py --check

check: lint test  ## What CI runs, end to end

clean:
	rm -rf .pytest_cache
	find . -name __pycache__ -type d -not -path './node_modules/*' -prune -exec rm -rf {} +
