"""Persistent Relay task checkpoints; all imported context remains untrusted data.

This layer stores only recorded task state and explicitly opted-in bounded
excerpts. It never executes project code or restores a working tree.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from . import relay
from .core import AuditError

VERSION = 1
STAGES = ("planning", "implementation", "debugging", "testing", "deployment", "maintenance", "unknown")
BUDGETS = {"compact": 8000, "standard": 32000, "detailed": 64000}
MAX_PACKAGE = 2_000_000
COMMANDS = {"save", "history", "recover", "reconcile", "project-memory", "merge-context",
            "export", "import", "link-audit", "context-doctor", "context", "usage"}


def checkpoint_state(conn, sid):
    row = relay._get_session(conn, sid)
    state = {key: row[key] for key in ("title", "goal", "next_step", "status", "agent", "workspace",
                                      "parent_session")}
    for key in ("completed", "decisions", "blockers", "snapshot"):
        state[key] = json.loads(row[key])
    state["pending_tools"] = [dict(x) for x in conn.execute(
        "SELECT tool_name,started_at FROM pending_tools WHERE session_id=? ORDER BY tool_id", (sid,))]
    return state


def extract_context(agent, event, payload):
    """Never read transcripts or arbitrary tool payload fields.
    
    Hooks expose different fields in different hosts. Unknown fields are
    ignored; a missing excerpt never implies complete capture.
    """
    if event in {"UserPromptSubmit", "beforeSubmitPrompt"}:
        role, keys = "user", ("prompt", "user_prompt")
    elif event == "afterAgentResponse" and agent == "cursor":
        role, keys = "assistant", ("text",)
    elif event == "Stop" and agent in {"claude", "codex"}:
        role, keys = "assistant", ("last_assistant_message",)
    else:
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            # Keep both beginning and ending so a final "Next:" isn't lost on a long reply.
            cleaned = relay.SECRET_WORD.sub(lambda m: m.group(1) + "=[REDACTED]", value)
            cleaned = re.sub(r"(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)",
                             "[REDACTED PRIVATE KEY]", cleaned)
            cleaned = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,})\b",
                             "[REDACTED TOKEN]", cleaned)
            truncated = len(cleaned) > relay.MAX_NOTE
            marker = "\n[... omitted ...]\n"
            half = (relay.MAX_NOTE - len(marker)) // 2
            excerpt = cleaned[:half] + marker + cleaned[-half:] if truncated else cleaned
            return {"role": role, "text": excerpt, "host": agent, "field": key,
                    "truncated": truncated,
                    "authority": "untrusted_excerpt", "provenance": "opt_in_host_event"}
    return None


def _events(sid, *, hydrate=True):
    conn = relay._connect()
    try:
        relay._get_session(conn, sid)
        rows = [dict(row) for row in conn.execute(
            "SELECT seq,kind,created_at,detail,event_hash FROM events WHERE session_id=? ORDER BY seq",
            (sid,))]
        if hydrate:
            from .relay_efficiency import hydrate_rows
            return list(hydrate_rows(rows))
        return rows
    finally:
        conn.close()


def _verified(sid):
    check = relay.verify(sid)
    if check["journal_integrity"] != "valid":
        raise AuditError("Cannot use an invalid Relay journal")
    return check


def history(sid, limit=30):
    check = _verified(sid)
    if not 1 <= limit <= 100:
        raise AuditError("History limit must be from 1 to 100")
    records = []
    rows = _events(sid)
    if not rows or rows[-1]["event_hash"] != check["verified_event_hash"]:
        raise AuditError("Session changed during validation; retry")
    for row in rows:
        detail = json.loads(row["detail"])
        state = detail.get("checkpoint_state")
        records.append({"checkpoint": row["seq"], "kind": row["kind"], "created_at": row["created_at"],
                        "digest": row["event_hash"], "state_available": isinstance(state, dict),
                        "next_step": state.get("next_step", "") if isinstance(state, dict) else None})
    return {"session_id": sid, "checkpoints": records[-limit:], "total": len(records),
            "execution_authorized": False}


def save(sid, *, stage=None, goal=None, next_step=None, done=None, decision=None, blocker=None,
         correction=None):
    if stage is not None and stage not in STAGES:
        raise AuditError("Invalid project stage")
    before = relay.inspect(sid)
    _verified(sid)
    conn = relay._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = relay._get_session(conn, sid)
            if row["status"] == "resumed_elsewhere" or row["last_event_hash"] != before["last_event_hash"]:
                raise AuditError("Session changed or was handed off; inspect again")
            snapshot = relay.workspace_snapshot(row["workspace"])
            updates = {}
            for key, values in (("completed", done), ("decisions", decision), ("blockers", blocker)):
                from .relay_efficiency import unique_recent
                updates[key] = relay._canonical(unique_recent(json.loads(row[key]) + [relay._text(v) for v in (values or [])])[-100:])
            conn.execute("UPDATE sessions SET snapshot=?,goal=?,next_step=?,completed=?,decisions=?,blockers=? WHERE id=?",
                         (relay._canonical(snapshot), relay._text(goal) if goal is not None else row["goal"],
                          relay._text(next_step) if next_step is not None else row["next_step"],
                          updates["completed"], updates["decisions"], updates["blockers"], sid))
            relay._event(conn, sid, "project-save", {"stage": stage,
                         "correction": relay._text(correction) if correction else None,
                         "snapshot": snapshot})
        return {"session_id": sid, "saved": True, "stage": stage,
                "execution_authorized": False, "verification": relay.verify(sid)}
    finally:
        conn.close()


def reconcile(sid, reason, confirm=False):
    """A human inspected side effects. Acknowledgment is not success evidence."""
    if not confirm or not isinstance(reason, str) or not reason.strip():
        raise AuditError("Confirm manual inspection and provide a reconciliation reason")
    before = relay.inspect(sid)
    if before["verification"]["journal_integrity"] != "valid":
        raise AuditError("Cannot reconcile a corrupt journal")
    conn = relay._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = relay._get_session(conn, sid)
            if row["last_event_hash"] != before["last_event_hash"] or row["status"] == "resumed_elsewhere":
                raise AuditError("Session changed or was handed off; inspect again")
            removed = conn.execute("DELETE FROM pending_tools WHERE session_id=?", (sid,)).rowcount
            snapshot = relay.workspace_snapshot(row["workspace"])
            conn.execute("UPDATE sessions SET snapshot=? WHERE id=?", (relay._canonical(snapshot), sid))
            relay._event(conn, sid, "operations-reconciled", {
                "reason": relay._text(reason), "acknowledged_pending": removed,
                "acknowledged_uncorrelated": before["verification"]["unpaired_tool_starts"],
                "outcome": "reviewed_unknown", "snapshot": snapshot})
        return {"session_id": sid, "acknowledged_pending": removed,
                "outcome": "reviewed_unknown", "execution_authorized": False}
    finally:
        conn.close()


def suggest_stage(next_step):
    """Keyword suggestion only; no project completion inferred."""
    import re
    first = (next_step or "").lower()
    for stage, words in (
        ("testing", r"\b(test|verify|validate|regression)\b"),
        ("debugging", r"\b(fix|debug|investigate|diagnose)\b"),
        ("deployment", r"\b(deploy|release|publish|package)\b"),
        ("planning", r"\b(plan|design|specify|requirements)\b"),
        ("implementation", r"\b(implement|build|add|create|write)\b")):
        if re.search(words, first):
            return stage
    return "unknown"


def _lineage(sid, selected):
    """Read only the selected checkpoint's recorded ancestors, capped at 16."""
    chain = []
    seen = {sid}
    workspace = json.loads(selected["detail"]).get("checkpoint_state", {}).get("workspace")
    parent = json.loads(selected["detail"]).get("checkpoint_state", {}).get("parent_session")
    while parent and parent not in seen and len(chain) < 16:
        seen.add(parent)
        checked = _verified(parent)
        records = _events(parent)
        if not records or records[-1]["event_hash"] != checked["verified_event_hash"]:
            raise AuditError("Ancestor changed during validation; retry")
        boundary = next((row for row in reversed(records) if row["kind"] == "handoff-out"
                         and json.loads(row["detail"]).get("receiving_session") == sid), None)
        if boundary is None:
            raise AuditError("Handoff lineage has no matching transfer event")
        state = json.loads(boundary["detail"]).get("checkpoint_state")
        if not isinstance(state, dict):
            # Pre-upgrade transfer: latest notes remain readable, but historical
            # context cannot be invented. Expose the incomplete ancestor chain.
            break
        if state.get("workspace") != workspace:
            raise AuditError("Handoff lineage workspace mismatch")
        chain.append((parent, [row for row in records if row["seq"] <= boundary["seq"]]))
        sid, parent = parent, state.get("parent_session")
    return list(reversed(chain)), bool(parent)


