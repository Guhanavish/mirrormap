"""Pure, dependency-free ProjectMirror auditing and report primitives.

No function in this module mutates the audited project. Outputs are placed in a
separate directory by the CLI.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "1.0"
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".next", ".nuxt", "dist", "build", "coverage", "venv", ".venv", "__pycache__", ".projectmirror", ".terraform", "target", ".cache"}
SECRET_NAMES = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials.json", "secrets.json", "settings.local.json"}
SOURCE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".html", ".vue", ".svelte", ".json"}
MAX_SOURCE_BYTES = 512_000
VALID_RESULTS = {"passed", "failed", "mismatch", "not_run", "inconclusive", "blocked", "stale"}
VALID_INTENT_STATES = {"approved", "draft", "inferred", "conflicted", "deprecated"}
VALID_IMPL_STATES = {"present", "partial", "absent_confirmed", "unknown", "inaccessible"}
VALID_CLASSES = {"complete", "missing", "partial", "broken", "mismatch", "unverified", "unknown", "undocumented", "spec_conflict"}
ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,160}$")


class AuditError(ValueError):
    """Actionable user/input error."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def load(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as ex:
        raise AuditError(f"Cannot read valid JSON at {path}: {ex}") from ex
    if not isinstance(obj, dict):
        raise AuditError(f"Expected a JSON object in {path}")
    return obj


