"""Conservative, bounded local analysis. No code execution or automatic edits."""
from __future__ import annotations
import ast
import re
import os
from pathlib import Path, PurePosixPath
from collections import deque

from . import relay
from .core import AuditError, ignored, MAX_SOURCE_BYTES, load, VALID_CLASSES
from .bolt_memory import safe_path, workspace, guardian
from .intelligence import verify_handoff, impact_preview


def audit_data(repo, directory):
    root = workspace(repo)
    directory = Path(directory).expanduser().resolve()
    if directory == root or root in directory.parents:
        raise AuditError("Audit data must be outside the project")
    def read(name):
        p = directory / name
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 16_000_000:
            raise AuditError("Invalid audit artifact: " + name)
        data = load(p)
        if not isinstance(data, dict):
            raise AuditError("Audit artifact must be an object")
        return data
    manifest = read("audit-manifest.json")
    handoff = read("audit-handoff.json")
    if manifest.get("project", {}).get("repo") != str(root):
        raise AuditError("Audit belongs to a different workspace")
    # Validate every listed file before digesting; prevent unbounded file reads.
    entries=handoff.get("artifacts")
    if not isinstance(entries,list) or len(entries)>200:
        raise AuditError("Invalid or oversized audit artifact list")
    for entry in entries:
        if not isinstance(entry, dict):
            raise AuditError("Invalid handoff entry")
        name = entry.get("name")
        if not isinstance(name, str) or "/" in name or "\\" in name or name in {"", ".", ".."}:
            raise AuditError("Unsafe artifact path")
        p = directory / name
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 16_000_000:
            raise AuditError("Invalid or oversized handoff artifact")
    checked = verify_handoff(directory, handoff)
    names = {x["name"] for x in handoff["artifacts"]}
    required = {"audit-manifest.json", "findings.json"}
    if not checked["valid"] or not required <= names:
        raise AuditError("Audit artifact integrity is insufficient")
    findings = read("findings.json")
    if findings.get("revision") != manifest["project"].get("revision"):
        raise AuditError("Audit revision mismatch")
    rows = findings.get("findings")
    if not isinstance(rows, list) or any(not isinstance(f, dict) or f.get("classification") not in VALID_CLASSES for f in rows):
        raise AuditError("Malformed findings")
    return root, manifest, findings, names, read


def completion_gate(repo, directory):
    root, manifest, findings, _, _ = audit_data(repo, directory)
    snapshot = relay.workspace_snapshot(root)
    revision = manifest["project"].get("revision")
    approved = [f for f in findings["findings"] if f.get("scope") == "approved"]
    unresolved = [f for f in findings["findings"] if f.get("requirement_id") and f["classification"] != "complete"]
    current_clean = bool(revision and snapshot["git_available"] and snapshot["head"] == revision
                         and not snapshot["changed"] and not snapshot["truncated"])
    capture=manifest.get("bolt_capture",{})
    capture_matches=(capture.get("before")==snapshot and capture.get("after")==snapshot)
    return {"status": "recorded_evidence_ready_for_review" if current_clean and capture_matches and approved and not unresolved else "review_required",
            "approved_count": len(approved), "unresolved": unresolved, "current_clean_revision": current_clean,
            "capture_snapshot_matches":capture_matches,
            "execution_authorized": False, "completion_certified": False,
            "notice": "Reviewed artifact bytes and recorded clean snapshots only; old audits without capture snapshots require review. Tests, origin and functional behavior are not independently attested."}


def regression(repo, before, after):
    _, bm, bf, _, _ = audit_data(repo, before)
    _, am, af, _, _ = audit_data(repo, after)
    old = {f["requirement_id"]: f for f in bf["findings"] if f.get("requirement_id")}
    new = {f["requirement_id"]: f for f in af["findings"] if f.get("requirement_id")}
    changes = []
    for rid, row in old.items():
        current = new.get(rid)
        if row["classification"] == "complete" and (not current or current["classification"] != "complete"):
            changes.append({"requirement": rid, "before": "complete",
                            "after": current["classification"] if current else "not_in_new_audit",
                            "classification": "possible_regression_or_evidence_loss"})
    return {"baseline_revision": bm["project"].get("revision"), "current_revision": am["project"].get("revision"),
            "candidates": changes, "execution_authorized": False, "regression_proven": False}


def _sources(root, limit):
    count = 0
    incomplete = False
    files = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (base/d).is_symlink() and not ignored((base/d).relative_to(root)))
        for name in sorted(names):
            path = base/name
            rel = path.relative_to(root)
            if path.is_symlink() or ignored(rel) or path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".html"}:
                continue
            if count >= limit:
                return files, True
            count += 1
            try:
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    incomplete = True
                    continue
                files[rel.as_posix()] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                incomplete = True
    return files, incomplete


