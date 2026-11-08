# Operating workflow and CLI contracts

Run `python -m projectmirror --help` for CLI usage. Python 3.10+ is required. No packages beyond the Python standard library are required for the runtime CLI.

1. **Initialize** with `init --repo <repo> --out <outside-repo-dir>`. `audit-manifest.json` contains git HEAD (if available) and scan scope.
2. **Import intent** using `intent --spec <requirements.md or JSON> --out <dir>`. The Markdown parser recognizes `- [REQ.id] Requirement` and indented `- [AC.id] Criterion`. It never invents features from prose. Default intent is `draft`; use `--state approved` **only after the user has approved the spec**.
3. **Index** with `index --repo <repo> --out <dir>`. Generates a structural implementation map, including Python top-level symbols via AST and heuristic JavaScript/TypeScript exports. Ignores secret-looking file names, hidden environments, dependency and build directories, symlinks and oversized files. Never executes project code. Reports skips and parser failures.
4. **Review identity links** by reading `implementation-map.json` and source. Write `links.json` with reviewed requirement and implementation IDs, then `link --from links.json --out <dir>`.
5. **Import verification (optional)** from actual isolated tests or user-supplied logs with `import-verification --from ... --out ...`. Do not invent a pass. Ensure exact revision and criterion IDs match the manifest and intent map.
6. **Confirm scoped absences (optional)** only after a suitable exhaustive audit using `absence --from ... --out ...`.
7. **Diff** with `diff --out <dir>` to generate JSON findings and an MD report. Classifications are deterministic over the supplied reviewed facts.
8. **Plan** with `plan --out <dir>`; `remediation-plan.md` is a review artifact. **STOP before project changes**.
9. **Render** with `render --out <dir>` for a Mermaid flowchart. `snapshot --out <dir>` copies versioned artifacts.
10. **After explicit host-enforced user approval**, allow a coding agent to implement approved tasks with appropriate file permission boundaries, then re-run checks and repeat analysis. The CLI itself intentionally does not write or deploy project code.

### Error and non-goals

This release fails closed on invalid identifiers, malformed JSON, duplicate nodes, bad reviewed links, and stale HEAD during indexing. It cannot guarantee a project's correctness, parse every language, execute safe runtime tests by itself, recognize semantic equivalence without reviewed links, or enforce human identity/authentication. The `check-approval` helper only checks metadata/digest/path consistency; it does not authenticate a user.

### Safe sample sequence

```bash
python -m projectmirror init --repo ./examples/demo-app --out /tmp/projectmirror-demo
python -m projectmirror intent --spec ./examples/demo-app/requirements.md --state approved --out /tmp/projectmirror-demo
python -m projectmirror index --repo ./examples/demo-app --out /tmp/projectmirror-demo
python -m projectmirror diff --out /tmp/projectmirror-demo
python -m projectmirror plan --out /tmp/projectmirror-demo
python -m projectmirror render --out /tmp/projectmirror-demo
```

The `--state approved` in the demonstration stands for a deliberately prepared **example** spec. In real projects, only use this after the user has actually approved the document.
