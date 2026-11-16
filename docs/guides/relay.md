# MirrorMap Relay — opt-in agent session continuity (v0.6 development preview)

Relay is an **experimental local metadata recorder and verified handoff interface** for interrupted coding-agent sessions. It does **not** transfer another model's hidden thoughts, read private conversation transcripts, or automatically execute the next operation. A saved checkpoint provides a trustworthy *local consistency check*, not proof that the last tool call succeeded or that the model's memory is complete.

## The experience: install, work, select, review, continue

1. Install the **MirrorMap Python CLI** in a persistent interpreter on the machine where your agents run. A copied `SKILL.md` is **not enough** to start automatic tracking.
2. Enable project-filtered host lifecycle hooks **once per agent** with `install-hooks --apply` (the command previews changes without `--apply`). Review hook permissions/trust in the host UI. The hook commands run automatically *without invoking the skill* during an Agent A session.
3. Work with Agent A normally. The host calls Relay at session starts, tool boundaries and context compaction when it supports those hooks. Relay persists bounded Git metadata, an event chain, and possible in-flight tools. A SessionStart instruction asks the agent to additionally record **structured task milestones** with `relay note`; if the agent doesn't comply, automatic metadata still exists but the semantic task cursor may be missing.
4. Open Agent B on the **same machine/user account**, install/load the same skill and CLI, and ask **"MirrorMap Relay, list saved sessions."** The skill tells Agent B to execute `python -m projectmirror relay sessions` (or use the two read-only MCP tools). Choose a session ID.
5. Agent B runs `python -m projectmirror relay resume --session SESSION_ID`, checks any warnings and the current files, then asks permission to continue the unfinished work. Relay does **not** replay or rerun pending shell commands automatically.

**Optional tracking lineage:** Once Agent B has started its own tracked session and the user confirms Agent A is stopped, Agent B may explicitly adopt the selected session so subsequent records continue under the new host:

```sh
python -m projectmirror relay adopt --from OLD_SESSION_ID --into NEW_SESSION_ID --confirm-source-stopped
```

Adoption requires a matching current workspace and verified journals with no unresolved tool calls. It copies explicit task milestones into Agent B's session and records a parent/child relationship; it **never** transfers execution permissions or reruns commands. If the old agent might still be active, do not adopt or edit concurrently.

A different computer/cloud agent **does not** share local sessions automatically. Secure cross-device synchronization, authenticating the owner, and restoring full worktrees are not implemented.

## Install the recording hooks

Run once inside the MirrorMap source checkout:

```sh
python -m pip install .
```

