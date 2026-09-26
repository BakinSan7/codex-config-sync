---
name: obsidian-idea-capture
description: Capture and organize the user's developing ideas, questions, decisions, and next steps as linked notes in the active Obsidian vault. Use when the user asks to record thoughts in Obsidian, build a project knowledge graph, or collect open questions without answering them. Do not use for generic prose notes outside Obsidian.
---

# Obsidian Idea Capture

Turn an evolving conversation into a small, navigable Obsidian graph while preserving the user's uncertainty and stage of thinking.

## Discover before editing

- Prefer the vault shown in the actually focused Obsidian window, then corroborate it with Obsidian configuration. When several vaults remain plausible and the user did not name one, do not guess; ask only for the intended vault or use a path explicitly supplied in the request.
- Inspect the existing folder and link topology before choosing note names or locations.
- Reuse and extend relevant notes instead of creating near-duplicates.
- Treat `.obsidian` runtime state as out of scope unless the user explicitly asks to change Obsidian settings.

## Capture mode

- Preserve the user's meaning, tone, alternatives, and uncertainty. Do not silently turn possibilities into decisions.
- Classify material only when useful: idea, open question, research topic, decision, constraint, or next step.
- When the user is collecting thoughts and has not requested advice, do not propose architecture, technology, genre, scope, or solutions.
- When the user says questions are only being recorded, create linked open-question or research nodes and do not answer them.
- Prefer a few meaningful notes with mutual `[[wikilinks]]` over many tiny orphan notes. Maintain a central project note linking to major topics and open questions.
- Keep headings and filenames stable. Merge repeated concepts rather than suffixing duplicate note names.

## Boundaries

- Do not create code/project scaffolding merely because the ideas may later become software.
- Do not alter a Git repository, sync method, saved Codex project, or cross-device configuration unless explicitly requested.
- If sync changes are requested, first identify the one active sync channel and back up metadata before changing it.

## Verification

- Write Markdown as UTF-8 and reread changed files after saving.
- Check that all new wikilinks resolve or are intentionally open nodes.
- Report which notes were created, updated, or linked; distinguish captured questions from answered research.
