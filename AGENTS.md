# Repository rules

- This repository is a public, dependency-free tool for a reviewed Codex and Claude Code profile on Windows and macOS, plus a catalog of skills offered at install time.
- Never add credentials, authentication state, cookies, private keys, chat history, generated memories, plugin caches, local project trust, personal paths or real user data.
- Never add personal funding links, cryptocurrency addresses, or donation QR codes to tracked files. Support links belong in repository metadata so generated repositories do not inherit them.
- `portable/` holds public examples only. `personal-skills/` holds the published catalog skills; they must stay free of personal data and project names.
- Third-party skills are referenced in `manifests/external-skills.json` by full commit SHA with their license; never copy their files into this repository.
- Keep the review contract: `preview` before `apply`, per-item decisions, remembered `keep`/`merge`, journaled rollback.
- Never follow symlinks, junctions, or reparse points in managed paths.
- Never add automatic publication, permission changes, plugin or MCP authorization, or execution of third-party code during preparation. `publish` commits only paths the user lists.
- Keep `docs/SKILLS.md`, `README.md` and `README.ru.md` in line with `manifests/skill-catalog.json`.
- Before committing, run the unit tests, `python scripts/portable_config.py scan --repo-root . --public-audit`, a wrapper smoke test, and `git diff --check`.
