from __future__ import annotations

import argparse
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("portable_config", REPO_ROOT / "scripts" / "portable_config.py")
assert SPEC and SPEC.loader
portable_config = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = portable_config
SPEC.loader.exec_module(portable_config)


class TomlMergeTests(unittest.TestCase):
    def test_merge_preserves_unmanaged_sections(self) -> None:
        original = (
            'model = "old"\n'
            'local_secret = "leave-this-value-alone"\n\n'
            '[projects."C:\\\\work"]\n'
            'trust_level = "trusted"\n\n'
            '[features]\n'
            'multi_agent = false\n'
        )
        rendered = portable_config.update_toml(
            original,
            {"": {"model": "new"}, "features": {"multi_agent": True, "memories": True}},
        )
        self.assertIn('model = "new"', rendered)
        self.assertIn('local_secret = "leave-this-value-alone"', rendered)
        self.assertIn('[projects."C:\\\\work"]', rendered)
        self.assertIn('trust_level = "trusted"', rendered)
        self.assertIn('multi_agent = true', rendered)
        self.assertIn('memories = true', rendered)

    def test_plugin_section_is_quoted(self) -> None:
        rendered = portable_config.update_toml("", {"plugins.gmail@openai-curated": {"enabled": True}})
        self.assertIn('[plugins."gmail@openai-curated"]', rendered)

    def test_local_only_keys_are_refused(self) -> None:
        for section, key in (("", "model"), ("", "model_reasoning_effort"), ("", "sandbox_mode"),
                             ("desktop", "sansFontSize"), ("mcp_servers.local", "command"),
                             ("plugins.example", "enabled"), ("agents", "max_threads")):
            with self.assertRaises(ValueError, msg=f"{section}.{key}"):
                portable_config.validate_portable_key(section, key)
        portable_config.validate_portable_key("desktop", "appearanceTheme")
        for key in ("hooks", "env", "permissions", "model", "statusLine"):
            with self.assertRaises(ValueError, msg=key):
                portable_config.validate_claude_key(key)
        portable_config.validate_claude_key("autoMemoryEnabled")

class ManifestAndInstallerTests(unittest.TestCase):
    def test_platform_manifest_separates_windows_only_resources(self) -> None:
        manifest = {"personal_skills": {"common": ["shared"], "windows": ["win-only"], "macos": []}}
        self.assertEqual(portable_config.platform_entries(manifest, "personal_skills", "windows"), ["shared", "win-only"])
        self.assertEqual(portable_config.platform_entries(manifest, "personal_skills", "macos"), ["shared"])
        self.assertEqual(portable_config.platform_entries({"agents": ["legacy"]}, "agents", "macos"), ["legacy"])

    def test_catalog_matches_bundled_and_pinned_skills(self) -> None:
        manifest = portable_config.load_json(REPO_ROOT / "manifests" / "portable-files.json")
        external = portable_config.load_json(REPO_ROOT / "manifests" / "external-skills.json")["codex_skill_installer"]
        catalog = portable_config.load_json(REPO_ROOT / "manifests" / "skill-catalog.json")["skills"]
        bundled = set(portable_config.platform_entries(manifest, "personal_skills", "macos"))
        offered = {entry["name"] for entry in catalog}
        self.assertLessEqual(offered, bundled | {spec["name"] for spec in external})
        self.assertEqual({spec["name"] for spec in external} - offered, set())
        self.assertEqual(bundled - offered, {"codex-config-sync"})
        for entry in catalog:
            self.assertTrue(entry["ru"] and entry["en"] and len(entry["ru"]) <= 120, entry["name"])
            self.assertTrue((REPO_ROOT / "personal-skills" / entry["name"] / "SKILL.md").is_file()
                            or entry["name"] in {spec["name"] for spec in external})

    @unittest.skipUnless(sys.platform == "darwin", "requires macOS system Bash")
    def test_macos_installer_is_preview_only_on_bash_3(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp).resolve()
            completed = subprocess.run(
                ["/bin/bash", str(REPO_ROOT / "codex-sync.sh"), "preview", "--working-tree",
                 "--codex-home", str(root/".codex"), "--claude-home", str(root/".claude"),
                 "--agents-home", str(root/".agents")],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertFalse((root / ".codex" / "AGENTS.md").exists())
            self.assertFalse((root / ".claude" / "CLAUDE.md").exists())
            self.assertTrue(list((root/".codex"/"portable-sync"/"plans").glob("*.json")))


class ScannerTests(unittest.TestCase):
    def test_scanner_detects_token_like_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            candidate = "gh" + "p_" + "A" * 30
            (root / "bad.txt").write_text(candidate, encoding="utf-8")
            result = portable_config.scan_command(argparse.Namespace(repo_root=root))
            self.assertTrue(result.errors)

    def test_scanner_allows_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "safe.md").write_text("token: ${SERVICE_TOKEN}\n", encoding="utf-8")
            result = portable_config.scan_command(argparse.Namespace(repo_root=root))
            self.assertFalse(result.errors)

    def test_external_skill_sources_are_full_commit_pins(self) -> None:
        manifest = portable_config.load_json(REPO_ROOT / "manifests" / "external-skills.json")
        self.assertEqual(set(manifest), {"codex_skill_installer"})
        for skill in manifest["codex_skill_installer"]:
            self.assertRegex(skill["ref"], r"^[0-9a-f]{40}$")
            self.assertRegex(skill["repo"], r"^[\w.-]+/[\w.-]+$")

    def test_task_history_archives_are_not_portable(self) -> None:
        self.assertFalse(list(REPO_ROOT.glob("docs/ARCHIVED_CHAT_CONTEXT*.md")))
        portable_memory = (REPO_ROOT / "portable" / "portable-memory.md").read_text(encoding="utf-8")
        self.assertNotIn("ARCHIVED_CHAT_CONTEXT", portable_memory)

    def test_public_audit_rejects_user_paths_and_sensitive_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            user_path = "/" + "Users/someone/projects/report.md"  # assembled so this file passes the audit itself
            (root / "notes.md").write_text(f"see {user_path}\n", encoding="utf-8")
            plain = portable_config.scan_command(argparse.Namespace(repo_root=root))
            audit = portable_config.scan_command(argparse.Namespace(repo_root=root, public_audit=True))
            self.assertFalse(plain.errors)
            self.assertTrue(any("absolute path" in error for error in audit.errors))
            (root / "notes.md").write_text("see ~/projects/report.md\n", encoding="utf-8")
            (root / "dump.sqlite").write_bytes(b"")
            result = portable_config.scan_command(argparse.Namespace(repo_root=root, public_audit=True))
            self.assertEqual(result.errors, ["Sensitive file is forbidden: dump.sqlite"])

