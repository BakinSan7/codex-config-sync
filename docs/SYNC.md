# Sync workflow

The profile repository is the single source. `scripts/sync_profile.py` (or the `codex-sync.sh` / `codex-sync.ps1` wrappers) compares it with each device and installs independent copies. Nothing is linked back to the repository, and nothing on a device is published unless you run `publish` with explicit files.

## What a profile contains

| Source in the repository | Installed as |
| --- | --- |
| `portable/AGENTS.md` + optional `portable/git-commit.md`, `portable/git-pr.md` | `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` (one composed document) |
| `portable/portable-memory.md` | `portable-memory.md` next to the instructions of each app |
| `personal-skills/<name>/` listed in `manifests/portable-files.json` | `skills/<name>/` of each app (Codex-only skills skip Claude Code) |
| pinned entries in `manifests/external-skills.json` | `skills/<name>/` of each app, downloaded from the author's commit |
| `config/common.json`, `config/<os>.json` | selected keys of `~/.codex/config.toml` |
| `claude_settings` in `manifests/profile.json` | selected keys of `~/.claude/settings.json` |
| `agents/*.toml`, `claude-agents/*.md` listed in the manifest | Codex custom agents and Claude Code subagents |

Paths of the shared sources are set in `manifests/portable-files.json` (`instructions_source`, `commit_rules_source`, `pr_rules_source`, `portable_memory_source`). `manifests/profile.json` sets the repository identity (`repository`), Codex-only skills and Claude Code settings.

## First installation

```bash
./codex-sync.sh bootstrap                 # macOS; asks which skills to install
.\codex-sync.ps1 bootstrap                # Windows
./codex-sync.sh bootstrap --skills recommended
```

`bootstrap` fetches the repository, shows the skill catalog, downloads only the chosen third-party skills, shows the review tree, installs new and incoming items, and verifies the result. If a file already exists on the device and differs, it is left untouched and needs your decision. A second clone is never created, and an existing directory with a different `origin` is refused.

The helper `scripts/setup.py --repository owner/name` clones your repository into `~/codex-config-sync` (or `--destination`) and runs `bootstrap`.

## Choosing skills

`catalog` lists every offered skill with a short explanation, the apps it supports, and for third-party skills the author and license. `--skills` accepts:

| Value | Meaning |
| --- | --- |
| `recommended` or an empty answer | skills marked ★ |
| `all` / `none` | everything / nothing from the catalog |
| `1,5,fact-check-post` | catalog numbers and names, separated by commas |

The choice is stored on the device. A skill you did not choose stays "not chosen" and is not recorded as a refusal. Removing or skipping a chosen skill takes it out of the device selection; asking for it again with `--skills` installs it again. Without `manifests/skill-catalog.json`, every listed skill is installed, which suits a private profile.

## Reviewing changes

```bash
./codex-sync.sh preview
./codex-sync.sh detail --plan <plan.json> --id codex:instructions
./codex-sync.sh apply --plan <plan.json> --decisions <decisions.json> --accept-safe
./codex-sync.sh verify
```

`preview` fast-forwards a clean clone, compares the repository, the last accepted state and the current files, and writes a plan into `~/.codex/portable-sync/plans`. The plan contains only managed values, never whole configuration files. Every item has a stable ID such as `codex:instructions`, `claude:memory`, `codex:skill:fact-check-post` or `claude:config:autoMemoryEnabled`.

Decisions go into a separate JSON file:

```json
{
  "codex:instructions": "accept",
  "claude:skill:haiku-writer": "skip",
  "claude:instructions": {"action": "merge", "text": "the complete approved document"}
}
```

| Action | Meaning |
| --- | --- |
| `accept` | add or replace the item with the repository version |
| `keep` | keep the local version and remember that choice |
| `skip` | do not install; an existing local copy stays |
| `remove` | remove the item on this device, recoverable through the journal |
| `merge` | write the complete document you approved (files only) |

Matching items are confirmed automatically. `--accept-safe` also accepts new items and updates where the local file did not change since the last sync. A conflict or an unknown base always needs a decision. A kept or merged local version comes back as a decision after the next profile change and is never replaced silently. A skipped or removed item is not reinstalled unless you choose it again. When the profile drops an item, the device is asked once; after the answer the item is no longer tracked.

A plan becomes stale when the repository, a managed file or the state changes after the review; create a new one. All results are validated before the first write, and a failure restores the files already written.

## Recovery

Every apply writes a journal under `~/.codex/portable-sync/transactions/<id>`:

```bash
./codex-sync.sh rollback --id <transaction id>
```

Rollback refuses files that changed after the installation and state that another sync already replaced. The journal can contain your previous local files; never publish it.

## Publishing your own changes

Edit the canonical files in your repository, then publish only the files you mean:

```bash
./codex-sync.sh publish "feat(profile): add a rule" portable/AGENTS.md
.\codex-sync.ps1 publish -Message "feat(profile): add a rule" -Paths portable/AGENTS.md
```

`publish` refuses pre-staged changes and incoming commits, runs the unit tests, the scanner and `git diff --check`, stages only the listed paths, commits, pushes and confirms the remote head. It never collects files from a device and never force-pushes; if the push fails, the local commit is kept and named.

## Claude Code notes

Claude Code reads user instructions from `~/.claude/CLAUDE.md`. Rules that belong to one device (for example, instructions added by a locally installed tool) go to `~/.claude/rules/*.md`; Claude Code loads them next to `CLAUDE.md`, so the shared file stays identical to the profile. Codex has no such folder, so a device-specific difference in `AGENTS.md` remains a `keep` or `merge` decision. Source: [Claude Code memory](https://code.claude.com/docs/en/memory).

## Readiness

The report separates: repository fetched, files installed, settings accepted by the review, client versions found, and what still needs a new session. `verify` checks files and remembered exceptions; it does not sign in to an app or run every tool of every skill. Installing on one device proves nothing about another.
