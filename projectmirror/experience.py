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


def _html_report(out: Path, title: str, findings: dict, meta: dict) -> Path:
    counts = findings.get("counts", {})
    def e(s: Any) -> str:
        return html.escape(str(s), quote=True)
    status_blocks = "".join(f'<section class="stat"><b>{int(n)}</b><span>{e(k).upper()}</span></section>'
                            for k, n in sorted(counts.items())) or '<section class="stat"><b>0</b><span>CONFIRMED GAPS</span></section>'
    items = "".join('<tr><td><code>' + e(f.get("id", "")) + '</code></td><td><span class="pill">' +
                    e(f.get("classification", "")) + '</span></td><td>' + e(f.get("title", "")) +
                    '</td><td>' + e(f.get("reason", "")) + '</td></tr>' for f in findings.get("findings", []))
    if not items:
        items = '<tr><td colspan="4">No classified requirements yet. Supply a reviewed specification to start a gap audit.</td></tr>'
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none';">
<title>MirrorMap | {e(title)}</title><style>
:root{{color-scheme:dark;font-family:ui-sans-serif,system-ui,Arial,sans-serif;background:#08131b;color:#e9f4f1}}
*{{box-sizing:border-box}}body{{margin:0;line-height:1.55;background:radial-gradient(ellipse at 65% 0%,#153d42 0%,#08131b 53%)}}
.container{{max-width:1100px;margin:auto;padding:40px 24px 72px}}
nav{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #29424a;padding-bottom:20px}}
.brand{{font-weight:800;letter-spacing:-.06em;font-size:24px}}.brand span{{color:#69dfbf}}
.muted{{color:#9eb5b7}}h1{{font-size:clamp(36px,6vw,70px);line-height:1.08;letter-spacing:-.045em;margin:80px 0 16px}}
.kicker{{color:#69dfbf;letter-spacing:.22em;font-size:12px;font-weight:700}}
.grid{{display:flex;flex-wrap:wrap;gap:12px;margin:38px 0 48px}}.stat{{background:#12232b;border:1px solid #28434a;border-radius:12px;padding:18px;flex:1;min-width:145px}}
.stat b{{display:block;font-size:38px;color:#e7f8ef}}.stat span{{font-size:11px;letter-spacing:.15em;color:#98c5bf}}
.panel{{background:#0d1e26;border:1px solid #28414a;border-radius:15px;overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:750px}}
th,td{{padding:14px 16px;border-bottom:1px solid #253d44;text-align:left;vertical-align:top}}th{{color:#85d6c2;font-size:12px;letter-spacing:.08em}}
tr:last-child td{{border-bottom:0}}code{{color:#bbf3df}}.pill{{border:1px solid #4b696c;background:#20323a;border-radius:100px;padding:4px 9px;font-size:12px}}
footer{{margin-top:32px;color:#a9bfc1;font-size:13px}}a{{color:#8beac9}}
</style></head><body><div class="container"><nav><div class="brand">◈ Mirror<span>Map</span></div><div class="muted">EVIDENCE ATLAS / REPORT</div></nav>
<header><h1>{e(title)}</h1><p class="kicker">INTENT &nbsp; / &nbsp; IMPLEMENTATION &nbsp; / &nbsp; VERIFICATION</p>
<p class="muted">Project: {e(meta.get('project',{}).get('repo','unknown'))}<br>Revision: {e(meta.get('project',{}).get('revision') or 'unversioned')}<br>
This audit is limited to available, reviewed evidence. Unknown does not mean missing.</p></header>
<div class="grid">{status_blocks}</div><h2>Requirement findings</h2><div class="panel"><table><thead><tr><th>ID</th><th>STATUS</th><th>REQUIREMENT</th><th>RATIONALE</th></tr></thead><tbody>{items}</tbody></table></div>
<footer>MirrorMap generated this report without changing the inspected project. No fix is approved by this document.</footer></div></body></html>'''
    file = out / "dashboard.html"
    file.write_text(body, encoding="utf-8")
    return file


def audit_project(repo: str | Path, spec: str | Path | None = None,
                  out: str | Path | None = None, mode: str = "quick",
                  *, spec_approved: bool = False, base: str | None = None,
                  baseline: str | Path | None = None,
                  links: str | Path | None = None,
                  verification: str | Path | None = None,
                  absence: str | Path | None = None,
                  max_files: int | None = None) -> dict:
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
    l = load(_safe_external_file(project, links, "Reviewed links")) if links else {"links": []}
    a = load(_safe_external_file(project, absence, "Absence evidence")) if absence else {"confirmations": []}
    findings = compare(i, implementation, v, l, a, m)
    save(target / "findings.json", findings)
    (target / "audit-report.md").write_text(markdown_report(findings, m), encoding="utf-8")
    plan = create_plan(findings, m, implementation)
    save(target / "plan.json", plan)
    (target / "remediation-plan.md").write_text(markdown_plan(plan), encoding="utf-8")
    (target / "mindmap.mmd").write_text(render(findings), encoding="utf-8")
    _html_report(target, "Project audit", findings, m)
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
                                absence=args.absence, max_files=args.max_files)
        elif args.command == "doctor":
            res = doctor()
        elif args.command == "dashboard":
            out = args.out.expanduser().resolve()
            m = load(out / "audit-manifest.json")
            ensure_output(Path(m["project"]["repo"]), out)
            res = {"path": str(_html_report(out, "Project audit", load(out / "findings.json"), m))}
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
