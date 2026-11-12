"""Experimental, local, newline-framed MCP JSON-RPC adapter.

The interface grants no code-edit permissions. It inspects only projects within
explicit allowlisted roots, and rejects unsupported tools and malformed input.
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
MAX_MESSAGE_CHARS = 1_000_000
MAX_REPORT_CHARS = 30_000

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
    {"name": "mirrormap_read_report", "description": "Read one generated MirrorMap report for an allowlisted project, capped to 30,000 characters.",
     "inputSchema": {"type": "object", "required": ["out"], "properties": {
         "out": {"type": "string"},
         "name": {"type": "string", "enum": ["audit-report.md", "remediation-plan.md", "mindmap.mmd"]}},
         "additionalProperties": False}},
]

_TOOL_SCHEMAS = {tool["name"]: tool["inputSchema"] for tool in TOOLS}


def _validate_tool_arguments(name: str, args: Any) -> dict:
    """Validate exactly the advertised, intentionally limited MCP tool inputs."""
    schema = _TOOL_SCHEMAS.get(name)
    if schema is None:
        raise AuditError(f"Unknown tool: {name}")
    if not isinstance(args, dict):
        raise AuditError("Tool arguments must be an object")
    unknown = set(args) - set(schema["properties"])
    if unknown:
        raise AuditError("Unsupported tool argument(s): " + ", ".join(sorted(map(str, unknown))))
    for required in schema.get("required", []):
        if required not in args:
            raise AuditError(f"Missing required tool argument: {required}")
    for key, value in args.items():
        definition = schema["properties"][key]
        if definition.get("type") == "string" and (not isinstance(value, str) or not value.strip()):
            raise AuditError(f"Tool argument {key} must be a nonempty string")
        if "enum" in definition and value not in definition["enum"]:
            raise AuditError(f"Invalid value for tool argument: {key}")
    return args


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
    args = _validate_tool_arguments(name, args)
    if name == "mirrormap_doctor":
        return doctor()
    if name == "mirrormap_audit":
        project = _allowlisted(Path(args["repo"]))
        spec = _allowlisted(Path(args["spec"])) if "spec" in args else None
        junit = _allowlisted(Path(args["junit"])) if "junit" in args else None
        return audit_project(project, spec=spec, out=args.get("out"), mode=args.get("mode", "quick"),
                             base=args.get("base"), junit_sources=[junit] if junit else None)
    if name == "mirrormap_read_report":
        out = Path(args["out"]).expanduser().resolve()
        m = load(out / "audit-manifest.json")
        project_data = m.get("project")
        if not isinstance(project_data, dict) or not isinstance(project_data.get("repo"), str):
            raise AuditError("Report manifest has no valid project repository")
        project = _allowlisted(Path(project_data["repo"]))
        ensure_output(project, out)
        fname = args.get("name", "audit-report.md")
        p = out / fname
        if p.is_symlink():
            raise AuditError("Refusing to follow a symlinked report")
        with p.open("r", encoding="utf-8") as file:
            content = file.read(MAX_REPORT_CHARS + 1)
        return {"report": content[:MAX_REPORT_CHARS], "truncated": len(content) > MAX_REPORT_CHARS}
    raise AuditError("Unknown tool")


def respond(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _error(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def dispatch(req: Any) -> dict | None:
    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid JSON-RPC request")
    mid = req.get("id")
    if "id" in req and (isinstance(mid, bool) or not (mid is None or isinstance(mid, (str, int)))):
        return _error(None, -32600, "Invalid JSON-RPC id")
    method = req.get("method")
    if not isinstance(method, str) or not method:
        return _error(mid, -32600, "Invalid method")
    if "id" not in req:
        return None  # Notification: no response, including unknown methods.
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
            params = req.get("params")
            if not isinstance(params, dict):
                return _error(mid, -32602, "Tool params must be an object")
            name = params.get("name")
            if not isinstance(name, str):
                return _error(mid, -32602, "Tool name must be a string")
            args = params.get("arguments", {})
            try:
                _validate_tool_arguments(name, args)
            except AuditError as ex:
                return _error(mid, -32602, str(ex))
            try:
                result = invoke(name, args)
                value = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
            except (AuditError, OSError, UnicodeError, ValueError, KeyError, TypeError) as ex:
                value = {"content": [{"type": "text", "text": str(ex)}], "isError": True}
        else:
            return _error(mid, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": mid, "result": value}
    except (AuditError, OSError, UnicodeError, ValueError, KeyError, TypeError) as ex:
        return _error(mid, -32602, str(ex))


def serve() -> int:
    for raw in sys.stdin:
        if len(raw) > MAX_MESSAGE_CHARS:
            respond(_error(None, -32600, "MCP request too large"))
            continue
        try:
            req = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError):
            respond(_error(None, -32700, "Parse error"))
            continue
        result = dispatch(req)
        if result is not None:
            respond(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
