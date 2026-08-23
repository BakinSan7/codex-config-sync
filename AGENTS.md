# Repository rules

- This repository is a public, dependency-free tool for safely synchronizing selected Codex configuration between Windows and macOS.
- Never add credentials, authentication state, cookies, private keys, chat history, generated memories, plugin caches, local project trust, or real user data.
- Never add personal funding links, cryptocurrency addresses, or donation QR codes to this tracked template. Upstream support links belong in repository metadata so generated repositories do not inherit them.
- Treat `portable/`, `personal-skills/`, `agents/`, and `config/` as public examples. Use placeholders only.
- Keep synchronization opt-in and two-phase: `plan` must precede `apply`.
- Never follow symlinks, junctions, or reparse points in managed paths.
- Never add automatic commit, push, permission, plugin authorization, MCP authorization, or third-party code execution.
- Before committing, run the unit tests, the public safety scan, wrapper smoke tests, and `git diff --check`.
