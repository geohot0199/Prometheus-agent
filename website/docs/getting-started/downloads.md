---
sidebar_position: 1.5
title: "Downloads"
description: "Download Prometheus Agent for Linux, macOS, Windows, and Android"
---

# Downloads

**Prometheus Agent** is free, MIT-licensed, and self-hosted. Install the CLI in one command, or add the native desktop app after install.

## CLI (recommended)

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/geohot0199/Prometheus-agent/main/scripts/install.sh | bash
```

Then reload your shell and start chatting:

```bash
source ~/.bashrc    # or: source ~/.zshrc
prometheus
```

### Windows (native, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/geohot0199/Prometheus-agent/main/scripts/install.ps1)
```

The installer sets up uv, Python 3.11, Node.js, ripgrep, ffmpeg, and a portable Git Bash if needed. Native Windows install lives under `%LOCALAPPDATA%\prometheus`.

## Desktop app

After the CLI is installed:

```bash
prometheus desktop
```

That builds **Prometheus Desktop** for your OS (macOS, Windows, or Linux). You can also pass `--include-desktop` to the Unix installer:

```bash
curl -fsSL https://raw.githubusercontent.com/geohot0199/Prometheus-agent/main/scripts/install.sh | bash -s -- --include-desktop
```

Packaged installers (`.dmg` / `.exe`) are published on the [GitHub Releases](https://github.com/geohot0199/Prometheus-agent/releases) page when a release is cut.

| Platform | How to get it |
| --- | --- |
| macOS 12+ | CLI installer, then `prometheus desktop` — or a release `.dmg` |
| Windows 10/11 | PowerShell installer, then `prometheus desktop` — or a release `.exe` |
| Linux (any distro) | CLI installer (`install.sh`). Run `prometheus desktop` for the native app |

## Source

```bash
git clone https://github.com/geohot0199/Prometheus-agent.git
cd Prometheus-agent
```

See [Installation](./installation.md) for layout, Termux notes, and troubleshooting, and [Updating](./updating.md) for `prometheus update`.
