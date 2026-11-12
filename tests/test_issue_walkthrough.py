"""Prevent accidental misinformation in the documented first-audit example."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from projectmirror.experience import audit_project

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "examples/demo-app"
SPEC = APP / "requirements.md"


class FirstAuditWalkthroughTests(unittest.TestCase):
    def test_two_demo_phases_and_read_only_output(self):
        with tempfile.TemporaryDirectory(prefix="mirrormap-first-audit-") as tmp:
            first = Path(tmp) / "initial"
            reviewed = Path(tmp) / "reviewed"
            code_before = (APP / "auth.py").read_bytes()
            initial = audit_project(APP, SPEC, out=first, mode="deep", spec_approved=True)
            self.assertEqual(initial["counts"], {"unknown": 3})
            self.assertFalse((first / "links.json").exists(), "Candidate links must not be trusted automatically")
            result = audit_project(
                APP, SPEC, out=reviewed, mode="deep", spec_approved=True,
                links=ROOT / "examples/fixture-reviewed-links.json",
                absence=ROOT / "examples/fixture-reviewed-absence.json",
            )
            self.assertEqual(result["counts"], {"missing": 1, "unverified": 2})
            findings = json.loads((reviewed / "findings.json").read_text(encoding="utf-8"))
            classifications = {f["id"]: f["classification"] for f in findings["findings"]}
            self.assertEqual(classifications["F-REQ.auth.login"], "unverified")
            self.assertEqual(classifications["F-REQ.auth.logout"], "unverified")
            self.assertEqual(classifications["F-REQ.auth.recovery"], "missing")
            for folder in (first, reviewed):
                self.assertTrue((folder / "dashboard.html").is_file())
                self.assertTrue((folder / "audit-report.md").is_file())
                self.assertTrue((folder / "remediation-plan.md").is_file())
            self.assertEqual((APP / "auth.py").read_bytes(), code_before)

    def test_worked_example_docs_are_present(self):
        a = (ROOT / "docs/guides/first-audit-walkthrough.md").read_text(encoding="utf-8")
        b = (ROOT / "docs/integrations/skills-cli-verification.md").read_text(encoding="utf-8")
        self.assertIn('"unknown": 3', a)
        self.assertIn('"missing": 1, "unverified": 2', a)
        self.assertIn('skills@1.7.6', b)
        self.assertIn("does not install the Python", b)


if __name__ == "__main__":
    unittest.main()
