# MirrorMap v0.2.0 — evidence atlas release

## Shipped

- `audit` one-command source inventory and evidence-based comparison with five modes (`quick`, `deep`, `pr`, `drift`, `visual`). Mode names describe the workflow, **not automatic runtime test execution**.
- `doctor` checks local prerequisites.
- `install-skill --dest ...` previews destination and only creates files with `--apply`, never overwriting an existing installation.
- HTML dashboard written outside the inspected project; all text escaped and no external scripts/assets.
- `candidate-links.json` heuristic candidate matches for manual review only.
- PR changed-file inventory with `--base`; baseline finding-status comparison with `--baseline`.
- Experimental local MCP stdio interface with explicit allowed roots.
- Python SDK function `audit_project(...)`.
- Multi-entrypoint documentation and a CI workflow example.
- Entirely refreshed evidence-atlas visual identity and README.

## Deliberately not shipped yet

- Automatic semantic requirement matching, executable safe test runners, browser screenshot capture, production deployment, code fixing, hosted interactive web dashboard, PyPI/npm publication, and certified support in every agent.
- One-click custom agent plugin installation or GitHub repository-topic administration.

The user and host agent remain responsible for approval of modifications and for supplying genuine runtime evidence.
