# Media evidence and action policy

Use multiple independent signals when a date is suspicious or conflicts with the expected chronology.

## Strong primary evidence

- JPEG and ordinary photos: embedded `DateTimeOriginal`, with timezone information when available.
- MOV/MP4: QuickTime creation metadata such as `MediaCreateDate`, interpreted with the format's timezone behavior.
- PNG: use `DateTimeOriginal` only when it is genuinely present and plausible.
- A byte-identical original linked to a trustworthy iPhoto/Photos database record.

## Supporting evidence

- iPhoto `AlbumData.xml`, event membership, original path, adjacent sequence, filename series, and surrounding captures.
- Consistent camera model, dimensions, timezone offset, GPS, folder/event context, and neighboring file chronology.
- A known export or backup provenance.

Supporting evidence may confirm a strong signal. It should not automatically override conflicting embedded capture metadata.

## Rejected as capture-date proof

- Windows creation/access time after copying or extraction.
- ICC profile dates.
- Folder year or filename alone.
- Database import/modification time without corroboration.

## Action thresholds

- **Confident:** one strong primary signal with no material conflict, or several independent supporting signals that converge. Move or copy and journal the evidence.
- **Probable:** useful evidence exists but a material ambiguity remains. Keep in sorting and record the likely date without applying it as fact.
- **Conflicting:** credible signals disagree. Do not move by year until resolved.
- **No evidence:** retain in sorting.

For deletion, date confidence is irrelevant: require a full SHA-256 match to a preserved nonzero destination and explicit authorization.

## Managed-library cautions

- Distinguish originals from previews, thumbnails, edited derivatives, and database placeholders.
- Preserve internal duplicates and zero-byte originals inside iPhoto/Photos structures unless an application-aware plan proves they are safe to remove.
- When reconciling against `AlbumData.xml`, count nonempty, missing, and zero-byte originals separately.
