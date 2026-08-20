"""Managed-mode detection across the Nix install shapes.

The NixOS module and the Home Manager module both mark the install as
managed, and the CLI then refuses a configuration change that it cannot
keep. The two modules write different values, and an install from an
earlier version writes an empty marker, so detection must handle all three.
"""

import os

import pytest

from prometheus_cli import config as config_mod


@pytest.fixture
def prometheus_home(tmp_path, monkeypatch):
    home = tmp_path / ".prometheus"
    home.mkdir()
    monkeypatch.setenv("PROMETHEUS_HOME", str(home))
    monkeypatch.delenv("PROMETHEUS_MANAGED", raising=False)
    return home


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        ("nixos", "nixos"),
        ("home-manager", "home-manager"),
        ("HOME-MANAGER", "home-manager"),
        # An install from an earlier version sets a bare "true". Only the
        # NixOS module did that.
        ("true", "nixos"),
        ("1", "nixos"),
        # Homebrew is not a distribution method, so these must not block a
        # configuration change.
        ("brew", None),
        ("homebrew", None),
        (None, None),
    ],
)
def test_env_var_names_the_managing_system(prometheus_home, monkeypatch, env_value, expected):
    if env_value is None:
        monkeypatch.delenv("PROMETHEUS_MANAGED", raising=False)
    else:
        monkeypatch.setenv("PROMETHEUS_MANAGED", env_value)

    assert config_mod.get_managed_system() == expected
    assert config_mod.is_managed() is (expected is not None)


@pytest.mark.parametrize(
    ("marker_text", "expected"),
    [
        ("home-manager", "home-manager"),
        ("nixos", "nixos"),
        # An install from an earlier version has an empty marker. Only the
        # NixOS module wrote one.
        ("", "nixos"),
    ],
)
def test_marker_file_names_the_managing_system(
    prometheus_home, monkeypatch, marker_text, expected
):
    """An interactive shell reads .managed, not the PROMETHEUS_MANAGED of the service."""
    (prometheus_home / ".managed").write_text(marker_text, encoding="utf-8")
    monkeypatch.delenv("PROMETHEUS_MANAGED", raising=False)

    assert config_mod.get_managed_system() == expected
    assert config_mod.is_managed() is True


def test_env_var_wins_over_the_marker(prometheus_home, monkeypatch):
    (prometheus_home / ".managed").write_text("nixos", encoding="utf-8")
    monkeypatch.setenv("PROMETHEUS_MANAGED", "home-manager")

    assert config_mod.get_managed_system() == "home-manager"


@pytest.mark.parametrize("managed_value", ["nixos", "home-manager"])
def test_managed_install_names_its_system_and_offers_an_update(
    prometheus_home, monkeypatch, tmp_path, managed_value
):
    """The message names the system, so the user knows what owns the install."""
    monkeypatch.setenv("PROMETHEUS_MANAGED", managed_value)

    # This test uses an install tree of its own. The real checkout can carry
    # a stamp from the install shape of the contributor. A stamp answers
    # first, and detection never reaches the managed state under test.
    install_tree = tmp_path / "install"
    install_tree.mkdir()

    assert managed_value in config_mod.format_managed_message("set model")
    assert "set model" in config_mod.format_managed_message("set model")
    assert config_mod.get_managed_update_command()
    assert config_mod.detect_install_method(install_tree) == managed_value
    # `prometheus update` cannot run on a managed install, so the advice must not
    # name it.
    assert config_mod.recommended_update_command() != "prometheus update"


@pytest.mark.parametrize("managed_value", ["nixos", "home-manager"])
def test_a_stamp_can_name_every_managed_system(
    prometheus_home, monkeypatch, tmp_path, managed_value
):
    """A stamp must give back every value that detection can return.

    Detection reads the stamp against an allowlist. A managed system that is
    absent from that allowlist gives "unknown". The update guidance then
    names a command that the managed guard refuses.
    """
    monkeypatch.delenv("PROMETHEUS_MANAGED", raising=False)
    install_tree = tmp_path / "install"
    install_tree.mkdir()

    config_mod.stamp_install_method(managed_value, project_root=install_tree)

    assert config_mod.detect_install_method(install_tree) == managed_value


def test_unmanaged_install_offers_no_update_command(prometheus_home, monkeypatch):
    monkeypatch.delenv("PROMETHEUS_MANAGED", raising=False)
    assert config_mod.get_managed_update_command() is None


def test_unreadable_marker_still_reports_managed(prometheus_home, monkeypatch):
    """A marker we cannot read is still a marker. Fail closed, not open."""
    marker = prometheus_home / ".managed"
    marker.write_text("home-manager", encoding="utf-8")
    marker.chmod(0o000)
    monkeypatch.delenv("PROMETHEUS_MANAGED", raising=False)
    try:
        if os.access(marker, os.R_OK):
            pytest.skip("running as a user that ignores file modes (for example root)")
        assert config_mod.is_managed() is True
    finally:
        marker.chmod(0o600)
