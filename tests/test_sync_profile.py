from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import sync_profile as sync
import publish_profile


class ProfileFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="profile-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for name in sync.SOURCE_DIRS:
            source = REPO / name
            if source.is_dir():
                shutil.copytree(source, self.repo/name, ignore=shutil.ignore_patterns("__pycache__"))
        # Tests never fetch third-party sources or operate on the real user's home.
        self.write_json("manifests/external-skills.json", {"codex_skill_installer": []})
        # Generic tests install every listed skill; catalog behaviour has its own tests.
        (self.repo/"manifests/skill-catalog.json").unlink()
        self.write_json("config/common.json", {"sections": {
            "": {"personality": "pragmatic", "model_context_window": 444000},
            "features": {"memories": True}, "memories": {"use_memories": True}}})
        profile=sync.read_json(self.repo/"manifests/profile.json")
        profile["claude_settings"]={"autoMemoryEnabled": True, "attribution": {"commit": "", "pr": "", "sessionUrl": False}}
        self.write_json("manifests/profile.json", profile)
        # A Windows-only skill and a Windows-only Codex agent exercise the platform boundaries.
        win=self.repo/"personal-skills/win-only"; win.mkdir(parents=True)
        (win/"SKILL.md").write_text("---\nname: win-only\ndescription: test\n---\n")
        (self.repo/"agents").mkdir(exist_ok=True); (self.repo/"agents/example.toml").write_text('name = "example"\n')
        manifest=sync.read_json(self.repo/"manifests/portable-files.json")
        manifest["personal_skills"]["windows"]=["win-only"]; manifest["agents"]["windows"]=["example.toml"]
        self.write_json("manifests/portable-files.json", manifest)
        subprocess.run(["git", "init", "-q", str(self.repo)],check=True)
        subprocess.run(["git","-C",str(self.repo),"-c","user.name=Test","-c","user.email=test@example.invalid",
                        "commit","--allow-empty","-qm","fixture"],check=True)
        self.args = argparse.Namespace(repo_root=self.repo, codex_home=self.root/"codex", claude_home=self.root/"claude",
                                       agents_home=self.root/"agents", state_dir=self.root/"state", platform="macos",
                                       apps=["codex","claude"])
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None,None,None)

    def write_json(self, name, data):
        path=self.repo/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data))

    def install(self):
        review=sync.plan(self.args)
        sync.apply_review(self.args,review,{},safe=True)
        return review

    def by_id(self, review, uid):
        return next(u for u in review["items"] if u["id"]==uid)


