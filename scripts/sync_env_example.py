#!/usr/bin/env python3
"""Keep .env.example in sync with the env vars the code actually reads.

Scans the source tree for environment-variable references
(``os.getenv``, ``os.environ.get``, ``os.environ[...]``,
``os.environ.setdefault``, ``os.environ.pop``) and compares them against
the variables documented in ``.env.example``. Anything referenced but
undocumented is emitted into a clearly-marked auto-generated section at
the bottom of ``.env.example``, grouped by prefix.

Usage:
    python scripts/sync_env_example.py            # rewrite .env.example
    python scripts/sync_env_example.py --check    # exit 1 if out of sync
    python scripts/sync_env_example.py --list     # print missing vars only

The curated part of ``.env.example`` (hand-written comments, grouping,
links) is preserved untouched — only the block between the
AUTO-GENERATED markers is managed by this script.

Runs in O(total source bytes): each file is streamed once, the regex is
precompiled, and results accumulate into a dict keyed by variable name.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

BEGIN_MARKER = "# >>> AUTO-GENERATED:env-sync >>>"
END_MARKER = "# <<< AUTO-GENERATED:env-sync <<<"

# Environment-variable lookups with a literal name. Dynamic lookups
# (f-strings, variables) are intentionally ignored — we can only document
# names we can see.
ENV_REF_RE = re.compile(
    r"""(?:
        os\.getenv\s*\(
      | os\.environ\.get\s*\(
      | os\.environ\.setdefault\s*\(
      | os\.environ\.pop\s*\(
      | os\.environ\[
    )\s*["']([A-Z][A-Z0-9_]{2,})["']""",
    re.VERBOSE,
)

# Variables documented in .env.example either as `NAME=` or `# NAME=`.
DOCUMENTED_RE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]{2,})\s*=")

# Directories that reference env vars only for tests/docs/scaffolding and
# must not generate user-facing .env.example entries.
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "tests",
    "website",
    "docs",
    "evals",
    ".venv-ci",
    ".venv",
    "skills",           # user-authored; env vars documented per-skill
    "optional-skills",  # same as skills
    "scripts",          # installer/CI plumbing, not user .env material
    "apps",             # desktop scaffolding reads OS env, not .env
}

# Environment variables that are OS/shell/runtime plumbing — inherited from
# the process environment and never configured via .env (python-dotenv does
# not override real env vars anyway). Documenting them would be noise.
ALLOWLIST: Set[str] = {
    # OS / session plumbing
    "HOME", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "APPDATA", "USERPROFILE",
    "PATH", "PWD", "OLDPWD", "SHELL", "TERM", "USER", "LOGNAME", "HOSTNAME",
    "LANG", "LC_ALL", "TZ", "TMPDIR", "TEMP", "TMP",
    "EDITOR", "VISUAL", "DISPLAY", "WAYLAND_DISPLAY", "COLUMNS", "LINES",
    "COLORFGBG", "COLORTERM", "NO_COLOR", "FORCE_COLOR",
    "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
    # SSH / container / CI detection probes
    "SSH_CONNECTION", "SSH_TTY", "SSH_CLIENT", "SSH_AUTH_SOCK",
    "KUBERNETES_SERVICE_HOST", "CI", "GITHUB_ACTIONS",
    # Windows architecture probes
    "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432", "COMSPEC",
    "SYSTEMROOT", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMDATA",
    # Termux / Android probes
    "PREFIX", "TERMUX_VERSION", "ANDROID_ROOT", "ANDROID_DATA",
    # Python runtime plumbing
    "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONPATH", "PYTHONHASHSEED",
    "PYTEST_CURRENT_TEST", "PYTEST_VERSION", "VIRTUAL_ENV",
    "UV_PYTHON", "UV_LINK_MODE", "PIP_NO_INPUT",
    # Terminal/toolkit probes
    "GHOSTTY_BIN_DIR", "GHOSTTY_RESOURCES_DIR", "PROMPT_TOOLKIT_NO_CPR",
    "VSCODE_INJECTION", "VSCODE_PID", "TERM_PROGRAM", "WT_SESSION",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def iter_source_files(root: Path) -> Iterable[Path]:
    """Yield candidate source files, pruning excluded dirs in O(1) each."""
    for path in sorted(root.rglob("*.py")):
        parts = set(path.relative_to(root).parts[:-1])
        if parts & EXCLUDED_DIRS:
            continue
        yield path


def scan_references(files: Iterable[Path], root: Path | None = None) -> Dict[str, List[str]]:
    """Map env var name -> list of referencing files (paths relative to
    ``root`` when given, so output is stable across checkouts)."""
    refs: Dict[str, List[str]] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        label = str(path.relative_to(root)) if root else str(path)
        for match in ENV_REF_RE.finditer(text):
            name = match.group(1)
            if name in ALLOWLIST:
                continue
            refs.setdefault(name, []).append(label)
    return refs


def documented_vars(example_path: Path) -> Set[str]:
    """Vars already present in .env.example (active or commented out),
    excluding the auto-generated block so it can be rebuilt from scratch."""
    found: Set[str] = set()
    in_generated = False
    for line in example_path.read_text(encoding="utf-8").splitlines():
        if line.strip() == BEGIN_MARKER:
            in_generated = True
            continue
        if line.strip() == END_MARKER:
            in_generated = False
            continue
        if in_generated:
            continue
        m = DOCUMENTED_RE.match(line)
        if m:
            found.add(m.group(1))
    return found


def group_key(name: str) -> str:
    """Group by first underscore-delimited prefix (OPENAI_API_KEY -> OPENAI)."""
    return name.split("_", 1)[0]


def render_generated_block(missing: Dict[str, List[str]]) -> str:
    if not missing:
        return ""
    lines: List[str] = [
        BEGIN_MARKER,
        "# The entries below are generated by `python scripts/sync_env_example.py`",
        "# from environment variables referenced in the source tree. Uncomment",
        "# and fill in the ones you need; re-run the script to refresh this",
        "# section instead of editing it by hand.",
        "#",
    ]
    groups: Dict[str, List[str]] = {}
    for name in missing:
        groups.setdefault(group_key(name), []).append(name)
    for prefix in sorted(groups):
        lines.append(f"# ── {prefix}_* ──")
        for name in sorted(groups[prefix]):
            seen_in = ", ".join(sorted({p for p in missing[name]})[:2])
            lines.append(f"# {name}=")
            if seen_in:
                lines.append(f"#   referenced in: {seen_in}")
        lines.append("#")
    if lines[-1] == "#":
        lines.pop()
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def split_example(text: str) -> Tuple[str, str]:
    """Return (curated part, trailing text after END_MARKER)."""
    begin = text.find(BEGIN_MARKER)
    if begin == -1:
        return text.rstrip("\n") + "\n", ""
    end = text.find(END_MARKER, begin)
    if end == -1:
        return text.rstrip("\n") + "\n", ""
    curated = text[:begin].rstrip("\n") + "\n"
    trailing = text[end + len(END_MARKER):]
    return curated, trailing.lstrip("\n")


def sync(example_path: Path, refs: Dict[str, List[str]], check: bool) -> int:
    documented = documented_vars(example_path)
    missing = {name: files for name, files in refs.items() if name not in documented}
    block = render_generated_block(missing)

    text = example_path.read_text(encoding="utf-8")
    curated, trailing = split_example(text)
    new_text = curated
    if block:
        new_text += "\n" + block
    if trailing:
        new_text += trailing
    if not new_text.endswith("\n"):
        new_text += "\n"

    if check:
        # In check mode we only care whether the generated block is stale:
        # recompute the block from the current file and compare.
        current_begin = text.find(BEGIN_MARKER)
        current_block = ""
        if current_begin != -1:
            end = text.find(END_MARKER, current_begin)
            if end != -1:
                current_block = text[current_begin : end + len(END_MARKER)] + "\n"
        if current_block == block:
            print(f".env.example in sync ({len(documented)} documented vars).")
            return 0
        print(
            f".env.example out of sync: {len(missing)} referenced vars "
            f"missing from the documented set. Run: python scripts/sync_env_example.py"
        )
        for name in sorted(missing):
            print(f"  + {name}")
        return 1

    example_path.write_text(new_text, encoding="utf-8")
    print(
        f".env.example updated: {len(documented)} already documented, "
        f"{len(missing)} added to the auto-generated section."
    )
    return 0


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if out of sync")
    parser.add_argument(
        "--list", action="store_true", help="print referenced-but-undocumented vars"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="path to .env.example (default: repo root .env.example)",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    example_path = args.env_file or (root / ".env.example")
    refs = scan_references(iter_source_files(root), root)

    if args.list:
        documented = documented_vars(example_path)
        for name in sorted(set(refs) - documented):
            print(name)
        return 0

    return sync(example_path, refs, check=args.check)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
