#!/usr/bin/env python3
"""Clone a Codex Config Sync repository once, then install the shared Codex and Claude Code profile."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

DEFAULT_REPOSITORY = "BakinSan7/codex-config-sync"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repository", default=DEFAULT_REPOSITORY, help="GitHub owner/name of your profile repository")
    p.add_argument("--destination", type=Path, help="where to keep the clone (default: recorded clone or ~/codex-config-sync)")
    p.add_argument("--preview", action="store_true", help="only show the review tree, change nothing")
    p.add_argument("--skills", help="recommended, all, none, or catalog numbers/names separated by commas")
    a = p.parse_args()
    if sys.version_info < (3, 11) or not shutil.which("git"):
        raise SystemExit("Нужны Python 3.11+ и Git.")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", a.repository):
        raise SystemExit("--repository должен иметь вид owner/name")
    codex = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    pointer = codex / "portable-repo-path"
    default = Path(pointer.read_text(encoding="utf-8").strip()) if pointer.exists() else Path.home() / "codex-config-sync"
    target = (a.destination or default).expanduser().absolute()
    expected = ("https://github.com/" + a.repository, "git@github.com:" + a.repository)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", expected[0] + ".git", str(target)], check=True)
        print("Локальный репозиторий создан: " + str(target), flush=True)
    origin = subprocess.check_output(["git", "-C", str(target), "remote", "get-url", "origin"], text=True).strip()
    if origin.rstrip("/").removesuffix(".git") not in expected:
        raise SystemExit("В папке другой репозиторий; код из неё не запускался: " + str(target))
    if subprocess.check_output(["git", "-C", str(target), "status", "--porcelain"], text=True).strip():
        raise SystemExit("В репозитории есть незавершённые изменения; разберите их до установки.")
    subprocess.run(["git", "-C", str(target), "fetch", "origin", "main", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(target), "merge", "--ff-only", "origin/main"], check=True)
    script = target / "scripts/sync_profile.py"
    if not script.is_file():
        raise SystemExit("Папка существует, но установщик профиля не найден: " + str(target))
    command = [sys.executable, str(script), "preview" if a.preview else "bootstrap", "--repo-root", str(target)]
    if a.skills is not None:
        command += ["--skills", a.skills]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
