# Examples

These files are not installed by the default manifest.

- `example-skill/` shows the minimum shape of a user-owned skill.
- `example-agent.toml` shows a portable custom-agent definition without machine paths.
- `common-config.json` shows a small portable config allowlist.
- `example-claude-agent.md` shows a portable Claude Code subagent definition.
- `claude-common-config.json` shows a small portable Claude `settings.json` allowlist.

Copy only the examples you understand into the corresponding canonical directory, add them to `manifests/portable-files.json`, run `doctor`, and review a new plan.