class SyncTests(ProfileFixture):
    def test_first_install_both_apps_and_idempotence(self):
        self.install()
        codex=self.args.codex_home; claude=self.args.claude_home
        self.assertEqual((codex/"AGENTS.md").read_text(encoding="utf-8"),(claude/"CLAUDE.md").read_text(encoding="utf-8"))
        self.assertTrue((claude/"skills/haiku-writer/SKILL.md").is_file())
        self.assertFalse((claude/"skills/context-watchdog").exists())
        self.assertTrue(tomllib.loads((codex/"config.toml").read_text(encoding="utf-8"))["memories"]["use_memories"])
        settings=json.loads((claude/"settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["attribution"],{"commit":"","pr":"","sessionUrl":False})
        again=sync.plan(self.args)
        self.assertTrue(all(u["status"]=="same" for u in again["items"]))
        result=sync.apply_review(self.args,again,{},safe=True)
        self.assertEqual(result["entries"],[])

    def test_windows_app_and_os_boundaries(self):
        self.args.platform="windows"
        self.install()
        self.assertTrue((self.args.codex_home/"skills/win-only/SKILL.md").exists())
        self.assertTrue((self.args.claude_home/"skills/win-only/SKILL.md").exists())
        self.assertTrue((self.args.codex_home/"agents/example.toml").exists())
        self.assertFalse((self.args.claude_home/"skills/context-watchdog").exists())

    def test_first_install_conflict_requires_choice_without_writes(self):
        self.args.codex_home.mkdir()
        path=self.args.codex_home/"AGENTS.md"; path.write_text("my rules")
        review=sync.plan(self.args)
        with self.assertRaisesRegex(ValueError,"Нужен выбор"):
            sync.apply_review(self.args,review,{},safe=True)
        self.assertEqual(path.read_text(encoding="utf-8"),"my rules")
        self.assertFalse((self.args.claude_home/"CLAUDE.md").exists())

    def test_keep_local_is_remembered_and_reasked_only_on_change(self):
        self.install()
        local=self.args.codex_home/"AGENTS.md"; local.write_text("local preference")
        review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"codex:instructions")["status"],"local")
        sync.apply_review(self.args,review,{"codex:instructions":"keep"},safe=True)
        self.assertEqual(self.by_id(sync.plan(self.args),"codex:instructions")["status"],"kept")
        source=self.repo/"portable/AGENTS.md"; source.write_text(source.read_text(encoding="utf-8")+"\nnew upstream rule\n",encoding="utf-8")
        review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"codex:instructions")["status"],"conflict")
        with self.assertRaisesRegex(ValueError,"Нужен выбор для codex:instructions"):
            sync.apply_review(self.args,review,{},safe=True)
        self.assertEqual(local.read_text(encoding="utf-8"),"local preference")

    def test_merged_document_survives_upstream_update(self):
        review=sync.plan(self.args)
        sync.apply_review(self.args,review,{"codex:instructions":{"action":"merge","text":"shared + device rules\n"}},safe=True)
        source=self.repo/"portable/AGENTS.md"; source.write_text(source.read_text(encoding="utf-8")+"\nnew upstream rule\n",encoding="utf-8")
        review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"codex:instructions")["status"],"conflict")
        with self.assertRaisesRegex(ValueError,"Нужен выбор"):
            sync.apply_review(self.args,review,{},safe=True)
        self.assertEqual((self.args.codex_home/"AGENTS.md").read_text(encoding="utf-8"),"shared + device rules\n")

    def test_skipped_and_removed_items_stay_absent_after_upstream_update(self):
        review=sync.plan(self.args)
        sync.apply_review(self.args,review,{"claude:skill:haiku-writer":"skip"},safe=True)
        sync.apply_review(self.args,sync.plan(self.args),{"codex:skill:haiku-writer":"remove"},safe=True)
        skill=self.repo/"personal-skills/haiku-writer/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8")+"\nupdated upstream\n",encoding="utf-8")
        review=sync.plan(self.args)
        for uid in ("claude:skill:haiku-writer","codex:skill:haiku-writer"):
            self.assertEqual(self.by_id(review,uid)["status"],"skipped")
        sync.apply_review(self.args,review,{},safe=True)
        self.assertFalse((self.args.claude_home/"skills/haiku-writer/SKILL.md").exists())
        self.assertFalse((self.args.codex_home/"skills/haiku-writer/SKILL.md").exists())

    def test_both_changed_is_conflict(self):
        self.install()
        (self.args.codex_home/"AGENTS.md").write_text("local change")
        source=self.repo/"portable/AGENTS.md"; source.write_text(source.read_text(encoding="utf-8")+"\nremote change",encoding="utf-8")
        self.assertEqual(self.by_id(sync.plan(self.args),"codex:instructions")["status"],"conflict")

    def test_preserve_secret_and_local_settings(self):
        self.args.codex_home.mkdir(); self.args.claude_home.mkdir()
        (self.args.codex_home/"config.toml").write_text('model_reasoning_effort="high"\n[local]\ncredential="private-local-value"\n')
        (self.args.claude_home/"settings.json").write_text(json.dumps({"model":"my-choice","env":{"PRIVATE":"local-value"}}))
        self.install()
        codex=tomllib.loads((self.args.codex_home/"config.toml").read_text(encoding="utf-8"))
        claude=json.loads((self.args.claude_home/"settings.json").read_text(encoding="utf-8"))
        self.assertEqual(codex["local"]["credential"],"private-local-value")
        self.assertEqual(codex["model_reasoning_effort"],"high")
        self.assertEqual(claude["env"]["PRIVATE"],"local-value")
        review=json.dumps(sync.plan(self.args))
        self.assertNotIn("private-local-value",review)
        self.assertNotIn("local-value",review)

    def test_stale_local_plan_is_rejected(self):
        self.install(); review=sync.plan(self.args)
        (self.args.codex_home/"AGENTS.md").write_text("edited later")
        with self.assertRaisesRegex(ValueError,"изменились после обзора"):
            sync.apply_review(self.args,review,{},safe=True)

    def test_stale_source_plan_is_rejected(self):
        review=sync.plan(self.args)
        (self.repo/"portable/AGENTS.md").write_text("new source")
        with self.assertRaisesRegex(ValueError,"Источник изменился"):
            sync.apply_review(self.args,review,{},safe=True)

    def test_tampered_plan_cannot_escape_managed_paths(self):
        review=sync.plan(self.args)
        review["items"][0]["path"]="../victim"
        with self.assertRaises(ValueError): sync.apply_review(self.args,review,{},safe=True)
        self.assertFalse((self.root/"victim").exists())

    def test_symlinks_inside_skill_and_roots_block(self):
        target=self.root/"outside"; target.write_text("outside")
        skill=self.repo/"personal-skills/haiku-writer"
        try:
            (skill/"linked.txt").symlink_to(target)
        except OSError:
            self.skipTest("This Windows account cannot create symlinks")
        with self.assertRaisesRegex(ValueError,"Ссылка"): sync.plan(self.args)

    def test_installed_skill_root_must_not_be_a_link(self):
        project=self.root/"project-skill"; project.mkdir(); (project/"SKILL.md").write_text("project copy")
        link=self.args.codex_home/"skills/haiku-writer"; link.parent.mkdir(parents=True)
        try:
            link.symlink_to(project,target_is_directory=True)
        except OSError:
            self.skipTest("This Windows account cannot create symlinks")
        with self.assertRaisesRegex(ValueError,"Ссылка"): sync.plan(self.args)
        self.assertEqual((project/"SKILL.md").read_text(),"project copy")

    def test_install_preserves_device_only_config(self):
        self.args.codex_home.mkdir()
        path=self.args.codex_home/"config.toml"
        path.write_text('model_reasoning_effort = "high"\n\n[desktop]\nsansFontSize = 14\n\n[features]\nmulti_agent = false\n\n'
                        '[agents]\nenabled = false\n\n[plugins."mac-local@example"]\nenabled = true\n',encoding="utf-8")
        self.install()
        doc=tomllib.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["model_reasoning_effort"],"high")
        self.assertEqual(doc["desktop"]["sansFontSize"],14)
        self.assertFalse(doc["features"]["multi_agent"])
        self.assertFalse(doc["agents"]["enabled"])
        self.assertTrue(doc["plugins"]["mac-local@example"]["enabled"])

    def test_collision_in_other_codex_discovery_root_blocks(self):
        path=self.args.agents_home/"skills/haiku-writer/SKILL.md"
        path.parent.mkdir(parents=True); path.write_text("competing")
        with self.assertRaisesRegex(ValueError,"Дублирующий"): sync.plan(self.args)

    def test_remove_skill_and_rollback(self):
        self.install()
        review=sync.plan(self.args)
        sync.apply_review(self.args,review,{"codex:skill:haiku-writer":"remove"},safe=True)
        target=self.args.codex_home/"skills/haiku-writer/SKILL.md"
        self.assertFalse(target.exists())
        self.assertEqual(self.by_id(sync.plan(self.args),"codex:skill:haiku-writer")["status"],"skipped")
        sync.rollback(self.args,review["id"])
        self.assertTrue(target.exists())

    def test_upstream_removal_is_explicit_and_resolved_once(self):
        self.install()
        path=self.repo/"manifests/portable-files.json"; m=json.loads(path.read_text(encoding="utf-8"))
        m["personal_skills"]["common"].remove("haiku-writer"); path.write_text(json.dumps(m))
        review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"codex:skill:haiku-writer")["status"],"removed")
        with self.assertRaisesRegex(ValueError,"Нужен выбор"): sync.apply_review(self.args,review,{},safe=True)
        sync.apply_review(self.args,review,{"codex:skill:haiku-writer":"remove","claude:skill:haiku-writer":"keep"},safe=True)
        again=sync.plan(self.args)
        self.assertFalse(any(u["id"].endswith(":skill:haiku-writer") for u in again["items"]))
        self.assertFalse((self.args.codex_home/"skills/haiku-writer/SKILL.md").exists())
        self.assertIn("haiku-writer",again["inventory"]["claude"]["local_skills"])
        self.assertTrue(all(u["status"]=="same" for u in again["items"]))

    def test_untracked_local_skills_survive(self):
        path=self.args.codex_home/"skills/my-local-skill/SKILL.md"
        path.parent.mkdir(parents=True); path.write_text("mine")
        self.install(); self.assertEqual(path.read_text(encoding="utf-8"),"mine")

    def test_removed_file_in_selected_skill_is_removed(self):
        self.install()
        source=self.repo/"personal-skills/haiku-writer/old.txt"; source.write_text("old")
        self.install(); source.unlink()
        self.install()
        self.assertFalse((self.args.codex_home/"skills/haiku-writer/old.txt").exists())

    def test_failure_rolls_back_every_completed_write(self):
        review=sync.plan(self.args)
        original=sync.write_entry; calls=0
        def fail_second(path,value):
            nonlocal calls
            calls+=1
            if calls==2: raise OSError("simulated disk error")
            return original(path,value)
        with mock.patch.object(sync,"write_entry",side_effect=fail_second):
            with self.assertRaises(OSError): sync.apply_review(self.args,review,{},safe=True)
        self.assertFalse((self.args.codex_home/"AGENTS.md").exists())
        self.assertEqual(sync.state_for(self.args)["items"],{})

    def test_rollback_refuses_later_user_edits(self):
        review=self.install()
        (self.args.codex_home/"AGENTS.md").write_text("later")
        with self.assertRaisesRegex(ValueError,"файл изменён"): sync.rollback(self.args,review["id"])

    def test_invalid_configuration_fails_before_any_install(self):
        self.args.claude_home.mkdir()
        (self.args.claude_home/"settings.json").write_text("not json")
        with self.assertRaises(ValueError): sync.plan(self.args)
        self.assertFalse((self.args.codex_home/"AGENTS.md").exists())

    def test_merge_exact_reviewed_document(self):
        review=sync.plan(self.args)
        sync.apply_review(self.args,review,{"codex:instructions":{"action":"merge","text":"approved combined rules\n"}},safe=True)
        self.assertEqual((self.args.codex_home/"AGENTS.md").read_text(encoding="utf-8"),"approved combined rules\n")
        self.assertEqual(self.by_id(sync.plan(self.args),"codex:instructions")["status"],"kept")

    def test_optional_skips_and_provenance_validation(self):
        spec={"name":"sample","repo":"example/skills","path":"skills/sample","ref":"a"*40}
        self.write_json("manifests/external-skills.json",{"codex_skill_installer":[spec]})
        profile=sync.read_json(self.repo/"manifests/profile.json"); profile["optional_skills"].append("sample")
        self.write_json("manifests/profile.json",profile)
        self.install()
        self.assertEqual(self.by_id(sync.plan(self.args),"codex:external:sample")["status"],"optional")
        folder=self.args.state_dir/"sources"/spec["ref"]/'sample'; folder.mkdir(parents=True)
        (folder/"SKILL.md").write_text("sample")
        proof={"repo":spec["repo"],"ref":spec["ref"],"path":spec["path"],"content":sync.content_hash(sync.tree(folder))}
        sync.save_json(folder/".portable-source.json",proof)
        self.assertIsNotNone(sync.external_tree(self.args,spec))
        (folder/"SKILL.md").write_text("tampered")
        with self.assertRaisesRegex(ValueError,"Повреждён"): sync.external_tree(self.args,spec)

    def test_review_explains_line_endings_agents_and_app_folders(self):
        self.args.platform="windows"
        self.install()
        skill=self.args.codex_home/"skills/haiku-writer/SKILL.md"
        skill.write_bytes(skill.read_bytes().replace(b"\n",b"\r\n"))
        synced=self.args.claude_home/"skills/synced/account-bucket/docx"
        synced.mkdir(parents=True); (synced/"SKILL.md").write_text("app-managed")
        review=sync.plan(self.args)
        self.assertIn("только переносы строк",self.by_id(review,"codex:skill:haiku-writer")["summary"])
        self.assertNotIn("synced",review["inventory"]["claude"]["local_skills"])
        self.assertEqual(self.by_id(review,"claude:config:autoMemoryEnabled")["label"],"Автопамять Claude")
        output=io.StringIO()
        with contextlib.redirect_stdout(output): sync.display(review)
        self.assertIn("example.toml",output.getvalue())

    def test_root_level_source_keeps_only_listed_files(self):
        spec={"name":"frames","repo":"example/frames","path":".","include":["SKILL.md","scripts"],"ref":"b"*40}
        files={name:sync.encoded(name) for name in ("SKILL.md","README.md","scripts/run.py","scriptsX/other.py",".github/FUNDING.yml")}
        self.assertEqual(set(sync.selected(files,spec)),{"SKILL.md","scripts/run.py"})
        folder=self.args.state_dir/"sources"/spec["ref"]/"frames"; folder.mkdir(parents=True)
        (folder/"SKILL.md").write_text("frames")
        sync.save_json(folder/".portable-source.json",{**sync.source_identity(spec),"content":sync.content_hash(sync.tree(folder))})
        self.assertIn("SKILL.md",sync.external_tree(self.args,spec))
        with self.assertRaisesRegex(ValueError,"Повреждён"): sync.external_tree(self.args,{**spec,"include":["SKILL.md"]})
        with self.assertRaises(ValueError): sync.external_tree(self.args,{**spec,"path":"../outside"})

    def test_facts_count_does_not_include_boundaries(self):
        doc=sync.encoded("# Memory\n\nIntro\n\n## Пользователь\n- A\n- B\n\n## Граница синхронизации\n- not a fact\n")
        self.assertEqual(sync.facts(doc),{"A","B"})

    def test_publish_never_collects_and_requires_explicit_paths(self):
        with mock.patch.object(sync,"validate_origin"):
            with self.assertRaisesRegex(ValueError,"согласованные файлы"):
                publish_profile.publish(self.repo,"test",[])

    def test_cli_first_run_and_repeat_are_automatic(self):
        flags=["--repo-root",str(self.repo),"--codex-home",str(self.args.codex_home),
               "--claude-home",str(self.args.claude_home),"--agents-home",str(self.args.agents_home),
               "--state-dir",str(self.args.state_dir),"--platform","macos","--working-tree"]
        for attempt in range(2):
            result=subprocess.run([sys.executable,str(REPO/"scripts/sync_profile.py"),"bootstrap",*flags],
                                  text=True,encoding="utf-8",capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("Профиль установлен",result.stdout)
        self.assertTrue((self.args.claude_home/"portable-repo-path").is_file())

    def test_selected_config_removal_preserves_other_keys(self):
        self.install(); review=sync.plan(self.args)
        sync.apply_review(self.args,review,{"codex:config:personality":"remove"},safe=True)
        config=tomllib.loads((self.args.codex_home/"config.toml").read_text(encoding="utf-8"))
        self.assertNotIn("personality",config)
        self.assertEqual(config["model_context_window"],444000)
        self.assertEqual(self.by_id(sync.plan(self.args),"codex:config:personality")["status"],"skipped")

    def test_crash_recovery_restores_prepared_transaction(self):
        review=self.install()
        path=self.args.state_dir/"transactions"/review["id"]/'journal.json'
        journal=sync.read_json(path); journal['status']='prepared'; sync.save_json(path,journal)
        with self.assertRaisesRegex(ValueError,"незавершённая"):
            sync.apply_review(self.args,sync.plan(self.args),{},safe=True)
        sync.rollback(self.args,review['id'])
        self.assertFalse((self.args.codex_home/'AGENTS.md').exists())

    def test_publisher_blocks_incoming_before_staging(self):
        calls=[]
        def fake_git(repo,*args):
            calls.append(args)
            return '1' if args[0]=='rev-list' else ''
        with mock.patch.object(sync,'validate_origin'),mock.patch.object(sync,'git',side_effect=fake_git):
            with self.assertRaisesRegex(ValueError,'появились изменения'):
                publish_profile.publish(self.repo,'test',['codex/AGENTS.md'])
        self.assertFalse(any(c[0] in ('add','commit','push') for c in calls))

    def test_unknown_decision_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Неизвестные пункты'):
            sync.apply_review(self.args,sync.plan(self.args),{'typo':'accept'},safe=True)

    def test_multiline_desktop_instructions_can_be_replaced(self):
        self.args.codex_home.mkdir()
        path=self.args.codex_home/'config.toml'
        path.write_text('[desktop]\ngit-commit-instructions = """first\nsecond\nthird"""\nlocal_choice="preserved"\n')
        review=sync.plan(self.args)
        sync.apply_review(self.args,review,{'codex:config:desktop.git-commit-instructions':'accept'},safe=True)
        doc=tomllib.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc['desktop']['local_choice'],'preserved')
        self.assertNotIn('second',doc['desktop']['git-commit-instructions'])

    def test_preview_reads_utf8_even_when_windows_default_is_cp1251(self):
        (self.repo/"portable/AGENTS.md").write_text("# Общение и контекст\n", encoding="utf-8")
        original=Path.read_text
        def windows_default(path,encoding=None,errors=None,**kwargs):
            return original(path,encoding=encoding or 'cp1251',errors=errors,**kwargs)
        with mock.patch.object(Path,'read_text',new=windows_default):
            review=sync.plan(self.args)
        text=sync.unpack(self.by_id(review,'codex:instructions')['desired']).decode()
        self.assertIn('Общение и контекст',text)


