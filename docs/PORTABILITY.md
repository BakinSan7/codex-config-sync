# Portability policy

The profile synchronizes behaviour that should be the same everywhere. Everything that describes one device, one account or one session stays on that device.

## Common

- the shared instructions document and the optional commit and pull request rules;
- the portable memory note: short reviewed facts, no history;
- skills without device dependencies, bundled or pinned to an author's commit;
- a small allowlist of `config.toml` keys in `config/common.json` and of `settings.json` keys in `claude_settings`;
- custom agents and Claude Code subagents whose dependencies exist on every device.

## Platform

Entries under `windows` or `macos` in `manifests/portable-files.json` and in `config/<os>.json` are installed only on that operating system. A skill is not moved to another OS because its name matches: rewrite OS-specific commands and check both systems, or keep it in the platform section.

## Local only

The scripts refuse these keys even when a profile lists them (`scripts/portable_config.py`):

- Codex: `model`, `model_reasoning_effort`, `model_provider`, `approval_policy`, `sandbox_mode`, `notify`, `profile` and provider URLs; the sections `agents`, `mcp_servers`, `model_providers`, `otel`, `plugins`, `profiles`, `projects`, `sandbox_workspace_write` and `windows`; desktop keys about fonts, hotkeys, notifications, reasoning, remote control and window size; secret-like key names;
- Claude Code: `model`, `env`, `hooks`, `statusLine`, `permissions`, `sandbox`, `enabledPlugins`, `extraKnownMarketplaces`, credential helpers and account keys.

They also never copy credentials, `auth.json`, `.credentials.json`, keys, cookies, Keychain or Credential Manager data, chats, sessions, auto-memory, logs, caches, SQLite databases, backups, plugin caches, project trust or absolute project paths.

Plugins, local MCP servers, hooks, scheduled tasks and additional instruction files are shown in the review as a device inventory. They are never copied.

## Device-specific instructions

Claude Code loads `~/.claude/rules/*.md` for every project next to `~/.claude/CLAUDE.md`. Put rules that belong to one device there, so the shared file stays equal to the profile. Codex has no equivalent folder: a device-specific `AGENTS.md` stays a remembered `keep` or `merge` decision.

## Duplicate skills

If a skill name exists both in `~/.codex/skills` and in `~/.agents/skills`, review and apply stop. Compare the folders, keep one canonical copy and remove the other discovery copy yourself.
