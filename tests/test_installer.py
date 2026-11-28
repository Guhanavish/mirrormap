"""Installer preview, managed repair, ownership and frozen-runtime contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror import installer, relay
from projectmirror.core import AuditError


class InstallerTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name)/"home"
        self.home.mkdir()
        self.repo=Path(tmp.name)/"project"
        self.repo.mkdir()
        h=patch.object(Path,"home",return_value=self.home)
        h.start()
        self.addCleanup(h.stop)
        import os
        env=patch.dict(os.environ,{"CODEX_HOME":str(self.home/".codex")})
        env.start()
        self.addCleanup(env.stop)
        probe=patch.object(installer,"_probe",return_value=True)
        probe.start()
        self.addCleanup(probe.stop)

    def test_preview_has_no_side_effects(self):
        p=installer.setup(self.repo,["codex"])
        self.assertFalse(p["applied"])
        self.assertFalse((self.home/".mirrormap").exists())
        self.assertFalse((self.home/".codex").exists())

    def test_install_repair_uninstall_and_retain_unrelated_data(self):
        cfg=relay._config_path("codex")
        cfg.parent.mkdir()
        cfg.write_text(json.dumps({"theme":"dark","hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"third-party"}]}]}}))
        result=installer.setup(self.repo,["codex"],apply=True,capture=True)
        self.assertTrue(result["applied"])
        self.assertTrue((self.home/".agents"/"skills"/"mirrormap"/"SKILL.md").is_file())
        original=json.loads(cfg.read_text())
        self.assertEqual(len(original["hooks"]["SessionStart"]),2)
        installer.setup(self.repo,["codex"],apply=True,action="repair")
        self.assertEqual(json.loads(cfg.read_text()),original)
        cfg.write_text(json.dumps({"theme":"dark","hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"third-party"}]}]}}))
        self.assertFalse(installer.diagnostics(self.repo)["managed_installations"][0]["hooks_present"])
        installer.setup(self.repo,[],apply=True,action="repair")
        self.assertTrue(installer.diagnostics(self.repo)["managed_installations"][0]["hooks_present"])
        installer.setup(self.repo,[],apply=True,action="uninstall")
        self.assertEqual(json.loads(cfg.read_text())["hooks"]["SessionStart"],[{"hooks":[{"type":"command","command":"third-party"}]}])
        self.assertTrue((self.home/".agents"/"skills"/"mirrormap"/"SKILL.md").is_file())

    def test_update_previous_engine_commands(self):
        installer.setup(self.repo,["claude"],apply=True)
        previous=json.loads((self.home/".mirrormap"/"installation.json").read_text())["entries"][0]
        with patch.object(installer,"_managed_engine",return_value=["/new/engine"]):
            result=installer.setup(self.repo,["claude"],apply=True,action="update")
        self.assertEqual(result["engine"],["/new/engine"])
        cfg=relay._config_path("claude").read_text()
        self.assertIn("/new/engine",cfg)
        self.assertNotIn(previous["commands"][0],cfg)
        self.assertEqual(len(json.loads(cfg)["hooks"]["SessionStart"]),1)

    def test_unmanaged_skill_is_not_overwritten(self):
        dest=installer._skill_dest("cursor")
        dest.mkdir(parents=True)
        (dest/"SKILL.md").write_text("my custom skill")
        result=installer.setup(self.repo,["cursor"],apply=True)
        self.assertEqual(result["results"][0]["skill"],"existing_unmanaged_or_modified")
        self.assertEqual((dest/"SKILL.md").read_text(),"my custom skill")

    def test_multi_project_hooks_preserved(self):
        other=self.repo.parent/"other"
        other.mkdir()
        installer.setup(self.repo,["codex"],apply=True)
        installer.setup(other,["codex"],apply=True)
        self.assertEqual(len(json.loads(relay._config_path("codex").read_text())["hooks"]["SessionStart"]),2)
        installer.setup(self.repo,["codex"],apply=True,action="uninstall")
        self.assertEqual(len(json.loads(relay._config_path("codex").read_text())["hooks"]["SessionStart"]),1)
        self.assertTrue(installer.diagnostics(other)["managed_installations"][0]["hooks_present"])

    def test_missing_engine_and_frozen_command(self):
        with patch.object(installer,"_probe",return_value=False):
            with self.assertRaises(AuditError):
                installer.setup(self.repo,["codex"],apply=True)
        self.assertFalse(relay._config_path("codex").exists())
        import sys
        with patch.object(sys,"frozen",True,create=True),patch.object(sys,"executable","/native/mirrormap"):
            self.assertEqual(relay.engine_command(),["/native/mirrormap"])
            command=relay.hook_configuration("codex",self.repo)["commands"][0]
            self.assertIn("/native/mirrormap",command)
            self.assertNotIn("-m projectmirror",command)

    def test_bad_configuration_and_manual_capture_rejected(self):
        cfg=relay._config_path("codex")
        cfg.parent.mkdir()
        cfg.write_text("invalid json")
        with self.assertRaises(ValueError):
            installer.setup(self.repo,["codex"],apply=True)
        self.assertEqual(cfg.read_text(),"invalid json")
        with self.assertRaises(AuditError):
            installer.setup(self.repo,["cursor"],mode="manual",capture=True)

    def test_lock_and_metadata_corruption(self):
        base=self.home/".mirrormap"
        base.mkdir()
        (base/"installation.lock").mkdir()
        with self.assertRaises(AuditError):
            installer.setup(self.repo,["codex"],apply=True)
        (base/"installation.lock").rmdir()
        (base/"installation.json").write_text("bad")
        self.assertTrue(installer.diagnostics()["metadata_error"])
        with self.assertRaises(ValueError):
            installer.setup(self.repo,["codex"],apply=True)


if __name__=="__main__":
    unittest.main()
