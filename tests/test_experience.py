"""New user-facing pipeline, safety and MCP contract tests."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror.core import AuditError, load
from projectmirror.experience import (audit_project, baseline_comparison,
                                      doctor, install_skill)
from projectmirror.mcp import dispatch

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "demo-app"
SPEC = EXAMPLE / "requirements.md"


class ExperienceTests(unittest.TestCase):
    def test_quick_inventory_without_spec_is_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "audit"
            result = audit_project(EXAMPLE, out=out)
            self.assertEqual(result["counts"], {})
            self.assertIn("No requirements supplied", " ".join(result["limitations"]))
            self.assertIn("Content-Security-Policy", (out / "dashboard.html").read_text())
            self.assertTrue((out / "plan.json").is_file())

    def test_deep_does_not_promote_candidates_to_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "audit"
            result = audit_project(EXAMPLE, spec=SPEC, out=out, mode="deep", spec_approved=True)
            self.assertEqual(result["counts"], {"unknown": 3})
            self.assertTrue((out / "candidate-links.json").is_file())
            self.assertFalse((out / "links.json").exists())

    def test_visual_is_not_claimed_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit_project(EXAMPLE, out=Path(tmp) / "out", mode="visual")
            self.assertTrue(any("NOT performed" in x for x in result["limitations"]))

    def test_pr_without_base_warns_instead_of_inventing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pr"
            audit_project(EXAMPLE, out=out, mode="pr")
            self.assertFalse(load(out / "pr-scope.json")["available"])

    def test_baseline_change_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, current = Path(tmp) / "base", Path(tmp) / "current"
            for d in (base, current):
                audit_project(EXAMPLE, spec=SPEC, out=d, spec_approved=True)
            data = load(current / "findings.json")
            data["findings"][0]["classification"] = "complete"
            from projectmirror.core import save
            save(current / "findings.json", data)
            result = baseline_comparison(current, base)
            self.assertEqual(len(result["changes"]), 1)

    def test_reject_output_inside_project(self):
        with self.assertRaises(AuditError):
            audit_project(EXAMPLE, out=EXAMPLE / "BAD_OUT")

    def test_installer_plan_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "agent" / "skills" / "mirrormap"
            info = install_skill(dest, apply=False)
            self.assertEqual(info["status"], "preview_only")
            self.assertFalse(dest.exists())

    def test_installer_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "skills" / "mirrormap"
            info = install_skill(dest, apply=True)
            self.assertTrue((dest / "SKILL.md").is_file())
            self.assertEqual(info["status"], "installed")
            with self.assertRaises(AuditError):
                install_skill(dest, apply=True)

    def test_doctor_reports_checks(self):
        self.assertTrue(doctor()["checks"])

    def test_mcp_initialize_tools_and_no_unlisted_access(self):
        init = dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "mirrormap")
        listing = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(listing["result"]["tools"]), 3)
        with patch.dict(os.environ, {"MIRRORMAP_ALLOWED_ROOTS": ""}):
            denied = dispatch({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "mirrormap_audit", "arguments": {"repo": str(EXAMPLE)}}})
            self.assertTrue(denied["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
