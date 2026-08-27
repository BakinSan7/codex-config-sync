# Portability policy

The project synchronizes reviewed behavior and reproducible user-owned files, not complete device state.

| Category | Common | OS-specific | Always local |
| --- | --- | --- | --- |
| Global instructions | Reviewed `AGENTS.md` | Rare | Project instructions in other repositories |
| Portable memory | Short manual note | Rare | Generated memory, sessions, chats, logs |
| Personal skills | Owned, portable skills | Skills with OS-only tools | Third-party installation state and dependencies |
| Custom agents | Definitions whose dependencies exist everywhere | OS-only agents | Runtime model availability and subagent limits |
| Config | Explicit stable allowlist | Explicit stable OS profile | Security, UI, paths, auth, plugins, MCP, telemetry |
| Credentials | Never | Never | Password manager, Keychain, Credential Manager, SSH agent |

## Enforced local-only configuration

The tool refuses known machine or security state rather than merely warning about it:

- `model_reasoning_effort`;
- `sandbox_mode`, `approval_policy`, and `approvals_reviewer`;
- `notify`, provider endpoints, provider tables, and profiles;
- `projects`, `plugins`, `mcp_servers`, `agents`, `windows`, `otel`, and sandbox write rules;
- desktop font, reasoning, notification, hotkey, remote-control, and window-size settings;
- secret-like configuration key names.

For Claude Code `settings.json`, the same rule refuses:

- `env` and every credential helper: `apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`,
  `otelHeadersHelper`;
- commands the terminal executes: `hooks` and `statusLine`;
- account state: `forceLoginMethod`, `forceLoginOrgUUID`, `oauthAccount`;
- secret-like key names anywhere in a settings path;
- `.credentials.json` and `~/.claude.json` as files: they hold tokens, project trust, and
  device history, and can never be listed as portable files.

Unknown future Codex or Claude Code settings are not automatically safe. The user must opt in and review current official documentation.

## Why plugins and MCP stay local

An inventory is not equivalent to a safe installation. Plugin IDs, enablement, OAuth state, MCP commands, runtime paths, environment variables, headers, and OS permissions can differ across devices. This project does not apply them.

## Why generated memory stays local

Generated memory and task history can contain private context, stale conclusions, local paths, or data that was never reviewed for publication. Only the manual Markdown note in `portable/portable-memory.md` is portable.
