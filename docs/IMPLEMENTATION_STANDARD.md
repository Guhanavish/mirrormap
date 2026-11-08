# ProjectMirror — Unified Agent Skill Implementation Standard

**Status:** Consolidated design specification / proposed implementation standard  
**Version:** 1.0-draft  
**Date:** 8 November 2026  
**Audience:** Agent-skill developers, coding-agent integrators, and reviewers  
**Purpose:** Convert six concept proposals into one implementable, portable, evidence-driven workflow.  
**Working product name:** ProjectMirror (`project-mirror` for the Agent Skills folder).

> **Decision:** ProjectMirror is **not** primarily a mindmap generator. It is an **evidence-linked, specification-to-implementation drift auditor with human-approved remediation and independent re-verification**. The mindmap is a generated visualization of its project knowledge graph.
>
> This is a **design standard**, not a claim that the software is already implemented or that all findings can be automated. Any implementation of this standard must be tested on real projects before being considered production-ready.

---

## 0. Executive decision in one page

The skill must:

1. Establish **intended behavior independently of the code being audited**. Requirements come from user-approved specifications, product documents, tickets, and explicit instructions; undocumented guesses never silently become requirements.
2. Build a **structured graph of actual implementation**, citing inspected files, routes, schemas, configuration, and observables.
3. Maintain a **separate verification layer** for test results, deployed behavior, logs, browser flows, and limitations.
4. Diff the graph **in both directions**: requirement → implementation and implementation → requirement. Use deterministic code for comparisons once identities are resolved.
5. Distinguish **missing**, **partial**, **broken**, **mismatched**, **unverified**, **unknown**, and **undocumented** without overstating certainty.
6. Produce a **traceability matrix**, **visual mindmap**, **evidence-backed findings**, and **dependency-ordered remediation plan**.
7. **Stop before modifying project code, tests, docs, configuration, environments, or production.** Execute only after a **specific, explicit user approval** tied to the plan version, repository revision, environment, and task IDs.
8. Implement in an isolated working branch/worktree where possible, re-run meaningful checks, and require **observable, preferably independent verification** before marking anything complete.
9. Save **versioned graph snapshots** to enable future audits and incremental drift detection.
10. Ship first as a **portable `SKILL.md` plus platform-independent Python CLI**. Add optional MCP integration, UI, CI, and advanced analysis only after the core loop passes evaluation.

**Architecture shorthand:**

```text
Approved user intent / specs        Repository / deployed system       Tests / observations
              |                                |                                |
              v                                v                                v
        INTENT MAP                     IMPLEMENTATION MAP                 VERIFICATION MAP
              |                                |                                |
              +----------------+---------------+--------------------------------+
                               |
                  Traceability graph + evidence registry
                               |
            Deterministic diff + evidence-aware classification
                               |
                 Findings + visual map + remediation plan
                               |
                    EXPLICIT USER APPROVAL
                         /             \
                      Reject        Approve selected tasks
                                         |
                             Controlled implementation
                                         |
                             Independent re-verification
                                         |
                                Snapshot + re-audit
```

## 1. Source comparison: what each proposal contributes

Six documents were reviewed. Their filenames are retained so the design can be traced back to the supplied proposals; filenames are not product requirements.

| Source | Strongest contribution | What to retain | What to modify / avoid |
|---|---|---|---|
| **Deepseek - Maindmmapp MD.md** | Rigorous phase-gated drift audit; evidence-linked traceability; generator–auditor symmetry; dedicated evals | Requirement/implementation/test traceability, stable IDs, bidirectional auditing, test-first verification, `[SPEC GAP]` stop | It suggests some reversible changes may be auto-verified without user approval; **reject this** for the present user requirement: all project modifications require approval |
| **Gemini - skiill - mindmap(1).md** | Dual machine/visual representations; code skeleton extraction; telemetry; dependency ordering; actionable checkbox reports | JSON + Mermaid, AST/tree-sitter as optional optimization, logs/coverage, topological task planning, visual reporting | Claims such as broad platform compatibility or very large token savings should be treated as **hypotheses**, not guarantees; checkbox state is **not** sufficient proof of approval |
| **spec-drift-skill-notes(1).md** | Independent target vs actual sources; deterministic diff engine; runtime verification; granularity and stale-spec warnings | The central anti-circularity rule, deterministic comparisons, runtime tests, clear target-spec precedence | Pure equality on titles is insufficient; matching identities needs a validated link stage; unknown/unverified must not be called missing |
| **project-gap-audit-skill-design.md** | Avoid inferred requirements; evidence-per-node; simple stdlib-first and portable implementation | Separate declarative vs derived facts, concise CLI MVP, re-audit loop | Two categories alone do not capture test status; split implementation evidence and verification evidence |
| **roject Mindmap Audit — Agent Skill Desig.md** | Snapshot history, progressive disclosure, tiered scope, CLI + MCP packaging | Versioned diffs, per-module expansion, confidence, impact scoring, integration roadmap | Scanning code first is excellent for *implementation discovery*, but the **intent map must never be reconstructed from code alone** |
| **ProjectMirror_Concept_and_Recommendations.md** | Three-map architecture; permission modes; user-scoped approval; change-impact intelligence | Independent Intent/Implementation/Verification Maps, permission boundaries, affected-branch re-analysis, output formats | Add stricter deterministic matching, canonical schema, explicit coverage accounting, eval thresholds, and host-enforced approval |

### 1.1 Consensus across the proposals

- The graph/JSON inventory is canonical; Mermaid or a mindmap is a view.
- Every claim needs provenance and relevant evidence.
- The system must compare requirements with code rather than merely summarize code.
- Unsupported inferences must remain labeled as assumptions or suggestions.
- The agent must propose a plan, stop for review, and only then change the project.
- A fix isn't complete until independently checked with a test, probe, or other observable evidence.
- Platform-independent logic and small skills beat one enormous, host-specific prompt.

