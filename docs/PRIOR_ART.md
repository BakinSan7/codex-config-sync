# Prior art and licensing

This project was designed after reviewing public Codex and dotfiles approaches. Architecture ideas were compared; code and documentation without compatible licensing were not copied.

## Official documentation

- OpenAI [`config.toml` reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- OpenAI [`AGENTS.md` guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- OpenAI [skills documentation](https://learn.chatgpt.com/docs/skills-and-plugins)

These establish the supported configuration surfaces. They do not prescribe this repository's cross-device synchronization workflow.

## Reviewed repositories

### `SunS1eep1ng/codex-dotfiles`

Reviewed for Windows/macOS scripts, backup behavior, portable/local separation, and safety scanning. No license was present at review time, so no code or text was copied.

Source: <https://github.com/SunS1eep1ng/codex-dotfiles>

### `Ithildur/codex-dotfiles`

Reviewed for shared/local/runtime layers, allowlisted Git surfaces, and primary/secondary roles. It is licensed AGPL-3.0-only; this MIT project uses an independent implementation.

Source: <https://github.com/Ithildur/codex-dotfiles>

### `dinoallo/.codex`

Reviewed for exact-revision skill provenance and refusal to overwrite unsafe destinations. No license was present at review time, so no code or text was copied.

Source: <https://github.com/dinoallo/.codex>

### General MIT dotfiles projects

`thuringia/dotfiles`, `jkomyno/.dotfiles`, and `lcatlett/mydots` were reviewed for shared/local configuration boundaries and explicit dry-run or promote workflows. No source code from those repositories is included.

- <https://github.com/thuringia/dotfiles>
- <https://github.com/jkomyno/.dotfiles>
- <https://github.com/lcatlett/mydots>

## Independent design choices

The hash-bound local plan, stale-plan rejection, automatic transactional rollback, link/reparse refusal, public-path audit, enforced local-only Codex sections, and non-downloading skill policy are original implementation choices in this repository.
