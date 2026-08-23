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
- `target_root` is `codex` or `agents`.
- `target` is relative to that local root.
- paths must use forward slashes and cannot contain `..`, drive letters, symlinks, or junctions.
- sensitive files and reserved managed areas such as `config.toml`, `skills/`, `agents/`, and
  `backups/` cannot be reached through `portable_files`; use their dedicated allowlists.

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

## Deletions

The tool never mirrors deletions automatically. To remove an owned file:

1. remove it from the canonical private repository;
2. remove it manually from each device after reviewing its purpose;
3. update the manifest if the whole skill or agent is no longer managed.

This avoids turning a manifest mistake into cross-device data loss.