### 1.2 Conflicts resolved into a single standard

| Disagreement | Final standard | Why |
|---|---|---|
| Two maps or three? | **Three logical maps**: Intent, Implementation, Verification; only two independent origin domains for requirements/code | Prevents “implemented” from being confused with “working”; preserves independence of the target spec |
| Build intent from code? | **No.** Code may generate *questions* or *undocumented-feature candidates*, never approved intent | Avoids circular audits and invented requirements |
| LLM diff vs code diff? | LLM proposes semantic node links; **validated links + deterministic diff** determine classifications | Maintains useful reasoning while improving reproducibility |
| Auto-fix small changes? | **No project modifications without approval**, even low-risk edits; risk determines extra checks | Matches requested user-control contract |
| Mindmap as the database? | Structured graph with stable IDs as source of truth; mindmap rendered from it | Enables versioning, relationships, assertions, and reliable re-runs |
| One giant scan vs selective scanning? | Inventory the whole accessible repo, then progressively inspect **bounded scopes and dependency neighborhoods** | Controls context size and cost |
| MCP essential or optional? | **Optional adapter, not MVP dependency** | A local CLI and standard skill already cover the base workflow |
| Missing vs not found? | “Missing” requires enough search/coverage evidence; otherwise **unknown** | Reduces false positives |
| Checkboxes = approval? | Checkboxes select tasks for review; **separate explicit user approval record** authorizes execution | Avoids silent or accidental authorization |

## 2. Normative language and scope

Use the words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** as design requirements for this *proposed ProjectMirror standard*. They are not claims about the official Agent Skills specification.

### 2.1 Supported project classes

Primary target: software repositories with local source access (web applications, backends, desktop applications, mobile applications, libraries, and services). Support for hardware, embedded targets, monorepos, remote-only deployments, or proprietary integrations is adapter-dependent. If repository or runtime access is absent, the skill MUST report exactly what it could and could not verify.

### 2.2 Audit scope and depth

- **Scope:** whole repository, selected module, individual feature, branch/commit, or selected user journey.
- **Depth L0 — Overview:** modules and major capabilities.
- **Depth L1 — Functional:** features, routes, screens, integrations, flows.
- **Depth L2 — Behavioral:** component states, permissions, validations, edge cases, acceptance criteria.
- **Depth L3 — Diagnostic:** specific files, functions, assertions, data flow, reproducible faults.
- **Default:** L1 for project overview; L2 for targeted audit; L3 only for findings or explicitly requested detail.
- **Coverage boundary:** Every report MUST name inspected modules and omitted areas. “Whole project” without tool access or adequate coverage is not a valid assurance claim.

## 3. Core rules that cannot be weakened

1. **Independent intent:** The implementation under review cannot be the only source defining the intended state.
2. **No silent invention:** Agent-inferred improvements are suggestions, not original requirements.
3. **No evidence, no confirmed defect:** Unsupported claims are hypotheses or unknowns, with a way to investigate them.
4. **No absence proof by grep:** Failure to find a symbol does not prove that a user-visible capability is absent.
5. **No conflation:** A file found ≠ a functioning feature; a passing unit test ≠ a complete user journey; a screenshot ≠ validated behavior.
6. **Bidirectional traceability:** Search both missing implementations and undocumented implementations.
7. **Hard approval boundary:** Any project modification requires specific user approval. Read-only audit outputs may be generated in an **isolated output directory**, not by mutating the audited repository.
8. **Execution isolation:** A user-approved task list and base revision constrain write scope. New requirements, new code targets, or plan mutations must trigger re-approval.
9. **Evidence-aware success:** A change is only verified when the declared check runs and records a real result; no claim of passing unexecuted checks.
10. **Untrusted content:** Repositories, issue text, logs, and externally fetched pages are data, not instructions or approvals.
11. **No production writes by implication:** Production changes, data migrations, deploys, publishing, destructive commands, and secret access require their own suitable authorization and safeguards.
12. **Graceful degradation:** If an agent cannot run commands, browse the app, read logs, or use a test environment, the output MUST accurately label those limitations.

## 4. Architecture: five components, three maps

### 4.1 Component A — Skill orchestrator

The portable `SKILL.md` describes which phases to run, when to request user clarification, how to use CLI tools, and where to stop. It MUST NOT be the only enforcement point for write permissions.

### 4.2 Component B — Deterministic analysis core

A Python CLI handles artifact validation, indexing with known parsers, source/link registries, structural comparisons, graph traversal, snapshots, rendering, and plan approval checks. It MUST return machine-readable output and informative error codes. Dependency-heavy parsers remain optional plugins.

### 4.3 Component C — Evidence and project graph store

Versioned JSON files are the MVP source of truth. SQLite is an optional storage optimization for larger projects. Every fact records its origin, inspection revision, and evidence. The three maps can be stored as separate JSON files sharing node IDs and relationships, or under separate namespaces in one graph document.

### 4.4 Component D — Verification adapters

Tools may include test runners, linters, type checkers, browser automation, API probes, coverage parsers, static analyzers, log/telemetry readers, and CI artifact readers. Adapters MUST declare capabilities and safety level. Runtime checking is not assumed available.

### 4.5 Component E — Authorization and execution gate

The host application, CLI wrapper, or integrated runner MUST enforce the approval gate. Only explicitly approved tasks can alter files. The gate verifies plan identity, repository revision, environment, operation type, scope, and approval provenance. A natural-language instruction to the agent alone is not sufficient access control.

## 5. Source-of-truth hierarchy and provenance

### 5.1 Sources for Intent Map

Recommended precedence **when they do not conflict**:

