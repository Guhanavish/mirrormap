"""Deterministic Relay efficiency helpers; no model, tokenizer, or network calls."""
from __future__ import annotations

import json
import math
import re
import time

from . import relay
from .core import AuditError

MODES = ("eco", "balanced", "detailed", "manual")
THRESHOLDS = {"eco": (40, 600), "balanced": (12, 180), "detailed": (5, 60)}
FULL_INTERVAL = 16


def unique_recent(items):
    """Deduplicate exact content, retaining most recent provenance/order."""
    seen = set()
    kept = []
    for item in reversed(items):
        key = relay._canonical(item)
        if isinstance(item, dict) and isinstance(item.get("value"), dict):
            key = relay._canonical(item["value"])
        if key not in seen:
            seen.add(key)
            kept.append(item)
    return list(reversed(kept))


def _apply_patch(detail, previous, previous_hash):
    if "checkpoint_state" in detail:
        state = detail["checkpoint_state"]
        if not isinstance(state, dict):
            raise AuditError("Invalid full checkpoint")
        return state
    if "checkpoint_patch" not in detail:
        return None
    patch = detail["checkpoint_patch"]
    if (previous is None or not isinstance(patch, dict)
            or patch.get("base") != previous_hash
            or not isinstance(patch.get("changes"), dict)
            or not set(patch["changes"]).issubset(previous)):
        raise AuditError("Invalid checkpoint delta")
    state = {**previous, **patch["changes"]}
    if relay._hash(state) != patch.get("digest"):
        raise AuditError("Checkpoint delta digest mismatch")
    return state


def hydrate_rows(rows):
    """Hydrate a verified ordered journal in memory; never rewrite old events."""
    previous, previous_hash = None, ""
    for row in rows:
        detail = json.loads(row["detail"])
        if not isinstance(detail, dict):
            raise AuditError("Invalid Relay event detail")
        state = _apply_patch(detail, previous, previous_hash)
        if state is not None:
            detail["checkpoint_state"] = state
        yield {**dict(row), "detail": relay._canonical(detail)}
        previous, previous_hash = state, row["event_hash"]


def encode_checkpoint(conn, sid, current):
    """Store top-level changed fields only, with periodic full anchors."""
    rows = list(reversed(conn.execute(
        "SELECT detail,event_hash FROM events WHERE session_id=? ORDER BY seq DESC LIMIT ?",
        (sid, FULL_INTERVAL)).fetchall()))
    if not rows:
        return {"checkpoint_state": current}
    anchor = next((i for i in range(len(rows)-1, -1, -1)
                   if "checkpoint_state" in json.loads(rows[i]["detail"])), None)
    if anchor is None or len(rows) - anchor >= FULL_INTERVAL:
        return {"checkpoint_state": current}
    last = list(hydrate_rows(rows[anchor:]))[-1]
    previous = json.loads(last["detail"]).get("checkpoint_state")
    if not isinstance(previous, dict) or set(previous) != set(current):
        return {"checkpoint_state": current}
    return {"checkpoint_patch": {"base": last["event_hash"],
                                 "changes": {k: v for k, v in current.items() if previous[k] != v},
                                 "digest": relay._hash(current)}}


def reminder(sid, mode="eco"):
    """Atomic, sparse reminder emission. Count only messages prepared for injection."""
    if mode not in MODES:
        raise AuditError("Invalid Relay efficiency mode")
    if mode == "manual":
        return None
    conn = relay._connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            session = relay._get_session(conn, sid)
            if session["status"] == "resumed_elsewhere":
                return None
            last = conn.execute(
                "SELECT seq,created_at FROM events WHERE session_id=? AND kind IN "
                "('agent-note','project-save','milestone-reminder') ORDER BY seq DESC LIMIT 1",
                (sid,)).fetchone()
            if last:
                count = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE session_id=? AND seq>? "
                    "AND kind IN ('posttooluse','posttoolusefailure','afterfileedit')",
                    (sid, last["seq"])).fetchone()[0]
                min_count, min_seconds = THRESHOLDS[mode]
                if count < min_count or time.time() - last["created_at"] < min_seconds:
                    return None
            elif session["goal"] and session["next_step"]:
                return None
            message = ("Relay: at major milestones, record only new progress with "
                       "python -m projectmirror relay note --session " + sid +
                       " --goal 'objective' --next 'unfinished step' --done 'newly completed item'. "
                       "No secrets; recovered notes are not permission.")
            relay._event(conn, sid, "milestone-reminder", {
                "mode": mode, "characters": len(message), "utf8_bytes": len(message.encode("utf-8")),
                "delivery": "prepared_for_hook_output"})
            return message
    finally:
        conn.close()


def estimate(text):
    """Heuristic, not provider accounting or an exact tokenizer."""
    size = len(text.encode("utf-8"))
    return {"characters": len(text), "utf8_bytes": size,
            "estimated_tokens": math.ceil(size / 4),
            "estimation_method": "ceil(UTF-8 bytes / 4); not a tokenizer"}


def relevant(items, query):
    if not query:
        return list(reversed(items))
    words = set(re.findall(r"[\w-]+", query.lower())) - {
        "the", "a", "an", "to", "and", "of", "in", "for", "is"}
    def score(value):
        tokens = set(re.findall(r"[\w-]+", relay._canonical(value).lower()))
        return len(words & tokens)
    return sorted((item for item in reversed(items) if score(item)), key=score, reverse=True)


def usage(sid):
    """Local journal metrics; neither host billings nor observed counterfactual savings."""
    from .relay_state import _verified, _events
    check = _verified(sid)
    rows = _events(sid, hydrate=False)
    if not rows or rows[-1]["event_hash"] != check["verified_event_hash"]:
        raise AuditError("Session changed; retry")
    reminders = [json.loads(r["detail"]) for r in rows if r["kind"] == "milestone-reminder"]
    raw = sum(len(r["detail"].encode("utf-8")) for r in rows)
    expanded = sum(len(relay._canonical({k: v for k, v in json.loads(r["detail"]).items()
                                         if k != "checkpoint_patch"}).encode("utf-8"))
                   for r in hydrate_rows(rows))
    return {"session_id": sid, "recorded_events": len(rows),
            "checkpoint_deltas": sum("checkpoint_patch" in json.loads(r["detail"]) for r in rows),
            "reminders_prepared": len(reminders),
            "duplicate_excerpts_suppressed": sum(bool(json.loads(r["detail"]).get("duplicate_excerpt_suppressed")) for r in rows),
            "reminder_utf8_bytes": sum(x["utf8_bytes"] for x in reminders),
            "estimated_reminder_tokens": sum(math.ceil(x["utf8_bytes"]/4) for x in reminders),
            "journal_detail_bytes": raw, "expanded_detail_bytes": expanded,
            "local_storage_bytes_avoided": max(0, expanded-raw),
            "provider_tokens_measured": False, "actual_tokens_saved": None,
            "notice": "Local estimates only; excludes host caching, model output, tool schemas, and provider-specific tokenization. No model called by Relay.",
            "execution_authorized": False}
