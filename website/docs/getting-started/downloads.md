---
sidebar_position: 1.5
title: "Downloads"
description: "Download Prometheus Agent for Linux, macOS, Windows, and Android"
---

# Downloads

**Prometheus Agent** is free, MIT-licensed, and self-hosted. Install the CLI in one command, or add the native desktop app after install.

**Latest release:** [Prometheus Agent v0.20.4 (2026.8.20)](https://github.com/geohot0199/Prometheus-agent/releases/tag/v2026.8.20) · [all releases](https://github.com/geohot0199/Prometheus-agent/releases)

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

Pinned to this release instead of `main`:

```bash
curl -fsSL https://raw.githubusercontent.com/geohot0199/Prometheus-agent/v2026.8.20/scripts/install.sh | bash
```

### Windows (native, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/geohot0199/Prometheus-agent/main/scripts/install.ps1)
```

The installer sets up uv, Python 3.11, Node.js, ripgrep, ffmpeg, and a portable Git Bash if needed. Native Windows install lives under `%LOCALAPPDATA%\prometheus`.

Pinned to this release:

```powershell
iex (irm https://raw.githubusercontent.com/geohot0199/Prometheus-agent/v2026.8.20/scripts/install.ps1)
```

You can also download the installers from the [GitHub release assets](https://github.com/geohot0199/Prometheus-agent/releases/latest):

| Asset | Platform |
| --- | --- |
| [Prometheus-install.sh](https://github.com/geohot0199/Prometheus-agent/releases/latest/download/Prometheus-install.sh) | Linux, macOS, WSL2, Termux |
| [Prometheus-install.ps1](https://github.com/geohot0199/Prometheus-agent/releases/latest/download/Prometheus-install.ps1) | Windows 10/11 (PowerShell) |
| [Source code (zip)](https://github.com/geohot0199/Prometheus-agent/archive/refs/tags/v2026.8.20.zip) | All |
| [Source code (tar.gz)](https://github.com/geohot0199/Prometheus-agent/archive/refs/tags/v2026.8.20.tar.gz) | All |

## Desktop app

After the CLI is installed:

```bash
prometheus desktop
```

That builds **Prometheus Desktop** for your OS (macOS, Windows, or Linux). You can also pass `--include-desktop` to the Unix installer:

```bash
curl -fsSL https://raw.githubusercontent.com/geohot0199/Prometheus-agent/main/scripts/install.sh | bash -s -- --include-desktop
```

Pre-built `.dmg` / `.exe` packages are not attached to this release. Use `prometheus desktop` (or the `--include-desktop` installer flag) to build the native app locally.

| Platform | How to get it |
| --- | --- |
| macOS 12+ | CLI installer, then `prometheus desktop` |
| Windows 10/11 | PowerShell installer, then `prometheus desktop` |
| Linux (any distro) | CLI installer (`install.sh`). Run `prometheus desktop` for the native app |

## Source

```bash
git clone https://github.com/geohot0199/Prometheus-agent.git
cd Prometheus-agent
```

Or grab a tagged snapshot from [GitHub Releases](https://github.com/geohot0199/Prometheus-agent/releases).

See [Installation](./installation.md) for layout, Termux notes, and troubleshooting, and [Updating](./updating.md) for `prometheus update`.
