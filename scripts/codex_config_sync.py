#!/usr/bin/env python3
"""Plan, apply, verify, and roll back a portable subset of Codex configuration."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import difflib
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - Python 3.11+ supplies tomllib.
    raise SystemExit("Codex Config Sync requires Python 3.11 or newer") from exc

VERSION = "0.1.0"
PLAN_SCHEMA = 1
MANIFEST_SCHEMA = 1
PLAN_RELATIVE = pathlib.PurePosixPath(".codex-sync/plan.json")

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".rules",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {".gitattributes", ".gitignore", "AGENTS.md", "LICENSE"}
SCAN_SKIP_DIRS = {
    ".git",
    ".codex-sync",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
TREE_SKIP_DIRS = SCAN_SKIP_DIRS
FORBIDDEN_FILE_NAMES = {
    "auth.json",
    "cookies.json",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
FORBIDDEN_DIRECTORY_NAMES = {
    ".gnupg",
    ".ssh",
    "archived_sessions",
    "secrets",
    "sessions",
}
FORBIDDEN_FILE_SUFFIXES = (".key", ".p12", ".pem", ".pfx", ".sqlite", ".sqlite3")
WINDOWS_RESERVED_DEVICE_NAMES = {"AUX", "CLOCK$", "CON", "CONIN$", "CONOUT$", "NUL", "PRN"}
RESERVED_CODEX_TARGETS = {"agents", "backups", "config.toml", "skills"}
RESERVED_AGENTS_TARGETS = {"skills"}

# Deliberately local-only. The project syncs behavior, not device security or runtime state.
LOCAL_ONLY_ROOT_KEYS = {
    "approval_policy",
    "approvals_reviewer",
    "chatgpt_base_url",
    "model_provider",
    "model_reasoning_effort",
    "notify",
    "openai_base_url",
    "profile",
    "sandbox_mode",
}
LOCAL_ONLY_SECTION_PREFIXES = {
    "agents",
    "mcp_servers",
    "model_providers",
    "otel",
    "plugins",
    "profiles",
    "projects",
    "sandbox_workspace_write",
    "windows",
}
LOCAL_ONLY_DESKTOP_FRAGMENTS = {
    "font",
    "hotkey",
    "notification",
    "reasoning",
    "remotecontrol",
    "windowsize",
}

KNOWN_TOKEN_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
]
ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(password|passwd|token|api[_-]?key|client[_-]?secret|private[_-]?key)\b"
    r"\s*[:=]\s*[\"']?([^\s\"']+)"
)
ABSOLUTE_USER_PATHS = [
    re.compile(r"(?i)\b[A-Z]:\\Users\\(?!<|%|\$)[A-Za-z0-9._-]+\\"),
    re.compile(r"/Users/(?!<|\$)[A-Za-z0-9._-]+/"),
    re.compile(r"/home/(?!<|\$)[A-Za-z0-9._-]+/"),
]


@dataclass
class Result:
    changed: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    backup_root: pathlib.Path | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def exit_code(self) -> int:
        return 1 if self.errors else 0


@dataclass(frozen=True)
class WriteSpec:
    key: str
    source_display: str
    target_display: str
    target_scope: str
    target_relative: pathlib.PurePosixPath
    target: pathlib.Path
    content: bytes


def repo_root_from_script() -> pathlib.Path:
    return pathlib.Path(__file__).absolute().parents[1]


def default_codex_home() -> pathlib.Path:
    configured = os.environ.get("CODEX_HOME")
    return pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / ".codex"


def default_agents_home() -> pathlib.Path:
    configured = os.environ.get("AGENTS_HOME")
    return pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / ".agents"


def detect_platform(explicit: str | None) -> str:
    if explicit:
        return explicit
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    raise RuntimeError("Unsupported platform; pass --platform windows or --platform macos")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lexical_exists(path: pathlib.Path) -> bool:
    return os.path.lexists(path)


def is_link_like(path: pathlib.Path) -> bool:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def validate_relative(raw: str | pathlib.PurePath, label: str) -> pathlib.PurePosixPath:
    value = str(raw)
    if not value or "\x00" in value or "\\" in value:
        raise ValueError(f"{label} must be a non-empty forward-slash relative path: {value!r}")
    relative = pathlib.PurePosixPath(value)
    if relative.is_absolute() or not relative.parts:
        raise ValueError(f"{label} must be relative: {value!r}")
    if any(part in {"", ".", ".."} or ":" in part for part in relative.parts):
        raise ValueError(f"Unsafe {label}: {value!r}")
    for part in relative.parts:
        _validate_windows_component(part, label)
    return relative


def _validate_windows_component(value: str, label: str) -> None:
    if value != value.rstrip(" ."):
        raise ValueError(f"Unsafe {label}: {value!r}")
    device = value.rstrip(" .").split(".", 1)[0].upper()
    if device in WINDOWS_RESERVED_DEVICE_NAMES or re.fullmatch(r"(?:COM|LPT)[1-9¹²³]", device):
        raise ValueError(f"Unsafe {label}: {value!r}")


def validate_component(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise ValueError(f"Unsafe {label}: {value!r}")
    if value in {".", ".."}:
        raise ValueError(f"Unsafe {label}: {value!r}")
    _validate_windows_component(value, label)
    return value


def is_relative_to(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_join(root: pathlib.Path, relative: str | pathlib.PurePath, label: str) -> pathlib.Path:
    pure = validate_relative(relative, label)
    root = root.expanduser().absolute()
    if lexical_exists(root):
        if is_link_like(root):
            raise ValueError(f"Refusing link or reparse point as managed root for {label}: {root}")
        if not root.is_dir():
            raise ValueError(f"Managed root must be a real directory for {label}: {root}")
    root_resolved = root.resolve(strict=False)
    candidate = root.joinpath(*pure.parts)

    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if lexical_exists(cursor) and is_link_like(cursor):
            raise ValueError(f"Refusing link or reparse point in {label}: {cursor}")

    resolved = candidate.resolve(strict=False)
    if not is_relative_to(resolved, root_resolved):
        raise ValueError(f"Refusing path outside managed root for {label}: {candidate}")
    return candidate


def sensitive_path_reason(relative: pathlib.PurePosixPath) -> str | None:
    lowered_parts = [part.lower() for part in relative.parts]
    if any(part in FORBIDDEN_DIRECTORY_NAMES for part in lowered_parts[:-1]):
        return "sensitive directory"
    name = lowered_parts[-1]
    if name in FORBIDDEN_FILE_NAMES:
        return "sensitive filename"
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "environment secret file"
    if name.endswith(FORBIDDEN_FILE_SUFFIXES):
        return "sensitive file type"
    return None


def reject_sensitive_path(relative: pathlib.PurePosixPath, label: str) -> None:
    reason = sensitive_path_reason(relative)
    if reason:
        raise ValueError(f"Refusing {reason} in {label}: {relative.as_posix()}")


def reject_reserved_target(target_root: str, relative: pathlib.PurePosixPath) -> None:
    first = relative.parts[0].lower()
    reserved = RESERVED_CODEX_TARGETS if target_root == "codex" else RESERVED_AGENTS_TARGETS
    if first in reserved:
        raise ValueError(
            f"portable_files cannot manage reserved {target_root} target: {relative.as_posix()}"
        )


def require_regular_file(path: pathlib.Path, label: str) -> None:
    if not lexical_exists(path):
        raise FileNotFoundError(f"Missing {label}: {path}")
    if is_link_like(path):
        raise ValueError(f"Refusing linked {label}: {path}")
    metadata = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"Expected regular file for {label}: {path}")


def walk_regular_files(root: pathlib.Path) -> list[pathlib.PurePosixPath]:
    if not lexical_exists(root):
        return []
    if is_link_like(root) or not root.is_dir():
        raise ValueError(f"Managed tree must be a real directory: {root}")
    found: list[pathlib.PurePosixPath] = []
    stack: list[tuple[pathlib.Path, pathlib.PurePosixPath]] = [(root, pathlib.PurePosixPath())]
    while stack:
        current, relative_root = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                relative = relative_root / entry.name
                if entry.name in TREE_SKIP_DIRS and entry.is_dir(follow_symlinks=False):
                    continue
                path = pathlib.Path(entry.path)
                if entry.is_symlink() or is_link_like(path):
                    raise ValueError(f"Refusing linked file inside managed tree: {path}")
                if entry.is_dir(follow_symlinks=False):
                    reject_sensitive_path(relative / "placeholder", "managed tree")
                    stack.append((path, relative))
                elif entry.is_file(follow_symlinks=False):
                    reject_sensitive_path(relative, "managed tree")
                    found.append(relative)
                else:
                    raise ValueError(f"Refusing special file inside managed tree: {path}")
    return sorted(found, key=lambda item: item.as_posix().lower())


def load_json(path: pathlib.Path) -> dict[str, Any]:
    require_regular_file(path, "JSON file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def atomic_write(path: pathlib.Path, content: bytes) -> None:
    if lexical_exists(path) and (is_link_like(path) or not path.is_file()):
        raise ValueError(f"Refusing to replace non-regular target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_link_like(path.parent):
        raise ValueError(f"Refusing linked target parent: {path.parent}")
    mode = 0o600
    if lexical_exists(path):
        mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        with contextlib.suppress(OSError):
            os.chmod(temporary, mode)
        if lexical_exists(path) and is_link_like(path):
            raise ValueError(f"Target became a link before replace: {path}")
        os.replace(temporary, path)
    finally:
        if lexical_exists(temporary):
            temporary.unlink()


def write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )
    atomic_write(path, content)


def quote_segment(segment: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        return segment
    return json.dumps(segment, ensure_ascii=False)


def section_header(section: str) -> str:
    return "[" + ".".join(quote_segment(part) for part in section.split(".")) + "]"


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported portable TOML value: {value!r}")


def assignment_name(line: str) -> str | None:
    match = re.match(r'^\s*((?:[A-Za-z0-9_-]+)|(?:"(?:[^"\\]|\\.)*"))\s*=', line)
    if not match:
        return None
    name = match.group(1)
    return json.loads(name) if name.startswith('"') else name


def _find_multiline_basic_end(line: str, start: int) -> int:
    """Return the next unescaped triple-double-quote delimiter, or -1."""
    candidate = line.find('"""', start)
    while candidate >= 0:
        backslashes = 0
        cursor = candidate - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return candidate
        candidate = line.find('"""', candidate + 1)
    return -1


