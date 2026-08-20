"""Tests for get_prometheus_home() profile-mode fallback warning.

Regression test for https://github.com/geohot0199/Prometheus-agent/issues/18594.

When PROMETHEUS_HOME is unset but an active_profile file indicates a non-default
profile is active, get_prometheus_home() should:
  1. STILL return ~/.prometheus (raising would brick 30+ module-level callers)
  2. Emit a loud one-shot warning to stderr so operators can diagnose
     cross-profile data contamination after the fact.

The warning goes to stderr directly (not through logging) because this
function is called at module-import time from 30+ sites, often before the
logging subsystem has been configured.
"""

from pathlib import Path

import pytest


@pytest.fixture
def fresh_constants(monkeypatch, tmp_path):
    """Import prometheus_constants fresh and reset the one-shot warn flag."""
    import importlib
    import prometheus_constants
    importlib.reload(prometheus_constants)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PROMETHEUS_HOME", raising=False)
    return prometheus_constants


class TestGetPrometheusHomeProfileWarning:
    def test_classic_mode_no_active_profile_no_warning(
        self, fresh_constants, tmp_path, capsys
    ):
        """Classic mode: no active_profile file → silent, returns ~/.prometheus."""
        result = fresh_constants.get_prometheus_home()
        assert result == tmp_path / ".prometheus"
        assert "PROMETHEUS_HOME fallback" not in capsys.readouterr().err


    def test_named_profile_unset_home_warns_once(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile=coder + PROMETHEUS_HOME unset → warn loudly, still return fallback."""
        prometheus_dir = tmp_path / ".prometheus"
        prometheus_dir.mkdir()
        (prometheus_dir / "active_profile").write_text("coder\n")

        result = fresh_constants.get_prometheus_home()

        # 1. Still returns the fallback — no import-time crash
        assert result == tmp_path / ".prometheus"
        # 2. Stderr got the warning exactly once
        err = capsys.readouterr().err
        assert err.count("PROMETHEUS_HOME fallback") == 1
        assert "'coder'" in err
        assert "#18594" in err

        # 3. One-shot: second and third calls don't re-warn
        fresh_constants.get_prometheus_home()
        fresh_constants.get_prometheus_home()
        err2 = capsys.readouterr().err
        assert "PROMETHEUS_HOME fallback" not in err2

    def test_prometheus_home_set_suppresses_warning(
        self, fresh_constants, tmp_path, capsys, monkeypatch
    ):
        """Even if active_profile is 'coder', setting PROMETHEUS_HOME suppresses warning."""
        profile_dir = tmp_path / ".prometheus" / "profiles" / "coder"
        profile_dir.mkdir(parents=True)
        (tmp_path / ".prometheus" / "active_profile").write_text("coder\n")
        monkeypatch.setenv("PROMETHEUS_HOME", str(profile_dir))

        result = fresh_constants.get_prometheus_home()

        assert result == profile_dir
        assert "PROMETHEUS_HOME fallback" not in capsys.readouterr().err

    def test_unreadable_active_profile_no_crash(
        self, fresh_constants, tmp_path, capsys
    ):
        """active_profile that can't be decoded → fall through silently."""
        prometheus_dir = tmp_path / ".prometheus"
        prometheus_dir.mkdir()
        # Write bytes that aren't valid utf-8
        (prometheus_dir / "active_profile").write_bytes(b"\xff\xfe\x00\x00")

        result = fresh_constants.get_prometheus_home()

        assert result == tmp_path / ".prometheus"
        # Shouldn't crash; shouldn't warn either (can't tell what profile was intended)
        assert "PROMETHEUS_HOME fallback" not in capsys.readouterr().err

