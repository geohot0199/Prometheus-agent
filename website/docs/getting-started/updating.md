---
sidebar_position: 3
title: "Updating & Uninstalling"
description: "How to update Prometheus Agent to the latest version or uninstall it"
---

# Updating & Uninstalling

## Updating

Update to the latest version with a single command:

```bash
prometheus update
```

This pulls the latest code from `main`, updates dependencies, and prompts you to configure any new options that were added since your last update.

:::tip
`prometheus update` automatically detects new configuration options and prompts you to add them. If you skipped that prompt, you can manually run `prometheus config check` to see missing options, then `prometheus config migrate` to interactively add them.
:::

### What happens during an update

When you run `prometheus update`, the following steps occur:

1. **Pre-update snapshot** — a lightweight state snapshot is saved by default (covers pairing data, cron jobs, `config.yaml`, `.env`, `auth.json`, and other state files that get modified at runtime; individual files over 1 GiB are skipped so a large sessions DB never slows the update down). Controlled by `updates.pre_update_backup` (`quick` by default, `full` for a zip of all of `PROMETHEUS_HOME`, `off` to disable). Recoverable via the snapshot restore flow described under [Snapshots and rollback](../user-guide/checkpoints-and-rollback.md).
2. **Git pull** — pulls the latest code from the `main` branch and updates submodules
3. **Post-pull syntax validation + auto-rollback** — after the pull, Prometheus compiles the nine critical files every `prometheus` invocation imports at startup. If any fails to parse (e.g. an orphan merge-conflict marker, an accidentally truncated file), Prometheus runs `git reset --hard <pre-pull-sha>` to roll the install back so your shell stays bootable. Re-run `prometheus update` once the upstream fix lands.
4. **Dependency install** — runs `uv pip install -e ".[all]"` to pick up new or changed dependencies
5. **Config migration** — detects new config options added since your version and prompts you to set them
6. **Gateway auto-restart** — running gateways are refreshed after the update completes so the new code takes effect immediately. Service-managed gateways (systemd on Linux, launchd on macOS) are restarted through the service manager. Manual gateways are relaunched automatically when Prometheus can map the running PID back to a profile.

### Updating against a non-default branch: `--branch`

By default `prometheus update` tracks `origin/main`. Pass `--branch <name>` to update against a different branch — useful for QA channels, feature branches, or release-candidate testing:

```bash
prometheus update --branch release-candidate
prometheus update --check --branch experimental   # preview behindness only
```

If your local checkout is on a different branch, Prometheus auto-stashes any uncommitted work, switches HEAD to the target branch, and then pulls. Branches that don't exist locally are auto-tracked from `origin/<name>` (`git checkout -B <name> origin/<name>`). Branches that don't exist anywhere fail cleanly — your stashed changes are restored before exit so you're never stranded in a weird state. The `main`-only fork-upstream sync logic is automatically skipped on non-`main` branches.

### Checkout parked on a feature branch

If the source checkout was left sitting on a feature branch (by tooling, a worktree experiment, or a manual checkout), `prometheus update` only switches it back to the update target automatically when that is provably safe: the working tree is clean **and** every commit on the parked branch is already contained in `origin/main` (`git cherry` reports nothing unmerged). In that case the update says so — `Checkout was parked on '<branch>' (fully merged) — switched back to main` — and stays on `main` afterwards.

When the parked branch has uncommitted changes or unmerged commits, Prometheus does **not** touch it. The code update is marked **SKIPPED** with a loud warning naming the branch, how far behind `origin/main` it is, and the exact commands to resolve — instead of pretending the update succeeded. The completion line always shows the actual branch and HEAD (`✓ Update complete! [main @ 30fcf9580]`) so drift is visible at a glance. Set `updates.auto_switch_parked_branch: false` in `config.yaml` to disable the auto-switch entirely (the skip warning still fires).

### Local changes on non-interactive updates

When you run `prometheus update` in a terminal, Prometheus stashes any uncommitted source-tree changes, pulls, then **asks** whether to restore them — exactly as it always has. Nothing changes for interactive updates.

When the update runs **without a terminal** — from the desktop/chat app's "Update" button or a gateway-triggered update — there's no prompt to answer. The `updates.non_interactive_local_changes` setting decides what happens to your stashed changes:

```yaml
# ~/.prometheus/config.yaml
updates:
  non_interactive_local_changes: stash   # default: keep + auto-restore
  # non_interactive_local_changes: discard  # throw local source edits away
```

- `stash` (default) — auto-stash, pull, then auto-restore your changes on top of the updated code. Nothing is lost; if a restore hits conflicts they're preserved in a git stash for manual recovery.
- `discard` — auto-stash and drop the stash after the pull, so the update always lands on a clean tree. Use this only on machines where you never intend to keep local edits to the Prometheus source. It stash-drops (not `git reset --hard` + `git clean -fd`), so ignored paths like `node_modules`, `venv`, and build outputs are never touched.