The host hooks use the **installed** Python package via `python -I -m projectmirror`, which excludes imports from untrusted project working directories. Install MirrorMap using a stable Python interpreter (and don't remove that interpreter while hooks are enabled). The hook preview displays the exact executable path.

For your project's absolute path, run the previews:

```sh
python -m projectmirror relay install-hooks --agent codex --project /absolute/path/to/my-app
python -m projectmirror relay install-hooks --agent claude --project /absolute/path/to/my-app
python -m projectmirror relay install-hooks --agent cursor --project /absolute/path/to/my-app
```

Once you have reviewed the settings and trust boundary, add `--apply` to **each agent you actually use**. Hooks are installed into the user's supported config locations (`~/.codex/hooks.json`, `~/.claude/settings.json`, and `~/.cursor/hooks.json`). Hooks are **project-filtered** and skip events from other workspaces. Preview is the default and never modifies settings. Existing unrelated hooks are preserved; unsupported/invalid existing structures fail closed. Do not commit hook configuration or credentials to the repository.

The hosts may require you to **review/trust** the hooks separately and restart/reload the agent. In Codex use `/hooks` to review and enable the commands. Cursor and Claude have their own hook settings. To remove only this project's installed commands:

```sh
python -m projectmirror relay uninstall-hooks --agent codex --project /absolute/path/to/my-app --apply
```

Uninstall for each relevant agent separately. The local session store is **not** removed automatically.

Official documentation: [Codex hooks](https://learn.chatgpt.com/docs/hooks), [Claude Code hooks](https://code.claude.com/docs/en/hooks), [Cursor hooks](https://cursor.com/docs/hooks). Host hook schemas and support can change. The included adapters are covered by synthetic event tests; actual live-session compatibility needs validation against the host's installed version.

## Use the saved sessions

```sh
# Agent B: discover sessions
python -m projectmirror relay sessions

# Optional: only show sessions from this project
python -m projectmirror relay sessions --workspace /absolute/path/to/my-app

# Show task notes and current consistency checks
python -m projectmirror relay inspect --session SESSION_ID

# Confirm whether journal and workspace still match
python -m projectmirror relay verify --session SESSION_ID

# Generate a read-only resume package
python -m projectmirror relay resume --session SESSION_ID

# Agents may record milestones even without the user summoning MirrorMap
python -m projectmirror relay note --session SESSION_ID \
  --goal 'Build the authentication flow' --done 'Created login endpoint' \
  --decision 'Keep sessions server-side' --next 'Test logout and expiry'

# Explicitly capture the current repository state after reconciliation
python -m projectmirror relay checkpoint --session SESSION_ID
```

If the project changed since the checkpoint, or if a tool was left in flight, the resume report explicitly blocks **automatic continuation**. It contains a human-readable warning. You can inspect changes and run a fresh manual checkpoint when appropriate; this does not turn an unverifiable action into a verified success.

### What is recorded automatically?

- Provider name, a **hashed** host session identifier, local project root, event type, timestamps, and tool **name/identifier** when supplied by the host.
- Git branch, HEAD, bounded changed-file paths, status flags and hashes of small files. Paths matching common secret-file patterns are redacted; file contents are never stored. Files larger than 2 MB aren't hashed; scans stop at 100 changed files and then report incomplete coverage.
- Whether a tool call was begun and later paired with a post-tool event, plus whether a call is still in flight.
- Optional concise user/agent-provided notes: task goal, completed milestones, decisions, blockers, and the next explicit action. These notes are **not** automatically inferred from hidden model reasoning.

**Not recorded:** raw user prompts, assistant thoughts, complete chat transcripts, tool command strings, raw tool outputs, source file contents, environment variables, or private credentials. Minimal credential-assignment redaction is a guardrail, not a perfect secret detector: do not put secrets in `relay note`.

## Security and reliability boundaries

- **Local first:** The default store is `~/.mirrormap/relay/sessions.sqlite3` (override with `MIRRORMAP_RELAY_HOME`), and the store directory must be private on POSIX. SQLite transactions and WAL make completed events durable; this is not a guarantee against sudden system-wide storage failures.
- **Scope:** Recording hooks are opt-in and project-filtered. The user should inspect generated commands before applying them. Hooks do not execute project source or grant permission to edit anything.
- **Agent B validation:** A digest-linked local event chain and bounded workspace fingerprint flag mismatched edits or checkpoint tampering. They do **not** authenticate the author of every event; local database owners can forge histories. Git unavailable, incomplete scans, and changed workspace contents lower confidence.
- **Event ambiguity:** Some host events do not expose a stable session ID or tool call ID. Cursor `sessionStart` can propagate a session ID to later hooks through a host-provided session environment; otherwise Relay **does not guess** which concurrent session an event belongs to. Unpaired starts remain uncertain.
- **Permissions:** Every resume is read-only context. It cannot grant execution, approve a previous plan, claim a test passed, or continue an interrupted command without reconciling side effects.
- **Identity and multiple writers:** SQLite serializes local writes, but this preview does not implement a trusted agent ownership lease or simultaneous active agent coordination. Do not let two agents edit the same worktree concurrently.
- **Privacy:** Even path names and task summaries may be sensitive. The store is local; don't sync or upload it without reviewing its contents and setting up protection.
- **Coverage:** Only hook events that the agent actually emits are recorded. An unexpected host crash can lose operations since the last durable event. Skills without hooks cannot record automatically.

## MCP session discovery

If you are using MirrorMap's read-only MCP server, configure `MIRRORMAP_ALLOWED_ROOTS` to the permitted workspace(s). The server advertises `mirrormap_relay_sessions` (optionally filter by workspace) and `mirrormap_relay_resume` (requires a selected session ID). Only sessions inside the allowlisted workspace are returned. The MCP server does **not** install hooks, write notes, or resume coding by itself.

## Troubleshooting

- **No sessions shown:** Confirm the Python package is installed, hooks were applied and trusted, the host emitted the relevant events, and both agents run under the same OS user account / `MIRRORMAP_RELAY_HOME`.
- **Session exists but no task details:** Automatic recording doesn't infer a goal or decisions. Have Agent A write a `relay note` after milestones; the SessionStart hook normally reminds the agent.
- **Resume says workspace differs:** Check Git status, untracked files, the branch and HEAD. Don't overwrite new work to make the checkpoint match.
- **Tool appears pending:** Check whether it completed in the real project; don't repeat irreversible commands automatically.
- **Installing a skill didn't activate tracking:** This is expected. Install the Python CLI and explicitly apply the lifecycle hook adapter once.
