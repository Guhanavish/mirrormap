"""CLI for ProjectMirror. Run: python -m projectmirror --help"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .core import (AuditError, SCHEMA, check_receipt, compare, create_plan,
                   ensure_output, git_info, index_repo, load, manifest,
                   markdown_plan, markdown_report, now, parse_spec, render,
                   save, validate_nodes)


def safe_audit_dir(path: Path) -> Path:
    """Fail closed if any command would write inside the audited repository."""
    out = path.resolve()
    mpath = out / "audit-manifest.json"
    if not mpath.exists():
        raise AuditError("Run init first; audit-manifest.json is missing")
    m = load(mpath)
    repo = m.get("project", {}).get("repo")
    if not isinstance(repo, str) or not repo:
        raise AuditError("Audit manifest is missing a valid project repo")
    ensure_output(Path(repo), out)
    return out


def cmd_main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"audit", "doctor", "dashboard", "baseline-diff", "install-skill", "mcp"}:
        from .experience import main
        return main(argv)
    parser = argparse.ArgumentParser(prog="projectmirror", description="Read-only, evidence-linked spec drift auditing", epilog="New: audit, doctor, dashboard, baseline-diff, install-skill, mcp (run command --help for details)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="create an audit manifest outside the project")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("intent", help="import approved or draft requirement nodes")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--state", choices=["draft", "approved"], default="draft")
    p = sub.add_parser("index", help="scan source structure, without executing it")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-files", type=int, default=12000)
    p = sub.add_parser("import-verification", help="import evidence-based verification results")
    p.add_argument("--from", dest="source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("link", help="import manually-reviewed requirement to implementation links")
    p.add_argument("--from", dest="source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("absence", help="import reviewed absence confirmations")
    p.add_argument("--from", dest="source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    for cmd in ("diff", "plan", "render", "snapshot"):
        p = sub.add_parser(cmd)
        p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("check-approval", help="validate receipt metadata and path scope (not an authorization service)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--paths", nargs="*", default=[])
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            repo = args.repo.resolve()
            out = ensure_output(repo, args.out)
            out.mkdir(parents=True, exist_ok=True)
            save(out / "audit-manifest.json", manifest(repo))
            print(f"Manifest created: {out / 'audit-manifest.json'}")
        elif args.command == "intent":
            out = safe_audit_dir(args.out)
            save(out / "intent-map.json", parse_spec(args.spec, args.state))
            print("Intent imported. Confirm source approval before treating any requirements as authoritative.")
        elif args.command == "index":
            if args.max_files < 1:
                raise AuditError("--max-files must be positive")
            repo, out = args.repo.resolve(), safe_audit_dir(args.out)
            ensure_output(repo, out)
            prior = load(out / "audit-manifest.json")
            if prior.get("project", {}).get("repo") != str(repo):
                raise AuditError("Audit manifest repository does not match --repo")
            current_revision, _ = git_info(repo)
            if prior["project"].get("revision") != current_revision:
                raise AuditError("Repository HEAD changed since init. Restart audit to avoid mixed-revision evidence")
            obj, scan = index_repo(repo, args.max_files)
            prior["scan"] = scan
            save(out / "implementation-map.json", obj)
            save(out / "audit-manifest.json", prior)
            print(f"Indexed {scan['scanned_files']} source files; skipped {scan['skipped_files']}; limitations: {len(scan['errors'])}")
        elif args.command in ("import-verification", "link", "absence"):
            out = safe_audit_dir(args.out)
            source = load(args.source)
            if args.command == "import-verification":
                validate_nodes(source, "verification-map", "verification")
                destination = "verification-map.json"
            elif args.command == "link":
                if not isinstance(source.get("links"), list):
                    raise AuditError("Expected links array")
                destination = "links.json"
            else:
                if not isinstance(source.get("confirmations"), list):
                    raise AuditError("Expected confirmations array")
                destination = "absence-confirmations.json"
            save(out / destination, source)
            print(f"Imported {destination}")
        elif args.command == "diff":
            out = safe_audit_dir(args.out)
            m = load(out / "audit-manifest.json")
            i = load(out / "intent-map.json")
            c = load(out / "implementation-map.json")
            v = load(out / "verification-map.json") if (out / "verification-map.json").exists() else {"schema_version": SCHEMA, "nodes": []}
            l = load(out / "links.json") if (out / "links.json").exists() else {"links": []}
            a = load(out / "absence-confirmations.json") if (out / "absence-confirmations.json").exists() else {"confirmations": []}
            findings = compare(i, c, v, l, a, m)
            save(out / "findings.json", findings)
            (out / "audit-report.md").write_text(markdown_report(findings, m), encoding="utf-8")
            print("Findings:", json.dumps(findings["counts"], sort_keys=True))
        elif args.command == "plan":
            out = safe_audit_dir(args.out)
            plan = create_plan(load(out / "findings.json"), load(out / "audit-manifest.json"), load(out / "implementation-map.json"))
            save(out / "plan.json", plan)
            (out / "remediation-plan.md").write_text(markdown_plan(plan), encoding="utf-8")
            print("Plan created for review. STOP before modifying the project.")
        elif args.command == "render":
            out = safe_audit_dir(args.out)
            (out / "mindmap.mmd").write_text(render(load(out / "findings.json")), encoding="utf-8")
            print(f"Mindmap rendered: {out / 'mindmap.mmd'}")
        elif args.command == "snapshot":
            out = safe_audit_dir(args.out)
            name = now().replace(":", "-")
            snapshot = out / "snapshots" / name
            suffix = 1
            while snapshot.exists():
                snapshot = out / "snapshots" / f"{name}-{suffix}"
                suffix += 1
            snapshot.mkdir(parents=True, exist_ok=False)
            for filename in ("audit-manifest.json", "intent-map.json", "implementation-map.json", "verification-map.json", "links.json", "absence-confirmations.json", "findings.json", "plan.json"):
                if (out / filename).exists():
                    shutil.copy2(out / filename, snapshot / filename)
            print(f"Saved snapshot: {snapshot}")
        elif args.command == "check-approval":
            out = safe_audit_dir(args.out)
            plan = load(out / "plan.json")
            receipt = load(args.receipt)
            check_receipt(plan, receipt, load(out / "audit-manifest.json"), args.paths)
            print("Receipt metadata and supplied changed paths are consistent; host authorization is still required.")
        return 0
    except (AuditError, OSError, UnicodeError, KeyError, TypeError) as exc:
        print(f"ProjectMirror error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cmd_main())
