"""Tests for scripts/sync_env_example.py (.env.example <-> source sync).

Covers the scanner regex, the auto-generated block lifecycle (generate,
preserve curated content, idempotence), and --check semantics. Ends with
a repo-level consistency test so .env.example can never silently drift
from the env vars the code reads.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync_env_example.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sync_env_example", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_env = _load_module()


# ── scanner ─────────────────────────────────────────────────────────────


def test_scanner_finds_all_lookup_forms(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text(
        "\n".join(
            [
                'import os',
                'a = os.getenv("FORM_ONE")',
                "b = os.environ.get('FORM_TWO')",
                'c = os.environ["FORM_THREE"]',
                'os.environ.setdefault("FORM_FOUR", "x")',
                'os.environ.pop("FORM_FIVE", None)',
            ]
        ),
        encoding="utf-8",
    )
    refs = sync_env.scan_references([src])
    assert set(refs) == {
        "FORM_ONE",
        "FORM_TWO",
        "FORM_THREE",
        "FORM_FOUR",
        "FORM_FIVE",
    }
    assert refs["FORM_ONE"] == [str(src)]


def test_scanner_ignores_dynamic_lookups_and_short_names(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text(
        "\n".join(
            [
                "import os",
                'os.getenv(f"{prefix}_API_KEY")',
                "os.getenv(var)",
                'os.getenv("AB")',          # too short to be an env contract
                'os.getenv("lower_case")',   # not UPPER_SNAKE
            ]
        ),
        encoding="utf-8",
    )
    assert sync_env.scan_references([src]) == {}


# ── generated block lifecycle ───────────────────────────────────────────


CURATED = (
    "# My hand-written intro\n"
    "# OPENAI_API_KEY=\n"
    "# ANTHROPIC_API_KEY=\n"
)


def _write_env(tmp_path: Path, content: str = CURATED) -> Path:
    p = tmp_path / ".env.example"
    p.write_text(content, encoding="utf-8")
    return p


def test_missing_vars_are_appended_grouped_and_sorted(tmp_path: Path) -> None:
    env = _write_env(tmp_path)
    refs = {
        "ZETA_TOKEN": ["a.py"],
        "ACME_KEY": ["b.py"],
        "ACME_URL": ["c.py"],
        "OPENAI_API_KEY": ["d.py"],  # already documented — must not reappear
    }
    assert sync_env.sync(env, refs, check=False) == 0
    text = env.read_text(encoding="utf-8")
    assert "# My hand-written intro" in text
    assert sync_env.BEGIN_MARKER in text and sync_env.END_MARKER in text
    # grouped by prefix, sorted within groups
    assert text.index("# ── ACME_* ──") < text.index("# ── ZETA_* ──")
    assert text.index("# ACME_KEY=") < text.index("# ACME_URL=")
    assert text.count("OPENAI_API_KEY=") == 1  # curated entry only


def test_sync_is_idempotent(tmp_path: Path) -> None:
    env = _write_env(tmp_path)
    refs = {"NOVA_TOKEN": ["x.py"]}
    sync_env.sync(env, refs, check=False)
    first = env.read_text(encoding="utf-8")
    sync_env.sync(env, refs, check=False)
    assert env.read_text(encoding="utf-8") == first


def test_stale_generated_block_is_replaced_not_duplicated(tmp_path: Path) -> None:
    env = _write_env(tmp_path)
    sync_env.sync(env, {"OLD_VAR": ["a.py"]}, check=False)
    sync_env.sync(env, {"NEW_VAR": ["b.py"]}, check=False)
    text = env.read_text(encoding="utf-8")
    assert text.count(sync_env.BEGIN_MARKER) == 1
    assert "OLD_VAR" not in text
    assert "# NEW_VAR=" in text


def test_check_mode_detects_drift(tmp_path: Path) -> None:
    env = _write_env(tmp_path)
    refs = {"DRIFT_VAR": ["a.py"]}
    assert sync_env.sync(env, refs, check=True) == 1  # stale
    sync_env.sync(env, refs, check=False)
    assert sync_env.sync(env, refs, check=True) == 0  # in sync


def test_documented_vars_ignore_generated_block(tmp_path: Path) -> None:
    env = _write_env(tmp_path)
    sync_env.sync(env, {"GEN_ONLY_VAR": ["a.py"]}, check=False)
    # The generated entry must not count as "curated documentation",
    # otherwise deleting a var from source could never remove it.
    assert "GEN_ONLY_VAR" not in sync_env.documented_vars(env)
    assert "OPENAI_API_KEY" in sync_env.documented_vars(env)


# ── repo-level consistency ──────────────────────────────────────────────


def test_repo_env_example_is_in_sync() -> None:
    """CI gate: run the real script in --check mode against the repo."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        ".env.example drifted from source env references:\n"
        + result.stdout
        + result.stderr
    )
