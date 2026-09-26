# Security model

## What the tool protects against

| Risk | Control |
| --- | --- |
| Copying account or device state between machines | Explicit manifests, an allowlist of settings, and refused local-only keys |
| Overwriting a file you changed on purpose | Per-item decisions; `keep` and `merge` are remembered and re-offered, never replaced silently |
| Applying a review that no longer matches reality | The plan records hashes of the repository, the managed files and the device state; any change makes it stale |
| Partial writes | Every result is validated before the first write; files are written atomically; a failure restores what was written |
| Undoing an installation later | A journal per apply and `rollback`, which refuses files changed after the installation |
| Escaping managed folders | Relative paths only; `..`, drive letters and backslashes are rejected; links, junctions and reparse points are refused on every path component |
| Running code from a downloaded skill | Third-party skills are fetched as data from an exact commit; nothing is executed during preparation |
| A tampered or changed third-party source | Only full commit SHAs are accepted; the prepared copy carries a content hash that is checked on every review |
| Publishing unrelated work | `publish` stages only the listed paths, refuses pre-staged changes and incoming commits, and never force-pushes |
| Secrets in the repository | The scanner rejects private-key material, known token formats, secret-like assignments, sensitive file names and folders; `--public-audit` also rejects user-specific absolute paths |

## Trust boundaries

- The repository you install from is trusted to the extent you reviewed it. The installer checks that the clone's `origin` matches `repository` in `manifests/profile.json`; an empty value disables that check and should be used only for local experiments.
- Third-party skills are trusted to the extent you trust their authors. The catalog shows the author and license; the pinned commit guarantees you get what was reviewed, not that it is harmless when an agent later uses it.
- Local plans and journals under `~/.codex/portable-sync` can contain your previous local files. They are created with restrictive permissions where the OS supports them and must never be published.

## What it does not protect against

- A malicious local administrator or a process racing filesystem operations during `apply`.
- Private information written in natural language that no pattern can recognize. The scanner is defense in depth, not proof.
- A compromised GitHub account or a malicious commit that you reviewed and accepted yourself.

## Reporting

See [SECURITY.md](../SECURITY.md).
