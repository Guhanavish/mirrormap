# MirrorMap Evidence Intelligence — v0.5 development preview

MirrorMap's optional read-only intelligence layer is a structured **investigation and evidence review system**, not an autonomous agent that runs application code. Outputs derive only from approved/draft requirements, scanned source structure, explicitly reviewed links, imported observations, and user-supplied inputs. All outputs live in a fresh audit directory **outside** the inspected project.

## First run

From the checked-out repository (Python 3.10+):

```bash
python -m projectmirror audit examples/demo-app \
  --spec examples/demo-app/requirements.md \
  --approved-spec --mode deep \
  --links examples/fixture-reviewed-links.json \
  --absence examples/fixture-reviewed-absence.json \
  --changed-path auth.py
```

The CLI prints the generated output directory. Open `dashboard.html`. Click **Evidence intelligence** links to inspect separate, machine-readable artifacts. The bundled fixture deliberately yields **1 missing and 2 unverified** requirements, based on the reviewed *sample* evidence. This is not a claim that arbitrary software bugs were discovered automatically.

To cross-check a handoff, run:

```bash
python -m projectmirror verify-handoff --out /path/to/fresh/audit-directory
```

A successful check confirms **byte integrity**, not identity, user consent, or that the source observations are genuine. A changed or missing file makes the check fail. The handoff manifest hashes files that were present at the end of the audit; generate a new audit if you need a new verified snapshot.

## What's generated

| Artifact | Purpose | Crucial limitation |
|---|---|---|
| `evidence-passports.json` | Feature-by-feature code/test evidence IDs, source hashes, revision matches | Not signed attestations or universal proof of functionality |
| `investigations.json` | Read-only suggestions for finding evidence about unknown/unverified requirements | Does not schedule tests or confer approval |
| `assumption-debt.json` | Unresolved questions and evidence gaps | Does not equate unknown with defective |
| `spec-conflicts.json` | Explicit `conflicts_with` pairs and acceptance-criterion ID collisions | Does not parse logical contradictions in arbitrary prose |
| `readiness-matrix.json` | Functional readiness versus separately unassessed security, accessibility, performance and deployment | No invented completeness score |
| `evidence-freshness.json` | Imported observations with current/stale/unknown revision relationship | Same revision does **not** prove tests really ran |
| `approval-draft.json` | Non-authorizing list of proposed tasks and file scopes | A JSON file cannot be consent; host must authorize and enforce |
| `audit-handoff.json` | SHA-256 digests for produced artifacts | Integrity only, no cryptographic origin authentication |
| `impact-preview.json` | Possible requirement impact for explicitly reviewed links to specified changed paths | Not a full dependency or regression analysis; only created for changed paths |
| `behavior-journeys.json` | User-supplied journey steps and existing observation IDs | No automatic browser execution; created only with `--journeys` |

### Requirements that explicitly conflict

Markdown requirement extraction doesn't attempt natural-language contradiction detection. For a *reviewed JSON intent map*, a requirement node can declare:

```json
{
  "id": "REQ.auth.login",
  "map": "intent",
  "title": "Login required",
  "requirement_state": "approved",
  "acceptance_criteria": [{"id":"AC.auth.login", "statement":"Users must authenticate"}],
  "conflicts_with": ["REQ.auth.guest"]
}
```

Both IDs must exist in the same intent map. A declared conflict is a review blocker (`spec_conflict`) and creates a read-only investigation task. The system **does not** silently choose a requirement to implement. If evidence is insufficient, claims remain `unknown` or `unverified`.

### Import a behavior journey (source-only; no browser tests)

Create a JSON file matching the [sample](../../examples/intelligence/journeys.json). Each step optionally references a known requirement and previously imported verification IDs. The adapter validates IDs and reported revisions:

```bash
python -m projectmirror audit /path/to/repo --spec /path/to/requirements.json \
  --approved-spec --verification /path/to/reviewed-test-observations.json \
  --journeys /path/to/journeys.json
```

A step may show `reported_pass`, `reported_failure`, or `unverified`. These observations do not override the main requirements audit or prove that production behavior is correct.

### Review possible impact

```bash
python -m projectmirror audit /path/to/repo --spec /path/to/spec.md \
  --approved-spec --links /path/to/reviewed-links.json \
  --changed-path src/auth.py --changed-path src/routes.py
```

Only exact paths linked through **reviewed** requirement-to-implementation mappings are returned. The report explicitly says `potentially_affected`; it does not assert regressions, derive transitive runtime dependencies, or execute tests.

### Evaluate on reviewed fixtures

The `evaluate` command accepts flat, reviewed ID-to-classification maps:

```bash
python -m projectmirror evaluate \
  --expected examples/intelligence/expected.json \
  --actual examples/intelligence/predicted.json
```

It reports missing-claim precision/recall and false completions *within that fixture*. This is not an estimate of performance on all projects. Do not present sample scores as general benchmarks.

## Safety and engineering boundaries

1. An audit request only authorizes read-only inspection. **No application source, tests, deployment, or external browser is executed by these commands.**
2. A linked source file is structural evidence; it cannot independently prove a feature works.
3. The tool never promotes candidates to reviewed links automatically.
4. Approval drafts have `approved: false` and `execution_authorized: false`; no CLI command changes these flags into a trusted permission.
5. Handoffs contain digests and may contain local paths; treat them as private when the repository is private.
6. Audit output directories must be **empty** when an audit starts. Reuse could mix old and new evidence, so the CLI fails closed instead.
7. This release doesn't implement production tracing, automatic Playwright execution, cross-repository contract proof, secure signed approvals, mutation testing, or model-driven semantic conflict detection. See the [research-driven roadmap](../ROADMAP_NEXT.md).

## For contributors

Review `projectmirror/intelligence.py`, `tests/test_intelligence.py`, and the supporting schema files in `schemas/`. Add independently labeled fixtures before promoting an analyzer from *suggestion* to *evidence*. Keep the standard-library core dependency-free, test against stale/untrusted inputs, and preserve read-only default behavior.