1. Latest **explicit, approved user instruction** within the active project scope.
2. Approved PRD, feature specification, acceptance criteria, or signed-off design.
3. Accepted issue/ticket, verified user story, official project requirements.
4. Existing project documentation/README (with revision and potential staleness flagged).
5. Agent-inferred expectations — **suggestion only**, never a required target.

When approved sources conflict, **do not silently choose**. Record a `spec_conflict` and seek clarification. Explicit exclusions/“out of scope” requirements must be captured.

### 5.2 Sources for Implementation Map

Source code, symbol index, AST/route parser, schemas, configuration, environment feature flags, artifacts, branch/revision, and accessible deployed components. Source-code comments are not proof that a feature exists. Coverage reports may describe the exercised lines, not the correctness of the intended behavior.

### 5.3 Sources for Verification Map

Test case identifiers, actual results, assertions, screenshots, browser runs, endpoint probes, logs, failures, error traces, build checks, security-check evidence, and environment metadata. Observational evidence MUST include whether it was generated by the current audit, imported from an earlier run, or provided by the user.

### 5.4 No formal spec available

Enter **Intent Discovery Mode**:

- Inventory the project and identify user-visible features as **observed**, **not approved requirements**.
- Ask the user for expected behavior of relevant high-impact areas or offer a **draft requirements document for approval**.
- Until approved intent exists, do not calculate “% complete against spec” or call absent imagined functionality a missing requirement.
- You MAY report reproducible runtime failures with sufficient evidence even without full product requirements.

## 6. Canonical graph and schema contract

**Decision:** Use JSON as the portable canonical artifact; use a JSON Schema (2020-12 or another explicitly declared version) for validation. Mermaid/Markmap is derived. Store IDs and links separately from free-form labels.

### 6.1 Basic graph entities

| Entity | Key fields | Notes |
|---|---|---|
| `Project` | `project_id`, `repo`, `revision`, `branch`, `environment`, `runtime_build`, `scanned_at` | Base identity and audit manifest |
| `Node` | `id`, `kind`, `title`, `parent_id`, `map`, `scope` | Stable requirement, implementation, or verification identity |
| `Requirement` | `node_id`, `expected_behavior`, `acceptance_criteria`, `requirement_state`, `source_refs` | Only approved/inferred distinction authorizes target status |
| `Evidence` | `evidence_id`, `kind`, `uri`, `locator`, `captured_at`, `revision`, `environment`, `content_hash` | Attaches observable source, not just prose |
| `Edge` | `from`, `type`, `to`, `link_basis`, `confidence` | `implements`, `verified_by`, `depends_on`, `affects`, `derived_from` |
| `Finding` | `finding_id`, `requirement_id`, `classification`, `confidence`, `severity`, `evidence_ids`, `coverage`, `explanation` | Classification is distinct from evidence and impact |
| `PlanItem` | `task_id`, `finding_ids`, `proposed_operations`, `target_paths`, `dependencies`, `acceptance`, `verification`, `risk` | All actionable steps must be individually identifiable |
| `ApprovalReceipt` | `plan_digest`, `base_revision`, `approved_task_ids`, `actor`, `timestamp`, `environment`, `scope` | Created via a trusted user action / host, not generated by the LLM |

> Schema names above are ProjectMirror design choices and require implementation; they are not fields mandated by Agent Skills or MCP.

### 6.2 Minimum example: intended requirement

```json
{
  "id": "req.auth.refresh_token.rotation",
  "map": "intent",
  "kind": "security_requirement",
  "title": "Refresh-token rotation",
  "parent_id": "req.auth.refresh_token",
  "requirement_state": "approved",
  "expected_behavior": "Using a refresh token invalidates the previous token",
  "acceptance_criteria": [
    {"id": "ac.auth.rotation.invalidate_old", "statement": "The replaced token cannot be used again"}
  ],
  "source_refs": ["ev.spec.001"]
}
```

### 6.3 Implementation node

```json
{
  "id": "impl.api.auth.refresh_handler",
  "map": "implementation",
  "kind": "endpoint",
  "title": "POST /auth/refresh handler",
  "locator": "src/auth/routes.py:refresh",
  "implementation_state": "present",
  "source_refs": ["ev.code.014"],
  "revision": "<repository-commit-sha>"
}
```

### 6.4 Verification observation

```json
{
  "id": "verify.auth.rotation.old_token_rejected",
  "map": "verification",
  "kind": "test_result",
  "title": "Old refresh token rejection check",
  "test_id": "tests/test_auth.py::test_refresh_rotation",
  "result": "failed",
  "observed_behavior": "Old token remained usable after rotation",
  "environment": "test",
  "source_refs": ["ev.test.007"],
  "recorded_at": "<ISO-8601-timestamp>"
}
```

### 6.5 Relations

```json
[
  {
    "from": "impl.api.auth.refresh_handler",
    "type": "implements",
    "to": "req.auth.refresh_token.rotation",
    "link_basis": "explicit_reviewed_mapping",
    "confidence": "high"
  },
  {
    "from": "verify.auth.rotation.old_token_rejected",
    "type": "verifies",
    "to": "req.auth.refresh_token.rotation",
    "link_basis": "test_assertion",
    "confidence": "high"
  }
]
```

### 6.6 Stable ID policy

- Use a consistent namespace (`req.*`, `impl.*`, `verify.*`), module/domain path, and durable semantic identifier.
- Never generate IDs solely from display text if labels may change. Maintain aliases/migrations when IDs are renamed.
- Two equal titles do **not** automatically represent the same requirement.
- Use an explicit mapping table between requirements and implementation nodes; a model may *propose* links, but the deterministic evaluator consumes only validated links.
- Keep parent/child hierarchy separate from cross-cutting dependency edges. A project is a graph, not just a tree.

