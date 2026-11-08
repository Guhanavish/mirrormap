# Interactive Evidence Atlas (offline dashboard)

Starting in v0.4, every guided audit creates a **self-contained interactive `dashboard.html`**. It is not a remote service, needs no account, and does not load scripts from a CDN.

## Explore the audit

```bash
python -m projectmirror audit examples/demo-app \
  --spec examples/demo-app/requirements.md --approved-spec --mode deep
```

Open the generated `dashboard.html` in a browser. The Evidence Atlas lets you:

- Browse a three-lane graph: **intent → implementation → verification**.
- Search by requirement text, finding ID and status.
- Filter by classification, select graph nodes with mouse or keyboard, and zoom the view.
- Inspect direct evidence, code locators and test observations for a selected finding.
- Inspect counts without mistaking `unknown` for `missing`.
- Use an offline, responsive, read-only interface. The complete machine-readable records remain in JSON.

If you import evidence later, regenerate the page with:

```bash
python -m projectmirror dashboard --out /absolute/path/to/audit-folder
```

## Security and completeness

The report uses a restrictive Content Security Policy, a hash-bound local script, safe JSON encoding, and DOM `textContent` for source strings. No network calls or remote resources. Graph drawing is capped at 120 visible findings for usability; `findings.json`, `implementation-map.json`, `verification-map.json`, and `mindmap.mmd` remain the complete (bounded by normal scan budgets) artifacts.

**The dashboard cannot approve a plan or edit a project.** It is a visualization, not an execution interface. Any user-approved execution requires a host-controlled authorization step.
