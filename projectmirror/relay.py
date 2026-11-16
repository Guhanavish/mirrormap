"""MirrorMap Relay: opt-in, local, metadata-only agent session checkpoints.

Relay never reads chat transcripts, stores tool inputs/outputs, runs project code,
executes a pending operation, or grants write approval to another agent.
A checkpoint can prove local consistency, not authorship or completeness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .core import AuditError

SCHEMA_VERSION = 1
MAX_HOOK_BYTES = 1_000_000
MAX_CHANGED = 100
MAX_HASH_BYTES = 2_000_000
MAX_NOTE = 1200
AGENTS = ("claude", "codex", "cursor")
EVENTS = {
    "claude": ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "PreCompact", "Stop", "SessionEnd"),
    "codex": ("SessionStart", "PreToolUse", "PostToolUse", "PreCompact", "Interrupt", "Stop", "SessionEnd"),
    "cursor": ("sessionStart", "preToolUse", "postToolUse", "postToolUseFailure", "afterFileEdit", "preCompact", "stop", "sessionEnd"),
}
SECRET_WORD = re.compile(r"(?i)(password|secret|token|authorization|api[_-]?key|private[_-]?key)\s*[:=]\s*([^\s,;]+)")
SENSITIVE_NAME = re.compile(r"(?i)(^|/)(\.env(?:\..*)?|id_rsa|id_ed25519|.*\.(?:pem|key|p12|pfx))$")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _text(value: str) -> str:
    if not isinstance(value, str):
        raise AuditError("Relay note must be text")
    # Do not turn a common textual credential assignment into an archived secret.
    redacted = SECRET_WORD.sub(lambda m: m.group(1) + "=[REDACTED]", value)
    return redacted[:MAX_NOTE]


def relay_home() -> Path:
    root = Path(os.environ.get("MIRRORMAP_RELAY_HOME", "~/.mirrormap/relay")).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise AuditError("Relay storage location is not a directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        # Reject world/group-readable stores rather than silently changing user policy.
        if root.stat().st_mode & 0o077:
            raise AuditError("Relay store must be private (chmod 700 the relay directory)")
    return root


def _connect() -> sqlite3.Connection:
    root = relay_home()
    database = root / "sessions.sqlite3"
    if database.is_symlink():
        raise AuditError("Refusing symlinked Relay database")
    connection = sqlite3.connect(str(database), timeout=12)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 12000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      agent TEXT NOT NULL,
      workspace TEXT NOT NULL,
      title TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      status TEXT NOT NULL,
      goal TEXT NOT NULL DEFAULT '',
      next_step TEXT NOT NULL DEFAULT '',
      completed TEXT NOT NULL DEFAULT '[]',
      decisions TEXT NOT NULL DEFAULT '[]',
      blockers TEXT NOT NULL DEFAULT '[]',
      snapshot TEXT NOT NULL DEFAULT '{}',
      last_event_hash TEXT NOT NULL DEFAULT '',
      parent_session TEXT
    );
    CREATE TABLE IF NOT EXISTS events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL REFERENCES sessions(id),
      kind TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      detail TEXT NOT NULL,
      previous_hash TEXT NOT NULL,
      event_hash TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS events_session ON events(session_id, seq);
    CREATE TABLE IF NOT EXISTS pending_tools (
      session_id TEXT NOT NULL REFERENCES sessions(id),
      tool_id TEXT NOT NULL,
      tool_name TEXT NOT NULL,
      started_at INTEGER NOT NULL,
      PRIMARY KEY (session_id, tool_id)
    );
    """)
    # Read existing preview stores without discarding recorded history.
    cols = {r["name"] for r in connection.execute("PRAGMA table_info(sessions)")}
    if "parent_session" not in cols:
        connection.execute("ALTER TABLE sessions ADD COLUMN parent_session TEXT")
    if os.name != "nt":
        try:
            os.chmod(database, 0o600)
        except OSError:
            pass
    return connection