def save(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def ensure_output(repo: Path, out: Path) -> Path:
    repo, out = repo.resolve(), out.resolve()
    if not repo.is_dir():
        raise AuditError(f"Repository directory does not exist: {repo}")
    if out == repo or repo in out.parents:
        raise AuditError("Audit output must be OUTSIDE the audited repository to protect read-only mode")
    return out


def git_info(repo: Path) -> tuple[str | None, str | None]:
    def run(*cmd: str) -> str | None:
        try:
            proc = subprocess.run(["git", "-C", str(repo), *cmd], capture_output=True, text=True, timeout=5, check=False)
            return proc.stdout.strip() if proc.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    return run("rev-parse", "HEAD"), run("branch", "--show-current")


def manifest(repo: Path) -> dict:
    sha, branch = git_info(repo)
    return {"schema_version": SCHEMA, "created_at": now(), "project": {"repo": str(repo.resolve()), "revision": sha, "branch": branch, "environment": "source"}, "scan": {"scope": "repository", "coverage": "not_scanned"}}


def validate_nodes(obj: dict, name: str, expected_map: str) -> list[dict]:
    if obj.get("schema_version") != SCHEMA:
        raise AuditError(f"{name}: unsupported schema_version (expected {SCHEMA})")
    nodes = obj.get("nodes")
    if not isinstance(nodes, list):
        raise AuditError(f"{name}: 'nodes' must be an array")
    seen = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not ID_RE.fullmatch(node["id"]):
            raise AuditError(f"{name}: each node requires a valid stable ID")
        if node["id"] in seen:
            raise AuditError(f"{name}: duplicate node ID {node['id']}")
        seen.add(node["id"])
        if node.get("map") != expected_map:
            raise AuditError(f"{name}: {node['id']} must have map={expected_map}")
        if not isinstance(node.get("title"), str) or not node["title"].strip():
            raise AuditError(f"{name}: {node['id']} needs a title")
        if expected_map == "intent":
            if node.get("requirement_state", "draft") not in VALID_INTENT_STATES:
                raise AuditError(f"{name}: {node['id']} has an invalid requirement state")
            criteria = node.get("acceptance_criteria", [])
            if not isinstance(criteria, list) or any(not isinstance(c, dict) or not isinstance(c.get("id"), str) for c in criteria):
                raise AuditError(f"{name}: {node['id']} has invalid acceptance criteria")
            ids = [c["id"] for c in criteria]
            if len(ids) != len(set(ids)):
                raise AuditError(f"{name}: {node['id']} has duplicate acceptance criterion IDs")
        elif expected_map == "implementation":
            if node.get("implementation_state", "present") not in VALID_IMPL_STATES:
                raise AuditError(f"{name}: {node['id']} has an invalid implementation state")
        elif expected_map == "verification":
            if node.get("result") not in VALID_RESULTS:
                raise AuditError(f"{name}: {node['id']} has invalid verification result")
            if not isinstance(node.get("evidence", []), list) or any(not isinstance(e, str) for e in node.get("evidence", [])):
                raise AuditError(f"{name}: {node['id']} evidence must be a list of strings")
            if not isinstance(node.get("criteria_ids", []), list) or any(not isinstance(c, str) for c in node.get("criteria_ids", [])):
                raise AuditError(f"{name}: {node['id']} criteria_ids must be a list of strings")
    return nodes


def parse_spec(path: Path, state: str = "draft") -> dict:
    """Extract explicit, ID-tagged requirements only. Never invent from prose.

    Format: '- [REQ.auth.login] User can log in' (optional criteria as
    indented '- [AC.auth.login.valid] ...' on the following lines).
    """
    if state not in {"draft", "approved"}:
        raise AuditError("Intent state must be draft or approved")
    if path.suffix.lower() == ".json":
        obj = load(path)
        validate_nodes(obj, "intent-map", "intent")
        return obj
    text = path.read_text(encoding="utf-8")
    nodes, latest, seen = [], None, set()
    req = re.compile(r"^\s*[-*]\s+\[(REQ[.\w-]+)\]\s+(.+?)\s*$", re.I)
    ac = re.compile(r"^\s+[-*]\s+\[(AC[.\w-]+)\]\s+(.+?)\s*$", re.I)
    for line_no, line in enumerate(text.splitlines(), 1):
        m = req.match(line)
        if m:
            rid, title = m.groups()
            if rid in seen:
                raise AuditError(f"Duplicate requirement ID {rid} in {path}")
            seen.add(rid)
            latest = {"id": rid, "map": "intent", "kind": "requirement", "title": title.strip(), "requirement_state": state, "acceptance_criteria": [], "source_refs": [f"{path.name}:{line_no}"]}
            nodes.append(latest)
        else:
            c = ac.match(line)
            if c and latest:
                aid, statement = c.groups()
                latest["acceptance_criteria"].append({"id": aid, "statement": statement.strip()})
    if not nodes:
        raise AuditError("No explicit requirements found. Use '- [REQ.feature] Description' lines or provide intent-map JSON; no requirements were invented")
    obj = {"schema_version": SCHEMA, "source": str(path.resolve()), "nodes": nodes}
    validate_nodes(obj, "intent-map", "intent")
    return obj


def ignored(rel: Path) -> bool:
    parts = rel.parts
    if any(part in SKIP_DIRS for part in parts):
        return True
    if any(part in SECRET_NAMES or part.startswith(".env.") for part in parts):
        return True
    if any(part.endswith(('.pem', '.key', '.p12', '.pfx', '.sqlite', '.db', '.lock')) for part in parts):
        return True
    return False


def index_repo(repo: Path, max_files: int = 12000) -> tuple[dict, dict]:
    from .frameworks import framework_route_candidates
    repo = repo.resolve()
    nodes, evidence, scanned, skipped, errors = [], [], 0, 0, []
    route_candidates = 0
    for root, dirs, files in os.walk(repo, followlinks=False):
        base = Path(root)
        dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink() and not ignored((base / d).relative_to(repo)))
        for name in sorted(files):
            path = base / name
            rel = path.relative_to(repo)
            if path.is_symlink() or ignored(rel) or path.suffix.lower() not in SOURCE_EXTS:
                skipped += 1
                continue
            if scanned >= max_files:
                errors.append(f"Max file limit ({max_files}) reached; inventory incomplete")
                break
            try:
                data = path.read_bytes()
                if len(data) > MAX_SOURCE_BYTES or b"\0" in data:
                    skipped += 1
                    continue
                # Parse only the file types we can support. Never expose contents.
                source = data.decode("utf-8")
            except (OSError, UnicodeError) as ex:
                errors.append(f"{rel.as_posix()}: {type(ex).__name__}")
                continue
            scanned += 1
            identifier = hashlib.sha256(rel.as_posix().encode()).hexdigest()[:16]
            node_id = f"impl.file.{identifier}"
            evidence_id = f"ev.code.{identifier}"
            nodes.append({"id": node_id, "map": "implementation", "kind": "file", "title": rel.as_posix(), "locator": rel.as_posix(), "implementation_state": "present", "source_refs": [evidence_id]})
            evidence.append({"id": evidence_id, "kind": "source_file", "uri": rel.as_posix(), "content_hash": hashlib.sha256(data).hexdigest()})
            routes = framework_route_candidates(rel, source, evidence_id)
            nodes.extend(routes)
            route_candidates += len(routes)
            if path.suffix.lower() == ".py":
                try:
                    tree = ast.parse(source)
                    syms = [(x.name, type(x).__name__, x.lineno) for x in tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                except SyntaxError:
                    errors.append(f"{rel.as_posix()}: Python syntax parse failed")
                    syms = []
                for symbol, kind, line in syms:
                    sid = hashlib.sha256((rel.as_posix()+":"+symbol).encode()).hexdigest()[:16]
                    nodes.append({"id": f"impl.symbol.{sid}", "map": "implementation", "kind": kind.lower(), "title": symbol, "locator": f"{rel.as_posix()}:{line}", "implementation_state": "present", "source_refs": [evidence_id]})
            elif path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
                # Heuristic only, NOT a full JavaScript/TypeScript parser.
                for match in re.finditer(r"(?m)^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let)\s+([A-Za-z_$][\w$]*)", source):
                    symbol = match.group(1)
                    sid = hashlib.sha256((rel.as_posix()+":"+symbol).encode()).hexdigest()[:16]
                    line = source.count("\n", 0, match.start()) + 1
                    nodes.append({"id": f"impl.symbol.{sid}", "map": "implementation", "kind": "export_heuristic", "title": symbol, "locator": f"{rel.as_posix()}:{line}", "implementation_state": "present", "source_refs": [evidence_id]})
        if scanned >= max_files:
            break
    return ({"schema_version": SCHEMA, "nodes": nodes, "evidence": evidence},
            {"scope": "repository", "coverage": "structural_only", "scanned_files": scanned, "skipped_files": skipped, "errors": errors, "max_files": max_files, "route_candidates": route_candidates,
             "route_limitations": "Candidates are static declarations/path conventions, not deployed behavior."})


def compare(intent: dict, implementation: dict, verification: dict, links: dict, absence: dict, manifest_obj: dict) -> dict:
    reqs = validate_nodes(intent, "intent-map", "intent")
    impls = validate_nodes(implementation, "implementation-map", "implementation")
    tests = validate_nodes(verification, "verification-map", "verification")
    by_impl = {n["id"]: n for n in impls}
    by_req = {n["id"]: n for n in reqs}
    edges = links.get("links", [])
    if not isinstance(edges, list):
        raise AuditError("links.links must be an array")
    mapped: dict[str, list[dict]] = {k: [] for k in by_req}
    mapped_impl = set()
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("requirement_id") not in by_req or edge.get("implementation_id") not in by_impl:
            raise AuditError(f"Invalid link: {edge}")
        if edge.get("basis") not in {"reviewed", "explicit"}:
            raise AuditError("Links must be explicitly reviewed, not auto-guessed")
        mapped[edge["requirement_id"]].append(by_impl[edge["implementation_id"]])
        mapped_impl.add(edge["implementation_id"])
    observed: dict[str, list[dict]] = {k: [] for k in by_req}
    for test in tests:
        if test.get("requirement_id") not in by_req:
            raise AuditError(f"Verification {test['id']} references unknown requirement")
        if test.get("result") not in VALID_RESULTS:
            raise AuditError(f"Invalid verification result for {test['id']}")
        observed[test["requirement_id"]].append(test)
    absent = {}
    for a in absence.get("confirmations", []):
        if not isinstance(a, dict) or a.get("requirement_id") not in by_req:
            raise AuditError("Invalid absence confirmation")
        if a.get("reviewed") is True and a.get("coverage") == "exhaustive" and a.get("evidence"):
            absent[a["requirement_id"]] = a
    rev = manifest_obj.get("project", {}).get("revision")
    findings = []
    for r in reqs:
        rid = r["id"]
        status = r.get("requirement_state", "draft")
        matches = mapped[rid]
        ver = observed[rid]
        valid_ver = [v for v in ver if v.get("revision") == rev and rev and v.get("evidence") and v.get("result") not in {"stale", "not_run", "blocked"}]
        criteria = {x.get("id") for x in r.get("acceptance_criteria", []) if isinstance(x, dict) and x.get("id")}
        if status == "conflicted":
            classification, reason = "spec_conflict", "Contradictory requirements require user resolution"
        elif status != "approved":
            classification, reason = "unknown", "Requirement is not user-approved; not counted as a confirmed gap"
        elif any(v["result"] == "failed" for v in valid_ver):
            classification, reason = "broken", "Current, evidenced verification reports a failure"
        elif any(v["result"] == "mismatch" for v in valid_ver):
            classification, reason = "mismatch", "Current, evidenced verification contradicts accepted behavior"
        elif any(x.get("implementation_state") == "absent_confirmed" for x in matches) or rid in absent:
            classification, reason = "missing", "Reviewed, scoped evidence supports absence"
        elif any(x.get("implementation_state") == "partial" for x in matches):
            classification, reason = "partial", "Mapped implementation is explicitly recorded as partial"
        elif not matches:
            classification, reason = "unknown", "No reviewed implementation link; absence is not established"
        elif any(x.get("implementation_state") in {"unknown", "inaccessible"} for x in matches):
            classification, reason = "unknown", "Implementation evidence is insufficient or inaccessible"
        elif criteria and all(any(v["result"] == "passed" and c in v.get("criteria_ids", []) for v in valid_ver) for c in criteria):
            classification, reason = "complete", "All explicitly identified acceptance criteria have current passing evidence"
        else:
            classification, reason = "unverified", "Implementation exists but relevant current passing checks are missing or incomplete"
        findings.append({"id": f"F-{rid}", "requirement_id": rid, "title": r["title"], "classification": classification, "reason": reason, "implementation_ids": [n["id"] for n in matches], "verification_ids": [n["id"] for n in ver], "evidence": absent.get(rid, {}).get("evidence", []) + [e for v in ver for e in v.get("evidence", [])], "scope": "approved" if status == "approved" else "non_approved"})
    # File inventory is not automatically 'undocumented behavior'. Restrict the
    # reverse check to explicit capability nodes, avoiding thousands of false positives.
    for item in impls:
        if item.get("kind") in {"feature", "capability", "endpoint"} and item["id"] not in mapped_impl:
            findings.append({"id": f"F-{item['id']}", "requirement_id": None, "title": item["title"], "classification": "undocumented", "reason": "Discovered capability has no reviewed requirement mapping; may be intentional", "implementation_ids": [item["id"]], "verification_ids": [], "evidence": item.get("source_refs", []), "scope": "reverse"})
    count = Counter(f["classification"] for f in findings)
    return {"schema_version": SCHEMA, "revision": rev, "counts": dict(sorted(count.items())), "findings": findings, "generated_at": now()}


def create_plan(findings: dict, manifest_obj: dict, implementation: dict) -> dict:
    index = {x["id"]: x for x in implementation.get("nodes", [])}
    tasks = []
    for f in findings["findings"]:
        kind = f["classification"]
        if kind not in {"broken", "mismatch", "missing", "partial", "unverified", "unknown"}:
            continue
        investigate = kind in {"unverified", "unknown"}
        # Investigation is read-only, even if its evidence points to source files.
        paths = [] if investigate else sorted({index[i].get("locator", "").split(":")[0] for i in f["implementation_ids"] if i in index and index[i].get("locator")})
        tasks.append({"task_id": f"T-{len(tasks)+1:03}", "finding_id": f["id"], "type": "investigate" if investigate else "remediate", "title": ("Investigate: " if investigate else "Address: ") + f["title"], "classification": kind, "allowed_paths": paths, "dependencies": [], "risk": "unassessed", "acceptance": "Provide reproducible evidence, then rerun the audit" if investigate else "Satisfy approved acceptance criteria and rerun relevant checks", "approval_required": True})
    base = {"schema_version": SCHEMA, "base_revision": manifest_obj.get("project", {}).get("revision"), "environment": manifest_obj.get("project", {}).get("environment", "source"), "tasks": tasks}
    base["plan_digest"] = digest(base)
    return base


def escape_mermaid(label: str) -> str:
    return re.sub(r"[\[\]{}()<>\"`|]", "", label).replace("\\", "/").replace("\n", " ")[:110]


def render(findings: dict, limit: int = 80) -> str:
    lines = ["flowchart TD", "    root[\"PROJECT MIRROR · Audit Overview\"]"]
    palette = {"complete": "ok", "missing": "bad", "broken": "bad", "mismatch": "bad", "partial": "warn", "unverified": "unknown", "unknown": "unknown", "spec_conflict": "warn", "undocumented": "extra"}
    for i, finding in enumerate(findings["findings"][:limit]):
        status = finding["classification"]
        label = escape_mermaid(finding["title"])
        lines.append(f'    n{i}["{status.upper()} · {label}"]')
        lines.append(f'    root --> n{i}')
        lines.append(f'    class n{i} {palette.get(status, "unknown")}')
    lines.extend(['    classDef ok fill:#e4f6ec,stroke:#268760,color:#164936', '    classDef bad fill:#fff1f0,stroke:#d74d48,color:#78302d', '    classDef warn fill:#fff5db,stroke:#b37a1c,color:#6b480c', '    classDef unknown fill:#eff2f6,stroke:#7a8795,color:#394452', '    classDef extra fill:#f2ecfa,stroke:#8964b0,color:#514069'])
    if len(findings["findings"]) > limit:
        lines.append(f'    more["... {len(findings["findings"])-limit} more findings; see audit-report.md"]')
        lines.append('    root --> more')
    return "\n".join(lines) + "\n"


def markdown_report(findings: dict, manifest_obj: dict) -> str:
    info = manifest_obj.get("project", {})
    lines = ["# ProjectMirror · Audit Report", "", f"**Repository:** `{info.get('repo', '(unknown)')}`", f"**Revision:** `{info.get('revision') or 'unversioned'}`", f"**Environment:** `{info.get('environment', 'source')}`", "", "> This is an evidence-limited audit, not a guarantee that the project is free of defects.", "", "## Results", "", "| Classification | Count |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in findings["counts"].items()]
    lines += ["", "## Findings", "", "| ID | Classification | Requirement / capability | Evidence status |", "|---|---|---|---|"]
    for f in findings["findings"]:
        title = f["title"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{f['id']}` | {f['classification']} | {title} | {len(f['evidence'])} reference(s) |")
    lines += ["", "## Caveats", "", "- Unlinked requirements are **unknown**, not automatically missing.", "- A repository index proves only the inspected structure, not user-visible behavior.", "- Passing checks support only their stated acceptance criteria.", "- Draft requirements are not treated as approved product scope.", "- No application files were changed by the audit engine.", ""]
    return "\n".join(lines)


def markdown_plan(plan: dict) -> str:
    rows = ["# ProjectMirror · Proposed Remediation Plan", "", f"**Base revision:** `{plan.get('base_revision') or 'unversioned'}`", f"**Plan digest:** `{plan['plan_digest']}`", "", "> REVIEW ONLY. Checked items are **not** authorization to execute. Approve task IDs explicitly in a trusted user interface before any project changes.", ""]
    for t in plan["tasks"]:
        rows += [f"### [ ] {t['task_id']} · {t['title']}", "", f"- Finding: `{t['finding_id']}` ({t['classification']})", f"- Action: {t['type']}", f"- Proposed file scope: {', '.join('`'+p+'`' for p in t['allowed_paths']) if t['allowed_paths'] else 'Not determined — requires review'}", f"- Acceptance: {t['acceptance']}", f"- Risk: {t['risk']} (requires assessment)", ""]
    rows += ["## Approval", "", "An explicit approval should identify **plan digest**, **task IDs**, **base revision**, and the permitted environment. A model-generated JSON approval file does not represent trusted user authorization.", ""]
    return "\n".join(rows)


def check_receipt(plan: dict, receipt: dict, manifest_obj: dict, paths: list[str]) -> None:
    original = {k: v for k, v in plan.items() if k != "plan_digest"}
    if plan.get("plan_digest") != digest(original):
        raise AuditError("Plan digest does not match contents; plan may have changed")
    if not plan.get("base_revision") or plan["base_revision"] != manifest_obj.get("project", {}).get("revision"):
        raise AuditError("Base revision is missing or mismatched")
    if receipt.get("plan_digest") != plan["plan_digest"] or receipt.get("base_revision") != plan["base_revision"]:
        raise AuditError("Approval receipt does not match plan digest / base revision")
    if receipt.get("environment") != plan.get("environment"):
        raise AuditError("Approval environment mismatch")
    if not receipt.get("actor") or not receipt.get("approved_at"):
        raise AuditError("Approval must have actor and timestamp")
    ids = receipt.get("approved_task_ids")
    if not isinstance(ids, list) or not ids:
        raise AuditError("No approved tasks")
    valid = {t["task_id"]: t for t in plan["tasks"]}
    if any(i not in valid for i in ids):
        raise AuditError("Receipt names unknown task ID")
    allowed = {p for i in ids if valid[i].get("type") == "remediate" for p in valid[i]["allowed_paths"]}
    for p in paths:
        pure = Path(p)
        if pure.is_absolute() or ".." in pure.parts or p not in allowed:
            raise AuditError(f"Changed path not in explicitly approved task scope: {p}")