def _toml_structural_lines(lines: list[str]) -> list[str]:
    """Blank multiline string contents while preserving TOML structure."""
    structural: list[str] = []
    delimiter: str | None = None
    for line in lines:
        output = list(line)
        index = 0
        while index < len(line):
            if delimiter:
                end = (
                    _find_multiline_basic_end(line, index)
                    if delimiter == '"""'
                    else line.find(delimiter, index)
                )
                blank_until = len(line) if end < 0 else end + len(delimiter)
                output[index:blank_until] = " " * (blank_until - index)
                if end < 0:
                    index = len(line)
                else:
                    delimiter = None
                    index = blank_until
                continue

            character = line[index]
            if character == "#":
                break
            if character not in {'"', "'"}:
                index += 1
                continue

            triple = character * 3
            if line.startswith(triple, index):
                end = (
                    _find_multiline_basic_end(line, index + 3)
                    if triple == '"""'
                    else line.find(triple, index + 3)
                )
                blank_until = len(line) if end < 0 else end + 3
                output[index:blank_until] = " " * (blank_until - index)
                if end < 0:
                    delimiter = triple
                    index = len(line)
                else:
                    index = blank_until
                continue

            # Skip an ordinary one-line string so quote-like text inside it cannot
            # accidentally open a multiline string. Keep it intact for quoted keys.
            quote = character
            index += 1
            while index < len(line):
                if quote == '"' and line[index] == "\\":
                    index += 2
                elif line[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
        structural.append("".join(output))
    return structural


def find_section(lines: list[str], section: str) -> tuple[int, int, bool]:
    structural = _toml_structural_lines(lines)
    headers = [
        index for index, line in enumerate(structural) if re.match(r"^\s*\[.+\]\s*(?:#.*)?$", line)
    ]
    if not section:
        return 0, headers[0] if headers else len(lines), True
    wanted = section_header(section)
    for position, start in enumerate(headers):
        if structural[start].strip() == wanted:
            end = headers[position + 1] if position + 1 < len(headers) else len(lines)
            return start + 1, end, True
    return len(lines), len(lines), False


def update_toml(text: str, sections: dict[str, dict[str, Any]]) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    had_final_newline = text.endswith(("\n", "\r"))
    lines = text.splitlines()
    for section, values in sections.items():
        for key, value in values.items():
            structural = _toml_structural_lines(lines)
            start, end, exists = find_section(lines, section)
            if not exists:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.append(section_header(section))
                start = end = len(lines)
            replacement = f"{quote_segment(key)} = {toml_value(value)}"
            found = next(
                (
                    index
                    for index in range(start, end)
                    if assignment_name(structural[index]) == key
                ),
                None,
            )
            if found is None:
                lines.insert(end, replacement)
            else:
                lines[found] = replacement
    rendered = newline.join(lines)
    if had_final_newline or rendered:
        rendered += newline
    tomllib.loads(rendered)
    return rendered


def get_section(document: dict[str, Any], section: str) -> dict[str, Any] | None:
    current: Any = document
    if section:
        for part in section.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current if isinstance(current, dict) else None


def validate_portable_key(section: str, key: str) -> None:
    root = section.split(".", 1)[0] if section else ""
    if not section and key in LOCAL_ONLY_ROOT_KEYS:
        raise ValueError(f"Local-only config key is forbidden: <root>.{key}")
    if root in LOCAL_ONLY_SECTION_PREFIXES:
        raise ValueError(f"Local-only config section is forbidden: {section}")
    if root == "desktop" and any(
        fragment in key.lower() for fragment in LOCAL_ONLY_DESKTOP_FRAGMENTS
    ):
        raise ValueError(f"Device UI setting is forbidden: desktop.{key}")
    if re.search(r"(?i)(password|passwd|token|api[_-]?key|client[_-]?secret|private[_-]?key)", key):
        raise ValueError(f"Secret-like config key is forbidden: {section or '<root>'}.{key}")


def load_config_profile(path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(path)
    sections = payload.get("sections", {})
    if not isinstance(sections, dict):
        raise ValueError(f"sections must be an object: {path}")
    for section, values in sections.items():
        if not isinstance(section, str) or not isinstance(values, dict):
            raise ValueError(f"Invalid config section in {path}: {section!r}")
        for key, value in values.items():
            if not isinstance(key, str):
                raise ValueError(f"Config key must be a string in {path}: {key!r}")
            validate_portable_key(section, key)
            toml_value(value)
    return payload


def expected_sections(repo_root: pathlib.Path, platform: str) -> dict[str, dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    for filename in ("common.json", f"{platform}.json"):
        payload = load_config_profile(safe_join(repo_root, f"config/{filename}", "config profile"))
        for section, values in payload.get("sections", {}).items():
            sections.setdefault(section, {}).update(values)
    return sections


def load_manifest(repo_root: pathlib.Path) -> dict[str, Any]:
    path = safe_join(repo_root, "manifests/portable-files.json", "manifest")
    manifest = load_json(path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(f"Unsupported manifest schema: {manifest.get('schema_version')!r}")
    files = manifest.get("portable_files", [])
    if not isinstance(files, list):
        raise ValueError("portable_files must be a list")
    seen_targets: set[tuple[str, str]] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            raise ValueError(f"portable_files[{index}] must be an object")
        source_raw = item.get("source")
        target_raw = item.get("target")
        if not isinstance(source_raw, str) or not isinstance(target_raw, str):
            raise ValueError(f"Source and target in portable_files[{index}] must be strings")
        source = validate_relative(source_raw, f"portable_files[{index}].source")
        target = validate_relative(target_raw, f"portable_files[{index}].target")
        reject_sensitive_path(source, f"portable_files[{index}].source")
        reject_sensitive_path(target, f"portable_files[{index}].target")
        target_root = item.get("target_root")
        if target_root not in {"codex", "agents"}:
            raise ValueError(f"Invalid target_root in portable_files[{index}]: {target_root!r}")
        reject_reserved_target(target_root, target)
        platforms = item.get("platforms")
        if (
            not isinstance(platforms, list)
            or not platforms
            or any(not isinstance(platform, str) for platform in platforms)
            or any(platform not in {"windows", "macos"} for platform in platforms)
        ):
            raise ValueError(f"Invalid platforms in portable_files[{index}]")
        required_on_collect = item.get("required_on_collect", False)
        if not isinstance(required_on_collect, bool):
            raise ValueError(f"required_on_collect in portable_files[{index}] must be a boolean")
        duplicate_key = (target_root, target.as_posix().lower())
        if duplicate_key in seen_targets:
            raise ValueError(f"Duplicate portable target: {target_root}/{target}")
        seen_targets.add(duplicate_key)
    for key in ("personal_skills", "agents"):
        table = manifest.get(key, {})
        if not isinstance(table, dict):
            raise ValueError(f"{key} must be an object")
        for profile in ("common", "windows", "macos"):
            entries = table.get(profile, [])
            if not isinstance(entries, list):
                raise ValueError(f"{key}.{profile} must be a list")
            for entry in entries:
                if not isinstance(entry, str):
                    raise ValueError(f"{key}.{profile} entries must be strings: {entry!r}")
                validate_component(entry, f"{key}.{profile} entry")
                if key == "agents" and not entry.endswith(".toml"):
                    raise ValueError(f"Agent definition must use a .toml file: {entry!r}")
    return manifest


def profile_entries(manifest: dict[str, Any], key: str, platform: str) -> list[str]:
    table = manifest.get(key, {})
    if not isinstance(table, dict):
        raise ValueError(f"{key} must be an object")
    common = table.get("common", [])
    selected = table.get(platform, [])
    if not isinstance(common, list) or not isinstance(selected, list):
        raise ValueError(f"{key} profiles must be lists")
    if any(not isinstance(value, str) for value in [*common, *selected]):
        raise ValueError(f"{key} profile entries must be strings")
    values = [*common, *selected]
    if len(values) != len({value.lower() for value in values}):
        raise ValueError(f"Duplicate {key} entry for {platform}")
    return values


def roots_for(args: argparse.Namespace) -> dict[str, pathlib.Path]:
    return {"repo": args.repo_root, "codex": args.codex_home, "agents": args.agents_home}


def validate_managed_roots(args: argparse.Namespace) -> None:
    for scope, root in roots_for(args).items():
        root = root.expanduser().absolute()
        if not lexical_exists(root):
            continue
        if is_link_like(root):
            raise ValueError(f"Managed {scope} root must not be a link or reparse point: {root}")
        if not root.is_dir():
            raise ValueError(f"Managed {scope} root must be a real directory: {root}")


def display_path(scope: str, relative: pathlib.PurePosixPath) -> str:
    labels = {"repo": "$REPO", "codex": "$CODEX_HOME", "agents": "$AGENTS_HOME"}
    return f"{labels[scope]}/{relative.as_posix()}"


def add_file_spec(
    specs: list[WriteSpec],
    result: Result,
    *,
    source: pathlib.Path,
    source_display: str,
    target: pathlib.Path,
    target_scope: str,
    target_relative: pathlib.PurePosixPath,
    required: bool,
) -> None:
    if not lexical_exists(source):
        message = f"Source is missing; target preserved: {source_display}"
        (result.errors if required else result.warnings).append(message)
        return
    try:
        require_regular_file(source, "managed source")
        if lexical_exists(target):
            require_regular_file(target, "managed target")
        specs.append(
            WriteSpec(
                key=f"{target_scope}:{target_relative.as_posix()}",
                source_display=source_display,
                target_display=display_path(target_scope, target_relative),
                target_scope=target_scope,
                target_relative=target_relative,
                target=target,
                content=source.read_bytes(),
            )
        )
    except (OSError, ValueError) as exc:
        result.errors.append(str(exc))


def add_tree_specs(
    specs: list[WriteSpec],
    result: Result,
    *,
    source_root: pathlib.Path,
    source_display: str,
    target_root: pathlib.Path,
    target_scope: str,
    target_relative_root: pathlib.PurePosixPath,
    required: bool,
) -> None:
    if not lexical_exists(source_root):
        message = f"Source tree is missing; target preserved: {source_display}"
        (result.errors if required else result.warnings).append(message)
        return
    try:
        files = walk_regular_files(source_root)
        if not files:
            result.warnings.append(f"Managed tree is empty: {source_display}")
        for relative in files:
            source = safe_join(source_root, relative, "managed tree source")
            target_relative = target_relative_root / relative
            target = safe_join(target_root, target_relative, "managed tree target")
            add_file_spec(
                specs,
                result,
                source=source,
                source_display=f"{source_display}/{relative.as_posix()}",
                target=target,
                target_scope=target_scope,
                target_relative=target_relative,
                required=True,
            )
    except (OSError, ValueError) as exc:
        result.errors.append(str(exc))


def personal_skill_collisions(
    manifest: dict[str, Any], args: argparse.Namespace, platform: str
) -> list[str]:
    collisions: list[str] = []
    for name in profile_entries(manifest, "personal_skills", platform):
        try:
            alternate = safe_join(args.agents_home, f"skills/{name}/SKILL.md", "alternate skill")
            if lexical_exists(alternate):
                collisions.append(
                    f"Skill collision: {name} is also discovered at $AGENTS_HOME/skills/{name}. "
                    "Merge it manually and keep one discovered copy."
                )
        except ValueError as exc:
            collisions.append(str(exc))
    return collisions


def build_file_specs(args: argparse.Namespace, direction: str, result: Result) -> list[WriteSpec]:
    manifest = load_manifest(args.repo_root)
    result.errors.extend(personal_skill_collisions(manifest, args, args.platform))
    specs: list[WriteSpec] = []
    roots = roots_for(args)

    for item in manifest.get("portable_files", []):
        if args.platform not in item["platforms"]:
            continue
        repo_relative = validate_relative(item["source"], "portable source")
        live_relative = validate_relative(item["target"], "portable target")
        live_scope = item["target_root"]
        repo_path = safe_join(args.repo_root, repo_relative, "portable source")
        live_path = safe_join(roots[live_scope], live_relative, "portable target")
        if direction == "to-device":
            source, target = repo_path, live_path
            source_display = display_path("repo", repo_relative)
            target_scope, target_relative = live_scope, live_relative
            required = True
        else:
            source, target = live_path, repo_path
            source_display = display_path(live_scope, live_relative)
            target_scope, target_relative = "repo", repo_relative
            required = bool(item.get("required_on_collect", False))
        add_file_spec(
            specs,
            result,
            source=source,
            source_display=source_display,
            target=target,
            target_scope=target_scope,
            target_relative=target_relative,
            required=required,
        )

    for name in profile_entries(manifest, "agents", args.platform):
        repo_relative = pathlib.PurePosixPath("agents") / name
        live_relative = pathlib.PurePosixPath("agents") / name
        repo_path = safe_join(args.repo_root, repo_relative, "agent source")
        live_path = safe_join(args.codex_home, live_relative, "agent target")
        if direction == "to-device":
            source, target, source_scope, target_scope = repo_path, live_path, "repo", "codex"
            required = True
        else:
            source, target, source_scope, target_scope = live_path, repo_path, "codex", "repo"
            required = False
        add_file_spec(
            specs,
            result,
            source=source,
            source_display=display_path(
                source_scope, repo_relative if source_scope == "repo" else live_relative
            ),
            target=target,
            target_scope=target_scope,
            target_relative=repo_relative if target_scope == "repo" else live_relative,
            required=required,
        )

    for name in profile_entries(manifest, "personal_skills", args.platform):
        repo_relative = pathlib.PurePosixPath("personal-skills") / name
        live_relative = pathlib.PurePosixPath("skills") / name
        repo_path = safe_join(args.repo_root, repo_relative, "personal skill source")
        live_path = safe_join(args.codex_home, live_relative, "personal skill target")
        if direction == "to-device":
            source_root, target_root = repo_path, args.codex_home
            source_display, target_scope, target_relative = (
                display_path("repo", repo_relative),
                "codex",
                live_relative,
            )
            required = True
        else:
            source_root, target_root = live_path, args.repo_root
            source_display, target_scope, target_relative = (
                display_path("codex", live_relative),
                "repo",
                repo_relative,
            )
            required = False
        if lexical_exists(source_root):
            try:
                marker = safe_join(source_root, "SKILL.md", "personal skill marker")
                require_regular_file(marker, "personal skill SKILL.md")
            except (OSError, ValueError) as exc:
                result.errors.append(str(exc))
                continue
        add_tree_specs(
            specs,
            result,
            source_root=source_root,
            source_display=source_display,
            target_root=target_root,
            target_scope=target_scope,
            target_relative_root=target_relative,
            required=required,
        )
    return specs


def build_config_specs(args: argparse.Namespace, direction: str, result: Result) -> list[WriteSpec]:
    sections = expected_sections(args.repo_root, args.platform)
    if not sections:
        result.ok.append("config:no-portable-keys-selected")
        return []
    config_relative = pathlib.PurePosixPath("config.toml")
    config_path = safe_join(args.codex_home, config_relative, "Codex config")
    if lexical_exists(config_path):
        try:
            require_regular_file(config_path, "Codex config")
        except (OSError, ValueError) as exc:
            result.errors.append(str(exc))
            return []

    if direction == "to-device":
        existing = (
            config_path.read_text(encoding="utf-8-sig") if lexical_exists(config_path) else ""
        )
        try:
            rendered = update_toml(existing, sections).encode("utf-8")
        except (OSError, ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
            result.errors.append(f"Cannot safely render $CODEX_HOME/config.toml: {exc}")
            return []
        return [
            WriteSpec(
                key="codex:config.toml",
                source_display="$REPO/config/{common,platform}.json",
                target_display="$CODEX_HOME/config.toml",
                target_scope="codex",
                target_relative=config_relative,
                target=config_path,
                content=rendered,
            )
        ]

    if not lexical_exists(config_path):
        result.warnings.append("Local config is missing; portable config profiles were preserved")
        return []
    try:
        document = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.errors.append(f"Cannot read local config: {exc}")
        return []
    specs: list[WriteSpec] = []
    for filename in ("common.json", f"{args.platform}.json"):
        relative = pathlib.PurePosixPath("config") / filename
        target = safe_join(args.repo_root, relative, "config profile")
        payload = load_config_profile(target)
        changed = False
        for section, values in payload.get("sections", {}).items():
            local_section = get_section(document, section)
            for key in list(values):
                if local_section is None or key not in local_section:
                    result.warnings.append(
                        f"Local config key missing; profile preserved: {section or '<root>'}.{key}"
                    )
                    continue
                if values[key] != local_section[key]:
                    values[key] = local_section[key]
                    changed = True
        if changed:
            content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            specs.append(
                WriteSpec(
                    key=f"repo:{relative.as_posix()}",
                    source_display="$CODEX_HOME/config.toml (selected keys only)",
                    target_display=display_path("repo", relative),
                    target_scope="repo",
                    target_relative=relative,
                    target=target,
                    content=content,
                )
            )
    return specs


def build_specs(args: argparse.Namespace, direction: str, result: Result) -> list[WriteSpec]:
    try:
        validate_managed_roots(args)
        specs = build_file_specs(args, direction, result)
        specs.extend(build_config_specs(args, direction, result))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result.errors.append(str(exc))
        return []
    seen: set[str] = set()
    unique: list[WriteSpec] = []
    for spec in specs:
        normalized = os.path.normcase(str(spec.target.absolute()))
        if normalized in seen:
            result.errors.append(f"Duplicate write target: {spec.target_display}")
            continue
        seen.add(normalized)
        unique.append(spec)
    return sorted(unique, key=lambda spec: spec.key.lower())


def operation_for(spec: WriteSpec) -> dict[str, Any] | None:
    before = None
    if lexical_exists(spec.target):
        require_regular_file(spec.target, "plan target")
        before = sha256_file(spec.target)
    after = sha256_bytes(spec.content)
    if before == after:
        return None
    return {
        "action": "create" if before is None else "update",
        "after_sha256": after,
        "before_sha256": before,
        "key": spec.key,
        "source": spec.source_display,
        "target": spec.target_display,
    }


def plan_payload(
    args: argparse.Namespace, direction: str, specs: list[WriteSpec]
) -> dict[str, Any]:
    operations = [operation for spec in specs if (operation := operation_for(spec)) is not None]
    return {
        "schema_version": PLAN_SCHEMA,
        "tool_version": VERSION,
        "direction": direction,
        "platform": args.platform,
        "repo_root": str(args.repo_root),
        "codex_home": str(args.codex_home),
        "agents_home": str(args.agents_home),
        "operations": operations,
    }


def build_plan(
    args: argparse.Namespace, direction: str, result: Result
) -> tuple[dict[str, Any], list[WriteSpec]]:
    specs = build_specs(args, direction, result)
    if result.errors:
        return {}, specs
    payload = plan_payload(args, direction, specs)
    payload["plan_id"] = sha256_bytes(canonical_json(payload))
    return payload, specs


def plan_path(args: argparse.Namespace) -> pathlib.Path:
    return safe_join(args.repo_root, PLAN_RELATIVE, "plan file")


def is_text_content(path: pathlib.PurePosixPath, content: bytes) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
        return False
    try:
        content.decode("utf-8-sig")
        return True
    except UnicodeDecodeError:
        return False


def show_diff(spec: WriteSpec) -> None:
    if not is_text_content(spec.target_relative, spec.content):
        return
    before = spec.target.read_bytes() if lexical_exists(spec.target) else b""
    try:
        before_lines = before.decode("utf-8-sig").splitlines(keepends=True)
        after_lines = spec.content.decode("utf-8-sig").splitlines(keepends=True)
    except UnicodeDecodeError:
        return
    diff = difflib.unified_diff(
        before_lines, after_lines, fromfile=spec.target_display, tofile=spec.source_display
    )
    for line in diff:
        print(line, end="" if line.endswith("\n") else "\n")


def scan_text(text: str, display: str, result: Result, *, public_audit: bool = False) -> None:
    pem_end_marker = "PRIVATE" + " KEY-----"
    if "-----BEGIN " in text and pem_end_marker in text:
        result.errors.append(f"Private key material found: {display}")
    if any(pattern.search(text) for pattern in KNOWN_TOKEN_PATTERNS):
        result.errors.append(f"Token-like value found: {display}")
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ASSIGNMENT_SECRET.search(line)
        if match and not looks_like_placeholder(match.group(2)):
            result.errors.append(
                f"Secret-like assignment found: {display}:{line_number} ({match.group(1)})"
            )
        if public_audit and any(pattern.search(line) for pattern in ABSOLUTE_USER_PATHS):
            result.errors.append(f"User-specific absolute path found: {display}:{line_number}")


def scan_write_specs(
    specs: list[WriteSpec], result: Result, *, public_audit: bool = False
) -> None:
    """Scan collected content before a from-device plan touches the repository."""
    for spec in specs:
        if not is_text_content(spec.target_relative, spec.content):
            continue
        try:
            text = spec.content.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        scan_text(text, spec.source_display, result, public_audit=public_audit)


def plan_command(args: argparse.Namespace) -> Result:
    result = Result()
    prescan = scan_command(args)
    result.ok.extend(prescan.ok)
    result.warnings.extend(prescan.warnings)
    result.errors.extend(prescan.errors)
    if result.errors:
        return result
    plan, specs = build_plan(args, args.direction, result)
    if result.errors:
        return result
    if args.direction == "from-device":
        scan_write_specs(specs, result, public_audit=args.public_audit)
        if result.errors:
            return result
    path = plan_path(args)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, {**plan, "created_at": dt.datetime.now(dt.UTC).isoformat()})
    result.changed.append(str(path))
    result.details.update(
        {
            "direction": plan["direction"],
            "operation_count": len(plan["operations"]),
            "plan_file": str(path),
            "plan_id": plan["plan_id"],
        }
    )
    operation_keys = {item["key"] for item in plan["operations"]}
    for spec in specs:
        if spec.key in operation_keys:
            if not args.json:
                print(
                    f"{next(item['action'] for item in plan['operations'] if item['key'] == spec.key).upper():6} {spec.target_display}"
                )
            if args.show_diff and not args.json:
                show_diff(spec)
        else:
            result.ok.append(spec.target_display)
    if not args.json:
        print(f"plan_id={plan['plan_id']}")
        print(f"plan_file={path}")
    return result


def backup_root_for(
    args: argparse.Namespace, direction: str, plan_id: str
) -> tuple[pathlib.Path, str, pathlib.PurePosixPath]:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    name = f"codex-config-sync-{stamp}-{plan_id[:8]}"
    if direction == "to-device":
        relative = pathlib.PurePosixPath("backups") / name
        return safe_join(args.codex_home, relative, "backup root"), "codex", relative
    relative = pathlib.PurePosixPath(".codex-sync/backups") / name
    return safe_join(args.repo_root, relative, "backup root"), "repo", relative


def create_backup(
    args: argparse.Namespace, direction: str, plan: dict[str, Any], specs: list[WriteSpec]
) -> pathlib.Path:
    root, _, _ = backup_root_for(args, direction, plan["plan_id"])
    root.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    operation_keys = {item["key"] for item in plan["operations"]}
    for spec in specs:
        if spec.key not in operation_keys:
            continue
        existed = lexical_exists(spec.target)
        backup_relative = pathlib.PurePosixPath("files") / spec.target_scope / spec.target_relative
        if existed:
            require_regular_file(spec.target, "backup source")
            destination = safe_join(root, backup_relative, "backup file")
            atomic_write(destination, spec.target.read_bytes())
        operation = next(item for item in plan["operations"] if item["key"] == spec.key)
        entries.append(
            {
                "target_scope": spec.target_scope,
                "target_relative": spec.target_relative.as_posix(),
                "target_display": spec.target_display,
                "backup_relative": backup_relative.as_posix() if existed else None,
                "before_sha256": operation["before_sha256"],
                "after_sha256": operation["after_sha256"],
                "existed": existed,
            }
        )
    manifest = {
        "schema_version": 1,
        "tool_version": VERSION,
        "direction": direction,
        "plan_id": plan["plan_id"],
        "repo_root": str(args.repo_root),
        "codex_home": str(args.codex_home),
        "agents_home": str(args.agents_home),
        "entries": entries,
    }
    write_json_atomic(safe_join(root, "manifest.json", "backup manifest"), manifest)
    return root


def rollback_backup(
    args: argparse.Namespace, backup_root: pathlib.Path, force: bool = False
) -> Result:
    result = Result()
    roots = roots_for(args)
    try:
        root = backup_root.expanduser().absolute()
        allowed = [
            safe_join(args.codex_home, "backups", "backup parent").resolve(strict=False),
            safe_join(args.repo_root, ".codex-sync/backups", "backup parent").resolve(strict=False),
        ]
        resolved = root.resolve(strict=True)
        if not any(is_relative_to(resolved, parent) for parent in allowed):
            raise ValueError(f"Backup is outside managed backup roots: {root}")
        if is_link_like(root):
            raise ValueError(f"Backup root must not be a link: {root}")
        manifest = load_json(safe_join(root, "manifest.json", "backup manifest"))
        for entry in reversed(manifest.get("entries", [])):
            scope = entry.get("target_scope")
            if scope not in roots:
                raise ValueError(f"Invalid backup target scope: {scope!r}")
            relative = validate_relative(entry.get("target_relative", ""), "backup target")
            target = safe_join(roots[scope], relative, "rollback target")
            current = (
                sha256_file(target)
                if lexical_exists(target) and target.is_file() and not is_link_like(target)
                else None
            )
            if not force and current != entry.get("after_sha256"):
                raise ValueError(
                    f"Rollback refused; target changed after apply: {entry.get('target_display')}"
                )
            if entry.get("existed"):
                backup_relative = validate_relative(entry.get("backup_relative", ""), "backup file")
                source = safe_join(root, backup_relative, "backup file")
                require_regular_file(source, "backup file")
                if sha256_file(source) != entry.get("before_sha256"):
                    raise ValueError(f"Backup hash mismatch: {source}")
                atomic_write(target, source.read_bytes())
            elif lexical_exists(target):
                require_regular_file(target, "newly created rollback target")
                target.unlink()
            result.changed.append(entry.get("target_display", str(target)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result.errors.append(str(exc))
    return result


def verify_command(args: argparse.Namespace) -> Result:
    result = Result()
    specs = build_specs(args, "to-device", result)
    if result.errors:
        return result
    for spec in specs:
        if not lexical_exists(spec.target):
            result.errors.append(f"Missing installed target: {spec.target_display}")
        elif sha256_file(spec.target) != sha256_bytes(spec.content):
            result.errors.append(f"Content differs: {spec.target_display}")
        else:
            result.ok.append(spec.target_display)
    return result


def apply_command(args: argparse.Namespace) -> Result:
    result = Result()
    path = plan_path(args)
    try:
        saved = load_json(path)
        direction = saved.get("direction")
        if direction not in {"to-device", "from-device"}:
            raise ValueError("Plan has an invalid direction")
        current, specs = build_plan(args, direction, result)
        if result.errors:
            return result
        if saved.get("plan_id") != current.get("plan_id"):
            raise ValueError(
                "Plan is stale or belongs to different paths. Run plan again and review it."
            )
        prescan = scan_command(args)
        if prescan.errors:
            raise ValueError(
                "Repository safety scan failed before apply: " + "; ".join(prescan.errors)
            )
        result.ok.extend(prescan.ok)
        result.warnings.extend(prescan.warnings)
        if not current["operations"]:
            result.ok.append("already-synchronized")
            return result
        backup_root = create_backup(args, direction, current, specs)
        result.backup_root = backup_root
        operation_keys = {item["key"] for item in current["operations"]}
        try:
            for spec in specs:
                if spec.key not in operation_keys:
                    continue
                # Re-run containment and link checks immediately before each write.
                safe_join(roots_for(args)[spec.target_scope], spec.target_relative, "apply target")
                atomic_write(spec.target, spec.content)
                if sha256_file(spec.target) != sha256_bytes(spec.content):
                    raise RuntimeError(f"Post-write hash mismatch: {spec.target_display}")
                result.changed.append(spec.target_display)
            postcheck = verify_command(args) if direction == "to-device" else scan_command(args)
            if postcheck.errors:
                raise RuntimeError("; ".join(postcheck.errors))
            result.ok.extend(postcheck.ok)
            result.warnings.extend(postcheck.warnings)
        except Exception as exc:  # noqa: BLE001 - transaction must roll back any failed write.
            rollback = rollback_backup(args, backup_root, force=True)
            if rollback.errors:
                result.errors.append(
                    f"Apply failed: {exc}; automatic rollback also failed: {'; '.join(rollback.errors)}"
                )
            else:
                result.errors.append(f"Apply failed and was rolled back: {exc}")
            result.changed.clear()
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result.errors.append(str(exc))
    return result


def looks_like_placeholder(value: str) -> bool:
    lowered = value.lower().strip()
    return (
        not lowered
        or lowered in {"null", "none", "example", "placeholder", "redacted", "changeme"}
        or lowered.startswith(("${", "<"))
        or "secret_ref" in lowered
        or lowered.endswith(("_token", "_password"))
    )


def scan_command(args: argparse.Namespace) -> Result:
    result = Result()
    root = args.repo_root.expanduser().absolute()
    try:
        if is_link_like(root):
            raise ValueError(f"Repository root must not be a link or reparse point: {root}")
        if not root.is_dir():
            raise ValueError(f"Repository root must be a real directory: {root}")
        for current_root, directories, filenames in os.walk(root, followlinks=False):
            current = pathlib.Path(current_root)
            relative_root = current.relative_to(root)
            directories[:] = [name for name in directories if name not in SCAN_SKIP_DIRS]
            for name in list(directories):
                path = current / name
                if is_link_like(path):
                    result.errors.append(
                        f"Symlink or reparse directory is forbidden: {(relative_root / name).as_posix()}"
                    )
                    directories.remove(name)
                    continue
                directory_relative = pathlib.PurePosixPath(
                    (relative_root / name / "placeholder").as_posix()
                )
                if sensitive_path_reason(directory_relative):
                    result.errors.append(
                        f"Sensitive directory is forbidden: {(relative_root / name).as_posix()}"
                    )
                    directories.remove(name)
            for name in filenames:
                path = current / name
                relative = relative_root / name
                if is_link_like(path):
                    result.errors.append(
                        f"Symlink or reparse file is forbidden: {relative.as_posix()}"
                    )
                    continue
                if sensitive_path_reason(pathlib.PurePosixPath(relative.as_posix())):
                    result.errors.append(f"Sensitive file type is forbidden: {relative.as_posix()}")
                    continue
                if path.suffix.lower() not in TEXT_SUFFIXES and name not in TEXT_NAMES:
                    continue
                try:
                    text = path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    result.warnings.append(f"Unreadable text-like file: {relative.as_posix()}")
                    continue
                scan_text(
                    text,
                    relative.as_posix(),
                    result,
                    public_audit=args.public_audit,
                )
    except (OSError, ValueError) as exc:
        result.errors.append(str(exc))
    if not result.errors:
        result.ok.append("repository-safety-scan")
    return result


def doctor_command(args: argparse.Namespace) -> Result:
    result = Result()
    try:
        validate_managed_roots(args)
        load_manifest(args.repo_root)
        expected_sections(args.repo_root, args.platform)
        result.ok.extend(
            ["manifest-schema", "portable-config-profiles", f"platform:{args.platform}"]
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result.errors.append(str(exc))
    scan = scan_command(args)
    result.ok.extend(scan.ok)
    result.warnings.extend(scan.warnings)
    result.errors.extend(scan.errors)
    if not shutil.which("git"):
        result.warnings.append(
            "Git was not found; local plan/apply still works, but repository sync does not"
        )
    else:
        result.ok.append("git")
    return result


def print_result(result: Result, json_output: bool) -> None:
    payload = {
        "changed": result.changed,
        "ok_count": len(result.ok),
        "warnings": result.warnings,
        "errors": result.errors,
        "backup": str(result.backup_root) if result.backup_root else None,
        "details": result.details,
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(
        f"changed={len(result.changed)} ok={len(result.ok)} warnings={len(result.warnings)} errors={len(result.errors)}"
    )
    if result.backup_root:
        print(f"backup={result.backup_root}")
    for item in result.warnings:
        print(f"WARNING {item}")
    for item in result.errors:
        print(f"ERROR {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("doctor", "plan", "apply", "verify", "rollback", "scan")
    )
    parser.add_argument("--repo-root", type=pathlib.Path, default=repo_root_from_script())
    parser.add_argument("--codex-home", type=pathlib.Path, default=default_codex_home())
    parser.add_argument("--agents-home", type=pathlib.Path, default=default_agents_home())
    parser.add_argument("--platform", choices=("windows", "macos"))
    parser.add_argument("--direction", choices=("to-device", "from-device"), default="to-device")
    parser.add_argument("--show-diff", action="store_true")
    parser.add_argument("--backup", type=pathlib.Path)
    parser.add_argument("--public-audit", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.repo_root = args.repo_root.expanduser().absolute()
    args.codex_home = args.codex_home.expanduser().absolute()
    args.agents_home = args.agents_home.expanduser().absolute()
    try:
        args.platform = detect_platform(args.platform)
        if args.command == "doctor":
            result = doctor_command(args)
        elif args.command == "plan":
            result = plan_command(args)
        elif args.command == "apply":
            result = apply_command(args)
        elif args.command == "verify":
            result = verify_command(args)
        elif args.command == "scan":
            result = scan_command(args)
        else:
            if args.backup is None:
                parser.error("rollback requires --backup PATH")
            result = rollback_backup(args, args.backup)
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = Result(errors=[str(exc)])
    print_result(result, args.json)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
