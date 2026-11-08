"""Experimental local stdio MCP interface (JSON-RPC, newline-framed).

Only grants read-only source inspection within explicitly allowed local roots.
It does NOT execute shell commands or edit the inspected project.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .core import AuditError, ensure_output, load
from .experience import audit_project, doctor

PROTOCOL = "2025-06-18"
VERSION = "0.4.0"

TOOLS = [
    {"name": "mirrormap_doctor", "description": "Report local tool presence; no repository access.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "mirrormap_audit", "description": "Read-only structural audit of an explicitly allowlisted local project; results written OUTSIDE the project. No source code execution or automatic approvals.",
     "inputSchema": {"type": "object", "required": ["repo"], "properties": {
         "repo": {"type": "string", "description": "Absolute folder path under MIRRORMAP_ALLOWED_ROOTS"},
         "spec": {"type": "string", "description": "Optional approved or draft requirements file"},
         "out": {"type": "string", "description": "Optional separate report output folder"},
         "mode": {"type": "string", "enum": ["quick", "deep", "pr", "drift", "visual"]},
         "base": {"type": "string", "description": "Git base ref for PR inventory"},
         "junit": {"type": "string", "description": "Optional existing JUnit XML report under MIRRORMAP_ALLOWED_ROOTS; only unreviewed candidates"}},
         "additionalProperties": False}},
    {"name": "mirrormap_read_report", "description": "Read one generated MirrorMap report for an allowlisted project, capped to 30 KB.",
     "inputSchema": {"type": "object", "required": ["out"], "properties": {
         "out": {"type": "string"},
         "name": {"type": "string", "enum": ["audit-report.md", "remediation-plan.md", "mindmap.mmd"]}},
         "additionalProperties": False}},
]


def _allowlisted(path: Path) -> Path:
    raw = os.getenv("MIRRORMAP_ALLOWED_ROOTS", "")
    roots = [Path(item).expanduser().resolve() for item in raw.split(os.pathsep) if item.strip()]
    candidate = path.expanduser().resolve()
    if not roots:
        raise AuditError("MIRRORMAP_ALLOWED_ROOTS is required for MCP project access")
    if not any(root == candidate or root in candidate.parents for root in roots):
        raise AuditError("Project path is not within MIRRORMAP_ALLOWED_ROOTS")
    return candidate


def invoke(name: str, args: dict) -> dict:
    if not isinstance(args, dict):
        raise AuditError("Tool arguments must be an object")
    if name == "mirrormap_doctor":
        return doctor()
    if name == "mirrormap_audit":
        if not isinstance(args.get("repo"), str):
            raise AuditError("repo path required")
        project = _allowlisted(Path(args["repo"]))
        spec = args.get("spec")
        if spec is not None:
            source = Path(spec).expanduser().resolve()
            _allowlisted(source)
        else:
            source = None
        junit = args.get("junit")
        if junit is not None and not isinstance(junit, str):
            raise AuditError("junit must be a path string")
        junit_path = _allowlisted(Path(junit)) if junit else None
        return audit_project(project, spec=source, out=args.get("out"), mode=args.get("mode", "quick"),
                             base=args.get("base"), junit_sources=[junit_path] if junit_path else None)
    if name == "mirrormap_read_report":
        out = Path(args.get("out", "")).expanduser().resolve()
        m = load(out / "audit-manifest.json")
        project = _allowlisted(Path(m["project"]["repo"]))
        ensure_output(project, out)
        fname = args.get("name", "audit-report.md")
        if fname not in {"audit-report.md", "remediation-plan.md", "mindmap.mmd"}:
            raise AuditError("Only generated report filenames are supported")
        p = out / fname
        return {"report": p.read_text(encoding="utf-8")[:30000], "truncated": p.stat().st_size > 30000}
    raise AuditError("Unknown tool")


def respond(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def dispatch(req: Any) -> dict | None:
    if not isinstance(req, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    mid, method = req.get("id"), req.get("method")
    if not isinstance(method, str):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32600, "message": "Invalid method"}}
    if mid is None:
        return None  # JSON-RPC notification
    try:
        if method == "initialize":
            value = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                     "serverInfo": {"name": "mirrormap", "version": VERSION},
                     "instructions": "Read-only audits only. No auto-approved requirements or code modifications. Configure MIRRORMAP_ALLOWED_ROOTS before use."}
        elif method == "ping":
            value = {}
        elif method == "tools/list":
            value = {"tools": TOOLS}
        elif method == "tools/call":
            params = req.get("params") or {}
            if not isinstance(params, dict):
                raise AuditError("Tool params must be an object")
            result = invoke(params.get("name", ""), params.get("arguments") or {})
            value = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": mid, "result": value}
    except (AuditError, OSError, ValueError, KeyError, TypeError) as e:
        if method == "tools/call":
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": str(e)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": str(e)}}


def serve() -> int:
    for raw in sys.stdin:
        if len(raw) > 1_000_000:
            continue
        try:
            req = json.loads(raw)
            result = dispatch(req)
            if result is not None:
                respond(result)
        except (json.JSONDecodeError, UnicodeError):
            respond({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
