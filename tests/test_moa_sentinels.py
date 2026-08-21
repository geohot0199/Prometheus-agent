"""Regression tests for the MoA virtual-provider sentinels.

Background: secret scanners flagged ``self.api_key = "moa-virtual-provider"``
in cli.py (and friends) as a hardcoded credential. The value is a *protocol
sentinel* — the MoA provider is virtual (``moa://local``) and no HTTP
request ever carries the key. To keep scanners quiet and the contract
explicit, the sentinel now lives in exactly one place
(``prometheus_constants``) and every production call site imports it.

These tests pin:
1. The sentinel values themselves (they are a protocol contract shared
   with persisted model_override dicts — changing them silently would
   break in-flight MoA sessions after an upgrade).
2. That the previously-flagged files never regress to raw string
   literals assigned to credential-shaped attributes.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from prometheus_constants import (
    MOA_VIRTUAL_PROVIDER_API_KEY,
    MOA_VIRTUAL_PROVIDER_BASE_URL,
    MOA_VIRTUAL_PROVIDER_SOURCE,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that previously contained the hardcoded sentinel literals and were
# fixed to import the shared constants instead.
FORMERLY_FLAGGED_FILES = (
    "cli.py",
    "agent/agent_init.py",
    "agent/agent_runtime_helpers.py",
    "gateway/run.py",
    "prometheus_cli/providers.py",
    "prometheus_cli/runtime_provider.py",
    "tui_gateway/methods_tools.py",
)


def test_sentinel_values_are_stable_protocol_contract() -> None:
    """The sentinels are persisted into model_override dicts; changing them
    silently would break MoA sessions restored across an upgrade."""
    assert MOA_VIRTUAL_PROVIDER_API_KEY == "moa-virtual-provider"
    assert MOA_VIRTUAL_PROVIDER_SOURCE == "moa-virtual-provider"
    assert MOA_VIRTUAL_PROVIDER_BASE_URL == "moa://local"


def test_sentinels_are_not_credential_shaped() -> None:
    """Guard against someone ever putting a real secret in these constants:
    real keys are long and high-entropy; sentinels are short words."""
    for value in (
        MOA_VIRTUAL_PROVIDER_API_KEY,
        MOA_VIRTUAL_PROVIDER_SOURCE,
        MOA_VIRTUAL_PROVIDER_BASE_URL,
    ):
        assert len(value) <= 32
        assert not re.search(r"[A-Za-z0-9]{24,}", value), (
            f"{value!r} looks like a real credential; sentinels must stay "
            "obviously non-secret"
        )


@pytest.mark.parametrize("relpath", FORMERLY_FLAGGED_FILES)
def test_no_raw_sentinel_literals_in_fixed_files(relpath: str) -> None:
    """The fixed files must reference the constants, never the literals.

    Comments and docstrings may still mention the values for explanation,
    so we walk the AST (code only) instead of grepping the raw text.
    """
    tree = ast.parse((REPO_ROOT / relpath).read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node.value in ("moa-virtual-provider", "moa://local"):
            offenders.append(f"{relpath}:{node.lineno}: {node.value!r}")
    assert not offenders, (
        "Raw MoA sentinel literals found; use the prometheus_constants "
        f"exports instead:\n" + "\n".join(offenders)
    )


def test_constants_module_stays_stdlib_only() -> None:
    """prometheus_constants is the dependency-free bedrock module; if it
    grows an unconditional third-party import, half the codebase inherits
    it. Imports guarded by ``try:`` (e.g. the win32-only psutil probe) are
    allowed because they degrade gracefully."""
    tree = ast.parse((REPO_ROOT / "prometheus_constants.py").read_text(encoding="utf-8"))
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            guarded.update(id(child) for child in ast.walk(node))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if id(node) in guarded:
                continue
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if id(node) in guarded:
                continue
            imported.add(node.module.split(".")[0])
    third_party = {
        name
        for name in imported
        if name not in sys.builtin_module_names and not _is_stdlib(name)
    }
    assert not third_party, f"non-stdlib imports in prometheus_constants: {third_party}"


def _is_stdlib(name: str) -> bool:
    if name in sys.stdlib_module_names:
        return True
    # Local first-party modules are fine (none exist today, but allow it).
    return (REPO_ROOT / name).exists() or (REPO_ROOT / f"{name}.py").exists()