def dependencies(repo, changed, hops=2, limit=2000, audit=None):
    root = workspace(repo)
    if not 1 <= hops <= 3 or not 1 <= limit <= 5000:
        raise AuditError("Dependency bounds exceeded")
    changed = list(dict.fromkeys(safe_path(x) for x in changed))
    if not changed or len(changed) > 100:
        raise AuditError("Provide 1–100 changed paths")
    files, incomplete = _sources(root, limit)
    available = set(files) | set(changed)
    reverse = {}
    def add(source, target):
        if target in available and source != target:
            reverse.setdefault(target, set()).add(source)
    for name, source in files.items():
        path = PurePosixPath(name)
        if path.suffix == ".py":
            try:
                tree = ast.parse(source)
            except (SyntaxError, ValueError, RecursionError):
                incomplete = True
                continue
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [x.name.replace(".", "/") for x in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = path.parent
                    if node.level:
                        for _ in range(node.level-1):
                            base = base.parent
                        prefix = str(base / (node.module or "").replace(".", "/"))
                    else:
                        prefix = (node.module or "").replace(".", "/")
                    modules = [prefix] + [prefix.rstrip("/")+"/"+x.name for x in node.names]
                for module in modules:
                    module=os.path.normpath(module).replace("\\","/")
                    add(name, module+".py")
                    add(name, module+"/__init__.py")
        elif path.suffix in {".js",".jsx",".ts",".tsx"}:
            for match in re.finditer(r"""(?:\bfrom\s*|\bimport\s*|\brequire\s*\(\s*)['"](\.[^'"]+)['"]""", source):
                # Pure normalization without following symlinks or reading target files.
                target = os.path.normpath(str(path.parent / match.group(1))).replace("\\","/")
                for suffix in ("", ".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts"):
                    add(name, target+suffix)
    visited = set(changed)
    queue = deque((p, 0) for p in changed)
    impacted = []
    while queue:
        path, distance = queue.popleft()
        if distance == hops:
            continue
        for parent in sorted(reverse.get(path, ())):
            if parent not in visited:
                visited.add(parent)
                impacted.append({"path": parent, "distance": distance+1, "via": path})
                queue.append((parent, distance+1))
    result={"changed": changed, "possible_dependents": impacted, "scan_incomplete": incomplete,
            "scanned_files": len(files), "max_hops": hops, "execution_authorized": False,
            "notice": "Static Python imports and JS/TS relative import heuristics only; dynamic imports, aliases and runtime behavior may be missed."}
    if audit is not None:
        _, manifest, _, names, read=audit_data(root,audit)
        if not {"implementation-map.json","links.json"} <= names:
            raise AuditError("Audit lacks digest-verified implementation map or reviewed links")
        result["reviewed_requirement_impacts"]=impact_preview(read("implementation-map.json"),
                                                               read("links.json"),sorted(visited))
        result["mapping_revision"]=manifest["project"].get("revision")
        result["mapping_revision_matches_head"]=result["mapping_revision"]==relay.workspace_snapshot(root).get("head")
    return result


def dead_features(repo, limit=2000):
    root = workspace(repo)
    if not 1 <= limit <= 5000:
        raise AuditError("Invalid scan limit")
    files, incomplete = _sources(root, limit)
    hits = []
    for path, source in files.items():
        if Path(path).suffix not in {".html",".jsx",".tsx"}:
            continue
        for match in re.finditer(r"<button\b([^<>]{0,1000})>", source, re.I):
            attrs = match.group(1)
            if not re.search(r"\b(?:onClick|onclick|form|disabled|data-[\w-]+)\b|\btype\s*=\s*['\"]submit['\"]", attrs):
                hits.append({"path": path, "line": source.count("\n",0,match.start())+1,
                             "kind": "button_without_visible_local_handler", "status": "candidate_only"})
                if len(hits) >= 200:
                    return {"candidates": hits, "scan_incomplete": True, "execution_authorized": False}
    return {"candidates": hits, "scan_incomplete": incomplete, "execution_authorized": False,
            "notice": "Static candidates only; forms, delegated handlers, frameworks and runtime wiring can make these buttons functional."}


def rollback_preview(repo, revision, paths):
    root = workspace(repo)
    if not isinstance(revision, str) or not re.fullmatch(r"[a-fA-F0-9]{7,64}", revision):
        raise AuditError("Supply a commit hash, not a command or Git expression")
    full = relay._git(root, "rev-parse", "--verify", revision+"^{commit}")
    if not full:
        raise AuditError("Commit not found")
    paths = list(dict.fromkeys(safe_path(x) for x in paths))
    if not paths or len(paths)>100:
        raise AuditError("Provide 1–100 explicit paths")
    # Literal pathspecs prevent glob or magic expansion.
    raw = relay._git(root, "--literal-pathspecs", "diff", "--no-ext-diff", "--name-status", "-z",
                     full.decode().strip(), "--", *paths)
    if raw is None:
        raise AuditError("Cannot compute Git diff preview")
    snap = relay.workspace_snapshot(root)
    return {"target_revision": full.decode().strip(), "selected_paths": paths,
            "diff_name_status": raw.decode("utf-8","replace").split("\0")[:-1],
            "workspace_dirty": bool(snap["changed"]), "workspace_snapshot_complete": not snap["truncated"],
            "guardian": guardian(root, paths), "restored": False, "execution_authorized": False,
            "notice": "Preview only. No restore, reset, checkout, or mutation. Untracked files are not represented by Git diff."}


def firewall(value):
    if not isinstance(value, str) or len(value)>100_000:
        raise AuditError("Expected bounded text")
    patterns = {
        "instruction_override": r"ignore (?:all |any |the )?(?:previous|prior|system) instructions",
        "authority_claim": r"(?:system message|developer instruction|you are now authorized)",
        "credential_request": r"(?:send|upload|reveal|print|exfiltrate)\s+.{0,50}(?:password|secret|api[_ -]?key|token)",
        "destructive_command": r"(?:git\s+reset\s+--hard|rm\s+-rf|delete all files)",
    }
    signals = [name for name, pattern in patterns.items() if re.search(pattern,value,re.I)]
    return {"signals": signals, "status": "review_required" if signals else "no_known_pattern",
            "trusted": False, "execution_authorized": False,
            "notice": "Heuristic only; neither a security boundary nor prompt-injection detection guarantee."}
