# Relay real-agent interoperability — validation checklist

**Status: real Codex / Claude Code / Cursor interoperability has not been certified.** Synthetic CLI tests do not run genuine agent host binaries.

## Setup

Use a disposable Git project without secrets; install MirrorMap into a persistent Python interpreter. Both agents must run on the same computer/user account with the same `MIRRORMAP_RELAY_HOME`. Preview `relay install-hooks --agent HOST --project /absolute/path` before applying and trusting native hooks. Do not run simultaneous agents editing the same worktree.

| Actual host pair | Hook tracking | Task notes | Session picker | Safe adoption | Crash recovery |
|---|---|---|---|---|---|
| Codex → Claude Code | Not tested | Not tested | Not tested | Not tested | Not tested |
| Claude Code → Cursor | Not tested | Not tested | Not tested | Not tested | Not tested |
| Cursor → Codex | Not tested | Not tested | Not tested | Not tested | Not tested |

## Field validation protocol

1. Record sanitized OS, host, Python, Git and MirrorMap version information.
2. Start Agent A on the disposable repository **without summoning MirrorMap**. Make a harmless edit; check `relay sessions` and `relay verify --session ID` for tracking.
3. Verify explicit `relay note` saved the real goal, decisions, completed work and precise unfinished action. A context reminder cannot substitute for a persisted note.
4. Trigger compaction or interruption if supported. Check event coverage; no invisible model reasoning can be recovered.
5. Stop Agent A; open Agent B, summon MirrorMap Relay, list sessions and select a checkpoint. Run `relay resume --session ID` and compare its claims against actual files.
6. Confirm `execution_authorized: false`, pending tools and workspace drift warnings. Test `relay adopt --from OLD --into NEW --confirm-source-stopped` only after the first agent is stopped.
7. Deliberately change the workspace, interrupt a tool or use an invalid session ID; the system must refuse unsafe automatic continuation and never replay commands.
8. Remove the test hooks and verify unrelated settings are unchanged. Do not publish private session databases.

## Existing synthetic verification

```sh
python -m unittest tests.test_relay -v
python -m unittest discover -s tests -v
```

These test synthetic events/CLI subprocesses only. **Release gate:** publish no broad production compatibility claims until real-host trials of at least one cross-agent pair and an interruption pass with a documented environment.

Sources: [Codex](https://learn.chatgpt.com/docs/hooks), [Claude](https://code.claude.com/docs/en/hooks), [Cursor](https://cursor.com/docs/hooks).

## Check an observed Agent A → Agent B transfer

After completing the real-host protocol above, and **after** Agent B records a milestone following adoption, run:

```sh
python -m projectmirror relay field-check --source OLD_SESSION_ID --target NEW_SESSION_ID
```

This command returns exit status **0** when all *recorded* checkpoint, lineage, milestone and workspace checks pass. Exit status **1** means at least one check failed; exit status **2** indicates invalid arguments, missing sessions or other input errors. In particular, it requires a source session note and a **new Agent B milestone after adoption**, so merely copying task metadata does not pass.

**Not a host certification:** Hook events can be fabricated and user notes are not authenticated. The report always includes `host_runtime_authenticated: false`. A maintainer must separately observe the actual Codex/Claude/Cursor sessions and record their versions, hook trust state, interruption and resumed work before declaring any real-host pair tested.

### Cursor reminder limitation

Cursor `sessionStart` supports `additional_context`, but `beforeSubmitPrompt` does **not** support context injection, per [Cursor's hook contract](https://cursor.com/docs/hooks). MirrorMap continues recording prompt-event metadata where a session ID is available but deliberately returns an empty output from that prompt hook. Do **not** claim that Cursor receives automatic mid-session milestone reminders from `beforeSubmitPrompt`. The skill or an explicit `relay note` remains necessary to persist precise task steps.