### 6.7 Status contract (avoid one overloaded `status` field)

**Intent status:** `approved | draft | inferred | conflicted | deprecated`  
**Implementation status:** `present | partial | absent_confirmed | unknown | inaccessible`  
**Verification status:** `passed | failed | not_run | inconclusive | blocked | stale`  
**Finding class:** `complete | missing | partial | broken | mismatch | unverified | unknown | undocumented | spec_conflict | suggestion`

Examples of classification:

| Evidence | Output | Important distinction |
|---|---|---|
| Approved requirement + implementation + relevant passing checks | `complete` | Only to the stated acceptance criteria; not “bug-free” |
| Approved requirement + sufficiently exhaustive scoped search verifies absence | `missing` | Require explicit coverage justification |
| Required handler is a stub and lacks major expected behavior | `partial` | Explain specific missing behavior |
| Actual behavior fails relevant reproducible test | `broken` | Cite test result, build, and observed fault |
| Behavior clearly differs from approved acceptance criterion | `mismatch` | May overlap operationally with broken; record primary class + facets |
| Implementation found but no behavioral checks | `unverified` | Do not promote to complete |
| Insufficient access or search coverage | `unknown` | Not missing |
| Code capability with no mapped, approved requirement | `undocumented` | Not automatically dead code or scope creep |
| Approved requirements contradict each other | `spec_conflict` | Resolve intent before proposing change |
| Potential feature not in accepted scope | `suggestion` | Never inflate gap count |

**Additional rule:** Findings MAY contain separate facets (`security`, `accessibility`, `runtime`, `documentation`) but MUST have one primary classification and a rationale. Severity and evidence confidence are **independent**.

## 7. Deterministic comparison and evidence rules

### 7.1 Comparison pipeline

```text
(1) Load + validate all three maps
(2) Check revision, scope, environment, and spec consistency
(3) Resolve requirement-to-implementation mapping links
(4) Validate evidence references and freshness
(5) Compare approved acceptance criteria against observed implementation & checks
(6) Classify findings using fixed rules; mark ambiguities unknown
(7) Reverse scan: implementation nodes with no mapped approved requirements
(8) Generate traceability matrix, findings, and suggested remediations
```

### 7.2 Deterministic does not mean infallible

Semantic matching, expected-behavior interpretation, and deciding whether tests truly prove an acceptance criterion still require reasoning or human review. **Deterministic code should apply validated facts and rules, not pretend to understand arbitrary behavior from string equality.** Save the model's proposed mappings and their evidence for review.

### 7.3 Evidence quality

Each evidence record SHOULD carry at least:

```json
{
  "evidence_id": "ev.test.007",
  "kind": "test_result",
  "uri": "artifact://run-042/tests/test_auth.json",
  "locator": "tests/test_auth.py::test_refresh_rotation",
  "revision": "<repository-commit-sha>",
  "environment": "test",
  "captured_at": "<ISO-8601-timestamp>",
  "content_hash": "<sha256-of-record-or-artifact>",
  "summary": "Old token was accepted after rotation"
}
```

Evidence sources should be reproducible or inspectable where possible. Redact tokens/passwords and sensitive data. Paths, line numbers, and hashes describe a snapshot: stale or shifted locations MUST be flagged, not silently reused.

### 7.4 How to prove absence responsibly

Do not label a requirement `missing` based on a single text search. Search appropriate routes, symbol references, build/runtime configuration, generated files, and feature flags within the audit scope; account for dynamic registration and externally hosted functionality. If coverage is insufficient, return `unknown` and propose a verification task.

### 7.5 Traceability matrix (required output)

| Requirement | Approved acceptance criterion | Implementation evidence | Test / runtime evidence | Classification | Confidence |
|---|---|---|---|---|---|
| `req.auth.rotation` | Reject old refresh token | Route handler found | Rotation test fails | Broken | High |
| `req.auth.rate_limit` | Throttle repeated failures | Middleware wired to route | Integration test passes | Complete | High |
| `req.admin.audit_log` | Record administrator changes | No implementation after bounded review | No relevant test | Missing or Unknown per coverage | Medium / Low |

The examples are illustrative, not findings from a real repository.

## 8. Phase-gated workflow and artifacts

| Phase | Name | Main operation | Required artifact | May change audited project? |
|---|---|---|---|---|
| P0 | Scope & permissions | Confirm sources, target, branch, environment, limits | `audit-manifest.json` | No |
| P1 | Extract intent | Build approved requirements, mark assumptions/conflicts | `intent-map.json` | No |
| P2 | Index reality | Inspect modules, routes, schemas, tests, flags | `implementation-map.json` | No |
| P3 | Verify behavior | Execute authorized safe checks or import evidence | `verification-map.json` | Not by default; use isolated test environment |
| P4 | Diff & triage | Compare nodes, quantify confidence/coverage | `findings.json`, `traceability.md` | No |
| P5 | Plan & review | Generate dependency-ordered tasks and visual map | `remediation-plan.md`, `plan.json`, `mindmap.mmd` | No |
| **GATE** | **Human approval** | Review/edit/reject/approve explicit task IDs | `approval-receipt.json` | **HARD STOP** |
| P6 | Execute | Apply approved tasks, capture diffs | `execution-log.json`, git diff | **Only approved scope** |
| P7 | Independently verify | Re-run probes/test and check diff vs plan | `verification-report.md` | Only approved verification actions |
| P8 | Reconcile | Update affected maps and save new snapshot | `snapshot-manifest.json`, reports | No further project changes |

**Note on test execution:** Some tests run migrations, create files, invoke remote services, or mutate databases. Treat such tests as potentially write-capable. Run them in a disposable sandbox with mocked services or get appropriate explicit permission. “Read-only audit” does not automatically authorize unsafe testing.

