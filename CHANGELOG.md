# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/BakinSan7/codex-config-sync/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BakinSan7/codex-config-sync/releases/tag/v0.1.0
