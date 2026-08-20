"""The decomposed command modules stay lazy after `import prometheus_cli.main`.

The main.py decomposition re-exports the sessions/update/dashboard command
surface from prometheus_cli.main so argparse wiring and monkeypatches keep
resolving. Those re-exports must not import the modules eagerly: every
`prometheus` invocation (including `prometheus --version`) would pay for update_cmd's
dependency chain (jwt, click, ...) even when no subcommand runs.
"""

import subprocess
import sys
import textwrap

import prometheus_cli.main


def test_importing_main_does_not_import_command_modules():
    code = textwrap.dedent(
        """
        import sys
        import prometheus_cli.main  # noqa: F401
        loaded = [
            m
            for m in (
                "prometheus_cli.update_cmd",
                "prometheus_cli.sessions_cmd",
                "prometheus_cli.dashboard_procs",
            )
            if m in sys.modules
        ]
        assert not loaded, f"eagerly imported: {loaded}"
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_lazy_reexports_resolve_to_real_objects():
    import prometheus_cli.dashboard_procs
    import prometheus_cli.sessions_cmd
    import prometheus_cli.update_cmd

    assert prometheus_cli.main.cmd_sessions is prometheus_cli.sessions_cmd.cmd_sessions
    assert (
        prometheus_cli.main._cmd_update_impl is prometheus_cli.update_cmd._cmd_update_impl
    )
    assert (
        prometheus_cli.main._scan_dashboard_processes
        is prometheus_cli.dashboard_procs._scan_dashboard_processes
    )
    # Back-compat alias resolves to the kill helper.
    assert (
        prometheus_cli.main._warn_stale_dashboard_processes
        is prometheus_cli.dashboard_procs._kill_stale_dashboard_processes
    )


def test_lazy_reexports_accept_monkeypatch(monkeypatch):
    sentinel = object()
    monkeypatch.setattr("prometheus_cli.main._cmd_update_impl", sentinel)
    assert prometheus_cli.main._cmd_update_impl is sentinel