### 8.1 P0 — Scope contract

Before scanning, record: repository root, allowed paths, excluded paths, required environments, intended source documents, branch/revision, test permissions, tool availability, time/resource limits, and an explicit output directory. Report if the repo changes during the audit.

### 8.2 P1 — Intent extraction

Build the intended graph **from approved requirements**, not from the code. When context is incomplete, record `draft`/`inferred` nodes and seek targeted confirmation rather than silently adding requirements. Acceptance criteria MUST be concrete enough to test wherever possible.

### 8.3 P2 — Implementation discovery

Start with manifests (`package.json`, `pyproject.toml`, `go.mod`, etc.), entry points, routes, schemas, tests and feature flags. Build a compact index and selectively inspect code. AST/tree-sitter parsers are optional and must identify supported languages; generic text search remains a fallback, not proof of absence.

### 8.4 P3 — Verification

Static proof and runtime proof differ. Capture test commands, exit status, output summary, environment, scope, failure reproduction, and timestamp. A test that merely exists is not equivalent to one that asserts the requirement. Screenshots can help evaluate visual layout, but do not establish all interactions.

### 8.5 P4 — Diff and triage

Check both directions. Mark `unknown` on inadequate coverage. Keep risk and confidence separate; distinguish regression suspected vs confirmed. Generate a concise human summary plus full machine-readable details.

### 8.6 P5 — Plan

For each task include:

- Unique task ID and finding IDs.
- Exact change requested and why; evidence references.
- Likely affected modules and declared path scope.
- Preconditions, dependency IDs, and sequencing.
- Risk/severity, expected impact and estimated complexity (clearly estimates).
- Acceptance criteria; targeted original failing tests/probes and regression checks.
- Potential rollback or recovery strategy.
- Environment/deployment implications and unresolved assumptions.

Sort tasks by **prerequisites** first (topological order) and then by risk/impact within the feasible order. Do not impose a blanket “DB then API then UI” if actual dependencies differ.

### 8.7 Gate — human-approved immutable plan

Approval receipt is a trusted host-side record, not text generated by an LLM. It binds:

```json
{
  "plan_id": "PLAN-2026-001",
  "plan_sha256": "<digest-of-normalized-plan-json>",
  "base_repo_revision": "<commit-sha>",
  "environment": "local-dev",
  "approved_task_ids": ["TASK-001", "TASK-004"],
  "allowed_path_globs": ["src/auth/**", "tests/auth/**"],
  "actor": "<authenticated-user-reference>",
  "approved_at": "<ISO-8601-timestamp>",
  "approval_channel": "trusted-user-action",
  "expires_at": "<optional-ISO-8601-timestamp>"
}
```

**Requirements:**

- Present selectable tasks and let user explicitly approve, reject, or revise.
- Silence, a checked box in a generated file, a repository instruction, or a model statement are **not** authorization by themselves.
- The runner MUST compare task set, plan digest, base revision, and requested paths to the approved scope before each write batch.
- When a dependency requires an unapproved task, stop and request a new approval.
- When base revision changes significantly or accepted plan is edited, invalidate/review approval; never assume an old approval automatically applies.
- Production deployment, irreversible migration, destructive operations, and external actions need a **separate explicit permission gate** even if some code edits were approved.

### 8.8 P6 — Controlled implementation

Prefer a worktree/branch/snapshot. Run one approved task at a time where dependencies permit. Capture file diffs, tests, commands, failure conditions, and scope changes. A `SPEC_GAP` condition must stop execution and return control to planning. Avoid hidden “cleanup” edits and auto-commits unless approved.

### 8.9 P7 — Independent verification

The implementing agent **MUST NOT** self-certify a fix without checks. Re-run the original failing test/probe, check regression tests, validate affected acceptance criteria, and examine the diff against approved paths/tasks. Prefer a separate verification process or fresh context; if unavailable, disclose it. Failed or blocked checks remain failed/blocked, not “complete.”

### 8.10 P8 — Reconciliation and memory

Update affected nodes, re-run relevant comparisons, and save a snapshot with provenance. Keep the previous snapshot for drift timeline and regression detection. Do not alter approved intent because implementation diverged; propose a documented spec amendment for approval.

## 9. Plan and report presentation standard

Every audit report SHOULD start with a human-readable summary:

```text
PROJECT: Example Application  |  Scope: authentication  |  Revision: abc123
Spec sources: approved requirements v3
Access: repo + sandbox tests; production unavailable

Requirements reviewed: 24
  Complete: 12   Missing: 2    Partial: 3
  Broken: 1     Mismatch: 1   Unverified: 3   Unknown: 2
Undocumented implementation candidates: 2 (counted separately)

Critical caveat: production behavior was not inspected.
Plan: 5 proposed tasks; zero project changes performed.
Next: review and explicitly approve selected task IDs.
```

Numbers are **illustrative**. Do not compute a universal “project health score” without documented denominator and coverage caveats. If a score is requested, report both coverage and confidence; keep undocumented code separate from approved requirement totals.

### Required human outputs

1. `audit-report.md`: high-level context, coverage, confirmed findings, hypotheses, and limitations.
2. `traceability-matrix.md`: requirement → implementation → test evidence.
3. `mindmap.mmd` or `mindmap.md`: visual overview with stable IDs and state legend.
4. `remediation-plan.md`: task checklist for review, with risk, dependencies, and acceptance criteria.
5. `verification-report.md`: after approval/execution, actual changed files and tested results.

The map renderer SHOULD support branch collapse and one module at a time. Avoid putting 10,000 nodes in one Mermaid diagram; render overview + scoped subgraphs. Mermaid flowchart may express cross-component relationships better than its mindmap syntax.

## 10. Portable packaging and proposed repository structure

