"""BOLT project records. Local, explicit, append-only and never execution authority."""
from __future__ import annotations
import json
import re
import time
from pathlib import Path, PurePosixPath

from . import relay
from .core import AuditError, ignored
from .relay_efficiency import relevant

KINDS = ("dna", "ui", "intent", "failure", "review", "model", "branch")
MAX_RECORD_BYTES = 24000
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
NOTICE = "Recorded assertions, not proof of behavior or user identity. No execution authority."


def workspace(repo):
    root = relay._workspace(repo)
    store = Path(relay.relay_home()).resolve()
    if store == root or root in store.parents:
        raise AuditError("BOLT store must be outside the project")
    return root


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise AuditError("Use a stable identifier of 1–96 safe characters")
    return value


def text(value, label="text"):
    if not isinstance(value, str) or not value.strip() or len(value) > relay.MAX_NOTE:
        raise AuditError(label + " must be nonempty text of at most 1200 characters")
    if re.search(r"(?i)-----BEGIN .*PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,})", value):
        raise AuditError("Do not record credential material")
    return relay._text(value)


def safe_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        raise AuditError("Expected a safe repository-relative POSIX path")
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts or p.as_posix() == "." or ignored(Path(value)):
        raise AuditError("Unsafe or excluded project path")
    return p.as_posix()


def _strings(values, label, cap=40, paths=False):
    if not isinstance(values, list) or len(values) > cap:
        raise AuditError(label + " must be a bounded list")
    return list(dict.fromkeys(safe_path(v) if paths else text(v, label) for v in values))


def normalize(kind, data):
    if not isinstance(data, dict):
        raise AuditError("Record data must be an object")
    fields = {
        "dna": {"title", "description", "tags", "refs"},
        "ui": {"title", "description", "tags", "refs"},
        "intent": {"title", "description", "protected_paths", "refs", "locked"},
        "failure": {"title", "description", "attempt", "outcome", "refs", "tags"},
        "review": {"target", "reviewer", "verdict", "description", "refs"},
        "model": {"title", "capabilities", "cost_per_million", "description", "refs"},
        "branch": {"title", "description", "session", "checkpoint", "checkpoint_digest", "snapshot_digest"},
    }
    if kind not in fields or set(data) - fields[kind]:
        raise AuditError("Unknown BOLT record kind or field")
    out = {}
    for k, v in data.items():
        if k in {"tags", "refs", "capabilities"}:
            out[k] = _strings(v, k)
        elif k == "protected_paths":
            out[k] = _strings(v, k, paths=True)
        elif k == "locked":
            if type(v) is not bool:
                raise AuditError("locked must be boolean")
            out[k] = v
        elif k == "checkpoint":
            if type(v) is not int or v < 1:
                raise AuditError("Invalid checkpoint")
            out[k] = v
        elif k == "cost_per_million":
            if type(v) not in (int, float) or not 0 <= v <= 1_000_000:
                raise AuditError("Cost must be a nonnegative finite amount in common configured units")
            out[k] = v
        elif k in {"checkpoint_digest", "snapshot_digest"}:
            if not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v):
                raise AuditError("Invalid digest")
            out[k] = v
        elif k in {"target", "reviewer", "session"}:
            out[k] = identifier(v)
        else:
            out[k] = text(v, k)
    required = {
        "dna": {"title", "description"}, "ui": {"title", "description"},
        "intent": {"title", "description", "locked", "protected_paths"},
        "failure": {"title", "description", "attempt", "outcome", "refs"},
        "review": {"target", "reviewer", "verdict", "description", "refs"},
        "model": {"title", "capabilities", "description"},
        "branch": fields["branch"],
    }
    if required[kind] - out.keys():
        raise AuditError("Missing required record fields: " + ", ".join(sorted(required[kind] - out.keys())))
    if kind == "review" and out["verdict"] not in {"support", "oppose", "unknown"}:
        raise AuditError("Invalid reviewer verdict")
    if kind == "failure" and out["outcome"] not in {"failed", "rejected", "inconclusive"}:
        raise AuditError("Invalid failure outcome")
    if kind == "model" and not out["capabilities"]:
        raise AuditError("At least one declared capability is required")
    if len(relay._canonical(out).encode("utf-8")) > MAX_RECORD_BYTES:
        raise AuditError("Record too large")
    return out


