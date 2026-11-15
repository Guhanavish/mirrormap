"""Evidence-intelligence contracts: review boundaries, integrity, and regression tests."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from projectmirror.core import AuditError, digest, load
from projectmirror.experience import audit_project
from projectmirror.intelligence import (
    add_conflict_plan_tasks, apply_declared_conflicts, assumption_debt,
    draft_approval_capsule, evaluation_summary, evidence_passports,
    handoff_manifest, impact_preview, investigation_queue, readiness_matrix,
    spec_conflicts, verify_handoff, freshness_report, behavior_journeys,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "demo-app"


def intent_nodes(conflicts=None):
    return {"schema_version": "1.0", "nodes": [
        {"id": "REQ.login", "map": "intent", "kind": "requirement",
         "title": "Login", "requirement_state": "approved",
         "acceptance_criteria": [{"id": "AC.login", "statement": "Valid users log in"}],
         **({"conflicts_with": conflicts} if conflicts is not None else {})},
        {"id": "REQ.logout", "map": "intent", "kind": "requirement",
         "title": "Logout", "requirement_state": "approved",
         "acceptance_criteria": [{"id": "AC.logout", "statement": "Users can log out"}]},
    ]}


def implementation_nodes():
    return {"schema_version": "1.0", "nodes": [
        {"id": "impl.file.abc", "map": "implementation", "title": "auth.py",
         "kind": "file", "locator": "src/auth.py", "source_refs": ["ev.file.abc"]},
        {"id": "impl.symbol.login", "map": "implementation", "title": "login",
         "kind": "functiondef", "locator": "src/auth.py:10", "source_refs": ["ev.file.abc"]}],
        "evidence": [{"id": "ev.file.abc", "uri": "src/auth.py", "kind": "source_file", "content_hash": "f" * 64}]}


def findings(status="unverified"):
    return {"schema_version": "1.0", "findings": [
        {"id": "F-REQ.login", "requirement_id": "REQ.login", "title": "Login",
         "classification": status, "reason": "No current evidence", "scope": "approved",
         "implementation_ids": ["impl.symbol.login"], "verification_ids": ["verify.login"], "evidence": []},
        {"id": "F-REQ.logout", "requirement_id": "REQ.logout", "title": "Logout",
         "classification": "unknown", "reason": "Not linked", "scope": "approved",
         "implementation_ids": [], "verification_ids": [], "evidence": []}],
        "counts": {status: 1, "unknown": 1}, "revision": "abc123"}


class EvidenceIntelligenceTests(unittest.TestCase):
    def test_passport_preserves_reported_observation_and_hash(self):
        report = evidence_passports(intent_nodes(), implementation_nodes(),
            {"schema_version": "1.0", "nodes": [
                {"id": "verify.login", "map": "verification", "title": "test login",
                 "requirement_id": "REQ.login", "result": "passed", "revision": "abc123",
                 "evidence": ["reported junit"], "criteria_ids": ["AC.login"]}]},
            findings(), {"project": {"revision": "abc123"}})
        self.assertEqual(report["authority"], "informational_only")
        self.assertEqual(report["records"][0]["evidence"][0]["sha256"], "f" * 64)
        self.assertTrue(report["records"][0]["evidence"][1]["current_revision"])
        self.assertIn("not independently attested", report["records"][0]["evidence"][1]["claim"])
        self.assertEqual(report["content_digest"], digest({k:v for k,v in report.items() if k!="content_digest"}))

    def test_stale_test_cannot_be_called_current(self):
        test = {"id": "verify.login", "map": "verification", "title": "previous test",
                "requirement_id": "REQ.login", "result": "passed", "revision": "oldsha",
                "evidence": ["prior report"], "criteria_ids": ["AC.login"]}
        output = evidence_passports(intent_nodes(), implementation_nodes(),
                                    {"schema_version": "1.0", "nodes": [test]}, findings(),
                                    {"project": {"revision": "abc123"}})
        self.assertFalse(output["records"][0]["evidence"][-1]["current_revision"])

    def test_explicit_spec_conflicts_and_review_task(self):
        clash = spec_conflicts(intent_nodes(conflicts=["REQ.logout"]))
        self.assertEqual(clash["count"], 1)
        derived = apply_declared_conflicts(findings("complete"), clash)
        self.assertEqual(derived["counts"], {"spec_conflict": 2})
        original = {"schema_version": "1.0", "base_revision": "abc", "environment": "source", "tasks": []}
        original["plan_digest"] = digest(original)
        plan = add_conflict_plan_tasks(original, derived)
        self.assertEqual(len(plan["tasks"]), 2)
        self.assertTrue(all(t["type"] == "investigate" and not t["allowed_paths"] for t in plan["tasks"]))
        self.assertEqual(plan["plan_digest"], digest({k:v for k,v in plan.items() if k!="plan_digest"}))

    def test_declared_conflict_rejects_invalid_reference(self):
        for entries in ("REQ.logout", ["REQ.notfound"], ["REQ.login"], [42]):
            with self.subTest(entries=entries), self.assertRaises(AuditError):
                spec_conflicts(intent_nodes(conflicts=entries))

    def test_criterion_id_collision(self):
        i = intent_nodes()
        i["nodes"][1]["acceptance_criteria"][0]["id"] = "AC.login"
        self.assertEqual(spec_conflicts(i)["conflicts"][0]["type"], "criterion_id_collision")

    def test_unknown_investigation_does_not_grant_permissions(self):
        tasks = investigation_queue(findings(), intent_nodes(), {"candidates": [
            {"requirement_id": "REQ.logout", "implementation_id": "impl.candidate", "heuristic_score": .8}]})
        self.assertEqual(len(tasks["investigations"]), 2)
        for task in tasks["investigations"]:
            self.assertTrue(task["requires_approval_for_execution"])
            self.assertFalse(task["automatic_execution"])
            self.assertEqual(task["authority"], "suggestion_only")
        self.assertEqual(tasks["investigations"][1]["candidate_implementation_ids"], ["impl.candidate"])

    def test_bad_candidate_scores_are_ignored(self):
        tasks = investigation_queue(findings(), intent_nodes(), {"candidates": [
            {"requirement_id": "REQ.logout", "implementation_id": "impl.bad", "heuristic_score": "bad"}]})
        self.assertFalse(tasks["investigations"][1]["candidate_implementation_ids"])

    def test_assumptions_are_not_reported_as_defects(self):
        debt = assumption_debt(findings(), intent_nodes())
        self.assertEqual(debt["total"], 2)
        self.assertTrue(all(item["staleness"] == "not_assessed" for item in debt["items"]))
        matrix = readiness_matrix(findings())
        self.assertTrue(all(r["security"] == "not_assessed" for r in matrix["features"]))

    def test_impact_only_for_reviewed_links_and_exact_paths(self):
        links = {"links": [
            {"requirement_id": "REQ.login", "implementation_id": "impl.symbol.login", "basis": "reviewed"},
            {"requirement_id": "REQ.logout", "implementation_id": "impl.file.abc", "basis": "candidate"}]}
        impact = impact_preview(implementation_nodes(), links, ["src/auth.py"])
        self.assertEqual(len(impact["possible_impacts"]), 1)
        self.assertEqual(impact["possible_impacts"][0]["claim"], "potentially_affected")
        self.assertEqual(impact["possible_impacts"][0]["certainty"], "not_a_verified_regression")
        for unsafe in ("../auth.py", "/tmp/auth.py", "C:\\auth.py"):
            with self.subTest(path=unsafe), self.assertRaises(AuditError):
                impact_preview(implementation_nodes(), links, [unsafe])

    def test_freshness_distinguishes_revision_from_execution_attestation(self):
        checks={"schema_version":"1.0","nodes":[
            {"id":"verify.old","map":"verification","title":"Old test","requirement_id":"REQ.login",
             "result":"passed","revision":"older","evidence":["old evidence"],"criteria_ids":["AC.login"]},
            {"id":"verify.new","map":"verification","title":"New test","requirement_id":"REQ.login",
             "result":"passed","revision":"abc123","evidence":["reported new evidence"],"criteria_ids":["AC.login"]}]}
        r=freshness_report(checks,{"project":{"revision":"abc123"}})
        self.assertEqual([x["freshness"] for x in r["observations"]],["stale_revision","revision_matched"])
        self.assertFalse(any(x["execution_attested"] for x in r["observations"]))

    def test_journey_import_requires_valid_imported_observations(self):
        v={"schema_version":"1.0","nodes":[
            {"id":"verify.login","map":"verification","title":"Login test","requirement_id":"REQ.login",
             "result":"passed","revision":"abc123","evidence":["reported"],"criteria_ids":["AC.login"]}]}
        source={"schema_version":"1.0","journeys":[{"id":"FLOW.login","title":"Login flow","steps":[
            {"id":"STEP.login","description":"User enters valid credentials", "requirement_id":"REQ.login",
             "verification_ids":["verify.login"]}]}]}
        result=behavior_journeys(source,intent_nodes(),v,{"project":{"revision":"abc123"}})
        self.assertEqual(result["journeys"][0]["steps"][0]["status"],"reported_pass")
        self.assertEqual(result["authority"],"user_supplied_mapping_only")
        stale=behavior_journeys(source,intent_nodes(),v,{"project":{"revision":"changed"}})
        self.assertEqual(stale["journeys"][0]["steps"][0]["status"],"unverified")
        source["journeys"][0]["steps"][0]["verification_ids"]=["verify.missing"]
        with self.assertRaises(AuditError):
            behavior_journeys(source,intent_nodes(),v,{"project":{"revision":"abc123"}})

    def test_approval_capsule_is_never_authorization(self):
        plan = {"schema_version": "1.0", "plan_digest": "abc", "base_revision": "deadbeef",
                "tasks": [{"task_id": "T-001", "type": "investigate", "allowed_paths": []}]}
        draft = draft_approval_capsule(plan)
        self.assertFalse(draft["execution_authorized"])
        self.assertFalse(draft["approved"])
        self.assertEqual(draft["approved_task_ids"], [])
        self.assertTrue(draft["host_enforcement_required"])

    def test_handoff_roundtrip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "findings.json").write_text('{"ok":true}', encoding="utf-8")
            payload = handoff_manifest({"project": {"revision": "abc"}},
                                       {"findings.json": root / "findings.json"})
            self.assertEqual(payload["authority"], "read_only_handoff")
            self.assertTrue(verify_handoff(root, payload)["valid"])
            (root / "findings.json").write_text('{"ok":false}', encoding="utf-8")
            out = verify_handoff(root, payload)
            self.assertFalse(out["valid"])
            self.assertEqual(out["errors"][0]["problem"], "size_mismatch" if len('{"ok":true}') != len('{"ok":false}') else "digest_mismatch")
            payload["artifacts"][0]["name"] = "../secrets"
            with self.assertRaises(AuditError):
                verify_handoff(root, payload)

    def test_handoff_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root / "file.json").write_text("test")
            (root / "link.json").symlink_to(root / "file.json")
            with self.assertRaises(AuditError):
                handoff_manifest({}, {"link.json": root / "link.json"})

    def test_evaluation_metrics_not_marketed_as_global_accuracy(self):
        report=evaluation_summary({"REQ.one": "missing", "REQ.two":"complete"},
                                  {"REQ.one":"missing", "REQ.two":"complete"})
        self.assertEqual(report["missing_precision"], 1.0)
        self.assertEqual(report["false_completion_count"], 0)
        with self.assertRaises(AuditError):
            evaluation_summary({"REQ.one": "nonsense"}, {"REQ.one":"missing"})
        with self.assertRaises(AuditError):
            evaluation_summary([], {})


class EndToEndIntelligenceTests(unittest.TestCase):
    def test_live_audit_generates_all_read_only_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"audit"
            result=audit_project(EXAMPLE, spec=EXAMPLE/"requirements.md", out=out,
                                 spec_approved=True, mode="deep",
                                 links=ROOT/"examples/fixture-reviewed-links.json",
                                 absence=ROOT/"examples/fixture-reviewed-absence.json",
                                 changed_paths=["auth.py"])
            self.assertEqual(result["counts"], {"missing":1,"unverified":2})
            names={"evidence-passports.json", "investigations.json", "assumption-debt.json",
                   "readiness-matrix.json", "spec-conflicts.json", "approval-draft.json",
                   "audit-handoff.json", "impact-preview.json"}
            self.assertTrue(all((out/n).is_file() for n in names))
            self.assertEqual(len(load(out/"impact-preview.json")["possible_impacts"]),2)
            self.assertTrue(verify_handoff(out,load(out/"audit-handoff.json"))["valid"])
            self.assertFalse(load(out/"approval-draft.json")["execution_authorized"])
            self.assertEqual(len(load(out/"investigations.json")["investigations"]),2)

    def test_cli_handoff_verify_and_change_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"audit"
            cmd=[sys.executable,"-m","projectmirror","audit",str(EXAMPLE),
                 "--spec",str(EXAMPLE/"requirements.md"),"--approved-spec",
                 "--out",str(out),"--changed-path","auth.py"]
            r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=25)
            self.assertEqual(r.returncode,0,r.stderr)
            check=subprocess.run([sys.executable,"-m","projectmirror","verify-handoff","--out",str(out)],
                                 cwd=ROOT,text=True,capture_output=True,timeout=25)
            self.assertEqual(check.returncode,0,check.stderr)
            (out/"findings.json").write_text("tampered")
            broken=subprocess.run([sys.executable,"-m","projectmirror","verify-handoff","--out",str(out)],
                                  cwd=ROOT,text=True,capture_output=True,timeout=25)
            self.assertEqual(broken.returncode,2)

    def test_json_schemas_are_parseable_and_match_output_shapes(self):
        sample_maps = {
            "evidence-passport.schema.json": "evidence-passports.json",
            "investigations.schema.json": "investigations.json",
            "audit-handoff.schema.json": "audit-handoff.json",
            "approval-draft.schema.json": "approval-draft.json",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"audit"
            audit_project(EXAMPLE, out=out)
            for schema_name, output_name in sample_maps.items():
                with self.subTest(schema=schema_name):
                    schema=json.loads((ROOT/"schemas"/schema_name).read_text(encoding="utf-8"))
                    data=load(out/output_name)
                    self.assertTrue(set(schema["required"]).issubset(data))
                    self.assertTrue(schema["$schema"].startswith("https://json-schema.org/"))
                    try:
                        from jsonschema import validate
                    except ImportError:
                        continue  # Optional schema validator; core stays stdlib-only.
                    validate(data,schema)

    def test_import_example_journey_is_unverified_without_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"audit"
            audit_project(EXAMPLE, spec=EXAMPLE/"requirements.md", spec_approved=True,
                          journeys=ROOT/"examples/intelligence/journeys.json", out=out)
            example=load(out/"behavior-journeys.json")
            self.assertEqual(example["total_steps"],2)
            self.assertTrue(all(step["status"]=="unverified"
                for journey in example["journeys"] for step in journey["steps"]))
            self.assertTrue(verify_handoff(out,load(out/"audit-handoff.json"))["valid"])

    def test_nonempty_output_rejected_to_prevent_stale_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"audit"
            audit_project(EXAMPLE, out=out)
            prior=(out/"findings.json").read_bytes()
            with self.assertRaisesRegex(AuditError,"not empty"):
                audit_project(EXAMPLE,out=out, mode="deep")
            self.assertEqual((out/"findings.json").read_bytes(),prior)

    def test_dashboard_links_are_to_real_local_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"audit"
            audit_project(EXAMPLE, out=out)
            page=(out/"dashboard.html").read_text(encoding="utf-8")
            self.assertIn('href="evidence-passports.json"',page)
            self.assertIn('href="investigations.json"',page)
            self.assertNotIn('href="http://',page)

    def test_conflicting_specs_produce_review_only_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            req=intent_nodes(conflicts=["REQ.logout"])
            file=root/"spec.json"
            file.write_text(json.dumps(req), encoding="utf-8")
            out=root/"audit"
            result=audit_project(EXAMPLE,spec=file,out=out,mode="deep")
            self.assertEqual(result["counts"],{"spec_conflict":2})
            plan=load(out/"plan.json")
            self.assertEqual(len(plan["tasks"]),2)
            self.assertTrue(all(t["type"]=="investigate" for t in plan["tasks"]))
            self.assertFalse(load(out/"approval-draft.json")["approved"])


if __name__ == "__main__":
    unittest.main()