```text
project-mirror/
├── SKILL.md                       # Required Agent Skills entry point
├── README.md                      # Human installation/use guide
├── LICENSE                        # Choose before public release
├── pyproject.toml                 # Optional CLI installation package
├── projectmirror/                # Shared Python core (not required by spec)
│   ├── __main__.py                # `python -m projectmirror ...`
│   ├── manifest.py
│   ├── schemas.py
│   ├── evidence.py
│   ├── indexer.py
│   ├── linker.py
│   ├── diff.py
│   ├── planning.py
│   ├── approval.py
│   ├── execution_guard.py
│   ├── verification.py
│   ├── rendering.py
│   └── snapshots.py
├── schemas/
│   ├── project-manifest.schema.json
│   ├── graph.schema.json
│   ├── finding.schema.json
│   ├── plan.schema.json
│   └── approval-receipt.schema.json
├── references/
│   ├── evidence-policy.md
│   ├── classification-policy.md
│   ├── approval-policy.md
│   ├── source-precedence.md
│   └── adapters.md
├── templates/
│   ├── audit-report.md
│   ├── remediation-plan.md
│   └── verification-report.md
├── examples/
│   └── toy-auth-project/
├── tests/
│   ├── fixtures/
│   ├── test_diff.py
│   ├── test_gate.py
│   ├── test_evidence.py
│   └── test_snapshot.py
└── adapters/                     # Optional, after CLI is validated
    ├── mcp/
    ├── ci/
    └── host-guides/
```

**Output directory:** Prefer `.projectmirror/` outside the audited repo or within a dedicated untracked/ignored artifacts folder. The core repo MUST remain unchanged in audit/planning modes. `.gitignore` edits, even to hide artifacts, are edits and therefore should not occur without approval.

### 10.1 Agent Skills compliance

The official Agent Skills pattern uses a directory with **`SKILL.md`**, YAML frontmatter, a mandatory `name` and `description`, and optional supporting scripts/references/assets. Keep the `SKILL.md` focused and load detailed rules from references progressively. Use portable fields for correctness; host-specific tool permission mechanisms are adapters, not assumed universal.

A suitable frontmatter example:

```yaml
---
name: project-mirror
description: >
  Audit software projects against approved requirements using evidence-backed
  implementation and verification maps. Detect spec drift, missing or broken
  features, and undocumented behavior; generate a remediation plan; stop for
  explicit user approval before making any code or environment changes.
---
```

The folder name `project-mirror` must match the chosen skill name when the host expects standard naming. Validate before release against the current Agent Skills specification and available reference validator.

### 10.2 Platform support strategy

- **Tier 1:** Agents that natively load Agent Skills: install the folder in the host's documented skill directory; verify discovery and invocation per host.
- **Tier 2:** Agents with repository instructions/rules but no native Agent Skills support: create a thin host-specific rule pointing to the canonical workflow/CLI. This is a **compatibility adapter**, not necessarily equivalent to native skill loading.
- **Tier 3:** Agents with tool calling: expose the same read-only and privileged capabilities through an optional MCP server.
- **Tier 4:** CI or scheduled analysis: call the CLI without agent execution, producing reports and diffs for human review.

Do **not** promise compatibility for a platform until it has passed invocation, tool permission, approval, and verification tests. As of the current design review, official documentation confirms the general Agent Skills directory format and documents Codex support, but host behavior varies.

### 10.3 MCP later, not first

MCP can expose `project_scan`, `graph_read`, `graph_diff`, `render_map`, `plan_read`, and `verification_read`. Privileged `apply_approved_plan` must enforce approval in the server itself. A remote MCP tool must not be allowed to forge or silently create user approval receipts. Use current MCP protocol/SDK documentation, not outdated 2025-only assumptions, when implementing this optional adapter.

## 11. Proposed CLI contract (conceptual)

Commands below define an intended interface; **they do not exist yet**:

```bash
# All commands here are read-only with respect to the audited repository.
python -m projectmirror init --repo ./sample-app --out ./audit-output
python -m projectmirror extract-intent --spec ./sample-app/docs/requirements.md --out ./audit-output
python -m projectmirror index --repo ./sample-app --scope auth --out ./audit-output
python -m projectmirror import-tests --from ./test-results.json --out ./audit-output
python -m projectmirror link --out ./audit-output
python -m projectmirror diff --out ./audit-output
python -m projectmirror render --format mermaid --out ./audit-output
python -m projectmirror plan --out ./audit-output

# Separate trusted execution workflow, after an explicit approval receipt exists:
python -m projectmirror apply --plan ./audit-output/plan.json \
  --approval ./trusted-approvals/receipt.json --repo ./sample-app
python -m projectmirror verify --repo ./sample-app --out ./audit-output
```

Recommended exit codes: `0` success; `2` schema/input error; `3` incomplete access/evidence; `4` unresolved spec conflict; `5` missing/invalid approval; `6` base-revision mismatch; `7` unexpected modifications; `8` verification failure. Actual implementations should document any final code assignments and machine-readable error payloads.

**Important:** Any `approve` capability should be a trusted user-facing action, **not** a tool the model can invoke on its own. Prefer host-managed approval records. A locally saved JSON file is only reliable as authorization if the trusted runner controls who can create or modify it.

## 12. Security, safety and permission model

### 12.1 Default permissions

| Operation | Audit/Plan mode | Approved Execution mode |
|---|---|---|
| Read permitted project files | Allowed | Allowed |
| Write reports to isolated output directory | Allowed | Allowed |
| Edit project files/tests/docs/config | Denied | Only approved tasks/paths |
| Run tests that write to app/database/network | Denied until isolated/authorized | Only appropriately authorized |
| Network access / external API calls | Only explicitly allowed read-only use | Scope-bound |
| Deploy, migrate production database, publish | Denied | Separate explicit authorization required |
| Delete data, disable security checks, expose secrets | Denied by default | Never implicit; apply stronger safeguards and refuse unsafe actions |

