"""Synthetic efficiency tests; no hosted model calls or billing measurements."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror import relay, relay_efficiency as efficiency, relay_state as state
from projectmirror.core import AuditError


class EfficiencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        env = patch.dict(os.environ, {"MIRRORMAP_RELAY_HOME": str(self.root / "private")})
        env.start()
        self.addCleanup(env.stop)
        for args in (("init",), ("config", "user.email", "test@example.com"), ("config", "user.name", "Test")):
            self.git(*args)
        (self.repo / "player.py").write_text("print('fixture')\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def event(self, name, mode="eco", capture=False, **payload):
        return relay.ingest_hook("claude", name, {"cwd": str(self.repo), "session_id": "one", **payload},
                                 self.repo, capture_context=capture, mode=mode)

    def start(self, mode="eco"):
        return self.event("SessionStart", mode=mode)["session_id"]

    def test_delta_history_roundtrip_and_periodic_anchors(self):
        sid = self.start()
        state.save(sid, goal="Independent audio", next_step="Fix output selection")
        first = state.history(sid)["checkpoints"][-1]["checkpoint"]
        for _ in range(20):
            self.event("UserPromptSubmit")
        state.save(sid, next_step="Verify output")
        self.assertEqual(state.recover(sid, first)["task"]["next_step"], "Fix output selection")
        self.assertEqual(state.recover(sid)["task"]["next_step"], "Verify output")
        self.assertEqual(relay.verify(sid)["journal_integrity"], "valid")
        report = efficiency.usage(sid)
        self.assertGreater(report["checkpoint_deltas"], 10)
        self.assertGreater(report["local_storage_bytes_avoided"], 0)
        self.assertIsNone(report["actual_tokens_saved"])

    def test_delta_tamper_blocks_recovery(self):
        sid = self.start()
        conn = relay._connect()
        try:
            with conn:
                row = conn.execute("SELECT seq,detail FROM events WHERE session_id=? ORDER BY seq DESC LIMIT 1", (sid,)).fetchone()
                detail = json.loads(row["detail"])
                detail["checkpoint_patch"]["changes"]["next_step"] = "malicious"
                conn.execute("UPDATE events SET detail=? WHERE seq=?", (json.dumps(detail), row["seq"]))
        finally:
            conn.close()
        self.assertEqual(relay.verify(sid)["journal_integrity"], "invalid")
        with self.assertRaises(AuditError):
            state.recover(sid)

    def test_adaptive_reminders_are_not_repeated_per_prompt(self):
        sid = self.start()
        with patch.object(efficiency.time, "time", return_value=10000):
            self.assertIn("relay note", efficiency.reminder(sid, "eco"))
            for _ in range(10):
                self.event("UserPromptSubmit")
                self.assertIsNone(efficiency.reminder(sid, "eco"))
            for i in range(5):
                self.event("PostToolUse", tool_use_id=str(i))
        with patch.object(efficiency.time, "time", return_value=10100):
            self.assertIsNone(efficiency.reminder(sid, "eco"))
            self.assertIn("relay note", efficiency.reminder(sid, "detailed"))
            self.assertIsNone(efficiency.reminder(sid, "manual"))
        self.assertEqual(efficiency.usage(sid)["reminders_prepared"], 2)

    def test_deduplication_and_relevant_budget(self):
        sid = self.start()
        state.save(sid, goal="Player", next_step="Verify independent seek",
                   done=["Build mixer", "Build mixer"], decision=["Use device IDs", "Use device IDs"],
                   blocker=["Do not overwrite existing files"])
        self.event("UserPromptSubmit", capture=True, prompt="Preserve seek controls")
        self.event("UserPromptSubmit", capture=True, prompt="Preserve seek controls")
        self.event("Stop", capture=True, last_assistant_message="Next: Verify seek")
        out = state.recover(sid, query="seek", max_tokens=2000)
        self.assertIn("Do not overwrite existing files", out["task"]["blockers"])
        self.assertNotIn("Use device IDs", out["decisions"])
        self.assertEqual(out["task"]["next_step"], "Verify independent seek")
        self.assertEqual(efficiency.usage(sid)["duplicate_excerpts_suppressed"], 1)
        self.assertLessEqual(len(relay._canonical(out).encode("utf-8")), 8000)
        tiny = state.recover(sid, max_tokens=128)
        self.assertTrue(tiny["budget"]["mandatory_context_exceeds_budget"])
        self.assertIn("Do not overwrite existing files", tiny["task"]["blockers"])

    def test_progressive_context_is_checkpoint_bound(self):
        sid = self.start()
        state.save(sid, next_step="Build output", decision=["Seek separate audio", "Seek slider design"])
        page = state.context_page(sid, query="seek", limit=1)
        self.assertEqual(page["total_matches"], 2)
        self.assertEqual(page["next_offset"], 1)
        state.save(sid, decision=["Seek later change"])
        other = state.context_page(sid, checkpoint=page["checkpoint"], query="seek", offset=1, limit=1)
        self.assertEqual(other["total_matches"], 2)
        self.assertNotEqual(other["items"], page["items"])
        self.assertFalse(other["execution_authorized"])

    def test_manual_and_mode_switch_preserve_third_party_hooks(self):
        config = self.root / "hooks.json"
        config.write_text('{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"third-party"}]}]}}')
        relay.modify_hooks("claude", self.repo, apply=True, config_path=config, mode="balanced")
        relay.modify_hooks("claude", self.repo, apply=True, config_path=config, mode="manual")
        hooks = json.loads(config.read_text())["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "Stop"})
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], "third-party")
        sid = self.start("manual")
        self.assertFalse(self.event("PreToolUse", mode="manual")["recorded"])
        state.save(sid, next_step="Review output")
        self.assertFalse(state.recover(sid)["ready_for_review"])
        self.assertFalse(relay.verify(sid)["automatic_tool_coverage_complete"])

    def test_mcp_compact_and_context_allowlist(self):
        from projectmirror.mcp import dispatch
        sid = self.start()
        state.save(sid, goal="Player", next_step="Verify seek", decision=["Independent seek"])
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "mirrormap_relay_brief", "arguments": {"session_id": sid, "max_tokens": 2000}}}
        with patch.dict(os.environ, {"MIRRORMAP_ALLOWED_ROOTS": str(self.repo)}):
            answer = dispatch(request)
            self.assertFalse(answer["result"].get("isError", False))
            body = json.loads(answer["result"]["content"][0]["text"])
            self.assertEqual(body["task"]["next_step"], "Verify seek")
            request["params"] = {"name": "mirrormap_relay_context", "arguments":
                                 {"session_id": sid, "checkpoint": body["checkpoint"], "query": "seek"}}
            page = json.loads(dispatch(request)["result"]["content"][0]["text"])
            self.assertEqual(page["total_matches"], 1)
            request["params"]["arguments"]["checkpoint"] = True
            self.assertTrue(dispatch(request)["result"]["isError"])
            request["params"]["arguments"]["checkpoint"] = body["checkpoint"]
        with patch.dict(os.environ, {"MIRRORMAP_ALLOWED_ROOTS": str(self.root / "other")}):
            self.assertTrue(dispatch(request)["result"]["isError"])

    def test_old_full_checkpoint_still_reads_after_delta(self):
        sid = self.start()
        with patch.object(efficiency, "encode_checkpoint", side_effect=lambda conn, sid, current: {"checkpoint_state": current}):
            state.save(sid, next_step="Old checkpoint")
        first = state.history(sid)["checkpoints"][-1]["checkpoint"]
        state.save(sid, next_step="New checkpoint")
        self.assertEqual(state.recover(sid, first)["task"]["next_step"], "Old checkpoint")
        self.assertEqual(relay.verify(sid)["journal_integrity"], "valid")


if __name__ == "__main__":
    unittest.main()
