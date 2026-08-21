"""Tests for gateway/outbound_text.py — extracted from gateway/run.py.

Pins both the behavior of the outbound-text safety helpers AND the
extraction contract itself: gateway/run.py must keep re-exporting every
moved name so the long tail of `from gateway.run import ...` call sites
(tests, tui_gateway, platform adapters) never breaks.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

import pytest

from gateway.outbound_text import (
    _format_exec_approval_fallback,
    _gateway_platform_value,
    _gateway_provider_error_reply,
    _gateway_surface_passes_raw_text,
    _interim_metadata,
    _is_transient_network_error,
    _looks_like_gateway_provider_error,
    _non_conversational_metadata,
    _redact_approval_command,
    _redact_gateway_user_facing_secrets,
    _sanitize_gateway_final_response,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

EXPORTED_NAMES = [
    "_format_exec_approval_fallback",
    "_gateway_platform_value",
    "_gateway_provider_error_reply",
    "_gateway_surface_passes_raw_text",
    "_GATEWAY_AUTH_ERROR_RE",
    "_GATEWAY_CONNECTION_ERROR_RE",
    "_GATEWAY_PROVIDER_ERROR_RE",
    "_GATEWAY_PROVIDER_ERROR_SHAPE_RE",
    "_GATEWAY_PROVIDER_POLICY_RE",
    "_GATEWAY_RATE_LIMIT_RE",
    "_GATEWAY_RAW_TEXT_PLATFORMS",
    "_GATEWAY_SECRET_PATTERNS",
    "_interim_metadata",
    "_is_transient_network_error",
    "_looks_like_gateway_provider_error",
    "_non_conversational_metadata",
    "_redact_approval_command",
    "_redact_gateway_user_facing_secrets",
    "_sanitize_gateway_final_response",
]


# ── extraction contract ─────────────────────────────────────────────────


def test_run_py_reexports_every_moved_name() -> None:
    """`from gateway.run import X` must keep working for all moved names."""
    tree = ast.parse((REPO_ROOT / "gateway" / "run.py").read_text(encoding="utf-8"))
    reexported: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "gateway.outbound_text"
        ):
            reexported.update(alias.name for alias in node.names)
    missing = set(EXPORTED_NAMES) - reexported
    assert not missing, f"gateway/run.py no longer re-exports: {sorted(missing)}"


def test_module_is_stdlib_only_at_import_time() -> None:
    """The extracted module must stay import-light: stdlib at module level.
    agent.* imports are allowed only inside function bodies (lazy)."""
    path = REPO_ROOT / "gateway" / "outbound_text.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    import sys

    for node in tree.body:  # top level only
        targets = []
        if isinstance(node, ast.Import):
            targets = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets = [node.module.split(".")[0]]
        for name in targets:
            assert name in sys.stdlib_module_names or name in {"__future__"}, (
                f"non-stdlib module-level import {name!r} in outbound_text.py — "
                "keep agent.* imports lazy inside functions"
            )


# ── platform normalization / surface classification ────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [("TELEGRAM", "telegram"), (" telegram ", "telegram"), ("", "")],
)
def test_platform_value_normalization(raw, expected):
    assert _gateway_platform_value(raw) == expected


def test_platform_value_unwraps_enums():
    from enum import Enum

    class Platform(Enum):
        DISCORD = "discord"

    assert _gateway_platform_value(Platform.DISCORD) == "discord"


@pytest.mark.parametrize(
    "platform,is_raw",
    [
        ("local", True),
        ("api_server", True),
        ("webhook", True),
        ("telegram", False),
        ("discord", False),
        ("", False),  # fail-closed: unknown -> chat surface
    ],
)
def test_raw_text_surface_classification(platform, is_raw):
    assert _gateway_surface_passes_raw_text(platform) is is_raw


# ── metadata markers ────────────────────────────────────────────────────


def test_non_conversational_metadata_only_marks_discord():
    assert _non_conversational_metadata(None, platform="discord") == {
        "non_conversational": True
    }
    assert _non_conversational_metadata({"a": 1}, platform="telegram") == {"a": 1}
    # original dict is never mutated
    base = {"a": 1}
    _non_conversational_metadata(base, platform="discord")
    assert base == {"a": 1}


def test_interim_metadata_marks_and_preserves():
    base = {"k": "v"}
    merged = _interim_metadata(base)
    assert merged == {"k": "v", "_interim_send": True}
    assert "_interim_send" not in base  # no mutation of caller state


# ── transient network error classification ──────────────────────────────


class TimedOut(Exception):  # name-matched classifier target
    pass


def test_transient_error_classification():
    assert _is_transient_network_error(TimedOut("slow")) is True
    assert _is_transient_network_error(ValueError("bug")) is False


def test_transient_error_walks_cause_chain():
    inner = TimedOut("inner")
    outer = RuntimeError("wrapped")
    outer.__cause__ = inner
    assert _is_transient_network_error(outer) is True


def test_transient_error_survives_self_referential_chain():
    exc = RuntimeError("loop")
    exc.__cause__ = exc  # pathological cycle — bounded walk must terminate
    assert _is_transient_network_error(exc) is False


# ── secret redaction ────────────────────────────────────────────────────


def test_user_facing_redaction_masks_secret_key():
    secret = "sk-" + "aB3" * 14
    out = _redact_gateway_user_facing_secrets(f"failed with {secret}")
    assert secret not in out


def test_user_facing_redaction_handles_none_and_empty():
    assert _redact_gateway_user_facing_secrets("") == ""
    assert _redact_gateway_user_facing_secrets(None) == ""  # type: ignore[arg-type]


def test_approval_command_redaction():
    secret = "ghp_" + "x9" * 20
    out = _redact_approval_command(f"curl -H 'Authorization: token {secret}'")
    assert secret not in out
    assert _redact_approval_command(None) == ""  # type: ignore[arg-type]


# ── provider error detection / shaping ─────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "API call failed after 3 retries",
        "HTTP 500 from upstream",
        "Error code: 429",
        "connection refused",
    ],
)
def test_provider_error_shapes_detected(text):
    assert _looks_like_gateway_provider_error(text) is True


def test_assistant_prose_not_misclassified():
    # Heuristic 1: length. Long answers that merely mention HTTP codes are
    # not provider envelopes.
    long_prose = (
        "When debugging APIs you will meet many status codes. "
        + "HTTP 404 means 'not found'. " * 20
    )
    assert len(long_prose) > 400
    assert _looks_like_gateway_provider_error(long_prose) is False
    # Heuristic 2: position. A SHORT message with the marker buried
    # mid-paragraph is prose, not an envelope (marker must lead).
    buried = (
        "Note for later: an HTTP 404 response just means the resource "
        "was not found on the server, nothing more."
    )
    assert _looks_like_gateway_provider_error(buried) is False
    assert _looks_like_gateway_provider_error("") is False


def test_provider_error_reply_categories():
    assert "authentication" in _gateway_provider_error_reply(
        "provider authentication failed (401)"
    ).lower()
    assert "rate" in _gateway_provider_error_reply("rate limited, 429").lower()
    # generic fallback for unknown provider failures
    assert _gateway_provider_error_reply("api call failed").startswith("⚠️")


# ── final response sanitization ─────────────────────────────────────────


def test_raw_surfaces_pass_through_untouched():
    raw = "diagnostic sk-" + "z" * 30
    assert _sanitize_gateway_final_response("local", raw) == raw


def test_chat_surface_gets_redacted_provider_category():
    secret = "sk-" + "q7" * 20
    out = _sanitize_gateway_final_response("telegram", f"API call failed: {secret}")
    assert secret not in out
    assert out.startswith("⚠️")  # rewritten to user-safe category


def test_chat_surface_keeps_normal_prose_but_redacts():
    secret = "sk-" + "m2" * 20
    out = _sanitize_gateway_final_response(
        "telegram", f"Here is your summary. (debug token {secret}) done."
    )
    assert "Here is your summary" in out
    assert secret not in out


def test_lone_surrogates_never_reach_chat_surface():
    broken = "hello \ud800 world"  # lone UTF-16 surrogate crashes chat encoders
    out = _sanitize_gateway_final_response("telegram", broken)
    out.encode("utf-8")  # must not raise UnicodeEncodeError


# ── exec approval fallback rendering ────────────────────────────────────


def test_exec_approval_fallback_full_menu():
    text = _format_exec_approval_fallback(
        "rm -rf /", "recursive delete", "!", allow_permanent=True, allow_session=True
    )
    assert "`!approve`" in text
    assert "`!approve session`" in text
    assert "`!approve always`" in text
    assert "`!deny`" in text
    assert "rm -rf /" in text


def test_exec_approval_fallback_smart_deny_minimal():
    text = _format_exec_approval_fallback(
        "curl evil", "smart deny", "!", smart_denied=True
    )
    assert "Smart DENY" in text
    assert "approve session" not in text
    assert "`!deny`" in text


def test_exec_approval_fallback_truncates_long_commands():
    text = _format_exec_approval_fallback("x" * 500, "long", "!")
    assert "x" * 500 not in text
    assert "..." in text
