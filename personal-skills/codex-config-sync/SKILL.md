---
name: codex-config-sync
description: Install or selectively synchronize a shared Codex and Claude Code profile from a Codex Config Sync repository; offer the skill catalog with short explanations, preview instructions, skills, memory and settings as a short text tree, apply the user's choices, and publish explicitly selected profile changes.
---

# Shared Profile Sync

Use `scripts/sync_profile.py` in the profile repository (or the `codex-sync.sh` / `codex-sync.ps1` wrappers). Commands, the decision schema and recovery are described in the repository's `docs/SYNC.md`; read it before installation, selection, recovery or publication.

## Locate or install

Read the current app's `portable-repo-path` (Codex: `~/.codex`, Claude Code: `~/.claude`). Check that the clone's `origin` matches `repository` in `manifests/profile.json`. If no clone is recorded, ask where to clone the user's repository instead of guessing.

When the user asks to install the profile, complete first-run setup: reuse the verified clone or clone the exact repository, check Python 3.11+ and Git, then run `bootstrap`. Do not create a second clone, overwrite a non-repository directory, install unrelated software, or claim private GitHub access without testing it. Missing authentication is a real blocker.

## Offer the skill catalog

When the repository has `manifests/skill-catalog.json`, skills are installed only when chosen. Before `bootstrap`, run `catalog` and show the user the numbered list with its short explanations, marks for recommended and already installed skills, the supported apps, and the author and licence of third-party skills. Ask which ones to install, then pass the answer as `--skills` (`recommended`, `all`, `none`, or numbers/names separated by commas). Third-party skills are downloaded only when chosen, from the exact pinned commit, and are never executed while being prepared.

A later request such as "add fact-check-post" is `preview --skills fact-check-post` followed by `apply --accept-safe` with the new plan. Skipping or removing a skill on this device takes it out of the device selection.

If the scripts report that this device's profile was installed from another repository or clone, stop and tell the user: continuing would replace their instructions, memory and skills. Add `--switch-repository` only after the user explicitly chooses to switch sources.

## Receive from GitHub

Run `preview` (fetch + fast-forward + local comparison). Use `--working-tree` only for a reviewed change being developed locally. Show a short indented tree using ├── and └──, not Mermaid. Group shared items once with app labels. Include personalization, every skill name, memory record count and additions, settings, and local-only integrations. Avoid raw paths, hashes, technical keys and line diffs unless requested.

Explain changed behavior in everyday language using the actual old and new content. Translate the user's choices into a decisions JSON file keyed by stable item ID: accept (add/replace), keep, skip, remove, or merge with the complete reviewed document. A kept or merged local version is offered again after the profile changes and is never replaced silently. Do not edit the plan JSON. Apply the plan, then verify. Remembered exceptions are intentional differences, not failures.

## Publish

Publish only completed, authorized changes to the user's own repository. Read the selected diff and run the checks. Use `codex-sync.sh publish "message" file1 file2` or `codex-sync.ps1 publish -Message "message" -Paths file1,file2`. No automatic device collection occurs. Never publish a receive-only operation, sweep unrelated files, or force-push over new incoming commits.

After publication verify the pushed commit, the remote head and the working tree. If a push fails, keep and name the local commit. Report separately what was installed, what the apps accepted, and what still needs a new session or a check on another device.

## Boundaries

Keep credentials, full auto-memory, chats, histories, logs, caches, runtime hooks, permissions, the default model and reasoning effort, and other device-specific configuration local; the scripts refuse known local-only keys. Plugins and connections are inventory unless the user authorizes their installation; account sign-in stays local.

Shared instructions have one source; Codex and Claude Code get independent copies. Do not install Codex-only skills into Claude Code. Put Claude Code rules that belong to one device in `~/.claude/rules/*.md` instead of editing `~/.claude/CLAUDE.md`. Back up replacements and use the journaled `rollback` command for recovery. Never bypass a review by copying installed files into the repository or back.
