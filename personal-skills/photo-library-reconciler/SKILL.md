---
name: photo-library-reconciler
description: Reconcile the user's photo and video libraries using embedded metadata, Mac/iPhoto evidence, hashes, and journals. Use for sorting media by capture date, comparing backups, recovering originals, resolving iPhoto libraries, or deleting proven external duplicates. Do not use for image editing or aesthetic curation.
---

# Photo Library Reconciler

Build one trustworthy media library without turning transfer timestamps, weak metadata, or similar filenames into false certainty.

Before moving or deleting media, read [references/evidence-policy.md](references/evidence-policy.md).

If the user asks only for an audit, comparison, or diagnosis, remain read-only and produce a proposed action journal. Apply dates, copy, move, restore, or delete files only when the request authorizes those changes.

## Workflow

1. Discover the live library, sorting area, backup sources, iPhoto/Photos metadata, and available free space. Do not reuse old paths without checking them.
2. Inventory files read-only. Separate normal media, zero-byte files, sidecars, database material, thumbnails/derivatives, and unreadable sources.
3. Extract metadata with ExifTool or an equivalent format-aware parser. Avoid Windows Shell metadata for large audits when ExifTool is available.
4. Assign dates only when the evidence reaches the action threshold in the reference and mutation is authorized. Retain uncertain or conflicting files in sorting with the evidence recorded.
5. Prefilter duplicate candidates by size and prove identity with SHA-256. Treat edited, truncated, recompressed, or same-name media as different unless hashes match.
6. Preflight moves and copies for missing sources, conflicts, free space, and destination containment. Journal every applied action.
7. For copies, moves, and recovery, verify SHA-256 or another byte-for-byte content check before treating the destination as preserved or removing the source. File size is only a prefilter and never sufficient proof.

## Destructive boundaries

- Deletion requires direct authorization and byte-for-byte duplicate proof.
- Preserve originals inside managed iPhoto/Photos library structures unless the user explicitly authorizes an application-aware cleanup.
- Do not delete zero-byte placeholders merely because a recovered copy exists; retain or quarantine them when the database may reference them.
- Keep uncertain files, conflicts, and source-disk read failures visible as unresolved rather than forcing a year.

## Completion

- Recount sources, destinations, unresolved files, zero-byte files, and exact duplicates.
- Confirm that every planned destination exists and that verified copies/moves have no hash mismatch.
- Save a CSV or JSON action journal in a dedicated service folder outside managed iPhoto/Photos library packages, including evidence, source, destination, action, and result.
- Report confident changes, retained uncertainty, deletions, and unreadable originals separately. Do not call the library complete while unresolved source read failures remain.
