# Codex Config Sync

**Безопасная синхронизация выбранных настроек Codex между Windows и macOS: `AGENTS.md`, личных skills, собственных агентов, переносимой заметки памяти и явно разрешённых значений `config.toml` — а также, по тем же правилам безопасности, `CLAUDE.md`, skills, субагентов и явно разрешённых значений `settings.json` для Claude Code.**

[English README](README.md)

> [!IMPORTANT]
> Это неофициальный community-проект, не связанный с OpenAI и не одобренный OpenAI.

## Зачем это нужно

Нельзя безопасно скопировать целиком `~/.codex`: там могут находиться авторизация, разрешения, доверенные проекты, plugin state, локальные пути, история, кэши и настройки конкретного устройства.

Codex Config Sync переносит только явную allowlist и использует безопасный процесс:

- раздельные профили `common`, `windows` и `macos`;
- обязательные два шага `plan` → `apply`;
- план привязан к хешам и устаревает после любого изменения;
- backup, атомарная запись, проверка и rollback;
- запрет path traversal, symlink, Windows junction и reparse point;
- сканирование распространённых токенов, приватных ключей и опасных файлов во время
  `plan` и повторно непосредственно перед `apply`;
- отсутствие автоматических `commit`, `push`, скачивания сторонних skills и переноса разрешений.

## Быстрый старт

На GitHub нажмите **Use this template**, создайте новый репозиторий и обязательно сделайте его **private**. Личную конфигурацию нельзя хранить в публичном fork.

На первом устройстве:

```powershell
# Windows
.\codex-sync.ps1 doctor
.\codex-sync.ps1 plan --direction from-device --show-diff
.\codex-sync.ps1 apply
.\codex-sync.ps1 scan
git diff
```

```bash
# macOS
./codex-sync.sh doctor
./codex-sync.sh plan --direction from-device --show-diff
./codex-sync.sh apply
./codex-sync.sh scan
git diff
```

После ручной проверки diff сохраните изменение в своём приватном Git-репозитории.

На втором устройстве:

```powershell
.\codex-sync.ps1 plan --direction to-device --show-diff
.\codex-sync.ps1 apply
.\codex-sync.ps1 verify
```

На Mac используются те же команды через `./codex-sync.sh`.

## Что синхронизируется

- `portable/AGENTS.md`;
- `portable/portable-memory.md`;
- только перечисленные в manifest личные skills и агенты;
- только заранее перечисленные значения `config.toml`;
- для Claude Code: `portable/CLAUDE.md`, перечисленные в manifest skills
  (`claude_skills`) и субагенты (`claude_agents`), а также явно разрешённые значения
  `settings.json` из `config/claude-*.json`;
- OS-specific компоненты только на соответствующей системе.

Цели Claude Code разрешаются относительно `$CLAUDE_HOME`: переменная окружения
`CLAUDE_CONFIG_DIR`, если задана, иначе `~/.claude`. Для синхронизации только Claude Code
установленный Codex не требуется, и наоборот.

По умолчанию списки skills, агентов и настроек пусты. Пользователь сам выбирает переносимую поверхность — см. [настройку](docs/CONFIGURATION.md).

## Что всегда остаётся локальным

- reasoning effort, шрифты, окна, hotkeys и уведомления;
- sandbox, approval policy, сеть и системные разрешения;
- project trust и абсолютные пути проектов;
- plugin/MCP IDs, команды, кэши, OAuth и авторизация;
- токены, cookies, SSH-ключи и password-manager data;
- чаты, полная память, sessions, логи, кэши, backups и вложения;
- сторонние skills и их исполняемые зависимости;
- для Claude Code: `.credentials.json`, `~/.claude.json`, `env`, `apiKeyHelper` и другие
  credential-хелперы, команды `hooks` и `statusLine`, состояние плагинов и MCP, projects,
  todos, shell snapshots и автоматически создаваемая память.

## Важные ограничения

- Автоматического смыслового merge нет: инструмент показывает diff, а решение принимает пользователь.
- Лишние файлы назначения автоматически не удаляются.
- Scanner снижает риск, но не доказывает отсутствие любых персональных данных.
- Перед добавлением новых настроек нужно сверяться с актуальной официальной документацией Codex.

Подробности: [миграция двух машин](docs/MIGRATION.md), [границы переносимости](docs/PORTABILITY.md), [модель безопасности](docs/SECURITY_MODEL.md), [устранение проблем](docs/TROUBLESHOOTING.md).

Лицензия: [MIT](LICENSE).