def recover(sid, checkpoint=None, budget="compact", *, max_tokens=None, query=None, _catalog=False):
    from .relay_efficiency import unique_recent, relevant, estimate
    if max_tokens is not None and (not isinstance(max_tokens, int) or not 128 <= max_tokens <= 32000):
        raise AuditError("Estimated token target must be 128 to 32000")
    check = _verified(sid)
    if budget not in BUDGETS:
        raise AuditError("Invalid context budget")
    rows = _events(sid)
    if not rows:
        raise AuditError("No durable checkpoints")
    if rows[-1]["event_hash"] != check["verified_event_hash"]:
        raise AuditError("Session changed during validation; retry")
    selected = rows[-1] if checkpoint is None else next((r for r in rows if r["seq"] == checkpoint), None)
    if selected is None:
        raise AuditError("Checkpoint not found")
    state = json.loads(selected["detail"]).get("checkpoint_state")
    historical = selected["seq"] != rows[-1]["seq"]
    if not isinstance(state, dict):
        if historical:
            raise AuditError("Legacy historical checkpoint lacks full state; use latest or save again")
        conn = relay._connect()
        try:
            state = checkpoint_state(conn, sid)
        finally:
            conn.close()
        ancestors, lineage_truncated = [], bool(state["parent_session"])
    else:
        ancestors, lineage_truncated = _lineage(sid, selected)
    entries, stage, corrections, audit_links = [], "unknown", [], []
    latest_mode = "eco"
    for owner, records in ancestors + [(sid, [r for r in rows if r["seq"] <= selected["seq"]])]:
        for row in records:
            detail = json.loads(row["detail"])
            if detail.get("efficiency_mode"):
                latest_mode = detail["efficiency_mode"]
            if detail.get("stage") in STAGES:
                stage = detail["stage"]
            for field, dest in (("context_excerpt", entries), ("correction", corrections), ("audit_link", audit_links)):
                if detail.get(field):
                    dest.append({"session": owner, "event": row["seq"], "value": detail[field]})
            if row["kind"] == "context-merged":
                entries.append({"session": owner, "event": row["seq"], "value": {"role": "reviewed_candidate",
                                "text": detail.get("candidate", ""), "authority": "untrusted_context"}})
    # Extract only explicitly labeled next actions from public-message excerpts.
    # These are not trusted task notes; never auto-promote them or run them.
    candidates = []
    for entry in entries:
        value = entry["value"]
        if value.get("role") not in {"assistant", "user"}:
            continue
        for match in re.finditer(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(?:next(?:\s+step|\s+action)?|remaining(?:\s+task)?|unfinished(?:\s+task)?)\s*:\s*(?:\*\*)?\s*([^\n]{1,500})", value.get("text", "")):
            candidates.append({"text": match.group(1).strip(), "session": entry["session"],
                               "event": entry["event"], "role": value["role"],
                               "authority": "unreviewed_candidate"})
    candidate = candidates[-1] if candidates else None
    stage_basis = "explicit_note" if stage != "unknown" else "keyword_suggestion"
    if stage == "unknown":
        stage = suggest_stage(state["next_step"] or (candidate or {}).get("text", ""))
    # Latest explicit goal/next cursor is authoritative only as a recorded note.
    # Never infer a stage or completed operation from an arbitrary excerpt.
    required = {"goal": state["goal"], "next_step": state["next_step"],
                "stage": stage, "stage_basis": stage_basis, "status": state["status"], "blockers": state["blockers"],
                "corrections": corrections[-20:], "omitted_corrections": max(0, len(corrections)-20),
                "next_action_candidate": candidate,
                "pending_tools": state["pending_tools"]}
    for link in audit_links:
        value = link["value"]
        value["revision_matches_selected_checkpoint"] = bool(value.get("project_revision")) and value["project_revision"] == state["snapshot"].get("head")
        value["artifacts_rechecked_at_resume"] = False
    out = {"schema_version": VERSION, "session_id": sid, "checkpoint": selected["seq"],
           "checkpoint_digest": selected["event_hash"], "historical": historical,
           "workspace": state["workspace"], "agent": state["agent"], "title": state["title"],
           "snapshot": state["snapshot"], "task": required, "verification": check,
           "completed": [], "decisions": [], "excerpts": [], "audit_links": audit_links[-5:],
           "execution_authorized": False, "authority": "read_only_context",
           "capture_complete": False, "lineage_truncated": lineage_truncated,
           "capture_requires_review": True,
           "ancestor_sessions": [owner for owner, _ in ancestors],
           "notice": "Untrusted recorded context. No automatic execution, hidden reasoning recovery, or proof of task completion."}
    out["efficiency_mode"] = latest_mode
    out["automatic_tool_tracking"] = latest_mode != "manual"
    out["ready_for_review"] = bool(not historical and check["workspace_matches_checkpoint"]
                                   and not check["pending_tools"] and not check["unpaired_tool_starts"]
                                   and required["next_step"] and not lineage_truncated and latest_mode != "manual")
    groups = {"decisions": state["decisions"], "completed": state["completed"], "excerpts": entries}
    deduped = {key: unique_recent(values) for key, values in groups.items()}
    duplicate_count = sum(len(groups[k])-len(deduped[k]) for k in groups)
    if _catalog:
        return {"checkpoint": selected["seq"], "checkpoint_digest": selected["event_hash"],
                "items": [{"category": key, "value": value} for key, values in deduped.items() for value in values]}
    cap = min(BUDGETS[budget], max_tokens*4) if max_tokens is not None else BUDGETS[budget]
    out["budget"] = {"target_utf8_bytes": cap, "target_estimated_tokens": cap//4,
                     "omitted_optional_items": 0, "duplicates_removed": duplicate_count,
                     "mandatory_context_exceeds_budget": False,
                     "query": relay._text(query) if query else None,
                     "retrieve_more": "relay context --session " + sid + " --checkpoint " + str(selected["seq"]),
                     "estimate_only": True}
    def fits():
        return len(relay._canonical(out).encode("utf-8")) <= cap
    mandatory_over = not fits()
    omitted = 0
    # Rank all optional items against the current task or explicit query;
    # ties retain newest items. Unmatched items remain retrievable on demand.
    ranked = relevant([{"category": key, "value": value} for key, values in deduped.items() for value in values],
                      query or state["next_step"])
    if not query:
        # Retain unrelated context if room remains; no semantic inference.
        ranked += [item for key, values in deduped.items() for value in reversed(values)
                   if (item := {"category": key, "value": value}) not in ranked]
    total = sum(len(v) for v in deduped.values())
    for item in ranked:
        field, value = item["category"], item["value"]
        out[field].append(value)
        if not fits():
            out[field].pop()
    omitted = total - sum(len(out[k]) for k in groups)
    # Keep mandatory safety warnings even when they alone exceed a target.
    # Include response metadata in the final budget measurement.
    out["budget"]["mandatory_context_exceeds_budget"] = mandatory_over
    out["budget"]["omitted_optional_items"] = omitted
    while not fits() and any(out[k] for k in groups):
        # Remove the lowest-priority included item, not mandatory context.
        for item in reversed(ranked):
            if item["value"] in out[item["category"]]:
                out[item["category"]].remove(item["value"])
                out["budget"]["omitted_optional_items"] += 1
                break
    out["budget"]["mandatory_context_exceeds_budget"] = not fits()
    return out


def context_page(sid, *, checkpoint=None, query=None, offset=0, limit=5, max_tokens=2000):
    from .relay_efficiency import relevant
    if not 0 <= offset or not 1 <= limit <= 30 or not 128 <= max_tokens <= 32000:
        raise AuditError("Invalid context page bounds")
    catalog = recover(sid, checkpoint, _catalog=True)
    items = relevant(catalog["items"], query)
    result = {"session_id": sid, "checkpoint": catalog["checkpoint"],
              "checkpoint_digest": catalog["checkpoint_digest"], "offset": offset,
              "next_offset": None, "total_matches": len(items), "items": [],
              "query": relay._text(query) if query else None,
              "execution_authorized": False, "authority": "untrusted_context",
              "notice": "Lexical retrieval of recorded optional context; not a verification result.",
              "target_estimated_tokens": max_tokens, "budget_exceeded": False}
    for item in items[offset:offset+limit]:
        result["items"].append(item)
        if len(relay._canonical(result).encode("utf-8")) > max_tokens*4:
            result["items"].pop()
            break
    if offset + len(result["items"]) < len(items):
        result["next_offset"] = offset + len(result["items"])
    result["budget_exceeded"] = (not result["items"] and offset < len(items)) or len(relay._canonical(result).encode("utf-8")) > max_tokens*4
    return result


def project_memory(workspace, limit=10):
    if not 1 <= limit <= 30:
        raise AuditError("Memory limit must be from 1 to 30")
    records = []
    for item in relay.list_sessions(workspace, limit):
        check = relay.verify(item["id"])
        if check["journal_integrity"] != "valid":
            continue
        record = relay.inspect(item["id"])
        records.append({key: record[key] for key in
                        ("id", "agent", "title", "goal", "next_step", "decisions", "blockers", "status")})
    return {"workspace": str(relay._workspace(workspace)), "sessions": records,
            "notice": "Historical session notes are candidates, not current approved requirements.",
            "execution_authorized": False}


def merge_context(source, target, *, apply=False, confirm_reviewed=False):
    if source == target:
        raise AuditError("Choose separate sessions")
    src, dst = relay.inspect(source), relay.inspect(target)
    _verified(source)
    _verified(target)
    if src["workspace"] != dst["workspace"]:
        raise AuditError("Context merge requires the same workspace")
    candidate = relay._text(relay._canonical({"goal": src["goal"], "next_step": src["next_step"],
                                             "decisions": src["decisions"], "blockers": src["blockers"]}))
    result = {"source": source, "target": target, "candidate": candidate, "applied": False,
              "execution_authorized": False, "notice": "Candidate only; never overwrites the target goal or next step."}
    if not apply:
        return result
    if not confirm_reviewed:
        raise AuditError("Explicit review required before recording merged context")
    conn = relay._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = relay._get_session(conn, target)
            if row["last_event_hash"] != dst["last_event_hash"] or row["status"] == "resumed_elsewhere":
                raise AuditError("Target changed; review again")
            relay._event(conn, target, "context-merged", {"source": source, "source_digest": src["last_event_hash"],
                                                        "candidate": candidate})
        return {**result, "applied": True}
    finally:
        conn.close()


def link_audit(sid, directory):
    from .intelligence import verify_handoff
    item = relay.inspect(sid)
    _verified(sid)
    root = Path(directory).expanduser().resolve()
    workspace = Path(item["workspace"])
    if root == workspace or workspace in root.parents:
        raise AuditError("Audit directory must be outside the project")
    manifest_path, handoff_path = root / "audit-manifest.json", root / "audit-handoff.json"
    for file in (manifest_path, handoff_path):
        if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_PACKAGE:
            raise AuditError("Invalid audit manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    project = manifest.get("project", {})
    if project.get("repo") != item["workspace"]:
        raise AuditError("Audit belongs to another workspace")
    report = verify_handoff(root, handoff)
    if not report["valid"] or not report["checked_files"] or not any(
            x.get("name") == "audit-manifest.json" for x in handoff.get("artifacts", [])):
        raise AuditError("Audit handoff does not verify the project manifest")
    linked = {"digest": hashlib.sha256(handoff_path.read_bytes()).hexdigest(),
              "project_revision": project.get("revision"),
              "revision_matched": bool(project.get("revision")) and
                                  project["revision"] == item["snapshot"].get("head"),
              "checked_files": report["checked_files"], "authority": "integrity_only"}
    conn = relay._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = relay._get_session(conn, sid)
            if row["last_event_hash"] != item["last_event_hash"] or row["status"] == "resumed_elsewhere":
                raise AuditError("Session changed; inspect again")
            relay._event(conn, sid, "audit-linked", {"audit_link": linked})
        return {**linked, "execution_authorized": False}
    finally:
        conn.close()


def export_context(sid, destination, confirm=False):
    if not confirm:
        raise AuditError("Review the context and explicitly confirm export")
    data = recover(sid, budget="detailed")
    path = Path(destination).expanduser()
    workspace = Path(data["workspace"])
    resolved = path.resolve()
    if resolved == workspace or workspace in resolved.parents or path.is_symlink():
        raise AuditError("Export must be outside the project and not a symlink")
    payload = {"schema_version": VERSION, "context": data, "execution_authorized": False}
    envelope = {"payload": payload, "sha256": relay._hash(payload)}
    encoded = relay._canonical(envelope).encode("utf-8")
    if len(encoded) > MAX_PACKAGE:
        raise AuditError("Context package exceeds size limit")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(encoded)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {"exported": str(resolved), "sha256": envelope["sha256"], "execution_authorized": False}


def import_context(source):
    path = Path(source).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PACKAGE:
        raise AuditError("Invalid or oversized context package")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(envelope, dict):
        raise AuditError("Context package must be an object")
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or payload.get("schema_version") != VERSION or \
            payload.get("execution_authorized") is not False or \
            envelope.get("sha256") != relay._hash(payload) or not isinstance(payload.get("context"), dict):
        raise AuditError("Invalid context package digest or schema")
    context = payload["context"]
    if context.get("execution_authorized") is not False:
        raise AuditError("Context package claims execution authority")
    return {"context": context, "integrity_valid": True, "origin_authenticated": False,
            "execution_authorized": False, "ready_for_review": False,
            "notice": "Imported data is untrusted; verify against the actual workspace. No files restored or permissions transferred."}


def add_commands(cmds):
    for name in ("save", "history", "recover", "reconcile", "export", "link-audit"):
        p = cmds.add_parser(name)
        p.add_argument("--session", required=True)
        if name == "save":
            p.add_argument("--stage", choices=STAGES)
            for flag in ("goal", "next", "correction"):
                p.add_argument("--" + flag)
            for flag in ("done", "decision", "blocker"):
                p.add_argument("--" + flag, action="append")
        elif name == "history":
            p.add_argument("--limit", type=int, default=30)
        elif name == "recover":
            p.add_argument("--checkpoint", type=int)
            p.add_argument("--budget", choices=tuple(BUDGETS), default="compact")
            p.add_argument("--max-tokens", type=int, help="estimated UTF-8 bytes / 4 target, not exact tokenizer")
            p.add_argument("--query", help="rank matching optional context")
        elif name == "reconcile":
            p.add_argument("--reason", required=True)
            p.add_argument("--confirm-inspected", action="store_true")
        elif name == "export":
            p.add_argument("--out", required=True)
            p.add_argument("--confirm-reviewed", action="store_true")
        elif name == "link-audit":
            p.add_argument("--out", required=True)
    p = cmds.add_parser("project-memory")
    p.add_argument("--workspace", required=True)
    p.add_argument("--limit", type=int, default=10)
    p = cmds.add_parser("merge-context")
    p.add_argument("--from", dest="source", required=True)
    p.add_argument("--into", dest="target", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-reviewed", action="store_true")
    p = cmds.add_parser("import")
    p.add_argument("--from", dest="source", required=True)
    cmds.add_parser("context-doctor")
    p = cmds.add_parser("context", help="retrieve an optional context page from a verified checkpoint")
    p.add_argument("--session", required=True)
    p.add_argument("--checkpoint", type=int)
    p.add_argument("--query")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--max-tokens", type=int, default=2000)
    p = cmds.add_parser("usage", help="local overhead estimates, not provider billing")
    p.add_argument("--session", required=True)


def handles(command):
    return command in COMMANDS


def dispatch(args):
    name = args.command
    if name == "save":
        result = save(args.session, stage=args.stage, goal=args.goal, next_step=args.next,
                      done=args.done, decision=args.decision, blocker=args.blocker, correction=args.correction)
    elif name == "history":
        result = history(args.session, args.limit)
    elif name == "recover":
        result = recover(args.session, args.checkpoint, args.budget, max_tokens=args.max_tokens, query=args.query)
    elif name == "context":
        result = context_page(args.session, checkpoint=args.checkpoint, query=args.query,
                              offset=args.offset, limit=args.limit, max_tokens=args.max_tokens)
    elif name == "usage":
        from .relay_efficiency import usage
        result = usage(args.session)
    elif name == "reconcile":
        result = reconcile(args.session, args.reason, args.confirm_inspected)
    elif name == "project-memory":
        result = project_memory(args.workspace, args.limit)
    elif name == "merge-context":
        result = merge_context(args.source, args.target, apply=args.apply, confirm_reviewed=args.confirm_reviewed)
    elif name == "export":
        result = export_context(args.session, args.out, args.confirm_reviewed)
    elif name == "import":
        result = import_context(args.source)
    elif name == "link-audit":
        result = link_audit(args.session, args.out)
    else:
        result = {"store": str(relay.relay_home()), "supported_adapters": list(relay.AGENTS),
                  "live_host_verified": False, "capture_default": "metadata_only",
                  "notice": "Opt-in excerpts require compatible host fields; run field validation."}
    relay._json(result)
    return 0