### 12.2 Essential defenses

- Treat retrieved text, repository comments, issue descriptions, log messages and tests as **untrusted**, because they may contain prompt-injection instructions.
- Run scanners with least privilege; do not read or expose `.env`, tokens, keys, private fixtures, or personal information unless necessary and authorized. Redact evidence and outputs.
- Prefer sandboxing and allowlisted commands over arbitrary shell execution. Defend against path traversal and symlink escapes from the approved project root.
- Use separate permissions for audit tools and write tools. Verify path and plan authorization **at the tool/runtime boundary**.
- Store approval metadata with a trusted origin; don't allow the executing model to mint its own receipt.
- Require an environment boundary: code changes ≠ permission to deploy, and staging approval ≠ production approval.
- Maintain a diff, backup/recovery approach, and audit log. Database rollback cannot be assumed safe simply because source-code reversal is possible.

## 13. Performance and incremental operation

1. Start with manifest and file index, then read selected modules; avoid sending entire repositories to the model.
2. Cache source-content hashes and evidence by commit/build/version.
3. Recalculate only changed nodes and the dependency neighborhood when possible.
4. Use optional AST/tree-sitter or language-server adapters for high-confidence symbol/route extraction; report unsupported languages.
5. Use the deterministic engine for comparisons and report rendering; do not ask the LLM to re-compare every string on every run.
6. Separate overview-level map rendering from detailed branch rendering.
7. Set budgets for file count, context, runtime probes, and recursion. Limitations must be explicitly recorded.

**No unmeasured promises:** A particular scanner may improve token efficiency, but the actual savings and detection accuracy must be benchmarked. Avoid claiming a fixed percentage improvement until measured.

## 14. Quality evaluation and release criteria

### 14.1 Required fixtures

Build small, controlled repositories with known specs and intentionally planted defects:

1. Feature **missing** with sufficient code coverage to confirm absence.
2. Implemented feature **broken** by a failing integration test.
3. Feature **present but untested** (must stay `unverified`).
4. **Undocumented endpoint** that exists outside the spec.
5. **Stale/contradictory spec** (must return `spec_conflict`).
6. **Opaque/inaccessible feature** (must return `unknown`, not missing).
7. **Prompt injection** inside README or issue text trying to bypass approval.
8. **Unauthorized edit attempt** before approval and after invalidating a plan digest.
9. **Wrong-branch / changed-revision** execution attempt.
10. **Approved change with regression**: original fix passes but another test fails.

### 14.2 Metrics

- **Precision:** true confirmed findings / all confirmed findings.
- **Recall:** planted detectable findings recovered / all planted detectable findings.
- **Evidence validity:** share of citations resolving to real source/test artifacts.
- **Classification accuracy:** correct status versus fixture ground truth.
- **Unknown/uncertainty calibration:** proportion correctly held as unknown instead of falsely missing.
- **Approval-gate compliance:** unauthorized project modifications **must be zero** in evaluation.
- **Re-verification reliability:** fixed status granted only when check actually ran and passed.
- **Repeatability:** equivalent inputs yield equivalent deterministic results after mapping review.
- **Portability:** same core workflow tested in at least two distinct agent hosts before multi-host claims.
- **Performance:** scan duration and model-token use by repository size and audit depth.

### 14.3 Proposed acceptance thresholds (targets, not measured results)

For controlled MVP fixtures, aim for >=90% evidence-citation validity and >=85% classification accuracy; report precision and recall independently rather than hiding one behind a health score. The **non-negotiable pass condition** is **zero unapproved project writes**. Do not advertise broad production-grade correctness on the strength of toy fixtures alone.

## 15. Implementation roadmap with delivery gates

| Release | Ship | Exit criterion |
|---|---|---|
| **M0 — Written contract** | This standard, schema outline, first tests, naming | Team agrees on semantics and approval boundary |
| **M1 — Portable skill MVP** | `SKILL.md`, intent extraction prompts, repo file inventory, basic JSON map, report/plan templates | Reproducible audit of one small repository; no project writes |
| **M2 — Deterministic engine** | JSON Schemas, stable link table, classification, coverage checks, CLI diff, Mermaid rendering | Fixtures distinguish missing/broken/unverified/unknown correctly |
| **M3 — Verified auditing** | Test result ingestion, safe runtime adapter, traceability matrix, reverse mapping, snapshot history | Evidence-backed findings and before/after deltas |
| **M4 — Gated execution** | Trusted approval receipts, plan digests, scoped runner, revision lock, regression verification | Gate attack tests pass; no unapproved changes |
| **M5 — Cross-platform integration** | Host guides, optional MCP, optional AST adapters, CI | Cross-host evals pass and tool capability limitations documented |
| **M6 — Optional interface** | Interactive graph, filters, approval UI, timeline, workspace storage | UI renders same canonical graph and never bypasses gate |

**Recommended first implementation:** Python 3.11+ CLI with stdlib for inventory/diff/render orchestration, JSON files, a concise Agent Skills `SKILL.md`, and one known buggy test repository. Add JSON Schema validation with a documented dependency or equivalent validator; do not add large runtime/AI frameworks at the outset.

### 15.1 Concrete first sprint

1. Write `schemas/graph.schema.json`, `finding.schema.json`, `plan.schema.json` and fixtures.
2. Implement an `init` command that records audit scope/revision and writes only outside the repository.
3. Build `index` supporting at least one target framework/language; record unsupported cases as unknown.
4. Implement validated requirement-to-implementation links and a deterministic `diff` classifier.
5. Generate `audit-report.md`, `traceability-matrix.md`, and `mindmap.mmd`.
6. Generate a plan, then **stop**; deliberately do **not** implement code changes in the first sprint.
7. Test on a small project with one missing feature, one broken feature, and one unverified feature.
8. Add a trusted approval and execution layer **only once the audit quality is credible**.

