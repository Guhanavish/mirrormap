"""Cross-module regressions found during the v0.4 maintenance audit."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror.core import AuditError, compare, parse_spec, validate_nodes
from projectmirror.evidence import collect_junit
from projectmirror.experience import audit_project


class SchemaAndEvidenceRegressions(unittest.TestCase):
    def setUp(self):
        self.intent = {"schema_version": "1.0", "nodes": [{
            "id": "REQ.login", "map": "intent", "title": "Login", "requirement_state": "approved",
            "acceptance_criteria": [{"id": "AC.login.valid", "statement": "A login works"}]}]}
        self.impl = {"schema_version": "1.0", "nodes": []}
        self.verification = {"schema_version": "1.0", "nodes": []}
        self.manifest = {"project": {"revision": "abc"}}

    def test_non_list_absence_is_rejected_not_marked_missing(self):
        for malicious in ("unreviewed claim", {"one": "missing"}, 123):
            with self.subTest(malicious=malicious), self.assertRaises(AuditError):
                compare(self.intent, self.impl, self.verification, {"links": []},
                        {"confirmations": malicious}, self.manifest)

    def test_absence_evidence_must_have_actual_list_of_strings(self):
        for bad in ("unverified", [None], [" "]):
            with self.subTest(bad=bad), self.assertRaisesRegex(AuditError, "Absence evidence"):
                compare(self.intent, self.impl, self.verification, {"links": []},
                        {"confirmations": [{"requirement_id": "REQ.login", "reviewed": True,
                                           "coverage": "exhaustive", "evidence": bad}]}, self.manifest)

    def test_valid_reviewed_absence_is_still_missing(self):
        findings = compare(self.intent, self.impl, self.verification, {"links": []},
                           {"confirmations": [{"requirement_id": "REQ.login", "reviewed": True,
                                               "coverage": "exhaustive", "evidence": ["reviewed source survey"]}]},
                           self.manifest)
        self.assertEqual(findings["counts"], {"missing": 1})

    def test_intent_criteria_match_schema(self):
        for criteria in ([{"id": "AC.login.valid"}],
                         [{"id": "??", "statement": "something"}],
                         [{"id": "AC.login.valid", "statement": " "}]):
            bad = {**self.intent, "nodes": [{**self.intent["nodes"][0], "acceptance_criteria": criteria}]}
            with self.subTest(criteria=criteria), self.assertRaisesRegex(AuditError, "acceptance criteria"):
                validate_nodes(bad, "intent-map", "intent")

    def test_verification_must_have_required_fields(self):
        examples = [
            {"id": "verify.login", "map": "verification", "title": "Test", "result": "passed", "evidence": ["real"]},
            {"id": "verify.login", "map": "verification", "title": "Test", "result": "passed", "requirement_id": "REQ.login"},
            {"id": "verify.login", "map": "verification", "title": "Test", "result": "passed", "requirement_id": "REQ.login", "revision": 42, "evidence": ["real"]},
        ]
        for node in examples:
            with self.subTest(node=node), self.assertRaises(AuditError):
                validate_nodes({"schema_version": "1.0", "nodes": [node]}, "verification-map", "verification")

    def test_missing_requirements_file_returns_audit_error(self):
        with self.assertRaisesRegex(AuditError, "Cannot read requirements"):
            parse_spec(Path("/this/path/should/not/exist/requirements.md"))

    def test_junit_io_error_is_actionable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.xml"
            path.write_text('<testsuite><testcase name="test" /></testsuite>')
            with patch.object(Path, 'read_bytes', side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(AuditError, "Cannot read JUnit XML"):
                    collect_junit([path], manifest_revision=None, intent=self.intent)

    def test_audit_pipeline_preserves_unknown_without_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "source"
            repo.mkdir()
            (repo / "main.py").write_text("def login(): pass\n")
            spec = repo / "spec.md"
            spec.write_text("- [REQ.login] Login is implemented\n  - [AC.login.valid] A valid user can login\n")
            out = root / "audit"
            result = audit_project(repo, spec=spec, out=out, spec_approved=True, mode="deep")
            self.assertEqual(result["counts"], {"unknown": 1})
            self.assertTrue((out / "dashboard.html").is_file())
            self.assertTrue((out / "remediation-plan.md").is_file())
            self.assertEqual((repo / "main.py").read_text(), "def login(): pass\n")


if __name__ == "__main__":
    unittest.main()
