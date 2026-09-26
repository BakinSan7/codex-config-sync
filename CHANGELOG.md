# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-26

The engine was replaced by the selective sync used in the maintainer's own profile. Commands and file layout changed; see the README.

### Added

- Skill catalog (`manifests/skill-catalog.json`) with short Russian and English explanations; `catalog` lists it, and `bootstrap` asks which skills to install or takes `--skills recommended|all|none|<numbers,names>`. The choice is stored per device.
- Ten bundled skills (`personal-skills/`) and six pinned third-party skills referenced by author, commit SHA and license; third-party skills are downloaded only when chosen, verified by content hash, and never executed during preparation.
- One shared instructions source installed as both `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md`, with optional commit and pull request rules.
- Per-item review decisions (`accept`, `keep`, `skip`, `remove`, `merge`) remembered on the device; kept and merged local versions are re-offered after a profile change and never replaced silently; skipped and removed items are not reinstalled.
- Journaled apply with `rollback`, `verify`, `detail`, and a review tree that also shows agents and line-ending-only differences.
- `publish` for committing and pushing only the listed files after tests and the scanner.
- A per-device source check: the scripts stop when a device's profile came from another repository or clone, instead of replacing it; `--switch-repository` switches on purpose.
- Claude Code subagents (`claude-agents/`) and settings (`claude_settings`) with refused local-only keys (`model`, `env`, `hooks`, `statusLine`, `permissions`, plugins, credential helpers).
- Scanner rules for sensitive file names and folders; `scan --public-audit` for user-specific absolute paths.

### Changed

- The default model is now a device setting and is refused in shared Codex and Claude Code settings.
- `codex-sync.sh` and `codex-sync.ps1` wrap the new commands; `repository` in `manifests/profile.json` sets the expected `origin`.

### Removed

- The v0.1 bidirectional `plan --direction` engine, `doctor`, and the separate `portable/CLAUDE.md`, `claude-skills/` and `config/claude-*.json` inputs.

## [0.1.0] - 2026-08-23

### Added

- Hash-bound two-phase `plan` → `apply` workflow.
- Windows PowerShell and macOS Bash entrypoints.
- Common, Windows, and macOS profiles for owned skills and custom agents.
- Selective, comment-preserving updates for reviewed `config.toml` keys.
- Backups, atomic writes, verification, manual rollback, and automatic rollback on failure.
- Path containment checks and rejection of symlinks, junctions, and reparse points.
- Rejection of Windows reserved device names and trailing-dot/space path components.
- Preflight scanning of local content before a `from-device` plan is written.
- Multiline-string-aware updates for opted-in `config.toml` keys.
- Repository scanner and public-template audit.
- Windows/macOS CI, bilingual onboarding, migration guidance, and security documentation.

[Unreleased]: https://github.com/BakinSan7/codex-config-sync/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/BakinSan7/codex-config-sync/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/BakinSan7/codex-config-sync/releases/tag/v0.1.0
