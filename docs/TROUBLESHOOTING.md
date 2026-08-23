# Troubleshooting

## `Plan is stale`

The repository, managed local target, platform, or selected config changed after the preview. This is expected protection.

Run `plan` again, review the new diff, then run `apply`.

## `Skill collision`

The same personal skill name is discoverable under both `$CODEX_HOME/skills` and `$AGENTS_HOME/skills`.

Compare the complete directories, merge the intended content into one canonical copy, and remove or retire the competing discovery copy manually. The tool will not pick a winner.

## `Refusing link or reparse point`

A managed path contains a symlink, macOS link, Windows junction, or other reparse point. This may be intentional in a dotfiles setup, but following it would weaken the containment guarantee.

Use real directories for managed paths or keep that component outside this tool.

## `Local-only config key is forbidden`

The selected key controls device state, permissions, runtime, authentication, or a known local-only surface. Remove it from `config/*.json` and configure it separately on each machine.

Do not bypass the validation by renaming or nesting the value elsewhere.

## `Source is missing; target preserved`

During `from-device`, an optional managed file or skill is absent locally. Nothing is deleted from the repository. Decide manually whether the repository copy should remain managed.

During `to-device`, a missing canonical repository source is an error.

## Automatic rollback occurred

At least one write or post-write check failed. The tool restored the pre-apply state and reports the backup path. Fix the first reported error, run `doctor`, then create and review a new plan.

If automatic rollback also fails, stop and preserve the backup directory. Do not run another apply until the target and backup hashes are inspected.

## Python is too old

Install Python 3.11 or newer and ensure `python` on Windows or `python3` on macOS resolves to that interpreter. You can set `PYTHON_BIN` for the Bash wrapper.

## PowerShell blocks the wrapper

Review the script, then run it under an execution policy permitted by your organization. Do not permanently weaken a managed corporate policy solely for this project.

The Python entrypoint is equivalent:

```text
python scripts/codex_config_sync.py doctor --platform windows
```

## Codex does not show the installed skill

`verify` only proves filesystem contents. Start a new Codex process, inspect the current discovery roots, validate `SKILL.md` frontmatter, and confirm that the skill's platform dependencies exist.
