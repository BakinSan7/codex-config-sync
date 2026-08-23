# Contributing

Contributions that improve portability, diagnostics, safety, documentation, or test coverage are welcome.

## Before opening a pull request

1. Keep the implementation dependency-free and compatible with Python 3.11 or newer.
2. Do not add real user configuration, credentials, third-party skills, symlinks, generated state, or OS permissions.
3. Preserve the two-phase plan contract and non-deleting default behavior.
4. Add or update tests for every behavior change.
5. Run:

```text
python -m unittest discover -s tests -v
python scripts/codex_config_sync.py doctor --platform windows --public-audit
python scripts/codex_config_sync.py doctor --platform macos --public-audit
git diff --check
```

Run the platform wrapper smoke test on the operating system you changed.

## Design rules

- Public safety is an allowlist, not a blacklist alone.
- Paths from manifests must remain relative and inside their declared root.
- Managed sources and targets must be regular files or directories, never links or reparse points.
- Any write to live Codex state requires a reviewed, unchanged plan and a backup.
- Never add automatic Git publication or third-party code execution.
- New configuration keys must be checked against current official Codex documentation and the local-only policy.

## Pull requests

Explain the user-visible outcome, security impact, tests, and platform coverage. Keep unrelated changes separate. By contributing, you agree that your contribution is licensed under the MIT License.
