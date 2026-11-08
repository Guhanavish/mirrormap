# ProjectMirror data model (v0.1)

All artifacts use `schema_version: "1.0"`. JSON is the authoritative record; diagrams are generated views.

## Intent map

```json
{
  "schema_version": "1.0",
  "nodes": [
    {
      "id": "REQ.auth.login",
      "map": "intent",
      "kind": "requirement",
      "title": "User can log in",
      "requirement_state": "approved",
      "acceptance_criteria": [
        {"id": "AC.auth.login.valid", "statement": "Correct credentials establish a user session"}
      ],
      "source_refs": ["requirements.md:8"]
    }
  ]
}
```

States: `approved`, `draft`, `inferred`, `conflicted`, `deprecated`. Only `approved` nodes are used as change requirements. An agent must not set `approved` without an actual user-approved specification.

## Implementation map

Indexed nodes are `impl.file.<hash>` or `impl.symbol.<hash>` with `implementation_state: present` and file locators. Reviewers may add manually inspected `endpoint`/`feature`/`capability` nodes or mark a node `partial`, `unknown`, or `absent_confirmed` **with justification**. The default scanner only records structural facts and content hashes, not runtime correctness.

## Reviewed links

```json
{"links": [{"requirement_id": "REQ.auth.login", "implementation_id": "impl.file.0123456789abcdef", "basis": "reviewed", "confidence": "high"}]}
```

The CLI validates linked IDs; fuzzy semantic matching is the *agent's proposal*, not a deterministic matching guarantee. Two similar titles are not sufficient proof.

## Verification map

```json
{
  "schema_version": "1.0",
  "nodes": [
    {
      "id": "verify.login.valid",
      "map": "verification",
      "title": "Login integration test",
      "requirement_id": "REQ.auth.login",
      "result": "passed",
      "criteria_ids": ["AC.auth.login.valid"],
      "revision": "COMMIT_SHA_FROM_MANIFEST",
      "evidence": ["tests/test_login.py::test_valid_user; run 42, passed"]
    }
  ]
}
```

Only current revision test results with explicit evidence and acceptance-criterion IDs can mark a linked requirement complete. Result enum: `passed`, `failed`, `mismatch`, `not_run`, `inconclusive`, `blocked`, `stale`.

## Reviewed absence confirmations

```json
{"confirmations": [{"requirement_id": "REQ.auth.recovery", "reviewed": true, "coverage": "exhaustive", "evidence": ["Reviewed auth routes, feature flags and auth provider for revision abc...; none implements recovery"], "explanation": "Recovery behavior not implemented"}]}
```

These records are **human- or agent-supplied claims**; the CLI cannot independently prove their quality. Missing status may be reported only when the scope and evidence support it.

## Plan

`plan.json` contains `base_revision`, `environment`, `tasks`, and `plan_digest`. The digest is SHA-256 of canonical JSON content excluding the digest field. Plan tasks carry IDs and an `allowed_paths` set. This is a proposal, **not an execution authorization**.
