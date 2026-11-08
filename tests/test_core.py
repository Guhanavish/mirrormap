"""Deterministic safety and classification tests for ProjectMirror."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from projectmirror.core import (
    AuditError, check_receipt, compare, create_plan, digest, ensure_output,
    ignored, index_repo, markdown_plan, markdown_report, parse_spec, render,
    validate_nodes,
)

REV = "d9b77b1e7b0a52c8"


def req(state="approved", criteria=None):
    return {"id": "REQ.auth.login", "map": "intent", "kind": "requirement",
            "title": "Users can log in", "requirement_state": state,
            "source_refs": ["requirements.md:3"],
            "acceptance_criteria": criteria if criteria is not None else [
                {"id": "AC.auth.login.valid", "statement": "Session is established"}]}


def impl(state="present", kind="function"):
    return {"id": "impl.symbol.aabbccdd", "map": "implementation", "kind": kind,
            "title": "login", "locator": "src/auth.py:4", "source_refs": ["ev.1"],
            "implementation_state": state}


def verification(result="passed", rev=REV, evidence=None, criteria=None):
    return {"id": "verify.login.valid", "map": "verification", "title": "test login",
            "requirement_id": "REQ.auth.login", "result": result,
            "revision": rev, "evidence": ["test_login.py::test_login passed"] if evidence is None else evidence,
            "criteria_ids": ["AC.auth.login.valid"] if criteria is None else criteria}


def material(intent=None, implementation=None, verification_nodes=None, linked=True, absences=None):
    i = {"schema_version": "1.0", "nodes": [intent if intent is not None else req()]}
    m = {"schema_version": "1.0", "nodes": [implementation if implementation is not None else impl()]}
    v = {"schema_version": "1.0", "nodes": verification_nodes or []}
    links = {"links": [{"requirement_id": "REQ.auth.login", "implementation_id": "impl.symbol.aabbccdd", "basis": "reviewed"}]} if linked else {"links": []}
    a = {"confirmations": absences or []}
    meta = {"project": {"revision": REV, "environment": "source", "repo": "/example"}}
    return i, m, v, links, a, meta


def classify(*args, **kwargs):
    return compare(*material(*args, **kwargs),)["findings"][0]["classification"]


class CoreTest(unittest.TestCase):
    def test_unlinked_is_unknown_not_missing(self):
        self.assertEqual(classify(linked=False), "unknown")

    def test_linked_but_not_verified(self):
        self.assertEqual(classify(), "unverified")

    def test_explicit_criterion_passes(self):
        self.assertEqual(classify(verification_nodes=[verification()]), "complete")

    def test_stale_test_is_not_pass(self):
        self.assertEqual(classify(verification_nodes=[verification(rev="old-commit")]), "unverified")

    def test_missing_evidence_is_not_pass(self):
        self.assertEqual(classify(verification_nodes=[verification(evidence=[])]), "unverified")

    def test_uncovered_second_criterion_is_unverified(self):
        r = req(criteria=[{"id": "AC.auth.login.valid"}, {"id": "AC.auth.login.revocation"}])
        self.assertEqual(classify(intent=r, verification_nodes=[verification()]), "unverified")

    def test_failing_check_is_broken(self):
        self.assertEqual(classify(verification_nodes=[verification(result="failed")]), "broken")

    def test_inconsistent_check_is_mismatch(self):
        self.assertEqual(classify(verification_nodes=[verification(result="mismatch")]), "mismatch")

    def test_confirmed_absence_is_missing(self):
        absence = {"requirement_id": "REQ.auth.login", "reviewed": True, "coverage": "exhaustive", "evidence": ["inspected all auth routes"]}
        self.assertEqual(classify(linked=False, absences=[absence]), "missing")

    def test_unreviewed_absence_is_unknown(self):
        absence = {"requirement_id": "REQ.auth.login", "reviewed": False, "coverage": "exhaustive", "evidence": ["grep found nothing"]}
        self.assertEqual(classify(linked=False, absences=[absence]), "unknown")

    def test_partial_is_partial(self):
        self.assertEqual(classify(implementation=impl(state="partial")), "partial")

    def test_draft_is_not_actionable(self):
        self.assertEqual(classify(intent=req(state="draft"), verification_nodes=[verification(result="failed")]), "unknown")

    def test_conflicted_requires_resolution(self):
        self.assertEqual(classify(intent=req(state="conflicted")), "spec_conflict")

    def test_undocumented_only_explicit_capabilities(self):
        i, m, v, l, a, meta = material(implementation=impl(kind="capability"), linked=False)
        result = compare(i, m, v, l, a, meta)
        self.assertEqual({f["classification"] for f in result["findings"]}, {"unknown", "undocumented"})
        self.assertEqual(len(result["findings"]), 2)

    def test_reject_invalid_link(self):
        data = list(material())
        data[3] = {"links": [{"requirement_id": "REQ.nope", "implementation_id": "impl.symbol.aabbccdd", "basis": "reviewed"}]}
        with self.assertRaises(AuditError):
            compare(*data)

    def test_reject_invalid_test_result(self):
        with self.assertRaises(AuditError):
            compare(*material(verification_nodes=[verification(result="imagined_pass")]))

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(AuditError):
            validate_nodes({"schema_version": "1.0", "nodes": [req(), req()]}, "intent", "intent")

    def test_missing_acceptance_criterion_reference_is_not_complete(self):
        self.assertEqual(classify(verification_nodes=[verification(criteria=["AC.other"])]), "unverified")

    def test_plan_is_not_authorization(self):
        i, m, v, l, a, meta = material(verification_nodes=[verification(result="failed")])
        findings = compare(i, m, v, l, a, meta)
        plan = create_plan(findings, meta, m)
        self.assertEqual(len(plan["tasks"]), 1)
        self.assertEqual(plan["tasks"][0]["allowed_paths"], ["src/auth.py"])
        self.assertTrue(plan["tasks"][0]["approval_required"])
        self.assertEqual(plan["plan_digest"], digest({k: v for k, v in plan.items() if k != "plan_digest"}))
        self.assertIn("not", markdown_plan(plan).lower())
        self.assertIn("broken", markdown_report(findings, meta))
        self.assertIn("flowchart TD", render(findings))

    def test_approval_metadata_and_paths(self):
        data = material(verification_nodes=[verification(result="failed")])
        plan = create_plan(compare(*data), data[5], data[1])
        receipt = {"plan_digest": plan["plan_digest"], "base_revision": REV,
                   "environment": "source", "actor": "trusted-host-user", "approved_at": "2026-11-08", "approved_task_ids": ["T-001"]}
        check_receipt(plan, receipt, data[5], ["src/auth.py"])
        with self.assertRaises(AuditError):
            check_receipt(plan, receipt, data[5], ["src/other.py"])
        with self.assertRaises(AuditError):
            check_receipt(plan, receipt, data[5], ["../src/auth.py"])
        with self.assertRaises(AuditError):
            check_receipt(plan, {**receipt, "plan_digest": "incorrect"}, data[5], [])
        with self.assertRaises(AuditError):
            check_receipt({**plan, "tasks": []}, receipt, data[5], [])

    def test_investigation_never_inherits_write_scope(self):
        data = material()
        plan = create_plan(compare(*data), data[5], data[1])
        self.assertEqual(plan["tasks"][0]["type"], "investigate")
        self.assertEqual(plan["tasks"][0]["allowed_paths"], [])
        receipt = {"plan_digest": plan["plan_digest"], "base_revision": REV,
                   "environment": "source", "actor": "trusted-host-user", "approved_at": "2026-11-08", "approved_task_ids": ["T-001"]}
        with self.assertRaises(AuditError):
            check_receipt(plan, receipt, data[5], ["src/auth.py"])

    def test_validation_rejects_malformed_evidence_and_criteria(self):
        with self.assertRaises(AuditError):
            classify(verification_nodes=[verification(evidence="trusted without source")])
        with self.assertRaises(AuditError):
            classify(intent=req(criteria=[{"id": "AC.dupe"}, {"id": "AC.dupe"}]))

    def test_output_not_allowed_inside_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "source"
            root.mkdir()
            with self.assertRaises(AuditError):
                ensure_output(root, root / ".projectmirror")
            with self.assertRaises(AuditError):
                ensure_output(root, root)
            self.assertEqual(ensure_output(root, Path(td) / "audit"), Path(td) / "audit")

    def test_spec_parser_requires_explicit_requirements_and_state(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "spec.md"
            path.write_text("# Intent\n- [REQ.auth.login] Users can log in\n  - [AC.auth.login.valid] Valid credentials work\n", encoding="utf-8")
            result = parse_spec(path, "approved")
            self.assertEqual(result["nodes"][0]["requirement_state"], "approved")
            self.assertEqual(result["nodes"][0]["acceptance_criteria"][0]["id"], "AC.auth.login.valid")
            path.write_text("# Nothing explicit\nJust some ideas.\n", encoding="utf-8")
            with self.assertRaises(AuditError):
                parse_spec(path)
            path.write_text("- [REQ.dup] A\n- [REQ.dup] B\n", encoding="utf-8")
            with self.assertRaises(AuditError):
                parse_spec(path)

    def test_index_scans_source_and_skips_common_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app.py").write_text("def serve():\n    return 1\nclass App: pass\n", encoding="utf-8")
            (root / "app.js").write_text("export function hello() {}\n", encoding="utf-8")
            (root / ".env").write_text("MY_SECRET=never-publish-this", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "secret.js").write_text("export const secret = 1", encoding="utf-8")
            nodes, scan = index_repo(root)
            names = [n["title"] for n in nodes["nodes"]]
            self.assertIn("app.py", names)
            self.assertIn("serve", names)
            self.assertIn("App", names)
            self.assertIn("hello", names)
            self.assertNotIn(".env", names)
            self.assertEqual(scan["scanned_files"], 2)
            self.assertNotIn("never-publish-this", json.dumps(nodes))
            self.assertTrue(ignored(Path(".env")))
            self.assertTrue(ignored(Path("node_modules") / "lib.js"))


if __name__ == "__main__":
    unittest.main()
