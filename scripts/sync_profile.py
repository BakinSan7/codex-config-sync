#!/usr/bin/env python3
"""Reviewable Codex + Claude profile sync. Standard library + Git, Python 3.11+."""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid

import portable_config as legacy

SCHEMA = 1
ORIGIN = "BakinSan7/codex-config-sync"  # fallback when manifests/profile.json has no "repository"
ABSENT = {"missing": True}
SKIP = {".git", "__pycache__", ".DS_Store", ".pytest_cache"}
SOURCE_DIRS = ("codex", "portable", "memory", "personalization", "personal-skills", "claude-agents", "config",
               "manifests", "agents", "rules", "scripts")
LABELS = {"same": "совпадает", "new": "добавить", "incoming": "обновление",
          "local": "изменено здесь", "conflict": "выбор", "unbased": "разные версии",
          "removed": "убрано из профиля", "kept": "оставлено локально",
          "skipped": "пропущено", "optional": "необязательный, пропущен",
          "unprepared": "источник ещё не получен"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def packed(data: bytes, mode=0o600):
    return {"data": base64.b64encode(data).decode(), "mode": mode & 0o777}


def encoded(text):
    return packed(text.encode())


def unpack(value):
    return base64.b64decode(value["data"], validate=True)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else default


def checked(path: Path):
    """Reject symlinks/junctions in every component, including managed roots."""
    path = path.absolute()
    for p in (path, *path.parents):
        if legacy.is_redirected_directory(p):
            raise ValueError(f"Ссылка вместо независимого пути: {p}")
    return path


def atomic(path, data, mode=0o600):
    checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".portable-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_json(path, value):
    atomic(path, json_bytes(value))


@contextlib.contextmanager
def locked(root):
    checked(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE).decode().strip()


def repository_slug(repo):
    """The GitHub owner/name this clone must come from; an empty value disables the check."""
    profile = read_json(repo / "manifests/profile.json", {}) or {}
    slug = profile.get("repository", ORIGIN)
    if slug and not re.fullmatch(r"[\w.-]+/[\w.-]+", slug):
        raise ValueError("Неверное значение repository в manifests/profile.json: " + str(slug))
    return slug


def repository_identity(repo):
    """owner/name of the GitHub origin; a clone without origin is identified by its folder."""
    try:
        url = git(repo, "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        return "local:" + str(repo)
    match = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$", url)
    return (match.group(1) if match else url).lower()


def guard_repository(args, state):
    """Stop when this device's profile was installed from another repository."""
    if not state["items"] or getattr(args, "switch_repository", False):
        return
    hint = (" Смена источника заменит установленные инструкции, память и skills версиями из нового "
            "репозитория. Делайте её только по явному решению пользователя: повторите с --switch-repository.")
    known = state.get("repository")
    if known:
        current = repository_identity(args.repo_root)
        if known != current:
            raise ValueError(f"Профиль на этом устройстве установлен из {known}, а запуск идёт из {current}." + hint)
        return
    # Profiles installed before this check recorded only the clone path.
    for root in roots_for(args).values():
        pointer = root / "portable-repo-path"
        if pointer.is_file():
            clone = Path(pointer.read_text(encoding="utf-8").strip()).expanduser()
            if clone.resolve() != args.repo_root.resolve():
                raise ValueError(f"Профиль на этом устройстве установлен из клона {clone}, а запуск идёт из {args.repo_root}." + hint)
            return


def validate_origin(repo):
    slug = repository_slug(repo)
    if not slug:
        return
    origin = git(repo, "remote", "get-url", "origin")
    if origin.rstrip("/").removesuffix(".git") not in (
        "https://github.com/" + slug, "git@github.com:" + slug
    ):
        raise ValueError("Неверный origin: ожидается репозиторий " + slug)


def refresh(repo):
    validate_origin(repo)
    if git(repo, "status", "--porcelain"):
        raise ValueError("В репозитории есть изменения. Сначала завершите их; --working-tree — только для разработки.")
    git(repo, "fetch", "origin", "main", "--quiet")
    before = git(repo, "rev-parse", "HEAD")
    git(repo, "merge", "--ff-only", "origin/main")
    return before != git(repo, "rev-parse", "HEAD")


def tree(root):
    checked(root)
    if not root.exists():
        return {}
    if not root.is_dir():
        raise ValueError(f"Ожидалась папка: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        checked(path)
        if path.is_file():
            result[path.relative_to(root).as_posix()] = packed(path.read_bytes(), path.stat().st_mode)
    return result


def fingerprint(repo):
    # Contents (including uncommitted implementation work), not just HEAD.
    return digest({name: tree(repo / name) for name in SOURCE_DIRS})


def content_hash(value):
    """Ignore OS-specific permission bits when deciding content equivalence."""
    if isinstance(value, dict):
        return digest({k: (v["data"] if isinstance(v, dict) and "data" in v else v)
                       for k, v in value.items() if k != "mode"})
    return digest(value)


def source_hash(item):
    if item.get("external"):
        return digest({"spec": item["external"], "content": content_hash(item["desired"])})
    return content_hash(item["desired"])


def roots_for(args):
    return {"codex": checked(args.codex_home), "claude": checked(args.claude_home)}


def state_path(args):
    return args.state_dir / "state.json"


def state_for(args):
    state = read_json(state_path(args), {"schema": SCHEMA, "items": {}})
    if state.get("schema") != SCHEMA:
        raise ValueError("Неизвестная версия состояния синхронизации")
    return state


def file_value(path):
    checked(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Ожидался файл: {path}")
    return packed(path.read_bytes(), path.stat().st_mode)


SOURCE_DEFAULTS = {"instructions_source": "codex/AGENTS.md",
                   "commit_rules_source": "personalization/git-commit.md",
                   "pr_rules_source": "personalization/git-pr.md"}


def source_file(repo, key):
    manifest = read_json(repo / "manifests/portable-files.json")
    return repo / safe_relative(manifest.get(key, SOURCE_DEFAULTS[key]))


def instructions(repo):
    result = source_file(repo, "instructions_source").read_text(encoding="utf-8")
    for key, title in (("commit_rules_source", "Коммиты"), ("pr_rules_source", "Pull requests")):
        path = source_file(repo, key)
        if path.is_file():
            result += "\n# " + title + "\n\n" + path.read_text(encoding="utf-8")
    return result


def safe_relative(name):
    path = PurePosixPath(name)
    if not name or not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"Недопустимый относительный путь: {name!r}")
    return path


def unit(uid, label, app, kind, path, desired, **extra):
    safe_relative(path)
    return dict(id=uid, label=label, app=app, kind=kind, path=path, desired=desired, **extra)


def source_path(spec):
    """Validated folder inside the pinned repository; "." means its root."""
    return "." if spec["path"] == "." else safe_relative(spec["path"]).as_posix()


def selected(files, spec):
    """Keep only the listed files or folders when the repository holds more than the skill."""
    if "include" not in spec:
        return files
    prefixes = [safe_relative(name).as_posix() for name in spec["include"]]
    return {name: value for name, value in files.items()
            if any(name == prefix or name.startswith(prefix + "/") for prefix in prefixes)}


def source_identity(spec):
    identity = {"repo": spec["repo"], "ref": spec["ref"], "path": spec["path"]}
    if "include" in spec:
        identity["include"] = spec["include"]
    return identity


def external_tree(args, spec):
    ref = spec["ref"]
    if not re.fullmatch(r"[0-9a-fA-F]{40}", ref) or not re.fullmatch(r"[\w.-]+/[\w.-]+", spec["repo"]):
        raise ValueError("Сторонний источник должен быть GitHub repo и полным SHA")
    source_path(spec)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", spec["name"]):
        raise ValueError("Недопустимое имя внешнего skill")
    folder = args.state_dir / "sources" / ref / spec["name"]
    proof = folder / ".portable-source.json"
    if not proof.is_file():
        return None
    files = tree(folder)
    metadata = json.loads(unpack(files.pop(".portable-source.json")))
    expected = source_identity(spec)
    if any(metadata.get(k) != v for k, v in expected.items()) or metadata.get("content") != content_hash(files):
        raise ValueError("Повреждён подготовленный источник: " + spec["name"])
    files[".portable-source.json"] = packed(json_bytes(metadata))
    return files


def prepare_external(args, include_optional=False):
    profile = read_json(args.repo_root / "manifests/profile.json")
    catalog = load_catalog(args.repo_root)
    chosen = set(getattr(args, "selected", ()) or ())
    specs = read_json(args.repo_root / "manifests/external-skills.json")["codex_skill_installer"]
    for spec in specs:
        name = spec["name"]
        optional = name in catalog or name in profile.get("optional_skills", [])
        if optional and not (include_optional or name in chosen or installed_skill(args, name)):
            continue
        if external_tree(args, spec) is not None:
            continue
        print("Получаю закреплённый источник: " + spec["name"], flush=True)
        with tempfile.TemporaryDirectory(prefix="portable-source-") as temp:
            checkout = Path(temp).resolve() / "repo"
            subprocess.run(["git", "init", "-q", str(checkout)], check=True)
            git(checkout, "remote", "add", "origin", "https://github.com/" + spec["repo"] + ".git")
            git(checkout, "fetch", "--depth=1", "origin", spec["ref"])
            git(checkout, "checkout", "--detach", "FETCH_HEAD", "--quiet")
            source = checkout / source_path(spec)
            files = selected(tree(source), spec)
            if "SKILL.md" not in files:
                raise ValueError("В источнике нет SKILL.md: " + spec["name"])
            # Data is copied, never executed during preparation.
            folder = args.state_dir / "sources" / spec["ref"] / spec["name"]
            for name, value in files.items():
                atomic(folder / name, unpack(value), value["mode"])
            save_json(folder / ".portable-source.json", {**source_identity(spec), "content": content_hash(files)})


CATALOG_GROUPS = {
    "work": ("Работа с задачами и проектами", "Tasks and projects"),
    "research": ("Исследования и проверка фактов", "Research and fact-checking"),
    "agents": ("Агенты и контекст", "Agents and context"),
    "browser": ("Браузер и визуальная проверка", "Browser and visual proof"),
    "media": ("Медиа и творчество", "Media and writing"),
}


def load_catalog(repo):
    """Skills offered for selection; without this file every listed skill is installed."""
    path = repo / "manifests/skill-catalog.json"
    if not path.is_file():
        return {}
    entries = {}
    for entry in read_json(path).get("skills", []):
        name = entry.get("name", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name in entries or not entry.get("ru") or not entry.get("en"):
            raise ValueError("Неверная запись каталога skills: " + repr(name))
        entries[name] = entry
    return entries


def parse_selection(catalog, text):
    names = list(catalog)
    text = (text or "").strip().lower()
    if text in ("", "recommended", "рекомендуемые"):
        return {name for name, entry in catalog.items() if entry.get("recommended")}
    if text in ("all", "все"):
        return set(names)
    if text in ("none", "0", "нет"):
        return set()
    chosen = set()
    for token in re.split(r"[,;\s]+", text):
        if not token:
            continue
        if token.isdigit() and 1 <= int(token) <= len(names):
            chosen.add(names[int(token) - 1])
        elif token in catalog:
            chosen.add(token)
        else:
            raise ValueError("Нет такого skill в каталоге: " + token)
    return chosen


def installed_skill(args, name):
    return any((root / "skills" / name / "SKILL.md").is_file() for root in roots_for(args).values())


def show_catalog(args, catalog, lang="ru"):
    repo = args.repo_root
    profile = read_json(repo / "manifests/profile.json")
    codex_only = set(profile.get("codex_only_skills", []))
    external = {s["name"]: s for s in read_json(repo / "manifests/external-skills.json")["codex_skill_installer"]}
    ru = lang == "ru"
    print(("Skills для установки · ★ рекомендуемые · ✓ уже установлены" if ru else
           "Skills available · ★ recommended · ✓ already installed"))
    group = None
    for number, (name, entry) in enumerate(catalog.items(), 1):
        if entry.get("group") != group:
            group = entry.get("group")
            title = CATALOG_GROUPS.get(group, (group, group))
            print("\n" + (title[0] if ru else title[1]))
        mark = "✓" if installed_skill(args, name) else ("★" if entry.get("recommended") else " ")
        apps = "Codex" if name in codex_only else "Codex + Claude"
        spec = external.get(name)
        if spec:
            licence = spec.get("license") or ("лицензия не указана автором" if ru else "no license stated")
            origin = ("автор: " if ru else "author: ") + spec["repo"] + " · " + licence
        else:
            origin = "в этом репозитории" if ru else "bundled with this repository"
        print(f"{number:>3} {mark} {name} — {entry['ru' if ru else 'en']}")
        print(f"        {apps} · {origin}")


def units(args):
    repo = args.repo_root
    manifest = read_json(repo / "manifests/portable-files.json")
    profile = read_json(repo / "manifests/profile.json")
    codex_only = set(profile.get("codex_only_skills", []))
    catalog = load_catalog(repo)
    chosen = set(getattr(args, "selected", ()) or ())
    result = []
    for app in args.apps:
        result.append(unit(app + ":instructions", "Персонализация", app, "file",
                           "AGENTS.md" if app == "codex" else "CLAUDE.md", encoded(instructions(repo))))
        result.append(unit(app + ":memory", "Память", app, "file", "portable-memory.md",
                           packed((repo / manifest["portable_memory_source"]).read_bytes())))
        for skill in legacy.platform_entries(manifest, "personal_skills", args.platform):
            if app == "claude" and skill in codex_only:
                continue
            safe_relative(skill)
            files = tree(repo / "personal-skills" / skill)
            if "SKILL.md" not in files:
                raise ValueError("Нет исходника skill: " + skill)
            result.append(unit(app + ":skill:" + skill, skill, app, "tree", "skills/" + skill, files,
                               optional=skill in catalog and skill not in chosen))
        for spec in read_json(repo / "manifests/external-skills.json")["codex_skill_installer"]:
            name = spec["name"]
            if app == "claude" and name in codex_only:
                continue
            desired = external_tree(args, spec)
            optional = name not in chosen and (name in catalog or name in profile.get("optional_skills", []))
            result.append(unit(app + ":external:" + name, name, app, "tree", "skills/" + name,
                               desired, external=spec, optional=optional))
    if "codex" in args.apps:
        for section, values in legacy.expected_sections(repo, args.platform, False).items():
            for key, value in values.items():
                result.append(unit("codex:config:" + (section + "." if section else "") + key,
                                   config_label(section, key), "codex", "toml", "config.toml", value,
                                   section=section, key=key))
        for key, source in (("git-commit-instructions", "commit_rules_source"), ("git-pr-instructions", "pr_rules_source")):
            path = source_file(repo, source)
            if path.is_file():
                result.append(unit("codex:config:desktop." + key, "Правила " + path.stem, "codex", "toml",
                                   "config.toml", path.read_text(encoding="utf-8").strip(),
                                   section="desktop", key=key))
        for name in legacy.platform_entries(manifest, "agents", args.platform):
            result.append(unit("codex:agent:" + name, name, "codex", "file", "agents/" + name,
                               packed((repo / "agents" / name).read_bytes())))
    if "claude" in args.apps:
        for name in legacy.platform_entries(manifest, "claude_agents", args.platform):
            safe_relative(name)
            result.append(unit("claude:agent:" + name, name, "claude", "file", "agents/" + name,
                               packed((repo / "claude-agents" / name).read_bytes())))
        for key, value in profile.get("claude_settings", {}).items():
            legacy.validate_claude_key(key)
            result.append(unit("claude:config:" + key, config_label("", key), "claude", "json",
                               "settings.json", value, key=key))
    return result


def config_label(section, key):
    return {"model": "Модель по умолчанию", "model_context_window": "Размер контекста",
            "memories": "Автопамять Codex", "generate_memories": "Создание автопамяти",
            "use_memories": "Использование автопамяти", "service_tier": "Режим обслуживания",
            "localeOverride": "Язык интерфейса", "personality": "Стиль общения",
            "appearanceTheme": "Тема интерфейса", "usePointerCursors": "Указатели мыши",
            "followUpQueueMode": "Очередь сообщений", "conversationDetailMode": "Подробность шагов",
            "show-context-window-usage": "Показывать заполнение контекста",
            "url": "Адрес справочника OpenAI", "autoMemoryEnabled": "Автопамять Claude",
            "attribution": "Подпись Claude в коммитах и PR"}.get(key, (section + "." if section else "") + key)


def actual(item, roots):
    path = checked(roots[item["app"]] / item["path"])
    kind = item["kind"]
    if kind == "file":
        return file_value(path)
    if kind == "tree":
        return tree(path)
    if not path.exists():
        return ABSENT
    if kind == "toml":
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        section = legacy.get_section(data, item["section"])
        return section.get(item["key"], ABSENT) if section is not None else ABSENT
    if kind == "json":
        return read_json(path)[item["key"]] if item["key"] in read_json(path) else ABSENT
    raise ValueError("Неизвестный тип элемента")


def missing(value, kind):
    return value == ABSENT if kind in ("toml", "json") else not value


def classify(item, current, previous):
    desired = item["desired"]
    choice = previous.get("choice") if previous else None
    if choice in ("keep", "skip", "remove", "merge"):
        if (previous.get("source") == source_hash(item) and
                previous.get("installed") == content_hash(current)):
            return "kept" if choice in ("keep", "merge") else "skipped"
        # A refusal outlives new source versions: never reinstall it silently.
        if choice in ("skip", "remove") and not item.get("retired") and missing(current, item["kind"]):
            return "skipped"
    if item.get("retired"):
        return "removed"
    if item.get("external") and desired is None:
        return "optional" if item.get("optional") else "unprepared"
    if content_hash(current) == content_hash(desired):
        return "same"
    if missing(current, item["kind"]):
        return "optional" if item.get("optional") and not previous else "new"
    if not previous:
        return "unbased"
    source_changed = previous.get("source") != source_hash(item)
    local_changed = previous.get("installed") != content_hash(current)
    # A deliberately kept or merged local version is never replaced automatically.
    if source_changed and (local_changed or choice in ("keep", "merge")):
        return "conflict"
    return "incoming" if source_changed else "local"


def facts(value):
    if not value:
        return set()
    text = unpack(value).decode()
    result, active = set(), False
    for line in text.splitlines():
        if line.startswith("## "):
            active = "Граница" not in line
        elif active and line.strip() and not line.startswith("#"):
            result.add(line.removeprefix("- ").strip())
    return result


def eol_only(old, new):
    """True when two stored files differ only by CRLF/LF line endings."""
    if not old or not new:
        return False
    a, b = unpack(old), unpack(new)
    return a != b and a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def summary(item, current):
    if item["id"].endswith(":memory"):
        old, new = facts(current), facts(item["desired"])
        return f"{len(new)} записей; +{len(new-old)} новых, −{len(old-new)} прежних"
    if item["kind"] == "tree":
        desired = item["desired"]
        if desired is None:
            return "установлен, версия не подтверждена" if current else "не установлен"
        changed = [name for name in set(current) | set(desired)
                   if content_hash(current.get(name)) != content_hash(desired.get(name))]
        if not changed:
            return "файлы совпадают"
        eol = sum(eol_only(current.get(name), desired.get(name)) for name in changed)
        return f"{len(changed)} файлов изменится" + (f", из них {eol} — только переносы строк" if eol else "")
    if item["kind"] in ("toml", "json"):
        def human(v):
            if v == ABSENT: return "не задано"
            if isinstance(v, bool): return "включено" if v else "выключено"
            if isinstance(v, str) and len(v) > 90: return "пользовательский текст"
            if isinstance(v, (dict, list)): return json.dumps(v, ensure_ascii=False)
            return str(v)
        return human(current) + " → " + human(item["desired"])
    old = unpack(current).decode(errors="replace") if current else ""
    new = unpack(item["desired"]).decode(errors="replace") if item["desired"] else ""
    changes = list(difflib.ndiff(old.splitlines(), new.splitlines()))
    return f"+{sum(s.startswith('+ ') for s in changes)} / −{sum(s.startswith('- ') for s in changes)} строк; доступен смысловой обзор"


def inventory(args):
    roots = roots_for(args)
    out = {}
    for app, root in roots.items():
        if app not in args.apps:
            continue
        config = root / ("config.toml" if app == "codex" else "settings.json")
        doc = (tomllib.loads(config.read_text(encoding="utf-8-sig")) if app == "codex"
               else read_json(config, {})) if config.exists() else {}
        out[app] = {"plugins": list(doc.get("plugins", doc.get("enabledPlugins", {}))),
                    "connections": list(doc.get("mcp_servers", {})),
                    "local_config_sections": sorted(doc),
                    "hooks": (root / "hooks.json").exists() or bool(doc.get("hooks")),
                    "extra_instructions": [n for n in ("AGENTS.override.md", "CLAUDE.local.md") if (root/n).exists()],
                    "local_skills": sorted(p.name for p in (root/"skills").iterdir()
                                           if (p/"SKILL.md").is_file()) if (root/"skills").exists() else [],
                    "rules": sorted(p.name for p in (root/"rules").iterdir()) if (root/"rules").exists() else [],
                    "automations": len(list((root/"automations").iterdir())) if (root/"automations").exists() else 0}
    return out


def plan(args):
    requested = set(getattr(args, "requested", ()) or ())
    roots = roots_for(args)
    state = state_for(args)
    guard_repository(args, state)
    items = units(args)
    ids = {u["id"] for u in items}
    # Only previously owned resources can be proposed for removal.
    for uid, old in state["items"].items():
        if uid not in ids and old["app"] in args.apps:
            items.append({**old["locator"], "desired": None, "retired": True})
    for item in items:
        if item["app"] == "codex" and item["kind"] == "tree":
            alternate = args.agents_home / item["path"] / "SKILL.md"
            if alternate.exists():
                raise ValueError(f"Дублирующий skill: {alternate}")
        current = actual(item, roots)
        item["before"] = content_hash(current)
        item["status"] = classify(item, current, state["items"].get(item["id"]))
        if item["kind"] == "tree" and item["label"] in requested and item["desired"] is not None:
            # An explicit request in this run overrides "not chosen" and an earlier skip.
            item["requested"] = True
            if item["status"] in ("optional", "skipped"):
                item["status"] = "new"
        item["summary"] = "Удаление только по выбору, с восстановлением" if item.get("retired") else summary(item, current)
        # Only managed values enter the plan, never whole credentials-bearing configs.
        item["current"] = current
    return {"schema": SCHEMA, "id": uuid.uuid4().hex, "repo": str(args.repo_root),
            "revision": git(args.repo_root, "rev-parse", "HEAD"), "source": fingerprint(args.repo_root),
            "roots": {k: str(v) for k,v in roots.items()}, "platform": args.platform,
            "apps": args.apps, "development": bool(git(args.repo_root,"status","--porcelain")),
            "state": digest(state), "items": items, "inventory": inventory(args),
            "catalog": bool(load_catalog(args.repo_root)),
            "selected": sorted(getattr(args, "selected", ()) or ()),
            "requested": sorted(getattr(args, "requested", ()) or ())}


def display(review):
    labels = {**LABELS, "optional": "не выбран"} if review.get("catalog") else LABELS
    print("Профиль · " + review["platform"] + " · " + review["revision"][:7] +
          (" + локальные правки" if review.get("development") else ""))
    def tags(group):
        return "; ".join(("Codex" if u["app"]=="codex" else "Claude") + ": " + labels[u["status"]] for u in group)
    for suffix, label in ((":instructions","Персонализация.md"),(":memory","Память")):
        group=[u for u in review["items"] if u["id"].endswith(suffix)]
        print("├── " + label + " — " + tags(group))
        if suffix==":memory":
            for u in group: print("│   └── " + u["app"] + ": " + u["summary"])
    skills={}
    for item in review["items"]:
        if item["kind"]=="tree": skills.setdefault(item["label"],[]).append(item)
    print(f"├── Skills · {len(skills)} в каталоге")
    for name, group in skills.items():
        print("│   ├── " + name + " — " + tags(group))
    agents=[u for u in review["items"] if ":agent:" in u["id"]]
    if agents:
        print("├── Агенты")
        for u in agents: print("│   ├── " + u["label"] + " — " + tags([u]))
    configs=[u for u in review["items"] if u["kind"] in ("toml","json")]
    matching=sum(u["status"]=="same" for u in configs)
    print(f"├── Настройки · {matching} совпадают")
    for u in configs:
        if u["status"]!="same": print("│   ├── " + u["label"] + " — " + labels[u["status"]])
    print("├── Только на устройстве")
    for app, info in review["inventory"].items():
        managed={u["label"] for u in review["items"] if u["kind"]=="tree" and u["app"]==app}
        extras=sorted(set(info.get("local_skills",[]))-managed)
        print(f"│   ├── {app}: плагины {len(info.get('plugins',[]))}, обработчики событий {'есть' if info.get('hooks') else 'нет'}, задачи {info.get('automations',0)}")
        for name in extras: print("│   │   ├── skill: " + name)
        for name in info.get("extra_instructions",[]): print("│   │   ├── инструкция: " + name)
        for name in info.get("rules",[]): print("│   │   ├── правило: " + name)
    needs = [u for u in review["items"] if u["status"] not in ("same","kept","skipped","optional")]
    print(f"└── Изменений для рассмотрения: {len(needs)} · ничего ещё не применено")


def plan_file(args, review):
    path = args.state_dir / "plans" / (review["id"] + ".json")
    save_json(path, review)
    return path


def decisions_for(review, selections, safe=False):
    known = {u["id"] for u in review["items"]}
    if set(selections) - known:
        raise ValueError("Неизвестные пункты выбора: " + ", ".join(sorted(set(selections)-known)))
    result = {}
    for item in review["items"]:
        choice = selections.get(item["id"])
        if choice is None:
            status = item["status"]
            if status == "same": choice = "accept"
            elif status == "new" and item.get("requested"): choice = "accept"
            elif status in ("kept", "skipped"): choice = "remember"
            # Not chosen is not a refusal: nothing is recorded, so it stays "not chosen".
            elif status == "optional": choice = "remember"
            elif safe and status in ("new", "incoming"): choice = "accept"
            else: raise ValueError("Нужен выбор для " + item["id"])
        if isinstance(choice, str): choice = {"action": choice}
        if choice.get("action") not in ("accept", "keep", "skip", "remove", "merge", "remember"):
            raise ValueError("Неизвестное действие: " + str(choice))
        if choice["action"] == "accept" and (item.get("retired") or item["status"] == "unprepared" or
                (item.get("external") and item["desired"] is None)):
            raise ValueError("Нет подготовленного источника для " + item["id"])
        if choice["action"] == "merge" and (item["kind"] != "file" or "text" not in choice):
            raise ValueError("Объединение требует полного утверждённого текста документа")
        result[item["id"]] = choice
    return result


def validate_plan(args, review):
    if review.get("schema") != SCHEMA or review["repo"] != str(args.repo_root):
        raise ValueError("План другого репозитория или версии")
    if review["roots"] != {k:str(v) for k,v in roots_for(args).items()} or review["platform"] != args.platform:
        raise ValueError("План относится к другому устройству")
    if review["apps"] != args.apps or review["source"] != fingerprint(args.repo_root):
        raise ValueError("Источник изменился: сформируйте новый обзор")
    if review["state"] != digest(state_for(args)):
        raise ValueError("После обзора была другая синхронизация")
    args.selected = set(review.get("selected", []))
    fresh = plan(args)
    original = {u["id"]: u for u in fresh["items"]}
    if len(review["items"]) != len(original) or {u["id"] for u in review["items"]} != set(original):
        raise ValueError("Изменён набор элементов плана")
    for item in review["items"]:
        if item != original[item["id"]]:
            raise ValueError("Файлы или план изменились после обзора: " + item["id"])


def set_toml(text, item, value, remove=False):
    if not remove:
        return legacy.update_toml(text, {item["section"]: {item["key"]: value}})
    # Scalar values only. Refuse ambiguous/multiline syntax rather than damage a config.
    lines = text.splitlines(keepends=True)
    start, end, _ = legacy.find_section([s.rstrip('\r\n') for s in lines], item["section"])
    for index in range(start, end):
        if legacy.assignment_name(lines[index]) == item["key"]:
            stop = legacy.assignment_end(lines, index, end)
            del lines[index:stop]
            break
    result = "".join(lines)
    doc = tomllib.loads(result)
    if item["key"] in (legacy.get_section(doc, item["section"]) or {}):
        raise ValueError("Не удалось однозначно убрать настройку")
    return result


def writes_for(args, review, choices):
    roots = roots_for(args)
    writes = {}
    for item in review["items"]:
        action = choices[item["id"]]["action"]
        if action in ("keep", "skip", "remember"):
            continue
        root = roots[item["app"]]
        path = checked(root / item["path"])
        desired = encoded(choices[item["id"]]["text"]) if action == "merge" else item["desired"]
        removing = action == "remove"
        if item["kind"] == "file":
            writes[path] = None if removing else desired
        elif item["kind"] == "tree":
            desired = {} if removing else desired
            previous = item["current"]
            for name in set(previous) | set(desired):
                safe_relative(name)
                writes[checked(path / name)] = desired.get(name)
        else:
            existing = writes.get(path, file_value(path))
            if item["kind"] == "toml":
                text = unpack(existing).decode('utf-8-sig') if existing else ""
                result = set_toml(text, item, desired, removing)
            else:
                doc = json.loads(unpack(existing)) if existing else {}
                if removing: doc.pop(item["key"], None)
                else: doc[item["key"]] = desired
                result = json_bytes(doc).decode()
            writes[path] = packed(result.encode(), existing["mode"] if existing else 0o600)
    # Validate all resulting syntax before the first write.
    for path, value in writes.items():
        if value is None: continue
        data = unpack(value)
        if path.suffix == ".toml": tomllib.loads(data.decode('utf-8-sig'))
        if path.suffix == ".json": json.loads(data)
    return {path:value for path,value in writes.items()
            if content_hash(file_value(path)) != content_hash(value)}


def write_entry(path, value):
    if value is None:
        checked(path)
        if path.is_file(): path.unlink()
    else:
        atomic(path, unpack(value), value["mode"])


def apply_review(args, review, selections, safe=False):
    with locked(args.state_dir):
        for existing in (args.state_dir / "transactions").glob("*/journal.json"):
            if read_json(existing).get("status") == "prepared":
                raise ValueError("Есть незавершённая установка; сначала rollback --id " + existing.parent.name)
        validate_plan(args, review)
        choices = decisions_for(review, selections, safe)
        writes = writes_for(args, review, choices)
        old_state = state_for(args)
        new_state = json.loads(json.dumps(old_state))
        roots = roots_for(args)
        txn = args.state_dir / "transactions" / review["id"]
        if txn.exists(): raise ValueError("План уже применялся; создайте новый")
        entries = []
        for path, value in writes.items():
            app = next(k for k,v in roots.items() if path.is_relative_to(v))
            entries.append({"app": app, "path": path.relative_to(roots[app]).as_posix(),
                            "old": file_value(path), "new": value})
        journal = {"schema": SCHEMA, "roots": review["roots"], "entries": entries,
                   "old_state": old_state, "status": "prepared"}
        save_json(txn / "journal.json", journal)
        completed = []
        try:
            for entry in entries:
                path = roots[entry["app"]] / entry["path"]
                if content_hash(file_value(path)) != content_hash(entry["old"]):
                    raise ValueError("Файл изменился во время установки: " + str(path))
                write_entry(path, entry["new"])
                completed.append(entry)
            for item in review["items"]:
                choice = choices[item["id"]]["action"]
                now = actual(item, roots)
                if choice == "accept" and content_hash(now) != content_hash(item["desired"]):
                    raise ValueError("Проверка результата не прошла: " + item["id"])
                if choice == "remember":
                    continue
                if item.get("retired"):
                    # Answered once: the item left the profile, a kept copy is simply local now.
                    new_state["items"].pop(item["id"], None)
                    continue
                locator = {k:v for k,v in item.items() if k not in ("before", "current", "summary", "status", "desired")}
                new_state["items"][item["id"]] = {
                    "app": item["app"], "locator": locator, "source": source_hash(item),
                    "installed": content_hash(now), "choice": "keep" if choice == "skip" and not missing(now,item["kind"]) else choice,
                }
            chosen = set(review.get("selected", []))
            for item in review["items"]:
                if item["kind"] == "tree" and choices[item["id"]]["action"] in ("skip", "remove"):
                    chosen.discard(item["label"])
            new_state["selected_skills"] = sorted(chosen)
            new_state["repository"] = repository_identity(args.repo_root)
            new_state.update(revision=review["revision"], last_transaction=review["id"])
            save_json(state_path(args), new_state)
            journal["status"] = "applied"
            journal["new_state"] = new_state
            save_json(txn / "journal.json", journal)
        except BaseException:
            for entry in reversed(completed):
                path = roots[entry["app"]] / entry["path"]
                if content_hash(file_value(path)) == content_hash(entry["new"]):
                    write_entry(path, entry["old"])
            save_json(state_path(args), old_state)
            journal["status"] = "rolled_back"
            save_json(txn / "journal.json", journal)
            raise
        for app in args.apps:
            atomic(roots[app] / "portable-repo-path", (str(args.repo_root)+"\n").encode())
        print(f"Применено и проверено: {len(entries)} файлов. Резервная копия: {txn}")
        return journal


def rollback(args, transaction):
    if not re.fullmatch(r"[a-f0-9]{32}", transaction):
        raise ValueError("Неверный идентификатор восстановления")
    with locked(args.state_dir):
        path = args.state_dir / "transactions" / transaction / "journal.json"
        journal = read_json(path)
        roots = roots_for(args)
        if not journal or journal["roots"] != {k:str(v) for k,v in roots.items()}:
            raise ValueError("Резервная копия другого устройства")
        if journal["status"] == "rolled_back":
            raise ValueError("Уже восстановлено")
        state = state_for(args)
        if journal["status"] == "applied" and digest(state) != digest(journal["new_state"]):
            raise ValueError("После этой операции была другая синхронизация")
        if journal["status"] == "prepared" and digest(state) != digest(journal["old_state"]) and state.get("last_transaction") != transaction:
            raise ValueError("После прерванной операции была другая синхронизация")
        for entry in journal["entries"]:
            safe_relative(entry["path"])
            current = content_hash(file_value(checked(roots[entry["app"]]/entry["path"])))
            if current not in (content_hash(entry["new"]), content_hash(entry["old"])):
                raise ValueError("После установки файл изменён: " + entry["path"])
        for entry in reversed(journal["entries"]):
            write_entry(roots[entry["app"]]/entry["path"], entry["old"])
        save_json(state_path(args), journal["old_state"])
        journal["status"] = "rolled_back"
        save_json(path, journal)
        print("Восстановлено предыдущее состояние профиля.")


def verify(args):
    state = state_for(args)
    if not state["items"]:
        raise ValueError("Установка ещё не подтверждена: сначала обзор и применение")
    review = plan(args)
    bad = [u for u in review["items"] if u["status"] not in ("same", "kept", "skipped", "optional")]
    if bad:
        for item in bad: print(item["id"] + " — " + LABELS[item["status"]])
        raise ValueError(f"Не проверено элементов: {len(bad)}")
    print("Установленные файлы соответствуют выбранному профилю. Локальные исключения учтены.")
    for app in args.apps:
        exe = shutil.which(app)
        if not exe:
            print(app + ": приложение не найдено, запуск не проверен")
            continue
        result = subprocess.run([exe,"--version"], text=True, capture_output=True, timeout=20)
        print(app + ": " + (result.stdout.strip() if result.returncode == 0 else "версия не подтверждена"))
    return review


def show_detail(review, uid):
    item = next((u for u in review["items"] if u["id"] == uid), None)
    if item is None: raise ValueError("Нет такого пункта")
    print(item["label"] + ": " + item["summary"])
    if item["kind"] == "file":
        before = unpack(item["current"]).decode().splitlines() if item["current"] else []
        after = unpack(item["desired"]).decode().splitlines() if item["desired"] else []
        removed=[line for line in before if line.strip() and line not in after]
        added=[line for line in after if line.strip() and line not in before]
        print("Уйдёт из действующих инструкций:\n" + ("\n".join(removed) or "Ничего"))
        print("Добавится:\n" + ("\n".join(added) or "Ничего"))
    elif item["kind"] == "tree" and item["desired"] is not None:
        for name in sorted(set(item["current"]) | set(item["desired"])):
            old, new = item["current"].get(name), item["desired"].get(name)
            if content_hash(old) != content_hash(new):
                print(("+ " if not old else "− " if not new else "↻ ") + name)


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["preview","bootstrap","apply","verify","rollback","detail","prepare","catalog"])
    p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--codex-home",type=Path,default=legacy.default_codex_home())
    p.add_argument("--claude-home",type=Path,default=legacy.default_claude_home())
    p.add_argument("--agents-home",type=Path,default=legacy.default_agents_home())
    p.add_argument("--state-dir",type=Path)
    p.add_argument("--platform",choices=["macos","windows"])
    p.add_argument("--apps",default="codex,claude")
    p.add_argument("--plan",type=Path)
    p.add_argument("--decisions",type=Path)
    p.add_argument("--id")
    p.add_argument("--working-tree",action="store_true",help="Use reviewed development source without fetching")
    p.add_argument("--no-fetch",action="store_true",help=argparse.SUPPRESS)
    p.add_argument("--accept-safe",action="store_true")
    p.add_argument("--include-optional",action="store_true")
    p.add_argument("--skills",help="recommended, all, none, or catalog numbers/names separated by commas")
    p.add_argument("--lang",choices=["ru","en"],default="ru",help="language of the skill catalog")
    p.add_argument("--switch-repository",action="store_true",
                   help="deliberately install from a different repository than the one this device's profile came from")
    return p


def main():
    args=parser().parse_args()
    args.repo_root=args.repo_root.expanduser().absolute()
    args.codex_home=args.codex_home.expanduser().absolute()
    args.claude_home=args.claude_home.expanduser().absolute()
    args.agents_home=args.agents_home.expanduser().absolute()
    args.state_dir=(args.state_dir or args.codex_home/"portable-sync").expanduser().absolute()
    args.platform=legacy.detect_platform(args.platform)
    args.apps=args.apps.split(",")
    if not args.apps or len(args.apps)!=len(set(args.apps)) or set(args.apps)-{"codex","claude"}:
        raise ValueError("Приложения: codex,claude")
    if args.command in ("preview","bootstrap") and not (args.working_tree or args.no_fetch):
        if refresh(args.repo_root):
            return subprocess.call([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],"--no-fetch"])
    catalog=load_catalog(args.repo_root)
    if args.command=="catalog":
        if not catalog: raise ValueError("В этом профиле нет каталога skills")
        show_catalog(args,catalog,args.lang)
        return 0
    args.selected=set(state_for(args).get("selected_skills",[]))
    args.requested=set()
    if catalog and args.skills is not None:
        args.requested=parse_selection(catalog,args.skills)
    elif catalog and args.command=="bootstrap":
        show_catalog(args,catalog,args.lang)
        if sys.stdin.isatty():
            answer=input("\nКакие skills установить? Номера или имена через запятую; Enter — рекомендуемые (★), all — все, none — ни одного: ")
            args.requested=parse_selection(catalog,answer)
        else:
            print("\nВыбор skills не передан: ставлю только общий профиль. Выбрать можно так: --skills recommended, --skills all или --skills 1,4,7.")
    args.selected|=args.requested
    if args.command in ("prepare","bootstrap"):
        prepare_external(args,args.include_optional)
        if args.command=="prepare": return 0
    if args.command in ("preview","bootstrap"):
        review=plan(args)
        display(review)
        path=plan_file(args,review)
        print("План: " + str(path))
        if args.command=="bootstrap":
            # First install is automatic only if it cannot overwrite an existing difference.
            apply_review(args,review,{},safe=True)
            verify(args)
            print("Профиль установлен; файлы проверены. Использование в новой сессии требует установленного клиента и действующего входа в аккаунт.")
    elif args.command=="apply":
        if not args.plan: raise ValueError("Нужен --plan из предварительного обзора")
        apply_review(args,read_json(args.plan),read_json(args.decisions,{}) if args.decisions else {},args.accept_safe)
        verify(args)
    elif args.command=="verify": verify(args)
    elif args.command=="rollback": rollback(args,args.id or "")
    elif args.command=="detail":
        if not args.plan or not args.id: raise ValueError("Нужны --plan и --id")
        show_detail(read_json(args.plan),args.id)
    return 0


if __name__=="__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print("Синхронизация остановлена: " + str(exc),file=sys.stderr)
        raise SystemExit(2)