class CatalogTests(ProfileFixture):
    def setUp(self):
        super().setUp()
        entries=[{"name":"haiku-writer","group":"media","recommended":True,"ru":"Хокку","en":"Haiku"},
                 {"name":"velosiped","group":"work","recommended":False,"ru":"Готовые решения","en":"Reuse"}]
        self.write_json("manifests/skill-catalog.json",{"schema":1,"skills":entries})

    def test_catalog_skills_install_only_when_chosen(self):
        self.args.selected={"haiku-writer"}
        self.install()
        self.assertTrue((self.args.claude_home/"skills/haiku-writer/SKILL.md").is_file())
        self.assertFalse((self.args.claude_home/"skills/velosiped").exists())
        self.assertTrue((self.args.claude_home/"skills/fact-check-post/SKILL.md").is_file())
        review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"claude:skill:velosiped")["status"],"optional")
        self.assertEqual(sync.state_for(self.args)["selected_skills"],["haiku-writer"])

    def test_explicit_request_overrides_an_earlier_removal(self):
        self.args.selected={"haiku-writer"}; self.install()
        sync.apply_review(self.args,sync.plan(self.args),{"codex:skill:haiku-writer":"remove"},safe=True)
        self.assertNotIn("haiku-writer",sync.state_for(self.args)["selected_skills"])
        self.args.selected=set(); review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"codex:skill:haiku-writer")["status"],"skipped")
        self.args.selected={"haiku-writer"}; self.args.requested={"haiku-writer"}
        review=sync.plan(self.args)
        self.assertEqual(self.by_id(review,"codex:skill:haiku-writer")["status"],"new")
        sync.apply_review(self.args,review,{})
        self.assertTrue((self.args.codex_home/"skills/haiku-writer/SKILL.md").is_file())

    def test_selection_parsing(self):
        catalog=sync.load_catalog(self.repo)
        self.assertEqual(sync.parse_selection(catalog,""),{"haiku-writer"})
        self.assertEqual(sync.parse_selection(catalog,"all"),{"haiku-writer","velosiped"})
        self.assertEqual(sync.parse_selection(catalog,"none"),set())
        self.assertEqual(sync.parse_selection(catalog,"2, haiku-writer"),{"haiku-writer","velosiped"})
        with self.assertRaisesRegex(ValueError,"Нет такого skill"): sync.parse_selection(catalog,"7")

    def test_catalog_lists_every_entry(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output): sync.show_catalog(self.args,sync.load_catalog(self.repo))
        self.assertIn("1 ★ haiku-writer — Хокку",output.getvalue())
        self.assertIn("velosiped — Готовые решения",output.getvalue())


