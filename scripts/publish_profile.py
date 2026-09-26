#!/usr/bin/env python3
"""Publish only explicitly selected repository files; never collect a whole device."""
import argparse
from pathlib import Path
import subprocess
import sys

import sync_profile as sync

ALLOWED = {"AGENTS.md", "CLAUDE.md", "README.md", "README.ru.md", "CHANGELOG.md", ".gitignore", ".gitattributes",
           "codex", "portable", "config", "memory", "personalization", "personal-skills", "agents",
           "claude-agents", "rules", "connections", "docs", "examples", "manifests", "scripts", "tests"}


def publish(repo, message, paths):
    sync.validate_origin(repo)
    if not paths:
        raise ValueError("Укажите согласованные файлы через --paths; автоматического сбора устройства нет.")
    for name in paths:
        parts = sync.safe_relative(name).parts
        if parts[0] not in ALLOWED:
            raise ValueError("Путь вне переносимого профиля: " + name)
    if sync.git(repo,"diff","--cached","--name-only"):
        raise ValueError("Есть ранее подготовленные изменения. Они не будут включены автоматически.")
    sync.git(repo,"fetch","origin","main","--quiet")
    behind = sync.git(repo,"rev-list","--count","HEAD..origin/main")
    if behind != "0":
        raise ValueError("В GitHub появились изменения. Сначала согласуйте входящий обзор.")
    subprocess.run([sys.executable,"-m","unittest","discover","-s",str(repo/"tests"),"-v"],check=True,cwd=repo)
    subprocess.run([sys.executable,str(repo/"scripts/portable_config.py"),"scan","--repo-root",str(repo)],check=True)
    sync.git(repo,"diff","--check")
    sync.git(repo,"add","-A","--",*paths)
    staged=sync.git(repo,"diff","--cached","--name-only")
    if not staged:
        print("publish=no-changes")
        return
    sync.git(repo,"diff","--cached","--check")
    print("Публикуются только выбранные файлы:\n" + staged,flush=True)
    sync.git(repo,"commit","-m",message)
    commit=sync.git(repo,"rev-parse","HEAD")
    try:
        sync.git(repo,"push","origin","HEAD:main")
    except subprocess.SubprocessError:
        print("Не опубликован локальный commit: " + commit,file=sys.stderr)
        raise
    sync.git(repo,"fetch","origin","main","--quiet")
    if commit != sync.git(repo,"rev-parse","origin/main"):
        raise ValueError("После push GitHub снова изменился; проверьте входящий commit")
    print("Опубликован commit: " + commit)
    dirty=sync.git(repo,"status","--porcelain")
    print("Рабочее дерево: " + ("есть оставленные изменения" if dirty else "чистое"))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--message",required=True)
    p.add_argument("--paths",nargs="+",required=True)
    a=p.parse_args()
    publish(a.repo_root.absolute(),a.message,a.paths)


if __name__=="__main__":
    try: main()
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print("Публикация остановлена: " + str(exc),file=sys.stderr)
        raise SystemExit(2)
