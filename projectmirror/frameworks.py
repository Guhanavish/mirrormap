"""Conservative framework *declaration* discovery for source inventories.

These are candidate routes from static syntax or naming conventions. They do not
prove the route is registered, deployed, reachable, authenticated, or correct.
Do not turn these nodes into reviewed requirement links automatically.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path


_NEXT_PAGE_EXTS = {".js", ".jsx", ".ts", ".tsx"}
_FASTAPI_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "api_route", "websocket"}


def _route_node(relative: str, evidence_id: str, *, route_path: str, framework: str,
                route_kind: str, method: str = "unspecified", line: int | None = None,
                confidence: str = "declaration_only", handler: str | None = None) -> dict:
    loc = f"{relative}:{line}" if line else relative
    key = f"{relative}\0{route_kind}\0{method}\0{route_path}\0{handler or ''}\0{line or 0}"
    short_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"impl.route.{short_id}",
        "map": "implementation", "kind": "route_candidate",
        "title": f"{method.upper() + ' ' if method != 'unspecified' else ''}{route_path}",
        "locator": loc, "implementation_state": "present", "source_refs": [evidence_id],
        "framework": framework, "route_kind": route_kind, "route_path": route_path,
        "http_method": method, "confidence": confidence,
        "warning": "Static route candidate only; deployment, registration, and behavior are not verified.",
    }


def _next_route(rel: Path, evidence_id: str) -> dict | None:
    if rel.suffix.lower() not in _NEXT_PAGE_EXTS:
        return None
    parts = rel.parts
    prefix_at = None
    section = None
    for index in (0, 1):
        if len(parts) > index + 1 and (index == 0 or parts[0] == "src") and parts[index] in ("app", "pages"):
            prefix_at, section = index, parts[index]
            break
    if prefix_at is None or section is None:
        return None
    leaf = rel.stem
    segments = list(parts[prefix_at + 1:-1])
    if section == "app":
        if leaf not in {"page", "route"}:
            return None
        kind = "page" if leaf == "page" else "handler"
    else:
        if leaf.startswith("_") or leaf in {"_app", "_document", "_error"}:
            return None
        if leaf == "index":
            pass
        else:
            segments.append(leaf)
        kind = "handler" if segments and segments[0] == "api" else "page"
    final = []
    for segment in segments:
        # Route groups and parallel slots are not part of the URL.
        if segment.startswith("(") and segment.endswith(")"):
            continue
        if segment.startswith("@"):
            continue
        # Intercepting routes and complex dynamic patterns are deliberately not guessed.
        if segment.startswith("(.)") or segment.startswith("(..)") or segment.startswith("(...)"):
            return None
        if segment.startswith("[[...") and segment.endswith("]]"):
            final.append(":" + segment[5:-2] + "*")
        elif segment.startswith("[...") and segment.endswith("]"):
            final.append(":" + segment[4:-1] + "+")
        elif segment.startswith("[") and segment.endswith("]"):
            final.append(":" + segment[1:-1])
        else:
            final.append(segment)
    route_path = "/" + "/".join(final)
    return _route_node(rel.as_posix(), evidence_id, route_path=route_path,
                       framework="nextjs_path_convention", route_kind=kind,
                       confidence="path_convention_only")


def _fastapi_routes(rel: Path, source: str, evidence_id: str) -> list[dict]:
    if rel.suffix.lower() != ".py":
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    # Only recognize decorators on instances assigned from FastAPI / APIRouter
    # constructors imported in this file. A generic @cache.get must not be
    # mistaken for a route merely because FastAPI is imported elsewhere.
    constructors = {}
    module_aliases = set()
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and statement.module in {"fastapi", "fastapi.applications", "fastapi.routing"}:
            constructors.update({alias.asname or alias.name: alias.name for alias in statement.names
                                 if alias.name in {"FastAPI", "APIRouter"}})
        elif isinstance(statement, ast.Import):
            module_aliases.update(alias.asname or alias.name for alias in statement.names
                                  if alias.name == "fastapi")
    receiver_names = set()
    for statement in tree.body:
        value = None
        names = []
        if isinstance(statement, ast.Assign):
            value = statement.value
            names = [target.id for target in statement.targets if isinstance(target, ast.Name)]
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            value = statement.value
            names = [statement.target.id]
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        direct = isinstance(func, ast.Name) and constructors.get(func.id) in {"FastAPI", "APIRouter"}
        qualified = (isinstance(func, ast.Attribute) and func.attr in {"FastAPI", "APIRouter"}
                     and isinstance(func.value, ast.Name) and func.value.id in module_aliases)
        if direct or qualified:
            receiver_names.update(names)
    if not receiver_names:
        return []
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute)
                    or not isinstance(dec.func.value, ast.Name) or dec.func.value.id not in receiver_names
                    or dec.func.attr not in _FASTAPI_METHODS or not dec.args):
                continue
            # Static strings only. Dynamic paths are not reconstructed.
            literal = dec.args[0]
            if not isinstance(literal, ast.Constant) or not isinstance(literal.value, str) or not literal.value.startswith("/"):
                continue
            method = dec.func.attr
            found.append(_route_node(rel.as_posix(), evidence_id, route_path=literal.value,
                                     framework="fastapi_decorator", route_kind="handler",
                                     method=method, line=dec.lineno, handler=node.name))
    return found


def framework_route_candidates(rel: Path, source: str, evidence_id: str) -> list[dict]:
    """Find candidate route *declarations* without executing source files."""
    output = []
    candidate = _next_route(rel, evidence_id)
    if candidate is not None:
        output.append(candidate)
    output.extend(_fastapi_routes(rel, source, evidence_id))
    return output
