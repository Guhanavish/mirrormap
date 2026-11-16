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
