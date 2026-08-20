# Prometheus CLI Reference

Live sources when anything looks stale: `prometheus --help`, `prometheus <command> --help`,
https://github.com/geohot0199/Prometheus-agent/docs/reference/cli-commands

### Global Flags

```
prometheus [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
prometheus chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
prometheus setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
prometheus model                Interactive model/provider picker
prometheus fallback [add|remove|list]  Fallback provider chain
prometheus config [show|edit|get|set|unset|path|env-path|check|migrate]
prometheus login / logout       OAuth sign-in / clear stored auth
prometheus doctor [--fix]       Check dependencies and config
prometheus status [--all]       Component status
```

### Tools & Skills

```
prometheus tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

prometheus skills list|browse|search QUERY|inspect ID
prometheus skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
prometheus skills config        Enable/disable skills per platform
prometheus skills check|update|uninstall|publish PATH
prometheus skills tap add REPO  Add a GitHub repo as a skill source
prometheus bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
prometheus mcp add NAME (--url or --command) | remove | list | test NAME
prometheus mcp catalog | install NAME     Curated catalog install
prometheus mcp configure NAME             Toggle tool selection
prometheus mcp serve                      Run Prometheus as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
prometheus gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `prometheus photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://github.com/geohot0199/Prometheus-agent/docs/user-guide/messaging/

### Sessions

```
prometheus sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
prometheus cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
prometheus webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
prometheus profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
prometheus profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
prometheus auth                 Interactive credential manager
prometheus auth add [PROVIDER]  Add OAuth or API-key credential (prometheus, openai-codex, qwen-oauth, …)
prometheus auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
prometheus desktop / gui        Native desktop app
prometheus dashboard            Web admin panel + embedded chat (--stop / --status)
prometheus proxy                OpenAI-compatible local proxy backed by an OAuth provider
prometheus portal               Quick setup / sign in via Prometheus Portal
prometheus kanban <verb>        Multi-agent work-queue board
prometheus project              Named multi-folder workspaces
prometheus skin list|use|set    Switch/tweak skins (see references/themes.md)
prometheus pets <verb>          Pet mascots (see references/petdex.md)
prometheus memory setup|status|off|reset   Memory provider
prometheus secrets bitwarden|onepassword   External secret stores
prometheus moa                  Mixture-of-Agents slots
prometheus hooks / security / backup / import / checkpoints / console
prometheus logs [-f] [errors]   View agent/error logs
prometheus send                 One-off message through a gateway platform
prometheus pairing / plugins / insights / journey / computer-use
prometheus acp                  ACP server (IDE integration)
prometheus completion bash|zsh|fish
prometheus update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `prometheus photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `prometheus config edit` · [Configuration docs](https://github.com/geohot0199/Prometheus-agent/docs/user-guide/configuration) |
| Tools / toolsets | `prometheus tools list` · [Tools reference](https://github.com/geohot0199/Prometheus-agent/docs/reference/tools-reference) |
| Skills catalog | `prometheus skills browse` · [Skills catalog](https://github.com/geohot0199/Prometheus-agent/docs/reference/skills-catalog) |
| Provider setup | `prometheus model` · [Providers guide](https://github.com/geohot0199/Prometheus-agent/docs/integrations/providers) |
| Env variables | `prometheus config env-path` · [Env vars reference](https://github.com/geohot0199/Prometheus-agent/docs/reference/environment-variables) |
| Gateway logs | `~/.prometheus/logs/gateway.log` (or `prometheus logs`) |
| Sessions | `prometheus sessions browse` (reads state.db) |