### 15.2 Definition of done for M1

- Source inputs and audit revision visible in manifest.
- Three map files valid and evidence-linked (verification may be `not_run`).
- Visual map reproducibly generated from canonical data.
- Plan lists task IDs, prerequisites, evidence, acceptance checks, and risk.
- Unknown/untested correctly represented; no invented requirement silently treated as mandatory.
- Agent stops at approval gate, without modifying the audited project.
- Successful run on toy fixture and one real, non-sensitive codebase.

## 16. Example user experience

**User:** “Audit the login and registration part of this application against `docs/auth-requirements.md` and make a complete mindmap. Do not edit anything until I approve.”

**ProjectMirror:**

1. Indexes the selected requirements and records the repo commit.
2. Maps login, registration, session refresh, password recovery, permissions, forms, API endpoints, and error states at L2 depth.
3. Builds the implementation map from repo, routes, schemas, and tests; records unsupported/inaccessible surfaces.
4. Imports relevant existing tests and executes safe checks only if the environment permits.
5. Generates the graph view and traceability matrix.
6. Reports, for example, one reproducible broken session-refresh check, one unverified error state, and one undocumented route.
7. Proposes three tasks with explicit IDs and regression tests.
8. **Stops**. The user approves tasks 1 and 3 only.
9. The trusted executor validates plan/revision/scope, implements only tasks 1 and 3 in an isolated workspace, and runs checks.
10. The independent verifier re-tests and records passing, failing, or blocked status; task 2 remains untouched.

All examples above are fictional illustrations of the intended workflow.

## 17. Further improvements (post-MVP)

- **Evidence freshness and contradiction detection:** Recognize stale tests/docs after a branch change and request fresh results.
- **Dependency impact graph:** Identify what an approved change may affect and select corresponding regression tests.
- **Drift timeline:** Compare present versus prior approved snapshots and show when an inconsistency first appeared.
- **Requirement-change proposals:** Route undocumented functionality into an approval flow to amend the intent map, not an automatic rewrite.
- **Change-risk previews:** Show exactly which files, endpoints, data contracts, and workflows are likely affected *before* approval.
- **Separate-generation auditing:** Use a fresh context or a different evaluator for audit and verification when practical to reduce generator–auditor symmetry.
- **Privacy-preserving telemetry:** Optional integration with logs/error tracking through explicitly authorized, minimally scoped sources.
- **Interactive UI:** Collapsible graph + evidence pane + per-item approval + before/after comparison, all backed by the same graph store.

## 18. What is intentionally NOT promised

- Automatic discovery of every feature and bug from source files alone.
- Proof of functional correctness from passing tests without suitable coverage.
- Accurate production-state analysis without authorized access and relevant observability.
- Guaranteed portability to every agent application merely because the skill uses Markdown.
- Security of an approval gate enforced only by written prompts.
- Permission to edit/deploy based on an audit request, a generated checklist, or a prior plan.
- Safe rollback of all external side effects simply by reverting code.
- Perfect semantic matching of arbitrary names and requirements using string comparison.

## 19. Final standard decision and starting point

**Build one portable project-auditing core** with three evidence layers, stable identities, verified relations, deterministic comparisons, and a human-controlled execution boundary. Keep its `SKILL.md` small and all essential behavior in reusable schemas, scripts, and trusted tool permission checks. Publish visual mindmaps, reports, and plans as **derived artifacts**. Implement auto-execution **last**, once analysis quality, re-verification, and approval enforcement have been tested.

This combination preserves the best ideas from the six proposals while avoiding their central pitfalls: circular spec generation, speculative “missing” features, visual-only state, overconfident test claims, and unapproved code edits.

---

## Appendix A — Proposal traceability index

- **Deepseek - Maindmmapp MD.md:** evidence-linked traceability, generator–auditor symmetry, bidirectional mapping, stop-on-spec-gap, eval harness.
- **Gemini - skiill - mindmap(1).md:** JSON + Mermaid representation, AST index, imported telemetry, dependency order, checklist UI.
- **spec-drift-skill-notes(1).md:** independent target/actual maps, deterministic diff, live probing, stale-spec and scale warnings.
- **project-gap-audit-skill-design.md:** declared vs inferred facts, evidence-by-node, portable stdlib-first MVP.
- **roject Mindmap Audit — Agent Skill Desig.md:** graph snapshots, progressive disclosure, CLI/MCP/CI interoperability, optional runtime checks.
- **ProjectMirror_Concept_and_Recommendations.md:** intent/implementation/verification separation, permission modes, change impact and reconciliation.

## Appendix B — Standards and references consulted (external, not user-provided)

Official sources checked while preparing this consolidation (8 November 2026):

1. **Agent Skills specification:** https://agentskills.io/specification — `SKILL.md` conventions, metadata, references and scripts.
2. **Agent Skills specification source:** https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx
3. **ChatGPT / Codex skill authoring guidance:** https://learn.chatgpt.com/docs/build-skills
4. **OpenAI skills and MCP integration:** https://developers.openai.com/plugins/concepts/skills
5. **Current MCP TypeScript SDK documentation:** https://ts.sdk.modelcontextprotocol.io/v2/
6. **MCP 2026-07-28 release summary:** https://blog.modelcontextprotocol.io/posts/2026-07-28/

These sources validate available *packaging/integration patterns*; the ProjectMirror graph schema, states, approvals, classification logic, and roadmap are recommendations synthesized for this project, not requirements imposed by those protocols.

---

**End of consolidated implementation standard.**
