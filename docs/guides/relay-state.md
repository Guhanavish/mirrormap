# Persistent project state (development preview)

Relay now records a bounded task snapshot with each durable hook event and supports deliberate switching even when an agent is healthy. It does not copy a model's hidden state, read transcript paths, run tests, or restore source files.

## Start and switch

Install the current source package and explicitly review host hooks as described in [Relay setup](relay.md). Metadata-only remains the default. To opt in to storing bounded, redacted user prompts and available final assistant message excerpts for a project, preview:

```sh
python -m projectmirror relay install-hooks --agent claude --project /absolute/path/to/project --capture-context
```

Apply with `--apply` only after reviewing the privacy impact. Repeat for the receiving host if desired. Reinstall without `--capture-context` to disable future excerpt collection. This does not erase old recordings. The capture flag can store sensitive content; redaction is best-effort, not comprehensive. Do not enable on secret-bearing sessions. No transcript files, hidden thoughts, arbitrary tool inputs or outputs are collected. Supported prompt and final-message fields depend on the host version; Cursor uses `afterAgentResponse`. The adapters are not yet live-certified.

Work normally. Explicit goal, decisions and task cursor still require a note or save from the user or agent. If an opted-in excerpt contains a labeled "Next:" or "Remaining task:", recovery exposes the most recent matching text as an **unreviewed candidate**. It never becomes a verified next step automatically. The session catalog shows the latest checkpoint ID and stage note or keyword suggestion. The existing resume CLI/MCP brief includes compact persistent context when the journal validates. On a deliberate switch:

```sh
mirrormap relay sessions
mirrormap relay save --session SESSION_ID --stage implementation --goal "Independent audio playback" --next "Verify independent seek"
mirrormap relay history --session SESSION_ID
mirrormap relay recover --session SESSION_ID --budget standard
```

Stop the original agent. Agent B lists sessions and asks which to resume, then runs `recover` and inspects the workspace. If the source stopped mid-tool, manually inspect side effects and use `relay reconcile --session ID --reason "Describe inspection" --confirm-inspected`. This records an acknowledged unknown outcome; it never claims success. Use the existing `adopt` command only after both journals and workspaces validate and the old agent has stopped. Linked ancestor excerpts and corrections are read as untrusted records. No command transfers execution permission.

## Additional commands

| Command | Behavior |
|---|---|
| `save --session ID` | Record a workspace/task checkpoint at any point; optional goal, next, stage, done, decision, blocker and correction. |
| `history --session ID` | Show durable event checkpoint IDs; old metadata-only entries may lack historical state. |
| `recover --session ID --checkpoint NUMBER` | Inspect a historical checkpoint; historical states never qualify for automatic continuation. |
| `recover --session ID --budget compact` | Character-budgeted optional context; mandatory warnings retained and omissions reported. |
| `project-memory --workspace PATH` | Review recorded notes from sessions of that workspace. |
| `merge-context --from ID --into ID` | Preview candidate context; add `--apply --confirm-reviewed` to record it without overwriting the target goal. |
| `link-audit --session ID --out AUDIT_DIRECTORY` | Verify matching audit manifest/artifact bytes and record its digest and revision match; not a verified test claim. |
| `export --session ID --out FILE --confirm-reviewed` | Export reviewed context outside the project, without overwriting files. Package contains private notes and paths. |
| `import --from FILE` | Validate package digest and present untrusted context for review; no worktree restoration or session overwrite. |
| `context-doctor` | Show local storage and adapter preview information. |

Stage detection is an explicit note or a deterministic keyword suggestion based on the recorded next step. A correction is a prioritized explicit note, not automatically parsed intent. Budgets are character targets, not model-token guarantees. Project memory and merge do not decide which competing instructions are correct. Portable packages are unsigned and unencrypted; review before transferring. A digest is not identity or authorization.

A Music Player fixture exercises independent audio, timeline corrections, unfinished tool calls and switching agents; no actual Music Player code is modified. Run `python -m unittest discover -s tests -v`. See [field validation](relay-field-validation.md) for genuine-host trials. Recovery can only preserve what was durably recorded. Current limits include no transcript importer, no semantic task inference from raw messages, no multi-agent ownership lease, no encrypted sync, no worktree restoration, and no certified live interoperability.
