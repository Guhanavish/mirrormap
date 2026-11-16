## Unreleased — Relay continuity hardening and website

- Fix Cursor `beforeSubmitPrompt` output to avoid unsupported context injection; preserve metadata-only event capture.
- Add read-only `relay field-check` CLI validation for recorded cross-agent lineage, safety, workspace fingerprints, and post-handoff milestones.
- Add regression coverage and documentation distinguishing synthetic events, recorded handoff validity and real-host certification.
- GitHub topic metadata correction and real-host interoperability signoff still require authorized GitHub settings and running installed host apps.

- Add conditional user-prompt hook reminders without retaining the user's input.
- Expand CLI-driven synthetic handoff tests and add live-host field validation instructions.
- Update the hosted website content to include Relay v0.6 and Evidence Intelligence v0.5 development previews.
- Keep v0.4 as the latest official release pending observed real-host handoff tests.

## [0.6.0b1] — MirrorMap Relay (development preview; no official GitHub Release)

### Added
- Opt-in, project-filtered Codex/Claude Code/Cursor hook configuration previews, installs and removals.
- Privacy-preserving SQLite session recorder with Git fingerprints, pending-tool tracking and bounded local event hash chains.
- CLI session list, inspect, verify, structured notes, checkpoint and read-only resume summaries, plus explicit cross-agent session adoption after safety checks.
- Two allowlist-filtered MCP tools for session discovery and checkpoint recovery.
- Agent skill instructions, detailed Relay guide and synthetic interruption, privacy, tamper, installation and MCP regression tests.

### Honest limitations
- Hook support is based on documented lifecycle schemas; not all host versions or crash scenarios are live-tested.
- Skill installation alone does not start recording. User must apply/trust hooks and install the Python CLI separately.
- No hidden model thoughts or transcript recovery, automatic execution, cross-device sync, provenance authentication, or distributed session locks.
- Sessions are local to the OS user and auto-tracking does not guarantee semantic task details unless milestones are recorded.

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

## [0.5.0b1] — 2026-11-15 — Evidence Intelligence (development preview, not a GitHub Release)

### Added
- Feature evidence passports (source hashes, imported verification records, revision freshness and explicit confidence limits).
- Read-only Unknown Resolution investigations, assumption-debt and per-dimension readiness outputs.
- Explicit specification-conflict declarations and acceptance-criterion collisions, with human-review tasks instead of silent resolution.
- Limited change-impact previews based only on reviewed source links; optional imported behavior-journey steps.
- Non-authorizing approval drafts and SHA-256 audit handoff verification.
- Local fixture-level evaluation metrics, dedicated JSON schema contracts, tests and offline dashboard links to intelligence reports.

### Safety and compatibility
- No application/test execution or code edits; evidence and approval claims remain host-verifiable only.
- An audit now rejects nonempty output directories to prevent accidentally reusing stale evidence. Use a fresh `--out` for each run.
- This is a source branch preview, **not** an official v0.5 GitHub Release. Advanced integrations remain in `docs/ROADMAP_NEXT.md`.


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
