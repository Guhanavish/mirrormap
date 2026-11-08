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
