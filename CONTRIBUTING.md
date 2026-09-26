# Contributing

Contributions that improve portability, diagnostics, safety, documentation, or test coverage are welcome.

## Before opening a pull request

1. Keep the scripts dependency-free and compatible with Python 3.11 or newer.
2. Do not add real user configuration, credentials, personal paths, symlinks, generated state, or OS permissions.
3. Keep the review contract: `preview` builds a plan, `apply` needs an unchanged plan, and a kept or merged local file is never replaced silently.
4. Add or update tests for every behavior change.
5. Run:

```text
python -m unittest discover -s tests -v
python scripts/portable_config.py scan --repo-root . --public-audit
git diff --check
```

Run the wrapper smoke test (`codex-sync.sh` or `codex-sync.ps1` with `bootstrap --working-tree --skills none` and temporary `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and `AGENTS_HOME`) on the operating system you changed.

## Design rules

- Public safety is an allowlist first; local-only keys are refused, not merely documented.
- Paths from manifests stay relative and inside their declared root.
- Managed sources and targets are regular files or directories, never links or reparse points.
- Any write to a live profile requires a reviewed, unchanged plan and a journal.
- Third-party skills are referenced by full commit SHA and fetched only when chosen; nothing from them runs during preparation.
- New catalog entries need short `ru` and `en` explanations and, for third-party skills, the author's license.
- New configuration keys must be checked against current official Codex and Claude Code documentation and the local-only policy.

## Pull requests

Explain the user-visible outcome, security impact, tests, and platform coverage. Keep unrelated changes separate. By contributing, you agree that your contribution is licensed under the MIT License.