def _git(repo: Path, *args: str) -> bytes | None:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=7, check=False)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _workspace(directory: str | Path) -> Path:
    path = Path(directory).expanduser().resolve()
    if not path.is_dir():
        raise AuditError("Workspace does not exist")
    top = _git(path, "rev-parse", "--show-toplevel")
    if top:
        candidate = Path(os.fsdecode(top.strip())).resolve()
        if candidate.is_dir():
            return candidate
    return path


def _project_match(directory: str | Path, project: str | Path) -> bool:
    return _workspace(directory) == _workspace(project)


def workspace_snapshot(workspace: str | Path) -> dict:
    """Bounded structural fingerprint. No project contents are persisted."""
    root = _workspace(workspace)
    head = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    raw = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    result: dict[str, Any] = {"workspace": str(root),
                              "head": head.decode("ascii", "replace").strip() if head else None,
                              "branch": branch.decode("utf-8", "replace").strip() if branch else None,
                              "git_available": raw is not None}
    if raw is None:
        result.update({"changed": [], "truncated": False,
                       "warning": "Git status unavailable; workspace content not verified"})
        return result
    chunks = raw.split(b"\0")
    changes = []
    index = 0
    while index < len(chunks) and chunks[index]:
        entry = chunks[index]
        index += 1
        if len(entry) < 4:
            continue
        flag, raw_name = entry[:2].decode("ascii", "replace"), entry[3:]
        # Rename/copy porcelain -z has a second original path, not another status record.
        if flag[0] in "RC" or flag[1] in "RC":
            index += 1
        name = os.fsdecode(raw_name)
        if SENSITIVE_NAME.search(name.replace("\\", "/")):
            # A sensitive path may exist; don't archive its name or bytes.
            name = "<redacted-sensitive-path>"
            meta = {"path": name, "status": flag, "sha256": None, "size": None}
        else:
            file = root / os.fsdecode(raw_name)
            meta = {"path": name[:400], "status": flag, "sha256": None, "size": None}
            if file.is_symlink():
                meta["type"] = "symlink-not-followed"
            elif file.is_file():
                try:
                    size = file.stat().st_size
                    meta["size"] = size
                    if size <= MAX_HASH_BYTES:
                        meta["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
                    else:
                        meta["type"] = "too-large-to-hash"
                except OSError:
                    meta["type"] = "unreadable"
        changes.append(meta)
        if len(changes) >= MAX_CHANGED:
            break
    result["changed"] = changes
    result["truncated"] = bool(index < len(chunks) and chunks[index])
    result["integrity"] = _hash({k: v for k, v in result.items() if k != "integrity"})
    return result


def _state_digest(conn: sqlite3.Connection, sid: str) -> str:
    row = conn.execute("SELECT agent,workspace,title,status,goal,next_step,completed,decisions,blockers,snapshot,parent_session "
                       "FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise AuditError("Unknown Relay session")
    pending = [tuple(x) for x in conn.execute("SELECT tool_id,tool_name,started_at FROM pending_tools "
                                              "WHERE session_id=? ORDER BY tool_id", (sid,))]
    return _hash({"session": dict(row), "pending": pending})


def _event(conn: sqlite3.Connection, sid: str, kind: str, detail: dict) -> None:
    row = conn.execute("SELECT last_event_hash FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise AuditError("Unknown Relay session")
    stamp = int(time.time())
    previous = row["last_event_hash"]
    detail = {**detail, "state_digest": _state_digest(conn, sid)}
    payload = {"session_id": sid, "kind": kind, "created_at": stamp,
               "detail": detail, "previous_hash": previous}
    signature = _hash(payload)
    conn.execute("INSERT INTO events(session_id,kind,created_at,detail,previous_hash,event_hash) VALUES (?,?,?,?,?,?)",
                 (sid, kind, stamp, _canonical(detail), previous, signature))
    conn.execute("UPDATE sessions SET updated_at=?,last_event_hash=? WHERE id=?", (stamp, signature, sid))


def _session_id(agent: str, native: str, workspace: Path) -> str:
    # Do not persist native host session IDs, which can reveal account metadata.
    return hashlib.sha256((agent + "\0" + native + "\0" + str(workspace)).encode()).hexdigest()[:24]


def _create(conn: sqlite3.Connection, agent: str, native: str, workspace: Path) -> str:
    if agent not in AGENTS:
        raise AuditError("Unsupported agent")
    if not native or len(native) > 300:
        raise AuditError("Host session identifier missing or invalid")
    sid = _session_id(agent, native, workspace)
    with conn:
        exists = conn.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone()
        if not exists:
            timestamp = int(time.time())
            snapshot = workspace_snapshot(workspace)
            conn.execute("INSERT INTO sessions(id,agent,workspace,title,created_at,updated_at,status,snapshot) "
                         "VALUES(?,?,?,?,?,?,?,?)", (sid, agent, str(workspace), workspace.name,
                                                        timestamp, timestamp, "active", _canonical(snapshot)))
            _event(conn, sid, "session-start", {"snapshot": snapshot})
    return sid


def ingest_hook(agent: str, event: str, payload: dict, project: str | Path | None = None) -> dict:
    """Handle host hook metadata. Does not store the original payload."""
    if agent not in EVENTS or event not in EVENTS[agent]:
        raise AuditError("Unsupported agent event")
    if not isinstance(payload, dict):
        raise AuditError("Hook input must be a JSON object")
    directory = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("CURSOR_PROJECT_DIR") or os.getcwd()
    workspace = _workspace(directory)
    store = Path(os.environ.get("MIRRORMAP_RELAY_HOME", "~/.mirrormap/relay")).expanduser().resolve()
    if store == workspace or workspace in store.parents:
        raise AuditError("Relay store must stay OUTSIDE the audited project")
    if project is not None and workspace != _workspace(project):
        return {"recorded": False, "reason": "outside-approved-project"}
    native = (payload.get("session_id") or payload.get("conversation_id")
              or (os.getenv("MIRRORMAP_RELAY_NATIVE_SESSION_ID") if agent == "cursor" else None))
    # Several Cursor hook types lack a session_id in their documented payload.
    # Failing closed is safer than associating concurrent sessions by guessing.
    if not isinstance(native, str) or not native:
        return {"recorded": False, "reason": "hook-event-has-no-session-id"}
    conn = _connect()
    try:
        sid = _create(conn, agent, native, workspace)
        with conn:
            row = conn.execute("SELECT status FROM sessions WHERE id=?", (sid,)).fetchone()
            if row["status"] == "resumed_elsewhere":
                return {"recorded": False, "reason": "session-handed-off", "session_id": sid}
            kind = event.lower()
            details: dict[str, Any] = {"event": event}
            if event in {"PreToolUse", "preToolUse"}:
                tool = payload.get("tool_name") or payload.get("tool") or "unspecified"
                details["tool"] = str(tool)[:96]
                tid = payload.get("tool_use_id") or payload.get("tool_id")
                if isinstance(tid, str) and tid:
                    conn.execute("INSERT OR IGNORE INTO pending_tools VALUES(?,?,?,?)",
                                 (sid, tid[:150], str(tool)[:96], int(time.time())))
                else:
                    details["warning"] = "Tool started without a correlatable ID"
                    _event(conn, sid, "uncorrelated-tool-start", details)
            elif event in {"PostToolUse", "PostToolUseFailure", "postToolUse", "postToolUseFailure"}:
                tid = payload.get("tool_use_id") or payload.get("tool_id")
                if isinstance(tid, str) and tid:
                    removed = conn.execute("DELETE FROM pending_tools WHERE session_id=? AND tool_id=?",
                                           (sid, tid[:150])).rowcount
                    details["paired_with_start"] = bool(removed)
                else:
                    details["paired_with_start"] = False
            if event in {"SessionEnd", "sessionEnd"}:
                reason = payload.get("reason")
                # 'completed' is a host session stop, not verified task completion.
                conn.execute("UPDATE sessions SET status=? WHERE id=?", ("ended", sid))
                if reason in {"aborted", "error", "window_close", "user_close"}:
                    details["end_reason"] = reason
            if event == "Interrupt":
                conn.execute("UPDATE sessions SET status=? WHERE id=?", ("interrupted", sid))
            snapshot = workspace_snapshot(workspace)
            details["snapshot"] = snapshot
            conn.execute("UPDATE sessions SET snapshot=? WHERE id=?", (_canonical(snapshot), sid))
            _event(conn, sid, kind, details)
        return {"recorded": True, "session_id": sid, "event": event}
    finally:
        conn.close()


def list_sessions(workspace: str | Path | None = None, limit: int = 30) -> list[dict]:
    if limit < 1 or limit > 100:
        raise AuditError("Limit must be from 1 to 100")
    conn = _connect()
    try:
        where, params = "", []
        if workspace is not None:
            where = " WHERE workspace=?"
            params.append(str(_workspace(workspace)))
        rows = conn.execute("SELECT id,agent,workspace,title,status,goal,next_step,updated_at "
                            "FROM sessions" + where + " ORDER BY updated_at DESC,id DESC LIMIT ?",
                            (*params, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _get_session(conn: sqlite3.Connection, sid: str) -> sqlite3.Row:
    if not re.fullmatch(r"[0-9a-f]{24}", sid):
        raise AuditError("Invalid Relay session ID")
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise AuditError("Relay session not found")
    return row


def record_note(sid: str, *, title: str | None = None, goal: str | None = None,
                next_step: str | None = None, done: list[str] | None = None,
                decision: list[str] | None = None, blocker: list[str] | None = None) -> None:
    conn = _connect()
    try:
        with conn:
            row = _get_session(conn, sid)
            updates = {"title": _text(title) if title is not None else row["title"],
                       "goal": _text(goal) if goal is not None else row["goal"],
                       "next_step": _text(next_step) if next_step is not None else row["next_step"]}
            for field, values in (("completed", done), ("decisions", decision), ("blockers", blocker)):
                original = json.loads(row[field])
                updates[field] = _canonical((original + [_text(item) for item in (values or [])])[-100:])
            conn.execute("UPDATE sessions SET title=?,goal=?,next_step=?,completed=?,decisions=?,blockers=? WHERE id=?",
                         (updates["title"], updates["goal"], updates["next_step"], updates["completed"],
                          updates["decisions"], updates["blockers"], sid))
            _event(conn, sid, "agent-note", {"title": updates["title"], "goal": updates["goal"],
                                              "next_step": updates["next_step"],
                                              "done": [_text(v) for v in (done or [])],
                                              "decision": [_text(v) for v in (decision or [])],
                                              "blocker": [_text(v) for v in (blocker or [])]})
    finally:
        conn.close()


def checkpoint(sid: str) -> dict:
    conn = _connect()
    try:
        with conn:
            row = _get_session(conn, sid)
            snapshot = workspace_snapshot(row["workspace"])
            conn.execute("UPDATE sessions SET snapshot=? WHERE id=?", (_canonical(snapshot), sid))
            _event(conn, sid, "manual-checkpoint", {"snapshot": snapshot})
        return {"session_id": sid, "snapshot": snapshot}
    finally:
        conn.close()


def verify(sid: str) -> dict:
    """Verify local chain and workspace state, not author identity or task completion."""
    conn = _connect()
    try:
        row = _get_session(conn, sid)
        events = conn.execute("SELECT session_id,kind,created_at,detail,previous_hash,event_hash "
                              "FROM events WHERE session_id=? ORDER BY seq", (sid,)).fetchall()
        previous = ""
        broken = False
        last_detail = None
        for event in events:
            try:
                detail = json.loads(event["detail"])
                last_detail = detail
                candidate = _hash({"session_id": event["session_id"], "kind": event["kind"],
                                   "created_at": event["created_at"], "detail": detail,
                                   "previous_hash": previous})
                if event["previous_hash"] != previous or event["event_hash"] != candidate:
                    broken = True
                previous = event["event_hash"]
            except (ValueError, TypeError):
                broken = True
        if not events or broken or previous != row["last_event_hash"] or not isinstance(last_detail, dict) or last_detail.get("state_digest") != _state_digest(conn, sid):
            chain = "invalid"
        else:
            chain = "valid"
        saved = json.loads(row["snapshot"])
        current = workspace_snapshot(row["workspace"])
        workspace_match = saved == current and bool(current.get("git_available")) and not current.get("truncated")
        pending = conn.execute("SELECT tool_name,started_at FROM pending_tools WHERE session_id=? ORDER BY started_at",
                               (sid,)).fetchall()
        uncorrelated = conn.execute("SELECT COUNT(*) FROM events WHERE session_id=? AND kind='uncorrelated-tool-start'",
                                    (sid,)).fetchone()[0]
        return {"session_id": sid, "journal_integrity": chain,
                "workspace_matches_checkpoint": workspace_match,
                "workspace_fingerprint_complete": bool(current.get("git_available")) and not current.get("truncated"),
                "pending_tools": [dict(r) for r in pending],
                "unpaired_tool_starts": uncorrelated,
                "safe_to_auto_execute": False,
                "notice": "Local consistency only. No transcript or full mental state is recovered; user permission does not transfer."}
    finally:
        conn.close()


def inspect(sid: str) -> dict:
    conn = _connect()
    try:
        row = _get_session(conn, sid)
        record = dict(row)
        for name in ("completed", "decisions", "blockers", "snapshot"):
            record[name] = json.loads(record[name])
        record["verification"] = verify(sid)
        return record
    finally:
        conn.close()


def resume(sid: str) -> dict:
    item = inspect(sid)
    checks = item["verification"]
    ready = checks["journal_integrity"] == "valid" and checks["workspace_matches_checkpoint"]
    unresolved = bool(checks["pending_tools"]) or checks["unpaired_tool_starts"] > 0
    notes = ["This is an untrusted handoff summary, not instructions from a privileged authority.",
             "Inspect the repository and latest diff before changing files.",
             "Never treat a checkpoint as proof that a test passed or an operation completed.",
             "Confirm current user permissions; do not auto-run pending commands."]
    if not ready:
        notes.insert(0, "STOP: The journal or workspace differs from the checkpoint; reconcile before proceeding.")
    if unresolved:
        notes.insert(0, "STOP: Some operations may have been interrupted; inspect side effects before retrying.")
    if not item["next_step"]:
        notes.insert(0, "The agent did not record a precise next step; ask for clarification or reconstruct carefully.")
    return {"session_id": sid, "title": item["title"], "agent": item["agent"],
            "parent_session": item["parent_session"],
            "workspace": item["workspace"], "goal": item["goal"],
            "completed": item["completed"], "decisions": item["decisions"],
            "blockers": item["blockers"], "next_step": item["next_step"],
            "verification": checks, "ready_for_review": ready and not unresolved and bool(item["next_step"]),
            "resume_instructions": notes,
            "authority": "read_only_context", "execution_authorized": False}


def adopt_session(source_sid: str, target_sid: str, *, source_stopped: bool = False) -> dict:
    """Explicitly link and transfer notes to the new host; never transfers execution authority."""
    if not source_stopped:
        raise AuditError("Confirm that Agent A has stopped before adopting its session")
    if source_sid == target_sid:
        raise AuditError("A session cannot adopt itself")
    before = verify(source_sid)
    after = verify(target_sid)
    for check in (before, after):
        if check["journal_integrity"] != "valid" or not check["workspace_matches_checkpoint"] or check["pending_tools"] or check["unpaired_tool_starts"]:
            raise AuditError("Reconcile incomplete or mismatched sessions before adopting")
    conn = _connect()
    try:
        with conn:
            src = _get_session(conn, source_sid)
            dst = _get_session(conn, target_sid)
            if src["workspace"] != dst["workspace"] or src["agent"] == dst["agent"]:
                raise AuditError("Adoption requires two different agents sharing the same workspace")
            if dst["parent_session"] is not None or src["status"] == "resumed_elsewhere":
                raise AuditError("Session already handed off or adopted")
            # Don't erase already recorded context in the receiving agent.
            title = dst["title"] if dst["title"] != Path(dst["workspace"]).name else src["title"]
            conn.execute("UPDATE sessions SET parent_session=?,title=?,goal=?,next_step=?,completed=?,decisions=?,blockers=? WHERE id=?",
                         (source_sid, title, dst["goal"] or src["goal"],
                          dst["next_step"] or src["next_step"],
                          _canonical((json.loads(src["completed"]) + json.loads(dst["completed"]))[-100:]),
                          _canonical((json.loads(src["decisions"]) + json.loads(dst["decisions"]))[-100:]),
                          _canonical((json.loads(src["blockers"]) + json.loads(dst["blockers"]))[-100:]), target_sid))
            conn.execute("UPDATE sessions SET status=? WHERE id=?", ("resumed_elsewhere", source_sid))
            _event(conn, source_sid, "handoff-out", {"receiving_session": target_sid,
                                                       "execution_authorized": False})
            _event(conn, target_sid, "handoff-in", {"from_session": source_sid,
                                                      "execution_authorized": False})
        return {"source": source_sid, "target": target_sid, "read_only_context_transferred": True,
                "execution_authorized": False,
                "warning": "No host operation was performed; confirm Agent A is inactive."}
    finally:
        conn.close()


def _quote_command(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def _config_path(agent: str) -> Path:
    home = Path.home()
    return {"claude": home / ".claude" / "settings.json",
            "codex": home / ".codex" / "hooks.json",
            "cursor": home / ".cursor" / "hooks.json"}[agent]


def hook_configuration(agent: str, project: str | Path, *, remove: bool = False,
                       config_path: Path | None = None) -> dict:
    """Return preview for additive user-level hook config; never mutate without apply."""
    if agent not in AGENTS:
        raise AuditError("Agent must be claude, codex, or cursor")
    root = _workspace(project)
    path = config_path or _config_path(agent)
    if path.is_symlink():
        raise AuditError("Refusing to modify symlinked agent settings")
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict):
        raise AuditError("Agent settings must be a JSON object")
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise AuditError("Existing hooks must be an object")
    if agent == "cursor":
        if config.get("version", 1) != 1:
            raise AuditError("Unsupported Cursor hook configuration version")
        config.setdefault("version", 1)
    commands = []
    # Hook scripts import the installed distribution in isolated Python mode to
    # avoid import-shadowing by an unrelated repository's projectmirror.py.
    for event in EVENTS[agent]:
        command = _quote_command([sys.executable, "-I", "-m", "projectmirror", "relay", "hook",
                                  "--agent", agent, "--event", event, "--project", str(root)])
        if agent == "cursor":
            record = {"command": command}
        else:
            record = {"hooks": [{"type": "command", "command": command, "timeout": 10}]}
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise AuditError("Existing hook event configuration must be an array")
        marker = f"relay hook --agent {agent} --event {event} --project"
        # Exactly match generated commands, preserve third-party hooks and others.
        match = [item for item in existing if _contains_command(item, command)]
        if remove:
            hooks[event] = [item for item in existing if not _contains_command(item, command)]
            if not hooks[event]:
                del hooks[event]
        elif not match:
            hooks[event].append(record)
        commands.append(command)
    if remove and not hooks:
        config.pop("hooks", None)
    return {"agent": agent, "project": str(root), "config_path": str(path),
            "configuration": config, "commands": commands,
            "action": "remove" if remove else "install",
            "notice": "User-level hooks are project-filtered; no agent settings are changed until --apply."}


def _contains_command(entry: Any, command: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("command") == command:
        return True
    children = entry.get("hooks")
    return isinstance(children, list) and any(isinstance(c, dict) and c.get("command") == command for c in children)


def modify_hooks(agent: str, project: str | Path, *, apply: bool = False,
                 remove: bool = False, config_path: Path | None = None) -> dict:
    result = hook_configuration(agent, project, remove=remove, config_path=config_path)
    if not apply:
        return {**result, "applied": False}
    path = Path(result["config_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reject configurations changed between read and write? single-process preview
    # doesn't reserve the host settings file; operators must review after editing.
    temp = path.with_name(path.name + ".mirrormap-tmp")
    if temp.exists() or temp.is_symlink():
        raise AuditError("Temporary config file already exists")
    with temp.open("x", encoding="utf-8") as out:
        json.dump(result["configuration"], out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    if os.name != "nt":
        os.chmod(temp, 0o600)
    os.replace(temp, path)
    return {**result, "applied": True}


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mirrormap relay", description="Opt-in metadata-only local agent context continuity")
    cmds = parser.add_subparsers(dest="command", required=True)
    p = cmds.add_parser("sessions", help="list saved sessions for the current user")
    p.add_argument("--workspace")
    p.add_argument("--limit", type=int, default=30)
    p = cmds.add_parser("inspect", help="show a session and its verification state")
    p.add_argument("--session", required=True)
    p = cmds.add_parser("verify", help="verify journal and workspace fingerprint")
    p.add_argument("--session", required=True)
    p = cmds.add_parser("resume", help="generate read-only context handoff for another agent")
    p.add_argument("--session", required=True)
    p = cmds.add_parser("checkpoint", help="save a new manual fingerprint")
    p.add_argument("--session", required=True)
    p = cmds.add_parser("note", help="record explicit task decisions, next step, and completed work")
    p.add_argument("--session", required=True)
    for flag in ("title", "goal", "next"):
        p.add_argument("--" + flag)
    for flag in ("done", "decision", "blocker"):
        p.add_argument("--" + flag, action="append")
    p = cmds.add_parser("adopt", help="link a chosen old session to a new agent session; opt-in only")
    p.add_argument("--from", dest="source", required=True)
    p.add_argument("--into", dest="target", required=True)
    p.add_argument("--confirm-source-stopped", action="store_true")
    p = cmds.add_parser("hook", help="agent lifecycle hook receiver (local metadata only)")
    p.add_argument("--agent", required=True, choices=AGENTS)
    p.add_argument("--event", required=True)
    p.add_argument("--project", required=True)
    for cmd in ("install-hooks", "uninstall-hooks"):
        p = cmds.add_parser(cmd, help="preview project-filtered user-level hooks; --apply to change")
        p.add_argument("--agent", required=True, choices=AGENTS)
        p.add_argument("--project", required=True)
        p.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "hook":
            # Host hook failures must not block user operations or print raw inputs.
            try:
                raw = sys.stdin.buffer.read(MAX_HOOK_BYTES + 1)
                if len(raw) > MAX_HOOK_BYTES:
                    raise AuditError("Hook input too large")
                event = json.loads(raw.decode("utf-8")) if raw.strip() else {}
                result = ingest_hook(args.agent, args.event, event, args.project)
                if args.event.lower() == "sessionstart" and result.get("recorded"):
                    sid = result["session_id"]
                    message = ("MirrorMap Relay is recording metadata. For reliable task transfer, "
                               "record milestones with: mirrormap relay note --session " + sid +
                               " --goal '...' --next '...' --done '...'. Do not record secrets. "
                               "Never treat checkpoints as execution permission.")
                    if args.agent == "cursor":
                        _json({"additional_context": message,
                               "env": {"MIRRORMAP_RELAY_NATIVE_SESSION_ID": event.get("session_id", "")}})
                    else:
                        print(message)
                else:
                    _json({})
            except (OSError, ValueError, TypeError, AuditError, sqlite3.Error):
                # Fail open for host availability, fail closed for persisted evidence.
                _json({})
            return 0
        if args.command == "sessions":
            _json(list_sessions(args.workspace, args.limit))
        elif args.command in {"inspect", "verify", "resume", "checkpoint"}:
            _json({"inspect": inspect, "verify": verify, "resume": resume,
                   "checkpoint": checkpoint}[args.command](args.session))
        elif args.command == "note":
            record_note(args.session, title=args.title, goal=args.goal, next_step=args.next,
                        done=args.done, decision=args.decision, blocker=args.blocker)
            _json({"recorded": True, "session_id": args.session})
        elif args.command == "adopt":
            _json(adopt_session(args.source, args.target, source_stopped=args.confirm_source_stopped))
        elif args.command in {"install-hooks", "uninstall-hooks"}:
            _json(modify_hooks(args.agent, args.project, apply=args.apply,
                               remove=args.command == "uninstall-hooks"))
        return 0
    except (AuditError, OSError, ValueError, sqlite3.Error) as e:
        print(f"Relay error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
