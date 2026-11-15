# MirrorMap engineering roadmap — Evidence Intelligence

**Status:** proposal and implementation tracking; not a promise of completed functionality. External tools are optional adapters, not built-in capabilities.

| Research idea | Current implementation (v0.5 preview) | Next validation milestone |
|---|---|---|
| ProofChain | Informational evidence passports with file hashes and observation revisions | Structured provenance receipts and independently signed attestation adapter |
| Unknown Resolution Engine | Deterministic, read-only investigation suggestions and candidate source IDs | Evidence acquisition cost and human-reviewed answer-to-criterion matching |
| Behavior Twin | Explicitly imported user-journey steps and reported test observations | Optional authorized Playwright trace ingestion with independently verified semantics |
| Counterfactual Change Lab | Direct-link possible-impact reports | Isolated patch sandbox and controlled regression experiments |
| Evidence Time Machine | Existing baseline snapshots plus revision freshness output | Artifact-level history and invalidation of evidence when dependencies change |
| Approval Capsule | Unsigned, **non-authorizing** plan draft | A trusted host/runner enforcing real consent, file scopes and expiration |
| Absence Witness | Existing reviewed scoped absence confirmations | Measured scan coverage and tamper-evident coverage manifests |
| Specification Conflict Detector | Explicit conflict declarations and criterion-ID collisions only | Opt-in suggested semantic contradictions, always reviewed |
| Test Strength Analyzer | Existing imported JUnit outcomes | Opt-in mutation score and test quality artifact adapters |
| Change Blast Radius | Exact reviewed implementation-to-requirement link lookup | Bounded transitive dependency analysis |
| Multi-repo Contract Atlas | Not implemented | Audited repo boundary model and Pact/OpenAPI import |
| Independent Reviewer | Not implemented | Permissioned separate verification process + disagreement reports |
| Assumption Debt | Read-only unknown/unverified inventory | Review ownership, aging and resolution history |
| Adaptive Verification Budget | High/medium suggestions; estimated cost unknown | Evidence-based information-gain and resource constraints |
| Evidence Replay Capsule | SHA-256 handoff manifest and verifier | Reproducible sandbox definitions and artifact provenance |
| Runtime-to-Requirement | Not implemented | Import sanitized OpenTelemetry spans and error reports |
| Feature Readiness Matrix | Functional status plus explicitly unassessed dimensions | Security/accessibility/performance evidence adapters |
| Project Knowledge Handoff | Read-only artifact integrity manifest | Reproducible multi-agent exchange and optional signatures |
| Local-First Privacy | Standard-library CLI and offline HTML | Auditable optional local-LLM integrations and privacy controls |
| Audit Evaluation Lab | Fixture-level classification metrics | Versioned external benchmark, precision/recall thresholds, blind evaluations |

## Principles

- **No invented verification.** Importing an observation is not independent proof of its provenance.
- **No automatic write permission.** Execution requires explicit user authorization enforced outside the model-generated artifact.
- **No dependency inflation.** Prefer optional integrations over one monolithic agent runtime.
- **No ranking by feature count alone.** Validate each phase against realistic fixed-defect projects, false positives, privacy risks and regression behavior.

## Recommended next release

Prioritize a real-world fixture benchmark, then an opt-in Playwright trace importer (not automatic browser execution) and a verified, scoped read-only impact traversal. A hosted multi-user dashboard and automatic code-changing executor should not precede a complete threat model.
