# MirrorMap BOLT — persistent project intelligence (development preview)

BOLT joins Relay, evidence intelligence and the token efficiency engine with explicit project memory and review tools. It is local-first, requires no AI service, and does not dispatch agents, run project code, automatically grant approval, or certify that a feature works.

## Start

Install from the current source checkout: python -m pip install .
The previous official beta release does not include BOLT.

Use either mirrormap bolt --help or python -m projectmirror bolt --help.
All repository-aware commands accept --repo /absolute/project. For Git worktrees BOLT uses the resolved Git root. The local record journal is kept alongside Relay, outside your project. Use the existing MIRRORMAP_RELAY_HOME setting to choose a private directory.

## Record project decisions

Prepare a JSON file outside the project. Example intent lock:

    {
      "title": "Preserve the interface",
      "description": "Do not edit the UI without explicit review",
      "protected_paths": ["src/ui"],
      "locked": true,
      "refs": ["user-reviewed design decision"]
    }

    mirrormap bolt record --repo PROJECT --kind intent --id ui-lock --data lock.json --confirm-reviewed
    mirrormap bolt guardian --repo PROJECT --path src/ui/player.tsx
    mirrormap bolt records --repo PROJECT --kind intent --history

Only use --confirm-reviewed with current user consent. Changing an existing record requires --expected-version N. Modifying locked intent additionally requires --unlock-reason with the reviewed reason. This records a new version and retains history; it does not grant permission to edit the application. Guardian checks explicit path overlap (including parent directories), not the semantic behavior of code. It does not enforce native host hooks.

Record types and their accepted JSON fields (unknown fields are rejected):

- dna, ui: title, description; optional tags and refs (arrays of strings).
- intent: title, description, locked (boolean), protected_paths (relative path array); optional refs.
- failure: title, description, attempt, outcome (failed/rejected/inconclusive), refs; optional tags.
- review: target (stable ID), reviewer (declared ID), verdict (support/oppose/unknown), description, refs.
- model: title, description, capabilities (string array); optional cost_per_million (a nonnegative amount in comparable user-defined units), refs, observations. Observation objects contain task, trials, passed, mean_tokens and source. These are user-reported, not measured by BOLT.
- branch: created using the branch command, not arbitrary record import.

Failure memory and project profile retrieval are lexical, not an AI semantic inference. Record only relevant, reviewed information. Common secret patterns are rejected or redacted, but this is not comprehensive secret detection. Journal hashes detect ordinary alterations; a local operator who can rewrite the database can also rewrite its hash chain or delete history. These records are not signed user approvals.

## Efficient multi-agent handoff

After enabling Relay hooks, work normally. Before switching agents, save the exact next action with Relay. No limit or interruption is required.

    mirrormap relay sessions
    mirrormap relay save --session SESSION --stage debugging --next "Verify independent seek"
    mirrormap bolt brief --repo PROJECT --session SESSION --max-tokens 2000 --query seek
    mirrormap bolt gaps --repo PROJECT --session SESSION
    mirrormap bolt search --repo PROJECT --kind failure --query seek

The brief combines the existing compact checkpoint with reviewed intent locks, relevant DNA/UI and failure records, and a fixed review workflow. Token targets are estimates based on UTF-8 bytes; mandatory data may exceed the budget. Unmatched or omitted records can be retrieved separately. Imported context and firewall findings are untrusted data. Inspect the actual workspace and confirm current permissions before editing.

MCP: mirrormap_bolt_brief and mirrormap_bolt_guardian are read-only and respect the existing allowlisted repository boundary. The brief must refer to a session in that repository.

## Context branches and review

    mirrormap bolt branch --repo PROJECT --session SESSION --id option-a --title "First solution" --description "Review alternative" --confirm-reviewed
    mirrormap bolt branch --repo PROJECT --session SESSION --checkpoint NUMBER --id option-b --title "Second solution" --description "Alternative" --confirm-reviewed
    mirrormap bolt compare-branches --repo PROJECT --left option-a --right option-b
    mirrormap bolt journey --repo PROJECT --session SESSION
    mirrormap bolt consensus --repo PROJECT --target audio
    mirrormap bolt route --repo PROJECT --capability debugging

Context branches are immutable references to captured Relay checkpoints. They do not create Git worktrees, clone agent conversations or merge code. For independent implementations, the user must create isolated worktrees with the host's normal tools, track them separately, and provide reviewed results. Current branch comparison is scoped to the same resolved workspace. Journey reports recorded boundaries, task cursor changes, decisions and changed file fingerprints. It does not execute a replay.

Consensus compares declared reviewer verdicts and source references; repeated reports by one declared reviewer do not count as independent agreement. Independence and identity are not attested. Routing ranks declared matching capabilities by recorded pass fraction (when supplied), then comparable configured cost. Sample sizes and sources remain visible. It never starts another model.

