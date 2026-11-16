"""Two-agent handoff validation and host-output contract regression tests.

All input events in this suite are synthetic. Passing does not certify actual
Codex, Claude Code, or Cursor host compatibility.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror import relay
from projectmirror.core import AuditError


class RelayFieldCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "project"
        self.repo.mkdir()
        self.store = self.root / "relay-private"
        self.patch = patch.dict(os.environ, {"MIRRORMAP_RELAY_HOME": str(self.store)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        for args in [("init",), ("config", "user.name", "Test"),
                     ("config", "user.email", "test@example.invalid")]:
            subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (self.repo / "file.py").write_text("pass\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-m", "init"], check=True,
                       stdout=subprocess.DEVNULL)

    def start(self, agent, name):
        event = "sessionStart" if agent == "cursor" else "SessionStart"
        return relay.ingest_hook(agent, event, {"session_id": name,
                                                "cwd": str(self.repo)}, self.repo)["session_id"]

    def make_pair(self, notes=True, adopt=True):
        source = self.start("claude", "real-agent-a-placeholder")
        if notes:
            relay.record_note(source, goal="Implement harmless fixture",
                              next_step="Inspect diff and write smoke test",
                              done=["Wrote initial file"])
        target = self.start("codex", "real-agent-b-placeholder")
        if adopt:
            relay.adopt_session(source, target, source_stopped=True)
            relay.record_note(target, done=["Agent B reviewed the recovered task"]) 
        return source, target

    def test_good_recorded_handoff_passes_without_claiming_host_certification(self):
        a, b = self.make_pair()
        check = relay.field_check(a, b)
        self.assertTrue(check["passed"], check)
        self.assertTrue(all(check["checks"].values()))
        self.assertFalse(check["host_runtime_authenticated"])
        self.assertFalse(check["execution_authorized"])
        self.assertEqual(check["source_agent"], "claude")
        self.assertEqual(check["target_agent"], "codex")
        self.assertNotIn("Implement harmless fixture", json.dumps(check))

    def test_no_false_pass_when_handoff_not_adopted(self):
        a, b = self.make_pair(adopt=False)
        check = relay.field_check(a, b)
        self.assertFalse(check["passed"])
        self.assertFalse(check["checks"]["handoff_lineage"])

    def test_no_false_pass_when_source_lacks_semantic_milestone(self):
        a, b = self.make_pair(notes=False)
        check = relay.field_check(a, b)
        self.assertFalse(check["passed"])
        self.assertFalse(check["checks"]["source_milestone_recorded"])

    def test_no_false_pass_after_untracked_workspace_change(self):
        a, b = self.make_pair()
        (self.repo / "file.py").write_text("print('changed')\n", encoding="utf-8")
        check = relay.field_check(a, b)
        self.assertFalse(check["passed"])
        self.assertFalse(check["checks"]["current_workspace_matches"])

    def test_no_false_pass_with_wrong_ids(self):
        a, _ = self.make_pair()
        with self.assertRaises(AuditError):
            relay.field_check(a, a)

    def test_cli_failed_and_passing_exit_codes(self):
        a, b = self.make_pair(adopt=False)
        def command():
            return subprocess.run([sys.executable, "-m", "projectmirror", "relay",
                                   "field-check", "--source", a, "--target", b],
                                  cwd=Path(__file__).resolve().parents[1],
                                  env={**os.environ, "MIRRORMAP_RELAY_HOME": str(self.store)},
                                  capture_output=True, text=True)
        bad = command()
        self.assertEqual(bad.returncode, 1, bad.stderr)
        self.assertFalse(json.loads(bad.stdout)["passed"])
        relay.adopt_session(a, b, source_stopped=True)
        still_waiting = command()
        self.assertEqual(still_waiting.returncode, 1)
        self.assertFalse(json.loads(still_waiting.stdout)["checks"]["post_handoff_milestone_recorded"])
        relay.record_note(b, done=["Agent B inspected checkpoint"])
        good = command()
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)["passed"])

    def test_cursor_prompt_hook_cannot_inject_additional_context(self):
        self.start("cursor", "cursor-probe")
        base = [sys.executable, "-m", "projectmirror", "relay", "hook",
                "--agent", "cursor", "--event", "beforeSubmitPrompt",
                "--project", str(self.repo)]
        with patch.dict(os.environ, {"MIRRORMAP_RELAY_NATIVE_SESSION_ID": "cursor-probe"}):
            result = subprocess.run(base, input=json.dumps({"cwd": str(self.repo),
                                    "prompt": "a private request"}), text=True,
                                    capture_output=True,
                                    cwd=Path(__file__).resolve().parents[1],
                                    env=os.environ.copy())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertNotIn("a private request", (self.store / "sessions.sqlite3")
                         .read_bytes().decode("latin1"))
        self.assertEqual(relay.verify(relay.list_sessions()[0]["id"])["journal_integrity"], "valid")


if __name__ == "__main__":
    unittest.main()
