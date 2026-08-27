# Configuration

The repository is intentionally useful but nearly empty by default. Your private repository becomes the canonical source after you review and customize it.

## Portable files

`manifests/portable-files.json` maps repository files to a managed root:

```json
{
  "source": "portable/AGENTS.md",
  "target_root": "codex",
  "target": "AGENTS.md",
  "platforms": ["windows", "macos"],
  "required_on_collect": false
}
```

- `source` is relative to the repository.
- `target_root` is `codex`, `agents`, or `claude`.
- `target` is relative to that local root. The `claude` root is `$CLAUDE_HOME`: the
  `CLAUDE_CONFIG_DIR` environment variable when set, `~/.claude` otherwise.
- paths must use forward slashes and cannot contain `..`, drive letters, symlinks, or junctions.
- sensitive files and reserved managed areas such as `config.toml`, `settings.json`, `skills/`,
  `agents/`, and `backups/` cannot be reached through `portable_files`; use their dedicated
  allowlists.

## Personal skills

Only add skills you own or may legally redistribute inside your private repository.

1. Put the complete skill in `personal-skills/example-skill/`.
2. Add `example-skill` to one manifest profile:

```json
"personal_skills": {
  "common": ["example-skill"],
  "windows": [],
  "macos": []
}
```

Use `windows` or `macos` when the skill depends on OS-specific commands, paths, or tools. Personal skills install to `$CODEX_HOME/skills`.

If the same name exists under `$AGENTS_HOME/skills`, planning stops. Compare the copies and keep one discovered version; the tool will not choose silently.

Third-party skills are outside the automatic installer by design. Verify their license, source revision, contents, and dependencies before installing them locally.

## Custom agents

Put reviewed TOML definitions in `agents/` and list the file name in `agents.common`, `agents.windows`, or `agents.macos`.

Do not mark an agent common merely because its TOML parses on both systems. Its commands and tools must also exist on both systems.

## Portable `config.toml` keys

The profiles are empty by default:

- `config/common.json`
- `config/windows.json`
- `config/macos.json`

Add only stable values you deliberately want to share. For example:

```json
{
  "sections": {
    "": {
      "personality": "pragmatic"
    },
    "features": {
      "memories": true
    }
  }
}
```

The tool updates only listed keys and preserves unrelated TOML values and comments. During `from-device`, it collects only keys that already exist in these JSON profiles.

Known local-only roots and sections are rejected, including reasoning effort, sandbox and approval policy, plugins, MCP servers, projects, providers, profiles, subagent runtime, Windows sandbox, telemetry, notifications, font sizes, and hotkeys.

Before adding a key, check OpenAI's current [`config.toml` reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Claude Code

The same manifest and the same safety rules cover Claude Code:

- `portable/CLAUDE.md` installs to `$CLAUDE_HOME/CLAUDE.md` through the default
  `portable_files` entry.
- Skills you own go to `claude-skills/<name>/` with a `SKILL.md` marker and are listed in the
  `claude_skills` table. They install to `$CLAUDE_HOME/skills/<name>/`.
- Subagent definitions go to `claude-agents/<name>.md` and are listed in the `claude_agents`
  table. They install to `$CLAUDE_HOME/agents/<name>.md`. See
  `examples/example-claude-agent.md`.
- Reviewed `settings.json` values live in `config/claude-common.json`,
  `config/claude-windows.json`, and `config/claude-macos.json` as dot-path keys:

```json
{
  "values": {
    "includeCoAuthoredBy": false,
    "permissions.defaultMode": "default"
  }
}
```

The tool updates only listed paths inside `$CLAUDE_HOME/settings.json` and preserves every
other value. During `from-device`, it collects only paths that already exist in these JSON
profiles. Known local-only roots are rejected outright: `env`, `apiKeyHelper`,
`awsAuthRefresh`, `awsCredentialExport`, `otelHeadersHelper`, `hooks`, `statusLine`,
`forceLoginMethod`, `forceLoginOrgUUID`, `oauthAccount`, and any secret-like key name.
`hooks` and `statusLine` stay local because they are commands the terminal executes, usually
with machine-specific paths.

Before adding a key, check Anthropic's current
[Claude Code settings reference](https://code.claude.com/docs/en/settings).

## Deletions

The tool never mirrors deletions automatically. To remove an owned file:

1. remove it from the canonical private repository;
2. remove it manually from each device after reviewing its purpose;
3. update the manifest if the whole skill or agent is no longer managed.

This avoids turning a manifest mistake into cross-device data loss.
