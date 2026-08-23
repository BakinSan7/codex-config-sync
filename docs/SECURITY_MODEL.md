# Security model

## Security goals

Codex Config Sync is designed to prevent common accidental failures:

1. copying an entire Codex home and exposing local state;
2. applying changes that differ from the reviewed preview;
3. writing outside the repository, `$CODEX_HOME`, or `$AGENTS_HOME` through manifest paths;
4. following symlinks, Windows junctions, or reparse points;
5. leaving a partially applied configuration after a write or verification failure;
6. committing recognizable credentials or private-key material;
7. deleting unrelated destination files;
8. silently choosing between duplicate skill discovery roots.

## Trust boundaries

```text
Public template
    |
    v
User-owned private Git repository ---- reviewed source
    |                                     |
    | plan (read-only)                    |
    v                                     v
Local hash-bound plan ---------------> apply process
                                          |
                              backup -> atomic writes -> verify
                                          |
                                          v
                              $CODEX_HOME / $AGENTS_HOME
```

The user trusts their private repository, local Python interpreter, operating system, and current account. Repository content remains untrusted until reviewed because an upstream or collaborator could modify it.

## Controls

### Hash-bound plans

`plan` records before and after SHA-256 values but not file content. `apply` regenerates the complete plan and refuses to continue if its ID changed. A source edit, target edit, path change, platform change, or config-profile change makes the plan stale.

### Path containment

Manifest paths must be relative forward-slash paths. Absolute paths, drive prefixes, `..`, backslashes, duplicate targets, sensitive filenames, reserved managed areas, symlinks, junctions, reparse points, and special files are rejected. Repository, Codex, and agents roots must also be real directories rather than links. The same containment check runs immediately before a managed write.

### Transactional behavior

Before applying, the tool copies every existing target into a timestamped backup and records before/after hashes. Writes use a temporary file in the destination directory followed by `os.replace`. A failed post-write hash, verification, or repository scan triggers automatic rollback.

### Non-deleting trees

Managed skills are additive. Files that exist only at the destination are preserved. Manual deletion is less convenient but avoids broad destructive behavior from a bad manifest.

### Secret scanning

The scanner checks common provider token formats, secret-like assignments, private-key markers, sensitive filenames, SQLite stores, `.env` files, and linked filesystem entries. It runs while creating a plan and again immediately before applying it, which closes the review-to-apply gap. A local-to-repository apply also scans the resulting repository and rolls back on failure. Public audit additionally detects common user-home paths.

The scanner cannot identify every credential or determine whether prose is personally sensitive. Always inspect `git diff` and the staged commit.

## Explicit non-goals

- defending against a malicious local administrator;
- defending against an attacker who can replace the Python interpreter or race filesystem operations during execution;
- encrypting repository content or backups;
- managing GitHub credentials or Git publication;
- installing or executing third-party skills;
- synchronizing OS permissions, plugin/MCP authorization, or browser state;
- resolving semantic conflicts automatically;
- proving that Codex has loaded a file in a new process.

## Backup handling

Device backups live under `$CODEX_HOME/backups/`. Repository-direction backups live under `.codex-sync/backups/`. The latter directory is ignored by Git. Backups can still contain personal configuration, so do not upload them and remove them manually after successful product-level verification.

Manual rollback refuses to overwrite a target that changed after `apply`. This protects later user edits. Automatic rollback is limited to the transaction that just wrote the target.

## Supply chain

The core has no third-party Python dependencies. CI actions are pinned to full commit SHAs. The repository does not download skills, run package managers, or execute config content.

Review updates to this tool before applying them to a private configuration repository.