class SafetyTests(ProfileFixture):
    def test_local_only_claude_setting_is_refused(self):
        profile=sync.read_json(self.repo/"manifests/profile.json")
        profile["claude_settings"]["hooks"]={"Stop":[]}
        self.write_json("manifests/profile.json",profile)
        with self.assertRaisesRegex(ValueError,"Local-only Claude setting"): sync.plan(self.args)

    def test_local_only_codex_key_is_refused(self):
        self.write_json("config/common.json",{"sections":{"":{"model":"any-model"}}})
        with self.assertRaisesRegex(ValueError,"Local-only config key"): sync.plan(self.args)

    def other_repository(self, keep_history=False):
        other=self.root/"other"
        shutil.copytree(self.repo,other,ignore=None if keep_history else shutil.ignore_patterns(".git"))
        if not keep_history:
            subprocess.run(["git","init","-q",str(other)],check=True)
            subprocess.run(["git","-C",str(other),"-c","user.name=Test","-c","user.email=test@example.invalid",
                            "commit","--allow-empty","-qm","other"],check=True)
        (other/"portable/AGENTS.md").write_text("template example\n",encoding="utf-8")
        return other

    def test_install_from_another_repository_is_refused(self):
        self.install()
        personal=(self.args.codex_home/"AGENTS.md").read_text(encoding="utf-8")
        self.args.repo_root=self.other_repository()
        with self.assertRaisesRegex(ValueError,"установлен из"): sync.plan(self.args)
        self.assertEqual((self.args.codex_home/"AGENTS.md").read_text(encoding="utf-8"),personal)
        self.args.switch_repository=True
        sync.apply_review(self.args,sync.plan(self.args),{},safe=True)
        self.assertEqual(sync.state_for(self.args)["repository"],sync.repository_identity(self.args.repo_root))
        self.assertEqual((self.args.codex_home/"AGENTS.md").read_text(encoding="utf-8").splitlines()[0],"template example")

    def test_profile_without_recorded_repository_uses_clone_path(self):
        self.install()
        state=sync.state_for(self.args); state.pop("repository"); sync.save_json(sync.state_path(self.args),state)
        sync.plan(self.args)
        self.args.repo_root=self.other_repository(keep_history=True)
        with self.assertRaisesRegex(ValueError,"клона"): sync.plan(self.args)

    def test_repository_slug_is_configurable(self):
        profile=sync.read_json(self.repo/"manifests/profile.json")
        profile["repository"]=""; self.write_json("manifests/profile.json",profile)
        sync.validate_origin(self.repo)  # an empty value disables the origin check
        profile["repository"]="not a slug"; self.write_json("manifests/profile.json",profile)
        with self.assertRaisesRegex(ValueError,"repository"): sync.validate_origin(self.repo)

if __name__=="__main__": unittest.main()
