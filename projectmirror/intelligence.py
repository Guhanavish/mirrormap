"""MirrorMap Evidence Intelligence: deterministic, inspectable read-only outputs.

Never promotes suggestions, code presence, or a test-import candidate into confirmed
functional evidence. Public artifacts do not contain original source contents.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .core import AuditError, SCHEMA, VALID_CLASSES, digest, now, validate_nodes

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,160}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _safe(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise AuditError(f"{label} needs a valid stable ID")
    return value


def _source_hashes(implementation: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for evidence in implementation.get("evidence", []):
        if not isinstance(evidence, dict):
            raise AuditError("Implementation evidence must be objects")
        key = evidence.get("uri")
        sha = evidence.get("content_hash")
        if isinstance(key, str) and isinstance(sha, str) and _SHA256.fullmatch(sha):
            out[key] = sha
    return out


def evidence_passports(intent: dict, implementation: dict, verification: dict,
                       findings: dict, manifest: dict) -> dict:
    """Project claims with evidence and precise limitations, not an attestation.

    A verification entry referencing current HEAD is a *reported observation*;
    no cryptographic attestation of where/when it ran is invented.
    """
    requirements = {n["id"]: n for n in validate_nodes(intent, "intent-map", "intent")}
    implementations = {n["id"]: n for n in validate_nodes(implementation, "implementation-map", "implementation")}
    verifications = {n["id"]: n for n in validate_nodes(verification, "verification-map", "verification")}
    revision = manifest.get("project", {}).get("revision")
    hashes = _source_hashes(implementation)
    records = []
    for finding in findings.get("findings", []):
        rid = finding.get("requirement_id")
        if rid not in requirements:
            continue
        requirement = requirements[rid]
        impl = [implementations[i] for i in finding.get("implementation_ids", []) if i in implementations]
        observed = [verifications[i] for i in finding.get("verification_ids", []) if i in verifications]
        evidence = []
        for node in impl:
            locator = node.get("locator", "")
            path = locator.rsplit(":", 1)[0] if re.search(r":\d+$", locator) else locator
            evidence.append({"type": "source", "node_id": node["id"], "locator": locator,
                             "sha256": hashes.get(path), "accepted": True,
                             "claim": "structural presence only"})
        for node in observed:
            match = bool(revision) and node.get("revision") == revision
            evidence.append({"type": "observation", "node_id": node["id"],
                             "result": node["result"], "criteria_ids": node.get("criteria_ids", []),
                             "revision": node.get("revision"), "current_revision": match,
                             "provenance": node.get("provenance", "unattested_import"),
                             "claim": "reported test observation; execution provenance not independently attested"})
        records.append({"id": f"passport.{rid}", "requirement_id": rid,
                        "title": requirement["title"], "classification": finding["classification"],
                        "acceptance_criteria": requirement.get("acceptance_criteria", []),
                        "evidence": evidence,
                        "absence_refs": list(finding.get("evidence", [])) if finding["classification"] == "missing" else [],
                        "limits": ["No source code execution", "No independent run attestation",
                                   "Scope only covers mapped criteria and available evidence"]})
    payload = {"schema_version": SCHEMA, "created_at": now(), "revision": revision,
               "records": records, "authority": "informational_only",
               "notice": "An evidence passport is not a signed or independently verified provenance attestation."}
    payload["content_digest"] = digest({k: v for k, v in payload.items() if k != "content_digest"})
    return payload


def spec_conflicts(intent: dict) -> dict:
    """Detect only *explicit* logical conflicts and inconsistent shared criterion IDs.

    Natural-language contradiction detection is intentionally not claimed.
    """
    nodes = validate_nodes(intent, "intent-map", "intent")
    by_id = {n["id"]: n for n in nodes}
    contradictions, seen, criterion_owner = [], set(), {}
    for node in nodes:
        declarations = node.get("conflicts_with", [])
        if not isinstance(declarations, list):
            raise AuditError("conflicts_with must be an array of requirement IDs")
        for entry in declarations:
            _safe(entry, "conflicts_with")
            if entry == node["id"] or entry not in by_id:
                raise AuditError("conflicts_with must reference a different existing requirement")
            pair = tuple(sorted((node["id"], entry)))
            if pair not in seen:
                contradictions.append({"type": "declared_conflict", "requirements": list(pair),
                                       "reason": "Explicitly declared requirement conflict; review before approval"})
                seen.add(pair)
        for criterion in node.get("acceptance_criteria", []):
            cid = criterion["id"]
            earlier = criterion_owner.get(cid)
            if earlier and earlier["statement"] != criterion["statement"]:
                contradictions.append({"type": "criterion_id_collision", "criterion_id": cid,
                                       "requirements": [earlier["requirement_id"], node["id"]],
                                       "reason": "Same acceptance-criterion ID has different statements"})
            elif not earlier:
                criterion_owner[cid] = {"requirement_id": node["id"], "statement": criterion["statement"]}
    return {"schema_version": SCHEMA, "conflicts": contradictions, "count": len(contradictions),
            "limit": "Only declared conflicts and exact criterion-ID inconsistencies are detected."}


def apply_declared_conflicts(findings: dict, conflicts: dict) -> dict:
    """Classify explicit conflicts as review blockers without inventing contradictions.

    A conflict is a claim from the supplied requirement document, not a proof
    that the project's behavior is defective. The source findings are not mutated.
    """
    affected = {rid for item in conflicts.get("conflicts", [])
                for rid in item.get("requirements", [])}
    revised = []
    for original in findings.get("findings", []):
        item = dict(original)
        if item.get("requirement_id") in affected:
            item["classification"] = "spec_conflict"
            item["reason"] = "Explicit requirement conflict or criterion-ID collision; user must resolve the specification"
            item["evidence"] = list(item.get("evidence", []))
        revised.append(item)
    counts: dict[str, int] = {}
    for item in revised:
        status = item["classification"]
        counts[status] = counts.get(status, 0) + 1
    return {**findings, "findings": revised, "counts": dict(sorted(counts.items()))}


def add_conflict_plan_tasks(plan: dict, findings: dict) -> dict:
    """Ensure explicitly conflicting specs produce human-review tasks, never edits."""
    tasks = list(plan.get("tasks", []))
    for finding in findings.get("findings", []):
        if finding.get("classification") != "spec_conflict":
            continue
        tasks.append({"task_id": f"T-{len(tasks)+1:03}", "finding_id": finding["id"],
                      "type": "investigate", "title": "Resolve specification conflict: " + finding["title"],
                      "classification": "spec_conflict", "allowed_paths": [],
                      "dependencies": [], "risk": "unassessed",
                      "acceptance": "Product owner approves a consistent specification before implementing",
                      "approval_required": True})
    revised = {**plan, "tasks": tasks}
    revised["plan_digest"] = digest({k: v for k, v in revised.items() if k != "plan_digest"})
    return revised


def investigation_queue(findings: dict, intent: dict, candidate_links: dict | None = None) -> dict:
    """Suggest read-only steps that reduce uncertainty; never schedule/run tests."""
    reqs = {n["id"]: n for n in validate_nodes(intent, "intent-map", "intent")}
    candidates: dict[str, list[dict]] = {}
    if candidate_links is not None:
        for candidate in candidate_links.get("candidates", []):
            candidates.setdefault(candidate.get("requirement_id", ""), []).append(candidate)
    tasks = []
    for f in findings.get("findings", []):
        if f.get("classification") not in {"unknown", "unverified", "partial", "spec_conflict"}:
            continue
        rid = f.get("requirement_id")
        if rid not in reqs:
            continue
        state = reqs[rid].get("requirement_state")
        if state != "approved":
            step = "Resolve/approve this requirement independently of the codebase"
            proof = "Approved requirement with explicit acceptance criteria"
            priority = "high"
        elif f["classification"] == "spec_conflict":
            step = "Resolve explicitly conflicting requirements with the product owner before accepting implementation evidence"
            proof = "Non-contradictory approved requirement IDs and criteria"
            priority = "high"
        elif f["classification"] == "unknown":
            step = "Review candidate source links or document scoped absence; do not infer missing from search"
            proof = "Reviewed source-to-requirement link or justified exhaustive absence record"
            priority = "high"
        elif f["classification"] == "unverified":
            step = "Review criteria coverage and collect an authorized, revision-matched test observation"
            proof = "Test result linked to relevant acceptance criteria, exact revision and test provenance"
            priority = "high"
        else:
            step = "Review partial implementation and reconcile acceptance criteria"
            proof = "Reviewed implementation state and independent verification"
            priority = "medium"
        hints = [h for h in candidates.get(rid, [])
                 if isinstance(h, dict) and isinstance(h.get("implementation_id"), str)
                 and isinstance(h.get("heuristic_score", 0), (int, float))]
        hints.sort(key=lambda c: -c.get("heuristic_score", 0))
        hints = hints[:3]
        tasks.append({"id": f"investigate.{rid}", "requirement_id": rid,
                      "finding_id": f["id"], "classification": f["classification"],
                      "priority": priority, "question": f"What evidence is needed to resolve {rid}?",
                      "suggested_step": step, "required_evidence": proof,
                      "candidate_implementation_ids": [h["implementation_id"] for h in hints],
                      "requires_approval_for_execution": True,
                      "automatic_execution": False, "estimated_cost": "unknown",
                      "authority": "suggestion_only"})
    return {"schema_version": SCHEMA, "created_at": now(), "investigations": tasks,
            "notice": "Proposals only: no tests, models, or project code were executed."}


def assumption_debt(findings: dict, intent: dict) -> dict:
    reqs = {n["id"]: n for n in validate_nodes(intent, "intent-map", "intent")}
    items = []
    for f in findings.get("findings", []):
        rid = f.get("requirement_id")
        if rid not in reqs or (f["classification"] not in {"unknown", "unverified", "partial", "spec_conflict"}):
            continue
        items.append({"requirement_id": rid, "classification": f["classification"],
                      "unresolved_question": f.get("reason", "Unverified evidence"),
                      "approved": reqs[rid].get("requirement_state") == "approved",
                      "staleness": "not_assessed", "owner": None, "follow_up": "investigate." + rid})
    return {"schema_version": SCHEMA, "items": items, "total": len(items),
            "notice": "This is an uncertainty inventory, not proof that features are defective."}


def readiness_matrix(findings: dict) -> dict:
    records = []
    for f in findings.get("findings", []):
        if not f.get("requirement_id"):
            continue
        status = f["classification"]
        functional = "supported_by_current_evidence" if status == "complete" else "unverified" if status in {"unverified", "unknown"} else "needs_review"
        records.append({"requirement_id": f["requirement_id"], "functional": functional,
                        "security": "not_assessed", "performance": "not_assessed",
                        "accessibility": "not_assessed", "deployment": "not_assessed",
                        "note": "Functional evidence does not imply security or deployment readiness."})
    return {"schema_version": SCHEMA, "features": records,
            "notice": "Unassessed dimensions stay unassessed. No fabricated completeness score."}


def impact_preview(implementation: dict, links: dict, changed_paths: list[str]) -> dict:
    """Pure graph-based *possible* impact, not a prediction of defects."""
    impl = {n["id"]: n for n in validate_nodes(implementation, "implementation-map", "implementation")}
    edges = links.get("links", [])
    if not isinstance(edges, list):
        raise AuditError("links.links must be an array")
    paths = []
    for path in changed_paths:
        if not isinstance(path, str) or not path or "\\" in path or Path(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise AuditError("Changed paths must be safe repository-relative POSIX paths")
        paths.append(path)
    affected = []
    for edge in edges:
        if not isinstance(edge, dict):
            raise AuditError("links.links must contain objects")
        inode = impl.get(edge.get("implementation_id"))
        if not inode or edge.get("basis") not in {"reviewed", "explicit"}:
            continue
        locator = inode.get("locator", "")
        file = re.sub(r":\d+$", "", locator)
        if file in paths:
            affected.append({"requirement_id": edge.get("requirement_id"),
                             "implementation_id": inode["id"], "changed_path": file,
                             "claim": "potentially_affected", "certainty": "not_a_verified_regression"})
    return {"schema_version": SCHEMA, "changed_paths": sorted(set(paths)),
            "possible_impacts": affected, "coverage": "only explicitly reviewed implementation links",
            "notice": "Unlinked dependencies, dynamic behaviors, and external services are not included."}


def handoff_manifest(manifest: dict, produced_artifacts: dict[str, Path]) -> dict:
    """Hash artifacts without exposing their contents; never grants execution authority."""
    entries = []
    for name, file in sorted(produced_artifacts.items()):
        if not file.is_file() or file.is_symlink():
            raise AuditError("Cannot include missing or symlinked handoff artifact")
        if name != file.name or '/' in name or '\\' in name:
            raise AuditError("Unsafe handoff artifact name")
        sha = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
        entries.append({"name": name, "sha256": sha.hexdigest(), "size_bytes": file.stat().st_size})
    return {"schema_version": SCHEMA, "project_revision": manifest.get("project", {}).get("revision"),
            "created_at": now(), "artifacts": entries,
            "authority": "read_only_handoff", "execution_approved": False,
            "note": "Agent handoff metadata is not a user approval, signature or attestation."}


def draft_approval_capsule(plan: dict) -> dict:
    """Generate a *template* requiring a trusted host to collect and enforce consent."""
    if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list):
        raise AuditError("Valid remediation plan required")
    return {"schema_version": SCHEMA, "plan_digest": plan.get("plan_digest"),
            "base_revision": plan.get("base_revision"), "environment": plan.get("environment"),
            "candidate_tasks": [{"task_id": t["task_id"], "type": t["type"],
                                  "allowed_paths": t["allowed_paths"]} for t in plan["tasks"]],
            "approved_task_ids": [], "approved": False,
            "expires_at": None, "trusted_approval_provenance": None,
            "host_enforcement_required": True, "execution_authorized": False,
            "warning": "Untrusted template only. Filling this JSON is not user consent."}


def evaluation_summary(expected: dict[str, str], actual: dict[str, str]) -> dict:
    """Useful for reproducible, human-ground-truthed fixture evaluations."""
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        raise AuditError("Ground truth and predictions must be maps")
    if not expected:
        raise AuditError("Evaluation needs a nonempty, independently reviewed ground truth")
    for label, data in (("Ground truth", expected), ("Predictions", actual)):
        if any(not isinstance(k, str) or not _ID.fullmatch(k) or not isinstance(v, str) or v not in VALID_CLASSES
               for k, v in data.items()):
            raise AuditError(f"{label} must map stable requirement IDs to valid classifications")
    tp = sum(1 for key, val in expected.items() if val == "missing" and actual.get(key) == "missing")
    fp = sum(1 for key, val in actual.items() if val == "missing" and expected.get(key) != "missing")
    fn = sum(1 for key, val in expected.items() if val == "missing" and actual.get(key) != "missing")
    false_complete = sum(1 for key, val in actual.items() if val == "complete" and expected.get(key) != "complete")
    return {"schema_version": SCHEMA, "evaluated_requirements": len(expected),
            "missing_precision": tp / (tp + fp) if tp + fp else None,
            "missing_recall": tp / (tp + fn) if tp + fn else None,
            "false_completion_count": false_complete,
            "ungraded_predictions": sorted(set(actual) - set(expected)),
            "warning": "Scores only assess supplied independently labeled fixture IDs."}


def verify_handoff(out: Path, handoff: dict) -> dict:
    """Check file bytes and refuse traversal/symlinks; never interpret as approval."""
    entries = handoff.get("artifacts")
    if handoff.get("authority") != "read_only_handoff" or not isinstance(entries, list):
        raise AuditError("Not a MirrorMap read-only handoff")
    root = out.expanduser().resolve()
    checked, errors, seen = 0, [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise AuditError("Handoff entries must be objects")
        name, expected = entry.get("name"), entry.get("sha256")
        if (not isinstance(name, str) or not name or name in {".", ".."}
                or "/" in name or "\\" in name or name in seen
                or not isinstance(expected, str) or not _SHA256.fullmatch(expected)):
            raise AuditError("Unsafe or invalid handoff artifact metadata")
        seen.add(name)
        path = root / name
        if path.is_symlink() or not path.is_file():
            errors.append({"name": name, "problem": "missing_or_symlink"})
            continue
        size = path.stat().st_size
        if size != entry.get("size_bytes"):
            errors.append({"name": name, "problem": "size_mismatch"})
            continue
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
        if sha.hexdigest() != expected:
            errors.append({"name": name, "problem": "digest_mismatch"})
            continue
        checked += 1
    return {"schema_version": SCHEMA, "valid": not errors,
            "checked_files": checked, "total_files": len(entries), "errors": errors,
            "notice": "Digest verification establishes byte integrity only; it does not establish origin, trust, or user approval."}


def freshness_report(verification: dict, manifest: dict) -> dict:
    """Revision-level freshness, not a statement that deployed behavior is current."""
    nodes = validate_nodes(verification, "verification-map", "verification")
    current = manifest.get("project", {}).get("revision")
    records = []
    for node in nodes:
        revision = node.get("revision")
        status = ("unknown" if not revision or not current else
                  "revision_matched" if revision == current else "stale_revision")
        records.append({"verification_id": node["id"], "requirement_id": node["requirement_id"],
                        "reported_result": node["result"], "revision": revision,
                        "freshness": status, "execution_attested": False})
    return {"schema_version": SCHEMA, "project_revision": current,
            "observations": records,
            "notice": "Revision matches do not prove run provenance, deployment parity, or behavioral correctness."}


def behavior_journeys(source: dict, intent: dict, verification: dict, manifest: dict) -> dict:
    """Import bounded, user-supplied journey steps without executing or inventing tests.

    Passing *reported* observations remain reported claims; this report does not
    change feature classifications and cannot make an unreviewed link authoritative.
    """
    if not isinstance(source, dict) or source.get("schema_version") != SCHEMA:
        raise AuditError("Journey input requires schema_version 1.0")
    journeys = source.get("journeys")
    if not isinstance(journeys, list) or len(journeys) > 100:
        raise AuditError("Journeys must be an array of at most 100 entries")
    known = {n["id"] for n in validate_nodes(intent, "intent-map", "intent")}
    tests = {n["id"]: n for n in validate_nodes(verification, "verification-map", "verification")}
    current = manifest.get("project", {}).get("revision")
    used = set()
    assembled = []
    count = 0
    for item in journeys:
        if (not isinstance(item, dict) or not isinstance(item.get("title"), str)
                or not item["title"].strip() or len(item["title"]) > 300):
            raise AuditError("Every journey needs a title")
        jid = _safe(item.get("id"), "Journey")
        if jid in used:
            raise AuditError("Duplicate journey ID")
        used.add(jid)
        steps = item.get("steps")
        if not isinstance(steps, list) or not steps:
            raise AuditError("Every journey needs a nonempty steps array")
        count += len(steps)
        if count > 2000:
            raise AuditError("Too many journey steps (2000 maximum)")
        processed, step_ids = [], set()
        for step in steps:
            if not isinstance(step, dict):
                raise AuditError("Journey steps must be objects")
            sid = _safe(step.get("id"), "Journey step")
            if sid in step_ids:
                raise AuditError("Duplicate step ID inside journey")
            step_ids.add(sid)
            description = step.get("description")
            if not isinstance(description, str) or not description.strip() or len(description) > 2000:
                raise AuditError("Journey step needs a description")
            rid = step.get("requirement_id")
            if rid is not None and rid not in known:
                raise AuditError("Journey step refers to unknown requirement")
            linked = step.get("verification_ids", [])
            if not isinstance(linked, list) or any(not isinstance(x, str) or x not in tests for x in linked):
                raise AuditError("Journey verification_ids must reference imported observations")
            if len(linked) != len(set(linked)):
                raise AuditError("Duplicate verification ID in journey step")
            if rid and any(tests[x]["requirement_id"] != rid for x in linked):
                raise AuditError("Journey evidence must refer to the same requirement as its step")
            observed = [tests[x] for x in linked]
            matched = [x for x in observed if current and x.get("revision") == current and x.get("evidence")]
            state = ("reported_failure" if any(x["result"] in {"failed", "mismatch"} for x in matched) else
                     "reported_pass" if matched and len(matched) == len(linked) and all(x["result"] == "passed" for x in matched) else
                     "unverified")
            processed.append({"id": sid, "description": description,
                              "requirement_id": rid, "verification_ids": linked,
                              "status": state})
        assembled.append({"id": jid, "title": item["title"], "steps": processed})
    return {"schema_version": SCHEMA, "project_revision": current,
            "journeys": assembled, "total_steps": count,
            "authority": "user_supplied_mapping_only",
            "notice": "No browser or app code was executed. Reported outcomes are not independently attested, and journey outcomes do not automatically change requirement classifications."}
