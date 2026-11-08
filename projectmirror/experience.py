"""MirrorMap convenience interfaces. All audits inspect source without executing it.

These operations intentionally do not install dependencies, run project tests,
or change the target repository. Approval and remediation belong to the host.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from .core import (SCHEMA, AuditError, compare, create_plan, ensure_output,
                   git_info, index_repo, load, manifest, markdown_plan,
                   markdown_report, parse_spec, render, save, now)

MODES = ("quick", "deep", "pr", "drift", "visual")


def _repo_path(repo: str | Path) -> Path:
    p = Path(repo).expanduser().resolve()
    if not p.is_dir():
        raise AuditError(f"Project directory does not exist: {p}")
    return p


def _output_path(repo: Path, out: str | Path | None) -> Path:
    if out is None:
        out = Path(tempfile.mkdtemp(prefix="mirrormap-audit-"))
    result = ensure_output(repo, Path(out).expanduser())
    result.mkdir(parents=True, exist_ok=True)
    return result


def _safe_external_file(repo: Path, candidate: str | Path, what: str) -> Path:
    # A spec may legitimately be inside the inspected repository. It must be read-only.
    path = Path(candidate).expanduser().resolve()
    if not path.is_file():
        raise AuditError(f"{what} not found: {path}")
    return path


def _tokens(s: str) -> set[str]:
    return {x for x in re.findall(r"[a-z][a-z0-9]+", s.lower())
            if x not in {"the", "and", "for", "are", "user", "users", "with", "from", "have", "does", "file", "code", "can", "should", "must"}}


def candidate_links(intent: dict, implementation: dict, max_per_requirement: int = 5) -> dict:
    """Generate *hints*, not trusted identity links. Never import these automatically."""
    suggestions = []
    code_nodes = [n for n in implementation.get("nodes", []) if n.get("kind") != "file"]
    for req in intent.get("nodes", []):
        wanted = _tokens(req["id"].replace(".", " ") + " " + req["title"])
        scores = []
        for node in code_nodes:
            have = _tokens(str(node.get("title", "")) + " " + str(node.get("locator", "")))
            overlap = len(wanted & have)
            if overlap:
                scores.append((overlap / max(len(wanted), 1), node))
        scores.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        for score, node in scores[:max_per_requirement]:
            suggestions.append({"requirement_id": req["id"], "implementation_id": node["id"],
                                "heuristic_score": round(score, 3), "reviewed": False,
                                "notice": "Candidate only. Not evidence of implementation or behavior."})
    return {"schema_version": SCHEMA, "generated_at": now(), "candidates": suggestions,
            "warning": "Never auto-import candidate links into links.json. Each association needs source review."}


def _run_git(repo: Path, *args: str) -> list[str] | None:
    try:
        proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def pr_scope(repo: Path, base: str | None) -> dict:
    if not base:
        return {"available": False, "reason": "No --base ref supplied; cannot compute PR differences", "changed_files": []}
    if not re.fullmatch(r"[\w./-]{1,200}", base) or base.startswith("-") or ".." in base:
        raise AuditError("Unsafe or invalid --base ref")
    files = _run_git(repo, "diff", "--name-only", "--diff-filter=ACMRT", f"{base}...HEAD", "--")
    if files is None:
        return {"available": False, "reason": f"Cannot diff ref {base} against HEAD; verify local git history", "changed_files": []}
    return {"available": True, "base": base, "changed_files": files,
            "note": "Changed-file inventory only; not a functional review or guarantee of scope."}


def baseline_comparison(out: Path, baseline: Path) -> dict:
    b = baseline.expanduser().resolve()
    if not b.is_dir():
        raise AuditError("Baseline directory not found")
    if not (b / "findings.json").is_file():
        raise AuditError("Baseline needs findings.json from a reviewed prior audit")
    before, after = load(b / "findings.json"), load(out / "findings.json")
    x = {r["id"]: r["classification"] for r in before.get("findings", [])}
    y = {r["id"]: r["classification"] for r in after.get("findings", [])}
    changes = [{"id": k, "before": x.get(k, "not_in_baseline"), "after": y.get(k, "not_in_current")}
               for k in sorted(x.keys() | y.keys()) if x.get(k) != y.get(k)]
    result = {"schema_version": SCHEMA, "baseline_revision": before.get("revision"),
              "current_revision": after.get("revision"), "changes": changes,
              "note": "Compares reported classifications; a changed result is not automatically a regression."}
    save(out / "baseline-diff.json", result)
    return result


def _html_report(out: Path, title: str, findings: dict, meta: dict,
                 implementation: dict | None = None,
                 verification: dict | None = None) -> Path:
    """Render the standalone interactive evidence atlas, retaining v0.3 API."""
    from .dashboard import write_dashboard
    return write_dashboard(out, title, findings, meta, implementation, verification)


def audit_project(repo: str | Path, spec: str | Path | None = None,
                  out: str | Path | None = None, mode: str = "quick",
                  *, spec_approved: bool = False, base: str | None = None,
                  baseline: str | Path | None = None,
                  links: str | Path | None = None,
                  verification: str | Path | None = None,
                  absence: str | Path | None = None,
                  max_files: int | None = None,
                  junit_sources: list[str | Path] | None = None,
                  test_map: str | Path | None = None) -> dict:
    """Run the read-only audit pipeline. Return generated artifacts and counts.

    No source code is run. A requirement with no reviewed link is UNKNOWN.
    """
    if mode not in MODES:
        raise AuditError(f"Unknown audit mode: {mode}")
    if max_files is None:
        max_files = {"quick": 1500, "deep": 12000, "pr": 5000, "drift": 12000, "visual": 5000}[mode]
    if max_files < 1:
        raise AuditError("max_files must be positive")
    project = _repo_path(repo)
    target = _output_path(project, out)
    m = manifest(project)
    m["mode"] = mode
    m["scan_budget"] = max_files
    m["limitations"] = ["Source is not executed", "Semantic links require manual review", "Browser checks require external host tooling"]
    if mode == "visual" and not verification:
        m["limitations"].append("No browser verification imported: visual audit is NOT performed")
    if mode == "pr":
        m["pr_scope"] = pr_scope(project, base)
    implementation, scan = index_repo(project, max_files)
    m["scan"] = scan
    save(target / "implementation-map.json", implementation)
    save(target / "audit-manifest.json", m)
    if spec:
        parsed = parse_spec(_safe_external_file(project, spec, "Specification"),
                            "approved" if spec_approved else "draft")
        save(target / "intent-map.json", parsed)
        if mode != "quick":
            hints = candidate_links(parsed, implementation)
            save(target / "candidate-links.json", hints)
        i = parsed
    else:
        i = {"schema_version": SCHEMA, "nodes": []}
        save(target / "intent-map.json", i)
        m["limitations"].append("No requirements supplied; structural inventory only")
        save(target / "audit-manifest.json", m)
    v = load(_safe_external_file(project, verification, "Verification evidence")) if verification else {"schema_version": SCHEMA, "nodes": []}
    if test_map and not junit_sources:
        raise AuditError("--test-map requires at least one --junit source")
    if junit_sources:
        from .evidence import collect_junit
        mapping = load(_safe_external_file(project, test_map, "Reviewed JUnit mapping")) if test_map else None
        collected, imported = collect_junit(junit_sources, manifest_revision=m['project']['revision'],
                                            intent=i, reviewed_mapping=mapping)
        save(target / "junit-candidates.json", collected)
        if mapping is None:
            m["limitations"].append("JUnit cases imported as UNLINKED candidate evidence; no reviewed test mapping provided")
        else:
            v = {"schema_version": SCHEMA, "nodes": v.get('nodes', []) + imported['nodes']}
            from .core import validate_nodes
            validate_nodes(v, 'verification-map', 'verification')
            m["limitations"].append("JUnit mapping declares current revision and criteria; test run provenance remains reviewer asserted")
        save(target / "audit-manifest.json", m)
    if v['nodes']:
        save(target / "verification-map.json", v)
    l = load(_safe_external_file(project, links, "Reviewed links")) if links else {"links": []}
    a = load(_safe_external_file(project, absence, "Absence evidence")) if absence else {"confirmations": []}
    findings = compare(i, implementation, v, l, a, m)
    save(target / "findings.json", findings)
    (target / "audit-report.md").write_text(markdown_report(findings, m), encoding="utf-8")
    plan = create_plan(findings, m, implementation)
    save(target / "plan.json", plan)
    (target / "remediation-plan.md").write_text(markdown_plan(plan), encoding="utf-8")
    (target / "mindmap.mmd").write_text(render(findings), encoding="utf-8")
    _html_report(target, "Project audit", findings, m, implementation, v)
    if mode == "pr":
        save(target / "pr-scope.json", m["pr_scope"])
    if mode == "drift":
        if baseline:
            baseline_comparison(target, Path(baseline))
        else:
            m["limitations"].append("No baseline supplied: no drift comparison performed")
            save(target / "audit-manifest.json", m)
    return {"directory": str(target), "mode": mode, "counts": findings["counts"],
            "files_scanned": scan["scanned_files"], "limitations": m["limitations"]}


def doctor() -> dict:
    import platform
    checks = [{"name": "python_3_10", "ok": sys.version_info >= (3, 10), "value": platform.python_version()},
              {"name": "git", "ok": shutil.which("git") is not None, "value": shutil.which("git") or "not found"},
              {"name": "package", "ok": True, "value": "MirrorMap Python core available"}]
    return {"schema_version": SCHEMA, "checks": checks,
            "note": "Tool presence is not a security, runtime, or platform compatibility guarantee."}


def install_skill(destination: Path, *, apply: bool) -> dict:
    src = Path(__file__).resolve().parents[1]
    if not (src / "SKILL.md").is_file():
        src = Path(__file__).resolve().parent / "skill_bundle"
    if not (src / "SKILL.md").is_file():
        raise AuditError("Skill bundle missing from this installation; use the GitHub source checkout.")
    dest = destination.expanduser().resolve()
    if dest.exists():
        raise AuditError(f"Destination already exists; refusing to overwrite: {dest}")
    chosen = ["SKILL.md", "references"]
    module_source = Path(__file__).resolve().parent
    preview = {"destination": str(dest), "items": chosen + ["projectmirror"],
               "status": "ready_to_install" if apply else "preview_only"}
    if apply:
        dest.mkdir(parents=True, exist_ok=False)
        for item in chosen:
            target = src / item
            if target.is_dir():
                shutil.copytree(target, dest / item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(target, dest / item)
        shutil.copytree(module_source, dest / "projectmirror", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        preview["status"] = "installed"
    return preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mirrormap", description="Read-only project intelligence and evidence-backed audits")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("audit", help="one-command structural audit and evidence-backed report")
    p.add_argument("repo", type=Path, help="local project folder to inspect")
    p.add_argument("--spec", type=Path, help="requirements file; without one, run inventory-only")
    p.add_argument("--out", type=Path, help="audit output folder (must be outside the project)")
    p.add_argument("--mode", choices=MODES, default="quick")
    p.add_argument("--approved-spec", action="store_true", help="use only when the user explicitly approved supplied requirements")
    p.add_argument("--base", help="base Git ref for PR changed-file inventory")
    p.add_argument("--baseline", type=Path, help="prior audit folder for drift comparison")
    p.add_argument("--links", type=Path, help="reviewed requirement-to-implementation mappings")
    p.add_argument("--verification", type=Path, help="real test/browser observations")
    p.add_argument("--absence", type=Path, help="reviewed, scoped absence records")
    p.add_argument("--max-files", type=int, default=None)
    p.add_argument("--junit", type=Path, action="append", default=[], help="existing JUnit XML file or directory; never runs tests")
    p.add_argument("--test-map", type=Path, help="explicitly reviewed test-to-criteria mapping JSON for JUnit evidence")
    p = commands.add_parser("evidence", help="collect existing JUnit XML reports into an initialized audit folder")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--junit", type=Path, action="append", required=True)
    p.add_argument("--test-map", type=Path)
    p = commands.add_parser("routes", help="list static framework route candidates (never verifies endpoints)")
    p.add_argument("repo", type=Path)
    p.add_argument("--max-files", type=int, default=5000)
    commands.add_parser("doctor", help="check local runtime prerequisites")
    p = commands.add_parser("dashboard", help="render offline HTML from an existing audit folder")
    p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("baseline-diff", help="compare findings with a reviewed baseline")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p = commands.add_parser("install-skill", help="preview or install the portable skill to a chosen agent skills folder")
    p.add_argument("--dest", type=Path, required=True)
    p.add_argument("--apply", action="store_true", help="create files (off by default; never overwrites)")
    commands.add_parser("mcp", help="launch experimental local MCP stdio server")
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            res = audit_project(args.repo, args.spec, args.out, args.mode, spec_approved=args.approved_spec,
                                base=args.base, baseline=args.baseline, links=args.links, verification=args.verification,
                                absence=args.absence, max_files=args.max_files,
                                junit_sources=args.junit, test_map=args.test_map)
        elif args.command == "evidence":
            from .evidence import collect_junit
            out = args.out.expanduser().resolve()
            m = load(out / 'audit-manifest.json')
            ensure_output(Path(m['project']['repo']), out)
            mapping = load(args.test_map) if args.test_map else None
            inventory, verification = collect_junit(args.junit, manifest_revision=m['project']['revision'],
                                                     intent=load(out / 'intent-map.json'), reviewed_mapping=mapping)
            save(out / 'junit-candidates.json', inventory)
            if mapping is not None:
                prior = load(out / 'verification-map.json') if (out / 'verification-map.json').is_file() else {'schema_version': SCHEMA, 'nodes': []}
                combined = {'schema_version': SCHEMA, 'nodes': prior['nodes'] + verification['nodes']}
                from .core import validate_nodes
                validate_nodes(combined, 'verification-map', 'verification')
                save(out / 'verification-map.json', combined)
            res = {'cases': len(inventory['cases']), 'mapped': inventory['mapped_cases'],
                   'candidates_path': str(out / 'junit-candidates.json'),
                   'next_step': 'Run diff, plan, render and dashboard to refresh outputs.'}
        elif args.command == "routes":
            repo = _repo_path(args.repo)
            if args.max_files < 1:
                raise AuditError("--max-files must be positive")
            inventory, scan = index_repo(repo, args.max_files)
            res = {"schema_version": SCHEMA, "repo": str(repo),
                   "candidates": [n for n in inventory["nodes"] if n["kind"] == "route_candidate"],
                   "scan": scan, "warning": "Static route declarations are not proof of runtime behavior."}
        elif args.command == "doctor":
            res = doctor()
        elif args.command == "dashboard":
            out = args.out.expanduser().resolve()
            m = load(out / "audit-manifest.json")
            ensure_output(Path(m["project"]["repo"]), out)
            i = load(out / 'implementation-map.json') if (out / 'implementation-map.json').is_file() else None
            v = load(out / 'verification-map.json') if (out / 'verification-map.json').is_file() else None
            res = {"path": str(_html_report(out, "Project audit", load(out / "findings.json"), m, i, v))}
        elif args.command == "baseline-diff":
            out = args.out.expanduser().resolve()
            m = load(out / "audit-manifest.json")
            ensure_output(Path(m["project"]["repo"]), out)
            res = baseline_comparison(out, args.baseline)
        elif args.command == "install-skill":
            res = install_skill(args.dest, apply=args.apply)
        else:
            from .mcp import serve
            return serve()
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except (AuditError, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        print(f"MirrorMap error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