def _connect():
    conn = relay._connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS bolt_records (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      workspace TEXT NOT NULL,
      kind TEXT NOT NULL,
      record_id TEXT NOT NULL,
      version INTEGER NOT NULL,
      payload TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      previous_hash TEXT NOT NULL,
      event_hash TEXT NOT NULL,
      UNIQUE(workspace,kind,record_id,version)
    );
    CREATE INDEX IF NOT EXISTS bolt_workspace_seq ON bolt_records(workspace,seq);
    """)
    return conn


def _read(conn, root):
    rows = conn.execute("SELECT * FROM bolt_records WHERE workspace=? ORDER BY seq", (str(root),))
    prev = ""
    latest = {}
    history = []
    for raw in rows:
        row = dict(raw)
        row["payload"] = json.loads(row["payload"])
        key = (row["kind"], row["record_id"])
        prior = latest.get(key)
        expected = 1 if prior is None else prior["version"]+1
        signed = {k: v for k, v in row.items() if k not in {"seq", "event_hash"}}
        if row["previous_hash"] != prev or row["event_hash"] != relay._hash(signed) or row["version"] != expected:
            raise AuditError("BOLT project record chain is invalid")
        if normalize(row["kind"], row["payload"]) != row["payload"]:
            raise AuditError("BOLT record schema is invalid")
        latest[key] = row
        history.append(row)
        prev = row["event_hash"]
    return history, latest, prev


def put(repo, kind, record_id, data, *, confirm=False, expected_version=None, unlock_reason=None):
    if not confirm:
        raise AuditError("Explicitly review and confirm the record")
    root = workspace(repo)
    rid = identifier(record_id)
    data = normalize(kind, data)
    conn = _connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            _, latest, prev = _read(conn, root)
            old = latest.get((kind, rid))
            version = old["version"] if old else 0
            if expected_version is not None and expected_version != version:
                raise AuditError("Record version changed; review again")
            if old and expected_version is None:
                raise AuditError("Updating a record requires its expected version")
            if old and kind == "intent" and old["payload"]["locked"] and old["payload"] != data:
                if not unlock_reason:
                    raise AuditError("Locked intent requires an explicit reviewed revision reason")
                # Preserve the revision reason as a recorded provenance reference.
                data["refs"] = _strings(data.get("refs", []) + ["Lock revision: " + text(unlock_reason)], "refs")
            signed = {"workspace": str(root), "kind": kind, "record_id": rid,
                      "version": version+1, "payload": data, "created_at": int(time.time()),
                      "previous_hash": prev}
            sha = relay._hash(signed)
            conn.execute("INSERT INTO bolt_records(workspace,kind,record_id,version,payload,created_at,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)",
                         (str(root), kind, rid, version+1, relay._canonical(data), signed["created_at"], prev, sha))
        return {**signed, "event_hash": sha, "execution_authorized": False, "notice": NOTICE}
    finally:
        conn.close()


def records(repo, kind=None, *, history=False):
    root = workspace(repo)
    if kind is not None and kind not in KINDS:
        raise AuditError("Unknown BOLT record kind")
    conn = _connect()
    try:
        conn.execute("BEGIN")
        all_rows, latest, _ = _read(conn, root)
        rows = all_rows if history else list(latest.values())
        return [r for r in rows if kind is None or r["kind"] == kind]
    finally:
        conn.close()


def search(repo, query, kind=None, limit=8):
    if not 1 <= limit <= 50:
        raise AuditError("Search limit must be 1–50")
    return {"records": relevant(records(repo, kind), query)[:limit],
            "matching": "lexical_candidates", "execution_authorized": False}


def guardian(repo, paths):
    paths = _strings(paths, "paths", cap=500, paths=True)
    conflicts = []
    for record in records(repo, "intent"):
        intent = record["payload"]
        if not intent["locked"]:
            continue
        for path in paths:
            if any(path == p or path.startswith(p + "/") for p in intent["protected_paths"]):
                conflicts.append({"intent": record["record_id"], "version": record["version"],
                                  "path": path, "reason": "protected_path_overlap"})
    return {"proposed_paths": paths, "review_required": bool(conflicts), "conflicts": conflicts,
            "enforced_by_host": False, "execution_authorized": False,
            "notice": "Explicit path-scope checks only. No overlap is not approval or semantic compliance."}


def consensus(repo, target):
    identifier(target)
    grouped = {}
    for row in records(repo, "review"):
        p = row["payload"]
        if p["target"] == target:
            grouped.setdefault(p["reviewer"], []).append(p)
    reviews = []
    for reviewer, items in grouped.items():
        verdicts = {x["verdict"] for x in items}
        reviews.append({"reviewer": reviewer, "verdict": next(iter(verdicts)) if len(verdicts)==1 else "unknown",
                        "refs": sorted(set(ref for x in items for ref in x["refs"])),
                        "reports": items})
    values = {x["verdict"] for x in reviews}
    state = ("disagreement" if {"support","oppose"} <= values else
             "recorded_agreement" if len(reviews)>=2 and len(values)==1 and "unknown" not in values else "insufficient")
    return {"target": target, "state": state, "reviews": reviews,
            "independence_verified": False, "execution_authorized": False,
            "notice": "Declared reviewer labels are not authenticated; agreement does not prove correctness."}


def route(repo, capability):
    capability = text(capability, "capability").casefold()
    candidates = []
    for row in records(repo, "model"):
        p = row["payload"]
        if capability in {x.casefold() for x in p["capabilities"]}:
            candidates.append({"id": row["record_id"], **p})
    candidates.sort(key=lambda x: (x.get("cost_per_million", float("inf")), x["id"]))
    return {"task": capability, "candidates": candidates, "basis": "user-declared capability and comparable cost",
            "automatically_dispatched": False, "execution_authorized": False}
