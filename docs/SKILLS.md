# Skills

The installer offers these skills as a numbered catalog (`catalog`, `bootstrap`). Only the skills you choose are installed; ★ marks the recommended set. The `codex-config-sync` skill is always installed because it runs the sync commands for Codex and Claude Code.

## Tasks and projects

| # | Skill | Apps | What it does | По-русски | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | navigate-project ★ | Codex, Claude | Restores orientation in a big project and picks one next verifiable step. | Когда проект разросся: восстанавливает картину и предлагает один следующий проверяемый шаг. | [bundled](../personal-skills/navigate-project/SKILL.md) |
| 2 | velosiped ★ | Codex, Claude | Looks for mature existing solutions and agrees on an approach before non-trivial coding. | Перед заметной разработкой ищет готовые зрелые решения и согласует подход до правки кода. | [bundled](../personal-skills/velosiped/SKILL.md) |
| 3 | cb-job-fit | Codex, Claude | Checks fit between a C&B, HR analytics or payroll vacancy and your CV; drafts a cover letter. | Сравнивает вакансию в C&B, HR-аналитике или payroll с вашим резюме и пишет сопроводительное письмо. | [bundled](../personal-skills/cb-job-fit/SKILL.md) |
| 4 | obsidian-idea-capture | Codex, Claude | Captures ideas, questions and decisions as linked notes in the open Obsidian vault. | Записывает мысли, вопросы и решения связанными заметками в открытое хранилище Obsidian. | [bundled](../personal-skills/obsidian-idea-capture/SKILL.md) |

## Research and fact-checking

| # | Skill | Apps | What it does | По-русски | Source |
| --- | --- | --- | --- | --- | --- |
| 5 | fact-check-post ★ | Codex, Claude | Fact-checks posts, news and screenshots against primary sources, claim by claim. | Проверяет факты в постах, новостях и скриншотах по первоисточникам, с вердиктом по каждому утверждению. | [bundled](../personal-skills/fact-check-post/SKILL.md) |
| 6 | deep-research | Codex, Claude | Deep multi-source research with cross-checked claims and an adversarial review pass. | Глубокое исследование важного вопроса: много источников, перекрёстная проверка, разбор возражений. | [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills/tree/aa8d778811a557a2c28ccadda4cf3d0bd028a4cc/research/deep-research/skills/deep-research) @ `aa8d778` · MIT |
| 7 | youtube-research | Codex, Claude | Researches YouTube channels and videos from subtitles or transcripts, with timestamps. | Исследует YouTube-каналы и видео по субтитрам и расшифровкам, с таймкодами в выводах. | [timbroddin/skills](https://github.com/timbroddin/skills/tree/2549b676c30e4ded58fc9ab050b5bcd8d98b15a2/skills/youtube-research) @ `2549b67` · no license stated |

## Agents and context

| # | Skill | Apps | What it does | По-русски | Source |
| --- | --- | --- | --- | --- | --- |
| 8 | orchestrate-subagents ★ | Codex, Claude | Runs a complex task purely through subagents: split, delegate, reconcile and verify. | Ведёт сложную задачу только через субагентов: делит работу, собирает результаты и проверяет их. | [bundled](../personal-skills/orchestrate-subagents/SKILL.md) |
| 9 | context-watchdog | Codex | Codex only: watches context cost in long work and prepares a fresh-chat handoff. | Только Codex: следит за расходом контекста в длинной работе и готовит перенос в новый чат. | [bundled](../personal-skills/context-watchdog/SKILL.md) |
| 10 | codex-weekly-mentor | Codex | Codex only: weekly retrospective of your chats with recurring agent problems and fixes. | Только Codex: недельный разбор ваших чатов — повторяющиеся ошибки агента и что поправить. | [bundled](../personal-skills/codex-weekly-mentor/SKILL.md) |

## Browser and visual proof

| # | Skill | Apps | What it does | По-русски | Source |
| --- | --- | --- | --- | --- | --- |
| 11 | acceptance-frames ★ | Codex, Claude | Proves a visible change with before/after frames a reviewer can accept at a glance. | Доказывает видимое изменение кадрами «до и после», которые можно принять с одного взгляда. | [BakinSan7/acceptance-frames](https://github.com/BakinSan7/acceptance-frames/tree/4715a133909c79e296445591967389e86ce68179) @ `4715a13` · MIT |
| 12 | playwright | Codex, Claude | Drives a real browser from the terminal: navigation, forms, screenshots, UI debugging. | Управляет настоящим браузером из терминала: переходы, формы, скриншоты, отладка интерфейса. | [openai/skills](https://github.com/openai/skills/tree/a5119697b819090e00e5d11ee1d86834d7c1043a/skills/.curated/playwright) @ `a511969` · Apache-2.0 |
| 13 | playwright-interactive | Codex | Codex only: a persistent browser session for iterative UI debugging. | Только Codex: постоянная сессия браузера для пошаговой отладки интерфейса. | [openai/skills](https://github.com/openai/skills/tree/ecc1fb8bc0b82f1d3c7a92a82167ae8e8e613a67/skills/.curated/playwright-interactive) @ `ecc1fb8` · Apache-2.0 |

## Media and writing

| # | Skill | Apps | What it does | По-русски | Source |
| --- | --- | --- | --- | --- | --- |
| 14 | photo-library-reconciler | Codex, Claude | Reconciles photo and video libraries by metadata and hashes; proves duplicates before deletion. | Наводит порядок в фото и видео по метаданным и хешам, находит дубли, ничего не теряя. | [bundled](../personal-skills/photo-library-reconciler/SKILL.md) |
| 15 | gpt-image-2-style-library | Codex, Claude | Style library and prompt templates for GPT Image 2 image generation. | Библиотека стилей и шаблонов запросов для генерации изображений GPT Image 2. | [freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2/tree/b477278bb2a36d4c59655eb0daa4ce48e8dbc4c4/agents/skills/gpt-image-2-style-library) @ `b477278` · MIT |
| 16 | haiku-writer | Codex, Claude | Writes a haiku about any topic, thought or event (in Russian). | Пишет хокку на любую тему, мысль или событие (по-русски). | [bundled](../personal-skills/haiku-writer/SKILL.md) |

## How third-party skills are installed

Third-party skills are not copied into this repository. Each one is pinned in `manifests/external-skills.json` to a GitHub repository, a folder and a full commit SHA. When you choose it, `prepare` fetches exactly that commit into `~/.codex/portable-sync/sources`, keeps only the listed files, records a content hash, and never executes anything. The installed copy is compared with that hash on every review. The license shown is the one published by the author; `youtube-research` has none stated, so check its terms before using it beyond personal use.

## Adding your own skills

1. Put the skill folder with its `SKILL.md` into `personal-skills/<name>/`.
2. List the name in `manifests/portable-files.json` under `common`, `windows` or `macos`.
3. To offer it as an optional catalog item, add an entry to `manifests/skill-catalog.json` with `group`, `recommended`, and short `ru` and `en` explanations. Skills that are not in the catalog are installed on every device.
4. List Codex-only skills in `codex_only_skills` of `manifests/profile.json`.
5. Run the tests and `./codex-sync.sh scan --public-audit` before publishing.

To add a third-party skill, add a pinned entry (`name`, `repo`, `path`, full `ref`, optional `include` and `license`) to `manifests/external-skills.json` and a catalog entry. Use `"path": "."` with `include` when the skill is the root of its repository.
