"""Synthetic persistent project-state and recovery tests; no real agent binary."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror import relay, relay_state as state
from projectmirror.core import AuditError


class StateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "music-player"
        self.repo.mkdir()
        self.env = patch.dict(os.environ, {"MIRRORMAP_RELAY_HOME": str(self.root / "private")})
        self.env.start()
        self.addCleanup(self.env.stop)
        for args in (("init",), ("config", "user.email", "test@example.com"), ("config", "user.name", "Test")):
            self.git(*args)
        (self.repo / "player.py").write_text("print('player')\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def start(self, agent="claude", native="one"):
        event = "sessionStart" if agent == "cursor" else "SessionStart"
        return relay.ingest_hook(agent, event, {"cwd": str(self.repo), "session_id": native},
                                 self.repo)["session_id"]

    def test_save_history_and_recovery_without_interruption(self):
        sid = self.start()
        state.save(sid, stage="implementation", goal="Independent audio", next_step="Split playback state")
        old = state.history(sid)["checkpoints"][-1]["checkpoint"]
        state.save(sid, stage="testing", next_step="Verify independent seek", done=["Split playback state"],
                   correction="Use independent timelines; supersedes linked seeking")
        previous = state.recover(sid, checkpoint=old)
        current = state.recover(sid)
        self.assertTrue(previous["historical"])
        self.assertFalse(previous["ready_for_review"])
        self.assertEqual(previous["task"]["next_step"], "Split playback state")
        self.assertEqual(current["task"]["next_step"], "Verify independent seek")
        self.assertEqual(current["task"]["stage"], "testing")
        self.assertTrue(current["ready_for_review"])
        self.assertFalse(current["execution_authorized"])
        self.assertEqual(current["task"]["corrections"][0]["value"],
                         "Use independent timelines; supersedes linked seeking")

    def test_automatic_opt_in_excerpts_and_privacy(self):
        sid = self.start()
        relay.ingest_hook("claude", "UserPromptSubmit", {"cwd": str(self.repo), "session_id": "one",
                          "prompt": "DO NOT STORE this raw prompt"}, self.repo)
        relay.ingest_hook("claude", "UserPromptSubmit", {"cwd": str(self.repo), "session_id": "one",
                          "prompt": "Preserve dark theme api_key=private-value"}, self.repo, capture_context=True)
        relay.ingest_hook("claude", "Stop", {"cwd": str(self.repo), "session_id": "one",
                          "last_assistant_message": "Next: verify device fallback"}, self.repo, capture_context=True)
        result = state.recover(sid)
        data = json.dumps(result)
        self.assertNotIn("DO NOT STORE", data)
        self.assertNotIn("private-value", data)
        self.assertIn("Preserve dark theme", data)
        self.assertIn("verify device fallback", data)
        self.assertFalse(result["capture_complete"])

    def test_cursor_response_workspace_roots_and_identity(self):
        p = {"workspace_roots": [str(self.repo)], "conversation_id": "cursor-thread"}
        sid = relay.ingest_hook("cursor", "sessionStart", p, self.repo)["session_id"]
        relay.ingest_hook("cursor", "afterAgentResponse", {**p, "text": "Saved mixer"},
                          self.repo, capture_context=True)
        self.assertIn("Saved mixer", json.dumps(state.recover(sid)))
        self.assertFalse(relay.ingest_hook("cursor", "afterAgentResponse",
                         {**p, "workspace_roots": [str(self.repo), str(self.root)]}, self.repo)["recorded"])

    def test_pending_and_uncorrelated_reconciliation(self):
        sid = self.start()
        state.save(sid, goal="Repair playback", next_step="Check audio")
        for payload in ({"tool_use_id": "one-tool"}, {}):
            relay.ingest_hook("claude", "PreToolUse",
                              {"cwd": str(self.repo), "session_id": "one", "tool_name": "Edit", **payload}, self.repo)
        self.assertFalse(state.recover(sid)["ready_for_review"])
        with self.assertRaises(AuditError):
            state.reconcile(sid, "Inspected", False)
        report = state.reconcile(sid, "Inspected file; unknown outcome", True)
        self.assertEqual(report["outcome"], "reviewed_unknown")
        self.assertEqual(relay.verify(sid)["unpaired_tool_starts"], 0)
        self.assertFalse(relay.verify(sid)["pending_tools"])
        self.assertTrue(state.recover(sid)["ready_for_review"])

    def test_adoption_keeps_captured_ancestor_context(self):
        sid = self.start()
        relay.ingest_hook("claude", "UserPromptSubmit", {"cwd": str(self.repo), "session_id": "one",
                          "prompt": "Preserve the master timeline"}, self.repo, capture_context=True)
        state.save(sid, stage="debugging", goal="Independent outputs", next_step="Fix device routing")
        new = self.start("codex", "two")
        relay.adopt_session(sid, new, source_stopped=True)
        result = state.recover(new)
        self.assertEqual(result["task"]["next_step"], "Fix device routing")
        self.assertEqual(result["task"]["stage"], "debugging")
        self.assertIn("Preserve the master timeline", json.dumps(result))
        self.assertIn(sid, result["ancestor_sessions"])
        with self.assertRaises(AuditError):
            state.save(sid, next_step="Wrong session")

    def test_export_import_no_authority_and_integrity(self):
        sid = self.start()
        state.save(sid, goal="Build player", next_step="Write tests")
        dest = self.root / "package.json"
        with self.assertRaises(AuditError):
            state.export_context(sid, dest)
        state.export_context(sid, dest, True)
        imported = state.import_context(dest)
        self.assertTrue(imported["integrity_valid"])
        self.assertFalse(imported["execution_authorized"])
        self.assertFalse(imported["ready_for_review"])
        with self.assertRaises(FileExistsError):
            state.export_context(sid, dest, True)
        payload = json.loads(dest.read_text())
        payload["payload"]["context"]["task"]["next_step"] = "forged"
        dest.write_text(json.dumps(payload))
        with self.assertRaises(AuditError):
            state.import_context(dest)

    def test_merge_is_reviewed_candidate_and_project_memory(self):
        source, target = self.start(), self.start("codex", "two")
        state.save(source, goal="Audio outputs", next_step="Inspect driver", decision=["Use device IDs"])
        state.save(target, goal="Timeline", next_step="Write seek tests")
        self.assertFalse(state.merge_context(source, target)["applied"])
        with self.assertRaises(AuditError):
            state.merge_context(source, target, apply=True)
        state.merge_context(source, target, apply=True, confirm_reviewed=True)
        out = state.recover(target)
        self.assertEqual(out["task"]["next_step"], "Write seek tests")
        self.assertIn("Use device IDs", json.dumps(out))
        self.assertEqual(len(state.project_memory(self.repo)["sessions"]), 2)

    def test_drift_blocks_ready_and_stage_is_suggested(self):
        sid = self.start()
        state.save(sid, next_step="Verify independent seek")
        out = state.recover(sid)
        self.assertEqual(out["task"]["stage"], "testing")
        self.assertEqual(out["task"]["stage_basis"], "keyword_suggestion")
        (self.repo / "player.py").write_text("changed")
        self.assertFalse(state.recover(sid)["ready_for_review"])

    def test_mode_change_and_temp_failure_recovery(self):
        config = self.root / "hooks.json"
        config.write_text('{"hooks":{}}')
        relay.modify_hooks("claude", self.repo, apply=True, config_path=config)
        relay.modify_hooks("claude", self.repo, apply=True, config_path=config, capture_context=True)
        hooks = json.loads(config.read_text())["hooks"]
        self.assertEqual(len(hooks["UserPromptSubmit"]), 1)
        self.assertIn("--capture-context", hooks["UserPromptSubmit"][0]["hooks"][0]["command"])
        original = config.read_text()
        with patch.object(relay.os, "replace", side_effect=OSError("simulated crash")):
            with self.assertRaises(OSError):
                relay.modify_hooks("claude", self.repo, apply=True, config_path=config)
        self.assertEqual(config.read_text(), original)
        self.assertEqual(list(self.root.glob("hooks.json.mirrormap-*.tmp")), [])

    def test_last_response_candidate_without_explicit_note(self):
        sid = self.start()
        relay.ingest_hook("claude", "Stop", {"cwd": str(self.repo), "session_id": "one",
                          "last_assistant_message": "A" * 1800 + "\nNext: Verify independent output routing"},
                          self.repo, capture_context=True)
        recovered = state.recover(sid)
        self.assertFalse(recovered["ready_for_review"])
        self.assertEqual(recovered["task"]["next_action_candidate"]["text"], "Verify independent output routing")
        self.assertEqual(recovered["task"]["stage"], "testing")
        self.assertEqual(relay.resume(sid)["project_state"]["task"]["next_action_candidate"]["text"],
                         "Verify independent output routing")
        self.assertFalse(relay.resume(sid)["execution_authorized"])

    def test_catalog_and_audit_link(self):
        from projectmirror.experience import audit_project
        sid = self.start()
        state.save(sid, stage="testing", next_step="Verify seek")
        listed = relay.list_sessions(self.repo)[0]
        self.assertEqual(listed["stage"], "testing")
        self.assertIsInstance(listed["latest_checkpoint"], int)
        out = self.root / "audit"
        audit_project(self.repo, out=out)
        linked = state.link_audit(sid, out)
        self.assertFalse(linked["execution_authorized"])
        recovered = state.recover(sid)
        self.assertEqual(recovered["audit_links"][-1]["value"]["digest"], linked["digest"])
        self.assertFalse(recovered["audit_links"][-1]["value"]["artifacts_rechecked_at_resume"])

    def test_cli_recover(self):
        sid = self.start()
        state.save(sid, goal="Player", next_step="Write tests")
        import sys
        result = subprocess.run([sys.executable, "-m", "projectmirror", "relay", "recover",
                                 "--session", sid, "--budget", "compact"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["task"]["next_step"], "Write tests")


if __name__ == "__main__":
    unittest.main()
