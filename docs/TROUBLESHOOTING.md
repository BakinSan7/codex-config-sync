# Troubleshooting

## «Источник изменился» or «Файлы или план изменились после обзора»

The repository, a managed file, the device state or the skill selection changed after `preview`. This is the stale-plan protection. Run `preview` again and apply the new plan.

## «Нужен выбор для …»

The item differs on the device and the tool cannot tell which side is intended: a local edit without a known base, a conflict, a kept or merged local version after a profile update, or an item removed from the profile. Look at it with `detail --plan <plan> --id <item>` and put `accept`, `keep`, `skip`, `remove` or a complete `merge` text into the decisions file.

## «Дублирующий skill»

The same skill name is discoverable in `~/.codex/skills` and `~/.agents/skills`. Compare both folders, keep one canonical copy and remove the other discovery copy yourself. The tool will not pick a winner.

## «Ссылка вместо независимого пути»

A managed path contains a symlink, a Windows junction or another reparse point. On macOS, `/tmp` itself is a link; use the real `/private/tmp` path for tests. Use real directories for managed paths.

## «Local-only config key is forbidden» or «Local-only Claude setting is forbidden»

The profile lists a setting that belongs to one device: model, reasoning effort, permissions, hooks, MCP commands, plugins or credentials. Remove it from `config/*.json` or `claude_settings` and set it on each device. Do not rename or nest the value to get around the check.

## «Неверный origin»

The clone's `origin` does not match `repository` in `manifests/profile.json`. If you created your own copy from the template, set `repository` to its `owner/name`.

## A third-party skill shows «источник ещё не получен»

Its pinned source is not in the local cache yet. Choose it with `--skills <name>` (or run `prepare --skills <name>`), then run `preview` again. Downloading needs access to GitHub.

## «Есть незавершённая установка»

A previous apply was interrupted. Restore it with `rollback --id <transaction>` from `~/.codex/portable-sync/transactions`, then create a new plan.

## Python is too old

Install Python 3.11 or newer. On Windows the wrapper tries `python`, `python3` and `py -3`; on macOS set `PYTHON_BIN` if `python3` is older.

## PowerShell blocks the wrapper

Review the script and run it under an execution policy your organization permits. The Python entry point is equivalent: `python scripts/sync_profile.py preview --platform windows`.

## Codex or Claude Code does not show an installed skill

`verify` proves only the files. Start a new session, check the app's skill folders, validate the `SKILL.md` frontmatter and make sure the skill's own dependencies are installed.