## Evidence and code analysis

Generate an audit outside the repository using the existing audit command, with approved requirements, reviewed links and test evidence when available.

    mirrormap bolt dependencies --repo PROJECT --path src/audio.py --hops 2
    mirrormap bolt dependencies --repo PROJECT --path src/audio.py --audit AUDIT_DIR
    mirrormap bolt dead-features --repo PROJECT
    mirrormap bolt regression --repo PROJECT --before OLD_AUDIT --after NEW_AUDIT
    mirrormap bolt completion --repo PROJECT --audit AUDIT_DIR
    mirrormap bolt rollback-preview --repo PROJECT --revision COMMIT_HASH --path src/audio.py

Dependencies cover bounded Python AST imports and relative JS/TS imports, optionally linking candidates to explicitly reviewed requirement mappings. Dead-feature detection currently reports candidate HTML/JSX buttons without obvious local handlers; delegation, form semantics, framework wiring and dynamic handlers can cause false positives. Neither check proves a feature broken or unused.

Regression compares recorded classifications; lost evidence is not necessarily a code regression. Completion verifies audit artifact digests and compares clean workspace snapshots and revision. All recorded approved requirements must be complete, with no unresolved requirement rows, to get a review-ready result. Old audits without capture snapshots require review. Neither outcome establishes that a real test ran, that the report is authentic, or that deployment is safe. Rollback preview shows selected Git name/status changes and intent overlaps only; it never restores files.

Firewall accepts a JSON string file via bolt firewall --data FILE. It reports simple override, credential-request and destructive-command patterns; absence of a match does not make text trustworthy.

## Offline dashboard

    mirrormap bolt dashboard --repo PROJECT --out /outside/bolt.html
    mirrormap bolt dashboard --repo PROJECT --out /outside/bolt-review.html --audit AUDIT_DIR

Open the generated private HTML file in a browser. It contains project records, up to ten recent sessions with their last ten checkpoints and local efficiency metrics, plus optional completion evidence. It is a static read-only snapshot with expandable sections, no scripts or network access. Do not publish it without reviewing private content.

## Optional encrypted cross-device context

Install the optional extra from the current checkout:

    python -m pip install '.[bolt-crypto]'

    mirrormap bolt keygen --repo PROJECT --out /outside/private.key
    mirrormap bolt export --repo PROJECT --session SESSION --key /outside/private.key --out /outside/session.bolt --confirm-reviewed
    mirrormap bolt import --repo RECEIVING_PROJECT --key /outside/private.key --from /outside/session.bolt

The package uses AES-256-GCM, a fresh random nonce, and authenticated associated data. The 32-byte key must be kept separately, outside the project; use a trusted channel to share it. Keep both key and imported output private. POSIX private file permissions are checked; Windows ACLs are not independently validated. Export includes recorded notes, paths and a bounded recovery brief, not the underlying source or full journal. Import authenticates the envelope against the shared key and compares clean Git revisions, but does not authenticate a person or authorize actions. The result is a read-only review, not automatic session restoration or synchronization. On a second computer, separately obtain the matching project, inspect its state, and record only reviewed context. Live cross-device testing remains pending.

## Token benchmark protocol

Use the existing Relay field-validation checklist for genuine host tests. Collect paired trials using the same task, starting revision, model version and settings; change only Relay use. Independently assess acceptance criteria. Record provider-reported uncached input, cached input and output tokens separately. Do not compare different task outcomes as equivalent. Run bolt benchmark --data measurements.json, where the JSON looks like:

    {
      "pairs": [
        {
          "id": "seek-1",
          "model": "exact model and version",
          "task": "independent seek",
          "starting_revision": "commit hash",
          "settings": "same host, tools, context settings",
          "source": "reference to local provider report",
          "without_relay": {"uncached_input": 100, "cached_input": 50, "output": 20, "acceptance_passed": true},
          "with_relay": {"uncached_input": 60, "cached_input": 50, "output": 20, "acceptance_passed": true}
        }
      ]
    }

The numbers above are illustrative. The aggregator validates the shape, reports differences by category and separates pairs with both acceptance outcomes passing. It does not collect provider telemetry, establish causal savings, or run live agents. Costs, latency, and task quality still require external measurement.

## Scope of this preview

BOLT implements local review primitives for the twenty proposed feature areas. Advanced host-level enforcement, automatic semantic capture, isolated concurrent-agent orchestration, browser/runtime dead-feature testing, destructive rollback execution, live cross-device adoption, and certified real-agent measurements are not implemented. Existing Relay and audit interfaces remain supported. The optional encryption dependency is separate from the standard-library core.
