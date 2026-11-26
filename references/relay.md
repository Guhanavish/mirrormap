# MirrorMap Relay usage and trust notes

The complete user guide is in `docs/guides/relay.md` in the project source. Do not assume merely installing the skill installs auto-tracking hooks.

- `python -m projectmirror relay sessions` lists saved sessions.
- `python -m projectmirror relay resume --session ID` validates the checkpoint and returns **read-only** continuation context.
- `python -m projectmirror relay note --session ID --next '...' --done '...'` adds explicit progress details to the local journal; do not include secrets.
- Automatic tracking requires a separate, reviewed installation of project-filtered hooks for Agent A using `relay install-hooks --agent AGENT --project ABSOLUTE_PATH --apply`.
- Do not rerun pending commands, assume old approvals apply, or claim identical hidden model state.
- If a journal or workspace is mismatched, inspect the current repository before continuing.
- The default SQLite store is local to the OS user. Cross-device synchronization is unsupported in this preview.

- To explicitly carry a selected task into the new host session, require user confirmation that the old agent stopped, then use `relay adopt --from OLD_SESSION_ID --into NEW_SESSION_ID --confirm-source-stopped`. This links notes and tracking, not host permissions.


## Persistent project state preview

Use `relay save --session ID --stage implementation --next 'precise remaining action'` for deliberate switching, `relay history --session ID` for recorded save points, and `relay recover --session ID --budget standard` for review. Older checkpoint data may lack historical fields. The optional `--capture-context` hook setting collects bounded user/assistant excerpts, not hidden reasoning; metadata remains the default. Reconcile pending operations after manual inspection, review merge candidates, and never transfer execution authority. Portable import is a read-only review, not a restore. See the source guide `docs/guides/relay-state.md`.


## Token-efficient handoffs (development preview)

Prefer `relay recover --session ID --budget compact` or MCP `mirrormap_relay_brief` for initial recovery; use `relay context --session ID --checkpoint NUMBER --query "specific question"` or `mirrormap_relay_context` for optional context only when needed. Do not request repeated full summaries. Use notes for new information or significant milestones. Eco is the default, with balanced/detailed/manual recording modes. User opt-in is required for excerpts. Approximate token targets can overflow for mandatory safety information; review all warnings. `relay usage --session ID` reports local estimates, not actual provider tokens saved. Legacy resume remains supported.
