"""Explicit offline encrypted transfer, using optional audited AES-GCM library."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path

from . import relay, relay_state, bolt_memory
from .core import AuditError
from .bolt import write_private, read_json, _session
from .bolt_analysis import firewall

AAD=b"MirrorMap BOLT context package v1"
MAX=2_000_000


def _aes():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM
    except ImportError as exc:
        raise AuditError("Encrypted transfer requires pip install 'projectmirror-skill[bolt-crypto]'") from exc


def keygen(repo,out):
    _aes()
    return {"key_file":write_private(repo,out,os.urandom(32)),
            "notice":"Keep the 32-byte key private. Transfer it separately via a trusted channel; never commit it.",
            "execution_authorized":False}


def _key(repo,path):
    root=bolt_memory.workspace(repo)
    p=Path(path).expanduser()
    resolved=p.resolve()
    if p.is_symlink() or resolved==root or root in resolved.parents or not p.is_file() or p.stat().st_size!=32:
        raise AuditError("Use a 32-byte key file outside the project")
    if os.name!="nt" and p.stat().st_mode & 0o077:
        raise AuditError("Key must be private (chmod 600)")
    return p.read_bytes()


def export_package(repo,sid,key,out,confirm=False):
    if not confirm:
        raise AuditError("Review context and explicitly confirm export")
    _session(repo,sid)
    state=relay_state.recover(sid,budget="detailed")
    payload={"version":1,"context":state,"records":bolt_memory.records(repo),"execution_authorized":False}
    encoded=relay._canonical(payload).encode("utf-8")
    if len(encoded)>MAX:
        raise AuditError("Export too large; review a smaller project record set")
    nonce=os.urandom(12)
    encrypted=_aes()(_key(repo,key)).encrypt(nonce,encoded,AAD)
    envelope={"version":1,"cipher":"AES-256-GCM","nonce":base64.b64encode(nonce).decode("ascii"),
              "ciphertext":base64.b64encode(encrypted).decode("ascii")}
    return {"output":write_private(repo,out,relay._canonical(envelope).encode("utf-8")),
            "encrypted":True,"execution_authorized":False,"notice":"Encrypted context only; no project source files or permissions."}


def import_package(repo,key,source):
    root=bolt_memory.workspace(repo)
    obj=read_json(source,3_000_000)
    if not isinstance(obj,dict) or set(obj)!={"version","cipher","nonce","ciphertext"} or obj["version"]!=1 or obj["cipher"]!="AES-256-GCM":
        raise AuditError("Unsupported encrypted package")
    try:
        nonce=base64.b64decode(obj["nonce"],validate=True)
        ciphertext=base64.b64decode(obj["ciphertext"],validate=True)
        if len(nonce)!=12 or len(ciphertext)>MAX+16:
            raise ValueError("Invalid package size")
        decoded=_aes()(_key(root,key)).decrypt(nonce,ciphertext,AAD)
        payload=json.loads(decoded)
    except Exception as exc:
        raise AuditError("Cannot authenticate or decrypt BOLT package; check key and integrity") from exc
    if not isinstance(payload,dict) or payload.get("version")!=1 or payload.get("execution_authorized") is not False:
        raise AuditError("Invalid package payload")
    context=payload.get("context")
    if not isinstance(context,dict) or context.get("execution_authorized") is not False or not isinstance(context.get("snapshot"),dict):
        raise AuditError("Invalid context payload")
    saved=context["snapshot"]
    current=relay.workspace_snapshot(root)
    def comparable(s):
        return {k:s.get(k) for k in ("head","changed","truncated","git_available")}
    # Clean commit match is deliberately conservative, since ignored/untracked
    # state and non-Git contents may differ across devices.
    same=bool(saved.get("head") and current.get("git_available") and saved.get("git_available")
              and not saved.get("changed") and not current.get("changed")
              and not saved.get("truncated") and not current.get("truncated") and comparable(saved)==comparable(current))
    return {"context":context,"records":payload.get("records",[]),"authenticated_with_shared_key":True,
            "clean_revision_matches":same,"origin_identity_verified":False,"ready_for_review":False,
            "execution_authorized":False,"firewall":firewall(relay._canonical(payload)[:100000]),
            "notice":"Authenticated encryption proves key possession, not identity or authorization. Import is a preview; nothing is restored or written into project memory."}
