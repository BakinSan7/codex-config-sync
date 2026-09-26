#!/usr/bin/env python3
"""Shared TOML and manifest helpers plus the repository secret scanner."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import stat
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Any


TEXT_SUFFIXES = {
    ".md", ".txt", ".toml", ".json", ".yaml", ".yml", ".py", ".ps1",
    ".sh", ".js", ".ts", ".css", ".html", ".rules", ".ini", ".cfg",
}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "backups", "reports"}
PRIVATE_KEY_NAMES = {
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "identity.pem",
}


# Copied from the v0.1 engine: files, keys and paths that never belong in a shared profile.
FORBIDDEN_FILE_NAMES = {
    ".credentials.json",
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

LOCAL_ONLY_CLAUDE_ROOT_KEYS = {
    "apiKeyHelper",
    "awsAuthRefresh",
    "awsCredentialExport",
    "env",
    "forceLoginMethod",
    "forceLoginOrgUUID",
    "hooks",
    "oauthAccount",
    "otelHeadersHelper",
    "statusLine",
}

ABSOLUTE_USER_PATHS = [
    re.compile(r"(?i)\b[A-Z]:\\Users\\(?!<|%|\$)[A-Za-z0-9._-]+\\"),
    re.compile(r"/Users/(?!<|\$)[A-Za-z0-9._-]+/"),
    re.compile(r"/home/(?!<|\$)[A-Za-z0-9._-]+/"),
]

# This profile treats the default model as a device choice as well.
LOCAL_ONLY_ROOT_KEYS = LOCAL_ONLY_ROOT_KEYS | {"model"}
LOCAL_ONLY_CLAUDE_ROOT_KEYS = LOCAL_ONLY_CLAUDE_ROOT_KEYS | {
    "enabledPlugins", "extraKnownMarketplaces", "model", "permissions", "sandbox",
}


@dataclass
class Result:
    changed: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def exit_code(self) -> int:
        return 1 if self.errors else 0


def repo_root_from_script() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_codex_home() -> pathlib.Path:
    configured = os.environ.get("CODEX_HOME")
    return pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / ".codex"


def default_agents_home() -> pathlib.Path:
    configured = os.environ.get("AGENTS_HOME")
    return pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / ".agents"


def default_claude_home() -> pathlib.Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / ".claude"


def detect_platform(explicit: str | None) -> str:
    if explicit:
        return explicit
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    raise RuntimeError("Unsupported platform; pass --platform windows or --platform macos")


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
    raise TypeError(f"Unsupported TOML value: {value!r}")


def assignment_name(line: str) -> str | None:
    match = re.match(r"^\s*((?:[A-Za-z0-9_-]+)|(?:\"(?:[^\"\\]|\\.)*\"))\s*=", line)
    if not match:
        return None
    name = match.group(1)
    if name.startswith('"'):
        return json.loads(name)
    return name


def find_section(lines: list[str], section: str) -> tuple[int, int, bool]:
    headers = [index for index, line in enumerate(lines) if re.match(r"^\s*\[.+\]\s*(?:#.*)?$", line)]
    if not section:
        return 0, headers[0] if headers else len(lines), True
    wanted = section_header(section)
    for position, start in enumerate(headers):
        if lines[start].strip() == wanted:
            end = headers[position + 1] if position + 1 < len(headers) else len(lines)
            return start + 1, end, True
    return len(lines), len(lines), False


def assignment_end(lines: list[str], start: int, limit: int) -> int:
    """Find an entire scalar/list assignment, including multiline strings."""
    for end in range(start + 1, limit + 1):
        try:
            tomllib.loads("\n".join(line.rstrip("\r\n") for line in lines[start:end]))
            return end
        except tomllib.TOMLDecodeError:
            continue
    raise ValueError("Cannot determine complete TOML assignment")


def update_toml(text: str, sections: dict[str, dict[str, Any]]) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    had_final_newline = text.endswith(("\n", "\r"))
    lines = text.splitlines()
    for section, values in sections.items():
        for key, value in values.items():
            start, end, exists = find_section(lines, section)
            if not exists:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.append(section_header(section))
                start, end = len(lines), len(lines)
            replacement = f"{quote_segment(key)} = {toml_value(value)}"
            found = None
            for index in range(start, end):
                if assignment_name(lines[index]) == key:
                    found = index
                    break
            if found is not None:
                stop = assignment_end(lines, found, end)
                lines[found:stop] = [replacement]
            else:
                lines.insert(end, replacement)
    rendered = newline.join(lines)
    if had_final_newline or rendered:
        rendered += newline
    # Prove that the resulting TOML parses before returning it.
    tomllib.loads(rendered)
    return rendered


def merge_sections(base: dict[str, dict[str, Any]], extra: dict[str, dict[str, Any]]) -> None:
    for section, values in extra.items():
        base.setdefault(section, {}).update(values)


def expected_sections(repo_root: pathlib.Path, platform: str, include_permissions: bool) -> dict[str, dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    for filename in ("common.json", f"{platform}.json"):
        path = repo_root / "config" / filename
        profile = load_json(path).get("sections", {}) if path.is_file() else {}
        for section, values in profile.items():
            for key in values:
                validate_portable_key(section, key)
        merge_sections(sections, profile)
    mcp_path = repo_root / "manifests" / "mcp.json"
    # Only URL-based servers the manifest lists explicitly; local commands stay on the device.
    for name, values in (load_json(mcp_path).get("managed_servers", {}) if mcp_path.is_file() else {}).items():
        sections[f"mcp_servers.{name}"] = values
    if include_permissions:
        permission_file = repo_root / "config" / f"permissions.{platform}.json"
        merge_sections(sections, load_json(permission_file).get("sections", {}))
    return sections


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



def validate_claude_key(key: str) -> None:
    if not isinstance(key, str) or not key or len(key) > 128 or not key.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Unsafe Claude setting name: {key!r}")
    if key in LOCAL_ONLY_CLAUDE_ROOT_KEYS:
        raise ValueError(f"Local-only Claude setting is forbidden: {key}")


def portable_manifest(repo_root: pathlib.Path) -> dict[str, Any]:
    return load_json(repo_root / "manifests" / "portable-files.json")


def platform_entries(manifest: dict[str, Any], key: str, platform: str) -> list[str]:
    """Return common plus platform-specific entries, retaining v1 list compatibility."""
    value = manifest.get(key, [])
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [*value.get("common", []), *value.get(platform, [])]
    raise TypeError(f"Manifest key {key!r} must be a list or platform table")


def is_redirected_directory(path: pathlib.Path) -> bool:
    """Return true for symlinked or Windows reparse-point directories."""
    if path.is_symlink():
        return True
    if not path.exists():
        return False
    attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def get_section(document: dict[str, Any], section: str) -> dict[str, Any] | None:
    current: Any = document
    if section:
        for part in section.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current if isinstance(current, dict) else None


KNOWN_TOKEN_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
]
ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(password|passwd|token|api[_-]?key|client[_-]?secret|private[_-]?key)\b\s*[:=]\s*[\"']?([^\s\"']+)"
)


def looks_like_placeholder(value: str) -> bool:
    lowered = value.lower().strip()
    return (
        not lowered
        or lowered in {"null", "none", "example", "placeholder", "redacted", "changeme"}
        or lowered.startswith("${")
        or lowered.startswith("<")
        or "secret_ref" in lowered
        or lowered.endswith("_token")
        or lowered.endswith("_password")
    )


def scan_command(args: argparse.Namespace) -> Result:
    result = Result()
    root = args.repo_root
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in FORBIDDEN_DIRECTORY_NAMES for part in relative.parts[:-1]):
            result.errors.append(f"Sensitive directory is forbidden: {relative}")
            continue
        if path.name in FORBIDDEN_FILE_NAMES or path.name.lower().endswith(FORBIDDEN_FILE_SUFFIXES):
            result.errors.append(f"Sensitive file is forbidden: {relative}")
            continue
        lowered_name = path.name.lower()
        if lowered_name in PRIVATE_KEY_NAMES or lowered_name.endswith((".pem", ".key")):
            result.errors.append(f"Private-key-like file is forbidden: {path.relative_to(root)}")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"AGENTS.md", ".gitignore", ".gitattributes"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            result.warnings.append(f"Unreadable text-like file: {path.relative_to(root)}")
            continue
        private_key_marker = "PRIVATE" + " KEY-----"
        if "-----BEGIN " in text and private_key_marker in text:
            result.errors.append(f"Private key material found: {path.relative_to(root)}")
        for pattern in KNOWN_TOKEN_PATTERNS:
            if pattern.search(text):
                result.errors.append(f"Token-like value found: {path.relative_to(root)}")
                break
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = ASSIGNMENT_SECRET.search(line)
            if match and not looks_like_placeholder(match.group(2)):
                result.errors.append(
                    f"Secret-like assignment found: {path.relative_to(root)}:{line_number} ({match.group(1)})"
                )
        if getattr(args, "public_audit", False):
            for line_number, line in enumerate(text.splitlines(), start=1):
                if any(pattern.search(line) for pattern in ABSOLUTE_USER_PATHS):
                    result.errors.append(f"User-specific absolute path found: {relative}:{line_number}")
        if path.name == "SKILL.md" and text.startswith("---"):
            end = text.find("\n---", 3)
            frontmatter = text[3:end] if end != -1 else ""
            for line_number, line in enumerate(frontmatter.splitlines(), start=2):
                if line.startswith("description:"):
                    value = line.split(":", 1)[1].strip()
                    if value and not value.startswith(("\"", "'", "|", ">")) and ": " in value:
                        result.errors.append(
                            f"Unquoted colon makes YAML ambiguous: {path.relative_to(root)}:{line_number}"
                        )
    if not result.errors:
        result.ok.append("secret-and-frontmatter-scan")
    return result


def print_result(result: Result, json_output: bool) -> None:
    payload = {
        "changed": result.changed,
        "ok_count": len(result.ok),
        "warnings": result.warnings,
        "errors": result.errors,
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"changed={len(result.changed)} ok={len(result.ok)} warnings={len(result.warnings)} errors={len(result.errors)}")
    for item in result.changed:
        print(f"CHANGED {item}")
    for item in result.warnings:
        print(f"WARNING {item}")
    for item in result.errors:
        print(f"ERROR {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scan",))
    parser.add_argument("--repo-root", type=pathlib.Path, default=repo_root_from_script())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--public-audit", action="store_true",
                        help="also reject user-specific absolute paths (for public repositories)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.repo_root = args.repo_root.expanduser().resolve()
    result = scan_command(args)
    print_result(result, args.json)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
