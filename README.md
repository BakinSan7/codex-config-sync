# Codex Config Sync

[![Validate](https://github.com/BakinSan7/codex-config-sync/actions/workflows/validate.yml/badge.svg)](https://github.com/BakinSan7/codex-config-sync/actions/workflows/validate.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows and macOS](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)](#requirements)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**One reviewed profile for Codex and Claude Code on Windows and macOS: shared instructions, portable memory, selected settings, and a catalog of skills you pick at install time.**

[Русская версия](README.ru.md)

> [!IMPORTANT]
> This is an unofficial community project. It is not affiliated with or endorsed by OpenAI or Anthropic.

## Why this exists

Copying `~/.codex` or `~/.claude` between machines mixes credentials, permissions, plugin state, caches, device paths and chat history. Codex Config Sync keeps a small, explicit profile in Git and installs independent copies on each device:

- one instructions file becomes `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md`;
- skills are offered as a catalog with short explanations, and only the ones you choose are installed;
- every change is shown as a short tree, and you decide per item: accept, keep, skip, remove or merge;
- your choices are remembered on the device, and a kept or merged local version is never replaced silently;
- writes are journaled and can be rolled back; links, junctions and reparse points are refused;
- settings that belong to one device (model, reasoning effort, permissions, hooks, MCP commands, plugins, credentials) are refused by the scripts.

## Requirements

- Windows 10/11 with PowerShell, or a supported macOS release;
- Python 3.11 or newer and Git;
- Codex and/or Claude Code for the profile to be used; the scripts themselves need only the Python standard library.

## Quick start

Clone the repository and run the first installation. The installer shows the skill catalog and asks which skills to install.

macOS:

```bash
git clone https://github.com/BakinSan7/codex-config-sync.git ~/codex-config-sync
cd ~/codex-config-sync
./codex-sync.sh bootstrap
```

Windows PowerShell:

```powershell
git clone https://github.com/BakinSan7/codex-config-sync.git $HOME\codex-config-sync
cd $HOME\codex-config-sync
.\codex-sync.ps1 bootstrap
```

When the installer runs without a terminal (for example, when an agent runs it), pass the choice explicitly: `--skills recommended`, `--skills all`, `--skills none`, or catalog numbers and names such as `--skills 1,5,fact-check-post`. To see the list first, run `catalog` (add `--lang en` for English descriptions).

To keep your own instructions and memory, use **Use this template** on GitHub, make the new repository **private**, set `repository` in `manifests/profile.json` to its `owner/name`, and clone that repository instead. Do not put personal configuration into a public fork.

## Skill catalog

| Skill | Apps | What it does | Source |
| --- | --- | --- | --- |
| navigate-project ★ | Codex, Claude | Restores orientation in a big project and picks one next verifiable step | bundled |
| velosiped ★ | Codex, Claude | Looks for mature existing solutions before non-trivial coding | bundled |
| cb-job-fit | Codex, Claude | Checks fit between a C&B or HR analytics vacancy and your CV; drafts a cover letter | bundled |
| obsidian-idea-capture | Codex, Claude | Captures ideas and questions as linked notes in Obsidian | bundled |
| fact-check-post ★ | Codex, Claude | Fact-checks posts and news against primary sources, claim by claim | bundled |
| deep-research | Codex, Claude | Deep multi-source research with cross-checked claims | alirezarezvani/claude-skills, MIT |
| youtube-research | Codex, Claude | Researches YouTube channels and videos from transcripts | timbroddin/skills, no license stated |
| orchestrate-subagents ★ | Codex, Claude | Runs a complex task purely through subagents | bundled |
| context-watchdog | Codex | Watches context cost in long work and prepares a handoff | bundled |
| codex-weekly-mentor | Codex | Weekly retrospective of your Codex chats | bundled |
| acceptance-frames ★ | Codex, Claude | Proves a visible change with before/after frames | BakinSan7/acceptance-frames, MIT |
| playwright | Codex, Claude | Drives a real browser from the terminal | openai/skills, Apache-2.0 |
| playwright-interactive | Codex | Persistent browser session for UI debugging | openai/skills, Apache-2.0 |
| photo-library-reconciler | Codex, Claude | Reconciles photo and video libraries by metadata and hashes | bundled |
| gpt-image-2-style-library | Codex, Claude | Style library and prompt templates for GPT Image 2 | freestylefly/awesome-gpt-image-2, MIT |
| haiku-writer | Codex, Claude | Writes a haiku about any topic (in Russian) | bundled |

★ recommended. Bundled skills live in `personal-skills/`. Third-party skills are not copied into this repository: when you choose one, the installer downloads the exact pinned commit from its author, checks the content hash, and never executes anything while preparing it. See [Skills](docs/SKILLS.md).

The `codex-config-sync` skill is always installed: it lets Codex and Claude Code run these commands for you.

## Everyday use

| Command | What it does | Writes |
| --- | --- | --- |
| `catalog` | Shows the skill catalog with ★ recommended and ✓ installed | Nothing |
| `bootstrap` | First installation: asks for skills, installs new items, verifies | Profile files |
| `preview` | Fetches the repository and shows what would change, as a tree | A local plan only |
| `apply --plan <plan> [--decisions <file>] [--accept-safe]` | Applies a reviewed plan with your choices | Profile files |
| `verify` | Checks that installed files match your choices | Nothing |
| `detail --plan <plan> --id <item>` | Shows the exact text that would change | Nothing |
| `rollback --id <transaction>` | Restores the state before an apply | Profile files |
| `scan [--public-audit]` | Looks for secrets, sensitive files and user paths | Nothing |
| `publish "message" <files>` | Commits and pushes only the listed files after tests and scan | Your repository |

Add a skill later with `preview --skills fact-check-post`, then `apply --plan <new plan> --accept-safe`. If a device already has a profile from another repository, the scripts stop instead of replacing it; `--switch-repository` switches on purpose. Details: [Sync workflow](docs/SYNC.md).

## What stays local

- the default model, reasoning effort and model availability;
- permissions, sandbox and approval settings, OS permissions;
- hooks, status line commands, MCP commands and plugin state;
- credentials, tokens, cookies, keys and password-manager data;
- chats, sessions, auto-generated memory, logs, caches and backups;
- device UI preferences such as fonts, window size and hotkeys.

Rules that belong to one Claude Code device go to `~/.claude/rules/*.md`, which Claude Code loads next to `CLAUDE.md`. See [Portability policy](docs/PORTABILITY.md).

## Important limitations

- The scanner is defense in depth, not proof that a file contains no private information.
- A merge is a complete document you approve; the tool does not merge text automatically.
- The threat model does not cover a malicious local administrator racing filesystem operations.
- Codex and Claude Code configuration evolves. Check the current official documentation before adding new keys.
- The scripts print their messages in Russian; the catalog is available in English with `--lang en`.

## Documentation

- [Sync workflow](docs/SYNC.md)
- [Skills](docs/SKILLS.md)
- [Portability policy](docs/PORTABILITY.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Prior art and licensing](docs/PRIOR_ART.md)
- [Contributing](CONTRIBUTING.md) and [Security policy](SECURITY.md)

Official references: Codex [`config.toml`](https://learn.chatgpt.com/docs/config-file/config-reference), [`AGENTS.md`](https://learn.chatgpt.com/docs/agent-configuration/agents-md) and [skills](https://learn.chatgpt.com/docs/skills-and-plugins); Claude Code [memory and rules](https://code.claude.com/docs/en/memory) and [settings](https://code.claude.com/docs/en/settings).

## License

[MIT](LICENSE) © 2026 BakinSan7. Third-party skills keep their own licenses and are downloaded from their authors.
