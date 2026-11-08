## [0.4.0] — 2026-11-08 — Evidence Atlas (beta)

### Added
- Automatic read-only collection of **existing JUnit XML** reports, with bounded parsing and SHA-256 provenance.
- Explicitly reviewed testcase-to-acceptance-criterion mappings; missing mappings never become verified evidence.
- Interactive, standalone three-lane graph in `dashboard.html` with search, status filters, zoom, keyboard selection, and evidence details.
- New `projectmirror evidence` command to import reports into an existing audit folder.
- Optional `junit` and `test-map` inputs for the reusable GitHub Action.
- Reproducible JUnit fixture, documentation and regression tests.

### Safety
- No tests executed by the importer or dashboard.
- Mapping revision equality and valid criterion IDs required to promote evidence.
- No remote scripts, telemetry, network dependency or code edits.
- XML DTDs/entities rejected, size and count limits imposed, raw tracebacks excluded.

## [0.3.0] — 2026-11-08 — Route Atlas (beta)

### Added
- Conservative source-only candidate-route discovery for Next.js App/Pages conventions and FastAPI literal route decorators, with evidence locators and explicit uncertainty labels.
- `mirrormap routes` / `python -m projectmirror routes` command for JSON route inventories without executing the project.
- Reusable `action.yml` composite GitHub Action, a PR workflow example, and documentation for read-only CI audit artifacts.
- Automated tests for supported route patterns, false-positive controls, and basic CLI use.

### Limitations
- Route candidates are **not** verified HTTP endpoints and do not prove successful deployments, authentication, or correct behavior.
- The composite action generates reports but does not import test evidence automatically or modify pull requests.
- No hosted dashboard, automatic browser tests, or production-release claims are implied.

# v0.2.0 — Evidence Atlas

- Added guided one-command audits with five clearly scoped modes.
- Added offline HTML reports, local MCP integration, Python SDK, candidate links, drift and PR views.
- Added non-overwriting skill installer, help guides, CI example and distinct MirrorMap brand design.
- Kept the evidence and user approval safety boundaries unchanged.

# Changelog

All notable changes are documented here. This project is in early beta; no production-stability guarantee is implied.

## [0.1.0] — 2026-11-08

### Added
- Portable Agent Skills `SKILL.md` with independent intent/implementation/verification maps.
- Dependency-free Python CLI for requirement import, structural repository indexing, evidence-linked comparisons, reports, remediation proposals, Mermaid visualization, and snapshots.
- Explicit read-only audit boundary and documented external approval model.
- Approval receipt **metadata consistency** checker (not an authorization or signature system).
- Portable JSON Schema documents and reviewed example fixtures.
- Regression tests and GitHub Actions Python matrix.
- Accessible project banner, detailed README, contribution/security guidance, and publication checklist.

### Known limitations
- Full semantic mapping and runtime test execution require external tools and reviewed evidence.
- JS/TS scanning uses export heuristics, not a full language parser.
- Structural source indexing is not evidence that a user-visible feature works.
- The CLI never makes changes to the audited project, including after plan approval.
