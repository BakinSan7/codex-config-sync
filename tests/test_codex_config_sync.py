from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "codex_config_sync", PROJECT_ROOT / "scripts" / "codex_config_sync.py"
)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


def write_json(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def manifest(
    *,
    skills: dict | None = None,
    agents: dict | None = None,
    claude_skills: dict | None = None,
    claude_agents: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "portable_files": [
            {
                "source": "portable/AGENTS.md",
                "target_root": "codex",
                "target": "AGENTS.md",
                "platforms": ["windows", "macos"],
                "required_on_collect": False,
            },
            {
                "source": "portable/portable-memory.md",
                "target_root": "codex",
                "target": "portable-memory.md",
                "platforms": ["windows", "macos"],
                "required_on_collect": False,
            },
            {
                "source": "portable/CLAUDE.md",
                "target_root": "claude",
                "target": "CLAUDE.md",
                "platforms": ["windows", "macos"],
                "required_on_collect": False,
            },
        ],
        "personal_skills": skills or {"common": [], "windows": [], "macos": []},
        "agents": agents or {"common": [], "windows": [], "macos": []},
        "claude_skills": claude_skills or {"common": [], "windows": [], "macos": []},
        "claude_agents": claude_agents or {"common": [], "windows": [], "macos": []},
    }


def make_repo(
    root: pathlib.Path, *, config: dict | None = None, custom_manifest: dict | None = None
) -> None:
    (root / "portable").mkdir(parents=True)
    (root / "personal-skills").mkdir()
    (root / "agents").mkdir()
    (root / "config").mkdir()
    (root / "manifests").mkdir()
    (root / "claude-agents").mkdir()
    (root / "claude-skills").mkdir()
    (root / "portable" / "AGENTS.md").write_text("portable instructions\n", encoding="utf-8")
    (root / "portable" / "portable-memory.md").write_text("portable memory\n", encoding="utf-8")
    (root / "portable" / "CLAUDE.md").write_text("portable claude instructions\n", encoding="utf-8")
    write_json(root / "manifests" / "portable-files.json", custom_manifest or manifest())
    write_json(root / "config" / "common.json", config or {"sections": {}})
    write_json(root / "config" / "windows.json", {"sections": {}})
    write_json(root / "config" / "macos.json", {"sections": {}})
    write_json(root / "config" / "claude-common.json", {"values": {}})
    write_json(root / "config" / "claude-windows.json", {"values": {}})
    write_json(root / "config" / "claude-macos.json", {"values": {}})


def args_for(
    repo: pathlib.Path,
    codex_home: pathlib.Path,
    agents_home: pathlib.Path,
    *,
    claude_home: pathlib.Path | None = None,
    platform: str = "windows",
    direction: str = "to-device",
    public_audit: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        command="doctor",
        repo_root=repo.absolute(),
        codex_home=codex_home.absolute(),
        agents_home=agents_home.absolute(),
        claude_home=(claude_home or codex_home.parent / ".claude").absolute(),
        platform=platform,
        direction=direction,
        show_diff=False,
        backup=None,
        public_audit=public_audit,
        json=False,
    )


def quiet_plan(arguments: argparse.Namespace) -> sync.Result:
    with contextlib.redirect_stdout(io.StringIO()):
        return sync.plan_command(arguments)


class TomlTests(unittest.TestCase):
    def test_multiline_strings_are_not_treated_as_sections_or_assignments(self) -> None:
        original = '[features]\nnote = """\npersonality = "trap"\n"""\n'
        rendered = sync.update_toml(original, {"features": {"personality": "safe"}})
        self.assertEqual(rendered.count('personality = "safe"'), 1)
        self.assertIn('personality = "trap"', rendered)
        self.assertEqual(sync.tomllib.loads(rendered)["features"]["note"], 'personality = "trap"\n')

    def test_literal_multiline_string_is_not_treated_as_an_assignment(self) -> None:
        original = "[features]\nnote = '''\npersonality = 'trap'\n'''\n"
        rendered = sync.update_toml(original, {"features": {"personality": "safe"}})
        self.assertEqual(rendered.count('personality = "safe"'), 1)
        self.assertIn("personality = 'trap'", rendered)

    def test_one_line_multiline_text_is_not_a_section(self) -> None:
        original = '[features]\nnote = """[fake]"""\npersonality = "old"\n'
        rendered = sync.update_toml(original, {"features": {"personality": "safe"}})
        self.assertNotIn("[fake]\npersonality", rendered)
        self.assertEqual(sync.tomllib.loads(rendered)["features"]["personality"], "safe")

    def test_triple_quotes_in_comments_and_ordinary_strings_do_not_hide_assignments(self) -> None:
        original = "[features]\nnote = '\"\"\"' # '''\npersonality = \"old\"\n"
        rendered = sync.update_toml(original, {"features": {"personality": "safe"}})
        self.assertEqual(rendered.count('personality = "safe"'), 1)
        self.assertEqual(sync.tomllib.loads(rendered)["features"]["personality"], "safe")

    def test_escaped_quotes_do_not_close_a_multiline_basic_string(self) -> None:
        original = (
            '[features]\nnote = """\nescaped delimiter: \\"""\n'
            'personality = "trap"\n"""\npersonality = "old"\n'
        )
        rendered = sync.update_toml(original, {"features": {"personality": "safe"}})
        self.assertIn('personality = "trap"', rendered)
        self.assertEqual(sync.tomllib.loads(rendered)["features"]["personality"], "safe")

    def test_merge_preserves_unmanaged_values_and_comments(self) -> None:
        original = (
            '# local comment\nmodel_reasoning_effort = "high"\n\n'
            '[projects."C:\\\\work"]\ntrust_level = "trusted"\n\n'
            "[desktop]\ncodeFontSize = 14\n"
        )
        rendered = sync.update_toml(original, {"": {"personality": "pragmatic"}})
        self.assertIn("# local comment", rendered)
        self.assertIn('model_reasoning_effort = "high"', rendered)
        self.assertIn('[projects."C:\\\\work"]', rendered)
        self.assertIn("codeFontSize = 14", rendered)
        self.assertIn('personality = "pragmatic"', rendered)

    def test_local_only_root_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Local-only"):
            sync.validate_portable_key("", "model_reasoning_effort")

    def test_local_only_section_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Local-only"):
            sync.validate_portable_key("mcp_servers.example", "url")

    def test_font_setting_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Device UI"):
            sync.validate_portable_key("desktop", "codeFontSize")


class PathSafetyTests(unittest.TestCase):
    def test_windows_reserved_components_are_rejected(self) -> None:
        for name in (
            "con.txt",
            "COM1",
            "lpt9.log",
            "COM¹.log",
            "PRN",
            "AUX",
            "NUL",
            "CLOCK$",
            "CONIN$",
            "CONOUT$.txt",
            "file.",
            "file ",
        ):
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                sync.validate_component(name, "component")
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    sync.safe_join(pathlib.Path(temporary), name, "path")

    def test_parent_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                sync.safe_join(pathlib.Path(temporary), "../outside", "test path")

    def test_backslash_manifest_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "forward-slash"):
                sync.safe_join(pathlib.Path(temporary), "skills\\outside", "test path")

    def test_absolute_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "relative"):
                sync.safe_join(pathlib.Path(temporary), "/outside", "test path")

    def test_unsafe_skill_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            sync.validate_component("../escape", "skill")

    def test_agent_definition_requires_toml_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            make_repo(
                root,
                custom_manifest=manifest(
                    agents={"common": ["reviewer.txt"], "windows": [], "macos": []}
                ),
            )
            with self.assertRaisesRegex(ValueError, r"\.toml"):
                sync.load_manifest(root)

    def test_manifest_rejects_auth_file_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            configured = manifest()
            configured["portable_files"][0]["target"] = "auth.json"
            make_repo(root, custom_manifest=configured)
            with self.assertRaisesRegex(ValueError, "sensitive filename"):
                sync.load_manifest(root)

    def test_manifest_cannot_bypass_config_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            configured = manifest()
            configured["portable_files"][0]["target"] = "config.toml"
            make_repo(root, custom_manifest=configured)
            with self.assertRaisesRegex(ValueError, "reserved codex target"):
                sync.load_manifest(root)

    def test_manifest_rejects_malformed_platform_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            configured = manifest()
            configured["portable_files"][0]["platforms"] = [[]]
            make_repo(root, custom_manifest=configured)
            with self.assertRaisesRegex(ValueError, "Invalid platforms"):
                sync.load_manifest(root)

    def test_source_symlink_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            real = root / "real.txt"
            link = root / "link.txt"
            real.write_text("value", encoding="utf-8")
            try:
                os.symlink(real, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "link"):
                sync.safe_join(root, "link.txt", "linked source")

    def test_tree_symlink_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "real.txt").write_text("value", encoding="utf-8")
            try:
                os.symlink(root / "real.txt", root / "linked.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "linked"):
                sync.walk_regular_files(root)

    def test_root_symlink_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            real = root / "real"
            link = root / "link"
            real.mkdir()
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "managed root"):
                sync.safe_join(link, "file.txt", "linked root")
            codex_arguments = args_for(root, link, root / "agents")
            with self.assertRaisesRegex(ValueError, "codex root"):
                sync.validate_managed_roots(codex_arguments)
            agents_arguments = args_for(root, real, link)
            with self.assertRaisesRegex(ValueError, "agents root"):
                sync.validate_managed_roots(agents_arguments)
            repo_arguments = args_for(link, real, root / "agents")
            scanned = sync.scan_command(repo_arguments)
            self.assertTrue(any("root" in error.lower() for error in scanned.errors))

    @unittest.skipUnless(os.name == "nt", "requires Windows junction support")
    def test_windows_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            real = root / "real"
            junction = root / "junction"
            real.mkdir()
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(real)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                self.skipTest("junction creation is unavailable")
            try:
                with self.assertRaisesRegex(ValueError, "reparse"):
                    sync.safe_join(root, "junction/file.txt", "junction target")
            finally:
                os.rmdir(junction)

    @unittest.skipUnless(os.name == "nt", "requires Windows junction support")
    def test_windows_root_junction_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            real = root / "real"
            junction = root / "junction"
            real.mkdir()
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(real)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                self.skipTest("junction creation is unavailable")
            try:
                with self.assertRaisesRegex(ValueError, "managed root"):
                    sync.safe_join(junction, "file.txt", "junction root")
                arguments = args_for(junction, root / ".codex", root / ".agents")
                scanned = sync.scan_command(arguments)
                self.assertTrue(any("root" in error.lower() for error in scanned.errors))
            finally:
                os.rmdir(junction)


class PlanApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.codex = self.root / ".codex"
        self.agents = self.root / ".agents"
        make_repo(self.repo)
        self.codex.mkdir()
        self.agents.mkdir()
        self.args = args_for(self.repo, self.codex, self.agents)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_plan_contains_hashes_but_not_file_content(self) -> None:
        result = quiet_plan(self.args)
        self.assertFalse(result.errors)
        payload = json.loads((self.repo / ".codex-sync" / "plan.json").read_text(encoding="utf-8"))
        serialized = json.dumps(payload)
        self.assertNotIn("portable instructions", serialized)
        self.assertEqual(len(payload["operations"][0]["after_sha256"]), 64)

    def test_plan_json_output_is_machine_readable(self) -> None:
        self.args.json = True
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = sync.plan_command(self.args)
            sync.print_result(result, json_output=True)
        payload = json.loads(output.getvalue())
        self.assertFalse(payload["errors"])
        self.assertEqual(payload["details"]["direction"], "to-device")
        self.assertGreater(payload["details"]["operation_count"], 0)

    def test_apply_requires_a_plan(self) -> None:
        result = sync.apply_command(self.args)
        self.assertTrue(result.errors)
        self.assertFalse((self.codex / "AGENTS.md").exists())

    def test_apply_creates_backup_and_verify_passes(self) -> None:
        (self.codex / "AGENTS.md").write_text("local instructions\n", encoding="utf-8")
        plan = quiet_plan(self.args)
        self.assertFalse(plan.errors)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        self.assertIsNotNone(applied.backup_root)
        self.assertEqual(
            (self.codex / "AGENTS.md").read_text(encoding="utf-8"), "portable instructions\n"
        )
        verified = sync.verify_command(self.args)
        self.assertFalse(verified.errors)

    def test_stale_plan_is_rejected(self) -> None:
        quiet_plan(self.args)
        (self.repo / "portable" / "AGENTS.md").write_text(
            "changed after review\n", encoding="utf-8"
        )
        applied = sync.apply_command(self.args)
        self.assertTrue(any("stale" in error.lower() for error in applied.errors))
        self.assertFalse((self.codex / "AGENTS.md").exists())

    def test_rollback_restores_previous_file(self) -> None:
        (self.codex / "AGENTS.md").write_text("before\n", encoding="utf-8")
        quiet_plan(self.args)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        assert applied.backup_root
        rolled_back = sync.rollback_backup(self.args, applied.backup_root)
        self.assertFalse(rolled_back.errors)
        self.assertEqual((self.codex / "AGENTS.md").read_text(encoding="utf-8"), "before\n")

    def test_rollback_refuses_target_changed_after_apply(self) -> None:
        quiet_plan(self.args)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        assert applied.backup_root
        (self.codex / "AGENTS.md").write_text("later user edit\n", encoding="utf-8")
        rolled_back = sync.rollback_backup(self.args, applied.backup_root)
        self.assertTrue(any("changed after apply" in error for error in rolled_back.errors))
        self.assertEqual(
            (self.codex / "AGENTS.md").read_text(encoding="utf-8"), "later user edit\n"
        )

    def test_from_device_collects_without_pushing(self) -> None:
        (self.codex / "AGENTS.md").write_text("reviewed local instructions\n", encoding="utf-8")
        collect_args = args_for(self.repo, self.codex, self.agents, direction="from-device")
        quiet_plan(collect_args)
        applied = sync.apply_command(collect_args)
        self.assertFalse(applied.errors)
        self.assertEqual(
            (self.repo / "portable" / "AGENTS.md").read_text(encoding="utf-8"),
            "reviewed local instructions\n",
        )

    def test_post_apply_scan_failure_rolls_back_collection(self) -> None:
        (self.codex / "AGENTS.md").write_text("reviewed local instructions\n", encoding="utf-8")
        collect_args = args_for(self.repo, self.codex, self.agents, direction="from-device")
        planned = quiet_plan(collect_args)
        self.assertFalse(planned.errors)
        clean = sync.Result(ok=["repository-safety-scan"])
        rejected = sync.Result(errors=["synthetic post-apply scan failure"])
        with mock.patch.object(sync, "scan_command", side_effect=[clean, rejected]):
            applied = sync.apply_command(collect_args)
        self.assertTrue(any("rolled back" in error for error in applied.errors))
        self.assertEqual(
            (self.repo / "portable" / "AGENTS.md").read_text(encoding="utf-8"),
            "portable instructions\n",
        )

    def test_from_device_plan_scans_write_content_before_writing_repo(self) -> None:
        candidate = "gh" + "p_" + "A" * 30
        (self.codex / "AGENTS.md").write_text(f"credential {candidate}\n", encoding="utf-8")
        collect_args = args_for(self.repo, self.codex, self.agents, direction="from-device")
        result = quiet_plan(collect_args)
        self.assertTrue(result.errors)
        self.assertTrue(any("token-like" in error.lower() for error in result.errors))
        self.assertEqual(
            (self.repo / "portable" / "AGENTS.md").read_text(encoding="utf-8"),
            "portable instructions\n",
        )
        self.assertFalse((self.repo / ".codex-sync" / "plan.json").exists())

    def test_from_device_plan_applies_public_audit_to_incoming_content(self) -> None:
        (self.codex / "AGENTS.md").write_text(
            "local path C:\\Users\\alice\\project\n", encoding="utf-8"
        )
        collect_args = args_for(
            self.repo,
            self.codex,
            self.agents,
            direction="from-device",
            public_audit=True,
        )
        result = quiet_plan(collect_args)
        self.assertTrue(
            any("user-specific absolute path" in error.lower() for error in result.errors)
        )
        self.assertEqual(
            (self.repo / "portable" / "AGENTS.md").read_text(encoding="utf-8"),
            "portable instructions\n",
        )
        self.assertFalse((self.repo / ".codex-sync" / "plan.json").exists())

    def test_apply_refuses_sensitive_repo_file_added_after_plan(self) -> None:
        planned = quiet_plan(self.args)
        self.assertFalse(planned.errors)
        (self.repo / "auth.json").write_text("{}\n", encoding="utf-8")
        applied = sync.apply_command(self.args)
        self.assertTrue(any("safety scan failed" in error.lower() for error in applied.errors))
        self.assertFalse((self.codex / "AGENTS.md").exists())

    def test_config_apply_preserves_local_only_settings(self) -> None:
        write_json(
            self.repo / "config" / "common.json",
            {"sections": {"": {"personality": "pragmatic"}}},
        )
        (self.codex / "config.toml").write_text(
            'model_reasoning_effort = "high"\n\n[desktop]\ncodeFontSize = 15\n',
            encoding="utf-8",
        )
        quiet_plan(self.args)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        rendered = (self.codex / "config.toml").read_text(encoding="utf-8")
        self.assertIn('personality = "pragmatic"', rendered)
        self.assertIn('model_reasoning_effort = "high"', rendered)
        self.assertIn("codeFontSize = 15", rendered)

    def test_existing_extra_skill_file_is_not_deleted(self) -> None:
        configured = manifest(skills={"common": ["owned"], "windows": [], "macos": []})
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        source = self.repo / "personal-skills" / "owned"
        source.mkdir()
        (source / "SKILL.md").write_text("owned skill\n", encoding="utf-8")
        target = self.codex / "skills" / "owned"
        target.mkdir(parents=True)
        (target / "local-note.txt").write_text("preserve me\n", encoding="utf-8")
        quiet_plan(self.args)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        self.assertTrue((target / "local-note.txt").exists())

    def test_platform_specific_skill_is_excluded_on_macos(self) -> None:
        configured = manifest(skills={"common": [], "windows": ["win-only"], "macos": []})
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        source = self.repo / "personal-skills" / "win-only"
        source.mkdir()
        (source / "SKILL.md").write_text("windows only\n", encoding="utf-8")
        mac_args = args_for(self.repo, self.codex, self.agents, platform="macos")
        quiet_plan(mac_args)
        applied = sync.apply_command(mac_args)
        self.assertFalse(applied.errors)
        self.assertFalse((self.codex / "skills" / "win-only").exists())

    def test_duplicate_skill_discovery_blocks_plan(self) -> None:
        configured = manifest(skills={"common": ["owned"], "windows": [], "macos": []})
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        source = self.repo / "personal-skills" / "owned"
        source.mkdir()
        (source / "SKILL.md").write_text("owned skill\n", encoding="utf-8")
        alternate = self.agents / "skills" / "owned"
        alternate.mkdir(parents=True)
        (alternate / "SKILL.md").write_text("collision\n", encoding="utf-8")
        result = quiet_plan(self.args)
        self.assertTrue(any("collision" in error.lower() for error in result.errors))

    def test_personal_skill_requires_skill_markdown(self) -> None:
        configured = manifest(skills={"common": ["owned"], "windows": [], "macos": []})
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        source = self.repo / "personal-skills" / "owned"
        source.mkdir()
        (source / "notes.md").write_text("not a skill marker\n", encoding="utf-8")
        result = quiet_plan(self.args)
        self.assertTrue(any("SKILL.md" in error for error in result.errors))

    def test_personal_skill_rejects_sensitive_file(self) -> None:
        configured = manifest(skills={"common": ["owned"], "windows": [], "macos": []})
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        source = self.repo / "personal-skills" / "owned"
        source.mkdir()
        (source / "SKILL.md").write_text("owned skill\n", encoding="utf-8")
        (source / ".env").write_text("placeholder\n", encoding="utf-8")
        result = quiet_plan(self.args)
        self.assertTrue(any("sensitive file" in error.lower() for error in result.errors))

    def test_doctor_reports_unsupported_config_value_without_traceback(self) -> None:
        write_json(
            self.repo / "config" / "common.json",
            {"sections": {"": {"personality": {"nested": "unsupported"}}}},
        )
        result = sync.doctor_command(self.args)
        self.assertTrue(any("Unsupported portable TOML value" in error for error in result.errors))


class ClaudeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.codex = self.root / ".codex"
        self.agents = self.root / ".agents"
        self.claude = self.root / ".claude"
        make_repo(self.repo)
        self.codex.mkdir()
        self.agents.mkdir()
        self.claude.mkdir()
        self.args = args_for(self.repo, self.codex, self.agents, claude_home=self.claude)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_claude_surfaces_apply_and_verify(self) -> None:
        write_json(
            self.repo / "manifests" / "portable-files.json",
            manifest(
                claude_skills={"common": ["notes"], "windows": [], "macos": []},
                claude_agents={"common": ["reviewer.md"], "windows": [], "macos": []},
            ),
        )
        (self.repo / "claude-agents" / "reviewer.md").write_text(
            "---\nname: reviewer\n---\nreview things\n", encoding="utf-8"
        )
        skill = self.repo / "claude-skills" / "notes"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: notes\n---\nkeep notes\n", encoding="utf-8")
        write_json(
            self.repo / "config" / "claude-common.json",
            {"values": {"includeCoAuthoredBy": False, "permissions.defaultMode": "plan"}},
        )
        (self.claude / "settings.json").write_text(
            json.dumps({"env": {"LOCAL_ONLY": "yes"}, "model": "opus"}, indent=2) + "\n",
            encoding="utf-8",
        )
        planned = quiet_plan(self.args)
        self.assertFalse(planned.errors)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        self.assertEqual(
            (self.claude / "CLAUDE.md").read_text(encoding="utf-8"),
            "portable claude instructions\n",
        )
        self.assertTrue((self.claude / "agents" / "reviewer.md").exists())
        self.assertTrue((self.claude / "skills" / "notes" / "SKILL.md").exists())
        settings = json.loads((self.claude / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["env"], {"LOCAL_ONLY": "yes"})
        self.assertEqual(settings["model"], "opus")
        self.assertIs(settings["includeCoAuthoredBy"], False)
        self.assertEqual(settings["permissions"]["defaultMode"], "plan")
        verified = sync.verify_command(self.args)
        self.assertFalse(verified.errors)

    def test_claude_settings_readback_from_device(self) -> None:
        write_json(
            self.repo / "config" / "claude-common.json",
            {"values": {"includeCoAuthoredBy": False, "permissions.defaultMode": "plan"}},
        )
        local_settings = {
            "includeCoAuthoredBy": True,
            "permissions": {"defaultMode": "acceptEdits"},
        }
        (self.claude / "settings.json").write_text(
            json.dumps(local_settings) + "\n", encoding="utf-8"
        )
        collect_args = args_for(
            self.repo,
            self.codex,
            self.agents,
            claude_home=self.claude,
            direction="from-device",
        )
        planned = quiet_plan(collect_args)
        self.assertFalse(planned.errors)
        applied = sync.apply_command(collect_args)
        self.assertFalse(applied.errors)
        payload = json.loads(
            (self.repo / "config" / "claude-common.json").read_text(encoding="utf-8")
        )
        self.assertIs(payload["values"]["includeCoAuthoredBy"], True)
        self.assertEqual(payload["values"]["permissions.defaultMode"], "acceptEdits")

    def test_local_only_claude_keys_are_rejected(self) -> None:
        for path_expression in (
            "env",
            "env.ANTHROPIC_MODEL",
            "apiKeyHelper",
            "hooks",
            "statusLine",
        ):
            with self.assertRaisesRegex(ValueError, "Local-only"):
                sync.validate_claude_settings_path(path_expression)

    def test_secret_like_claude_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Secret-like"):
            sync.validate_claude_settings_path("integrations.myApiKey")

    def test_claude_settings_path_crossing_scalar_fails(self) -> None:
        write_json(
            self.repo / "config" / "claude-common.json",
            {"values": {"permissions.defaultMode": "plan"}},
        )
        (self.claude / "settings.json").write_text(
            json.dumps({"permissions": "broken"}) + "\n", encoding="utf-8"
        )
        planned = quiet_plan(self.args)
        self.assertTrue(any("non-object" in error for error in planned.errors))

    def test_claude_agent_requires_md_extension(self) -> None:
        write_json(
            self.repo / "manifests" / "portable-files.json",
            manifest(claude_agents={"common": ["helper.txt"], "windows": [], "macos": []}),
        )
        with self.assertRaisesRegex(ValueError, r"\.md"):
            sync.load_manifest(self.repo)

    def test_reserved_claude_target_is_rejected(self) -> None:
        configured = manifest()
        configured["portable_files"][2]["target"] = "settings.json"
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        with self.assertRaisesRegex(ValueError, "reserved claude target"):
            sync.load_manifest(self.repo)

    def test_claude_credentials_filename_is_sensitive(self) -> None:
        self.assertEqual(
            sync.sensitive_path_reason(pathlib.PurePosixPath(".credentials.json")),
            "sensitive filename",
        )

    def test_claude_only_backup_lives_under_claude_home(self) -> None:
        configured = manifest()
        configured["portable_files"] = [configured["portable_files"][2]]
        write_json(self.repo / "manifests" / "portable-files.json", configured)
        planned = quiet_plan(self.args)
        self.assertFalse(planned.errors)
        applied = sync.apply_command(self.args)
        self.assertFalse(applied.errors)
        assert applied.backup_root
        self.assertTrue(
            str(applied.backup_root).startswith(str(self.claude)),
            f"backup landed outside the Claude home: {applied.backup_root}",
        )
        self.assertFalse((self.codex / "backups").exists())

    def test_missing_claude_profiles_are_optional(self) -> None:
        for filename in ("claude-common.json", "claude-windows.json", "claude-macos.json"):
            (self.repo / "config" / filename).unlink()
        doctor = sync.doctor_command(self.args)
        self.assertFalse(doctor.errors)
        planned = quiet_plan(self.args)
        self.assertFalse(planned.errors)


class ScannerTests(unittest.TestCase):
    def test_scanner_detects_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            candidate = "sk-" + "A" * 30
            (root / "bad.md").write_text(candidate, encoding="utf-8")
            arguments = args_for(root, root / ".codex", root / ".agents")
            result = sync.scan_command(arguments)
            self.assertTrue(result.errors)

    def test_scanner_allows_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "safe.md").write_text('token = "${SERVICE_TOKEN}"\n', encoding="utf-8")
            arguments = args_for(root, root / ".codex", root / ".agents")
            result = sync.scan_command(arguments)
            self.assertFalse(result.errors)

    def test_public_audit_detects_user_home_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            value = "C:" + "\\Users\\" + "alice\\private.txt"
            (root / "bad.md").write_text(value, encoding="utf-8")
            arguments = args_for(root, root / ".codex", root / ".agents", public_audit=True)
            result = sync.scan_command(arguments)
            self.assertTrue(any("absolute path" in error for error in result.errors))

    def test_scanner_rejects_private_key_file_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "id_ed25519").write_text("placeholder", encoding="utf-8")
            arguments = args_for(root, root / ".codex", root / ".agents")
            result = sync.scan_command(arguments)
            self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