In the desktop app this is **Settings → Advanced → In-App Update Local Changes**.

**Desktop updates never auto-restore.** The desktop updater invokes `prometheus update --keep-stash`: local source edits are still stashed so the update can proceed, but they are **not** re-applied afterward — they stay parked in `git stash` and the update log prints the exact `git stash apply <ref>` command to bring them back. This prevents local edits from silently riding along across desktop updates and breaking the freshly updated install. (`non_interactive_local_changes: discard` still wins if you've opted into discarding.) To restore parked changes manually:

```bash
cd ~/.prometheus/prometheus-agent   # or your install root
git stash list --format='%gd %H %s'   # find the prometheus-update-autostash entry
git stash apply stash@{0}
```

You can pass `--keep-stash` to a terminal `prometheus update` too if you want the same never-reapply behavior interactively.

### Preview-only: `prometheus update --check`

Want to know if an update is available before pulling? Run `prometheus update --check` — it fetches and compares commits against `origin/main`. No files are modified, no gateway is restarted. Useful in scripts and cron jobs that gate on "is there an update".

### Full pre-update backup: `--backup`

For high-value profiles (production gateways, shared team installs) you can opt into a full pre-pull backup of `PROMETHEUS_HOME` (config, auth, sessions, skills, pairing):

```bash
prometheus update --backup
```

Or make it the default for every run:

```yaml
# ~/.prometheus/config.yaml
updates:
  pre_update_backup: full
```

`updates.pre_update_backup` is a single knob with three modes: `quick` (default — the lightweight state snapshot described above), `full` (the quick snapshot plus a complete `PROMETHEUS_HOME` zip; can add minutes on large homes), and `off` (no pre-update backup at all — `--no-backup` does the same for a single run). Legacy boolean values still work: `true` means `full`, `false` means `off`.

:::tip Moving to a new machine instead?
Update backups protect an in-place update. If you're migrating your whole setup to different hardware, use `prometheus backup` + `prometheus import` instead — see [Exporting Prometheus to another machine](/reference/faq#exporting-prometheus-to-another-machine) and [`prometheus backup` vs `prometheus profile export`](/reference/faq#prometheus-backup-vs-prometheus-profile-export).
:::

### Windows: another `prometheus.exe` is running

On Windows, `prometheus update` will refuse to run if it detects another `prometheus.exe` process holding the venv's entry-point executable open — most commonly the Prometheus Desktop app's spawned backend, an open `prometheus` REPL in another terminal, or a running gateway:

```
$ prometheus update
✗ Another prometheus.exe is running:
    PID 12345  prometheus.exe

  Updating now would fail to overwrite ...\venv\Scripts\prometheus.exe because
  Windows blocks REPLACE on a running executable.

  Close Prometheus Desktop, exit any open `prometheus` REPLs, and
  stop the gateway (`prometheus gateway stop`) before retrying.
  Override with `prometheus update --force` if you've already
  confirmed those processes will not write to the venv.
```

Close the listed processes and re-run. If you're sure the concurrent process won't interfere (rare — usually only useful when an antivirus shim is mis-attributed), pass `--force` to skip the check. In that case the updater will still retry the `.exe` rename with exponential backoff and, on stubborn locks, schedule the replacement for next reboot via `MoveFileEx(MOVEFILE_DELAY_UNTIL_REBOOT)` so the update can complete.

A second, separate guard refuses to touch the venv while any process is running from its Python interpreter (the Desktop app's backend, a gateway, a Python REPL). Those processes keep native extension files (`.pyd`) locked, and a dependency sync that dies partway on an access-denied error strands the install between versions. This guard is **not** bypassed by `--force`; if you're certain the detected holders are false positives, use the explicit `prometheus update --force-venv`.

#### Windows venv recreation is transactional

When the Windows installer must recreate an existing `venv`, it first moves the old directory to a unique `venv.stale.*` name, then creates and verifies the replacement. The old tree is deleted only after the dependency install completes and the baseline imports pass in the new tree — until then it is the rollback source (recorded in `venv.pending-backup`).

If the move cannot be completed, the installer stops and leaves the live `venv` untouched. If `uv` fails or reports success without creating the interpreter, any partial replacement is moved to `venv.failed.*` and the previous venv is restored. This keeps the health and blocker checks usable after a failed install.

A `venv.stale.*` or `venv.failed.*` directory can remain when another process still owns a file handle. Close Prometheus Desktop, gateways, and Python processes using the install, then retry the install/update; parked directories are cleaned up best-effort after a successful recreation.

Expected output looks like:

```
$ prometheus update
Updating Prometheus Agent...
📥 Pulling latest code...
Already up to date.  (or: Updating abc1234..def5678)
📦 Updating dependencies...
✅ Dependencies updated
🔍 Checking for new config options...
✅ Config is up to date  (or: Found 2 new options — running migration...)
🔄 Restarting gateways...
✅ Gateway restarted
✅ Prometheus Agent updated successfully!
```

### Recommended Post-Update Validation

`prometheus update` handles the main update path, but a quick validation confirms everything landed cleanly:

1. `git status --short` — if the tree is unexpectedly dirty, inspect before continuing
2. `prometheus doctor` — checks config, dependencies, and service health
3. `prometheus --version` — confirm the version bumped as expected
4. If you use the gateway: `prometheus gateway status`
5. If `doctor` reports npm audit issues: run `npm audit fix` in the flagged directory

:::warning Dirty working tree after update
If `git status --short` shows unexpected changes after `prometheus update`, stop and inspect them before continuing. This usually means local modifications were reapplied on top of the updated code, or a dependency step refreshed lockfiles.
:::

### If your terminal disconnects mid-update

`prometheus update` protects itself against accidental terminal loss:

- The update ignores `SIGHUP`, so closing your SSH session or terminal window no longer kills it mid-install. `pip` and `git` child processes inherit this protection, so the Python environment cannot be left half-installed by a dropped connection.
- All output is mirrored to `~/.prometheus/logs/update.log` while the update runs. If your terminal disappears, reconnect and inspect the log to see whether the update finished and whether the gateway restart succeeded:

```bash
tail -f ~/.prometheus/logs/update.log
```

- `Ctrl-C` (SIGINT) and system shutdown (SIGTERM) are still honored — those are deliberate cancellations, not accidents.

You no longer need to wrap `prometheus update` in `screen` or `tmux` to survive a terminal drop.

### Checking your current version

```bash
prometheus --version
```

Compare against the latest release at the [GitHub releases page](https://github.com/geohot0199/Prometheus-agent/releases).

### Updating from Messaging Platforms

You can also update directly from Telegram, Discord, Slack, WhatsApp, or Teams by sending:

```
/update
```

This pulls the latest code, updates dependencies, and restarts running gateways. The bot will briefly go offline during the restart (typically 5–15 seconds) and then resume.

### Manual Update

If you installed manually (not via the quick installer):

```bash
cd /path/to/prometheus-agent
# Activate the venv you created during install (outside the source tree)
export VIRTUAL_ENV="$HOME/.prometheus/venvs/prometheus-dev"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# Pull latest code
git pull origin main

# Reinstall (picks up new dependencies)
uv pip install -e ".[all]"

# Check for new config options
prometheus config check
prometheus config migrate   # Interactively add any missing options
```

### Rollback instructions

If an update introduces a problem, you can roll back to a previous version:

```bash
cd /path/to/prometheus-agent

# List recent versions
git log --oneline -10

# Roll back to a specific commit
git checkout <commit-hash>
uv pip install -e ".[all]"

# Restart the gateway if running
prometheus gateway restart
```

To roll back to a specific release tag (substitute your previous tag — e.g. a recent release like `v2026.5.16`, or any earlier tag from `git tag --sort=-version:refname`):

```bash
git checkout vX.Y.Z
uv pip install -e ".[all]"
```

:::warning
Rolling back may cause config incompatibilities if new options were added. Run `prometheus config check` after rolling back and remove any unrecognized options from `config.yaml` if you encounter errors.
:::

### Note for Nix users

Nix is no longer an explicitly supported install path (best-effort only) — see [Nix Setup](./nix-setup.md). If you installed via Nix flake, updates are managed through the Nix package manager:

```bash
# Update the flake input
nix flake update prometheus-agent

# Or rebuild with the latest
nix profile upgrade prometheus-agent
```

Nix installations are immutable — rollback is handled by Nix's generation system:

```bash
nix profile rollback
```

See [Nix Setup](./nix-setup.md) for more details.

---

## Uninstalling

```bash
prometheus uninstall
```

The uninstaller gives you the option to keep your configuration files (`~/.prometheus/`) for a future reinstall.

:::tip Moving to a new machine rather than leaving?
Take your setup with you before removing anything: `prometheus backup` captures the entire `~/.prometheus` directory including credentials, while `prometheus profile export` packs a single profile with credentials excluded by design (so an export alone is not a full backup). See [`prometheus backup` vs `prometheus profile export`](/reference/faq#prometheus-backup-vs-prometheus-profile-export).
:::

### Manual Uninstall

```bash
rm -f ~/.local/bin/prometheus
rm -rf /path/to/prometheus-agent
rm -rf ~/.prometheus            # Optional — keep if you plan to reinstall
```

:::info
If you installed the gateway as a system service, stop and disable it first:
```bash
prometheus gateway stop
# Linux: systemctl --user disable prometheus-gateway
# macOS: launchctl remove ai.prometheus.gateway
```
:::
