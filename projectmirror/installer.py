"""User-scoped setup manager. Preview first; preserve unrelated settings and Relay data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import relay, __version__
from .core import AuditError
from .relay_efficiency import MODES


def home():
    return Path.home() / ".mirrormap"


def _read(path):
    if path.is_symlink():
        raise AuditError("Refusing symlinked installation metadata")
    if not path.exists():
        return {"schema": 1, "entries": []}
    if path.stat().st_size > 1_000_000:
        raise AuditError("Installation metadata is too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("entries"), list):
        raise AuditError("Invalid installation metadata")
    return data


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise AuditError("Refusing symlinked installation metadata")
    fd, name = tempfile.mkstemp(prefix=".mirrormap-install-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _skill_dest(agent):
    # User-scope only. Never edit project files or global PATH.
    base = Path.home()
    return {"codex": base / ".agents" / "skills" / "mirrormap",
            "claude": base / ".claude" / "skills" / "mirrormap",
            "cursor": base / ".cursor" / "skills" / "mirrormap"}[agent]


def _bundle():
    src = Path(__file__).resolve().parent / "skill_bundle"
    if not (src / "SKILL.md").is_file():
        raise AuditError("Packaged skill bundle missing")
    return src


def _bundle_files(src):
    return [src / "SKILL.md", *sorted((src / "references").glob("*.md"))]


def _skill_hashes(dest):
    if not dest.is_dir() or dest.is_symlink():
        return None
    result = {}
    for path in _bundle_files(dest):
        if path.is_symlink() or not path.is_file():
            return None
        result[path.relative_to(dest).as_posix()] = _digest(path)
    return result


def _install_skill(agent, old):
    dest = _skill_dest(agent)
    src = _bundle()
    desired = _skill_hashes(src)
    owned = old.get("skill_hashes") if old else None
    if dest.exists() or dest.is_symlink():
        actual = _skill_hashes(dest)
        if not owned or actual != owned:
            return {"path": str(dest), "status": "existing_unmanaged_or_modified", "hashes": owned}
        # Only replace previously owned files if there are no unexpected entries.
        allowed = set(owned)
        actual_files = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file() or p.is_symlink()}
        if actual_files != allowed or (dest / "references").is_symlink():
            return {"path": str(dest), "status": "existing_unmanaged_or_modified", "hashes": owned}
        if actual == desired:
            return {"path": str(dest), "status": "already_installed", "hashes": owned}
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".mirrormap-skill-", dir=dest.parent))
    backup = None
    try:
        for source in _bundle_files(src):
            target = stage / source.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if dest.exists():
            backup = Path(tempfile.mkdtemp(prefix=".mirrormap-previous-", dir=dest.parent))
            backup.rmdir()
            os.replace(dest, backup)
        try:
            os.replace(stage, dest)
        except BaseException:
            if backup:
                os.replace(backup, dest)
            raise
        if backup:
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"path": str(dest), "status": "installed", "hashes": desired}


def _managed_engine(apply):
    engine = relay.engine_command()
    if not getattr(sys, "frozen", False):
        return engine
    source = Path(sys.executable).resolve()
    # Immutable hash-named binaries allow update while the old executable runs.
    dest = home() / "bin" / _digest(source)[:24] / ("mirrormap.exe" if os.name == "nt" else "mirrormap")
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or (dest.exists() and _digest(dest) != _digest(source)):
            raise AuditError("Managed executable has unexpected content")
        if not dest.exists():
            fd, name = tempfile.mkstemp(prefix=".engine-", dir=dest.parent)
            os.close(fd)
            try:
                shutil.copy2(source, name)
                os.chmod(name, 0o700)
                os.replace(name, dest)
            finally:
                Path(name).unlink(missing_ok=True)
    return [str(dest)]


def _probe(engine):
    try:
        result = subprocess.run(engine + ["relay", "--help"], capture_output=True, timeout=60, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def diagnostics(project=None):
    info = _read(home() / "installation.json")
    agents = []
    for agent in relay.AGENTS:
        command = {"codex": "codex", "claude": "claude", "cursor": "cursor"}[agent]
        agents.append({"agent": agent, "detected": bool(shutil.which(command) or relay._config_path(agent).parent.is_dir()),
                       "config": str(relay._config_path(agent)), "skill": str(_skill_dest(agent))})
    entries = []
    for item in info["entries"]:
        if project is not None and item["project"] != str(relay._workspace(project)):
            continue
        cfg = Path(item["config"])
        present = False
        try:
            if cfg.is_file() and not cfg.is_symlink():
                hooks = json.loads(cfg.read_text(encoding="utf-8")).get("hooks", {})
                present = all(any(relay._contains_command(x, command) for values in hooks.values() for x in values)
                              for command in item["commands"])
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        entries.append({"agent": item["agent"], "project": item["project"], "hooks_present": present,
                        "engine_exists": Path(item["engine"][0]).is_file(),
                        "skill_present": (_skill_dest(item["agent"]) / "SKILL.md").is_file(),
                        "engine": item["engine"]})
    return {"version": __version__, "runtime": "bundled" if getattr(sys, "frozen", False) else "python",
            "engine": relay.engine_command(), "git": shutil.which("git"), "agents": agents,
            "managed_installations": entries, "host_hook_delivery_verified": False,
            "notice": "Local detection only. Remote/sandboxed agents need their own installation. Review and trust hooks in the host."}


def setup(project, agents, *, mode="eco", capture=False, apply=False, action="setup"):
    root = relay._workspace(project)
    state_path = home() / "installation.json"
    state = _read(state_path)
    if home().resolve() == root or root in home().resolve().parents:
        raise AuditError("Installer must remain outside the project")
    if mode not in MODES or (mode=="manual" and capture):
        raise AuditError("Invalid mode/capture combination")
    existing = {(i["project"], i["agent"]): i for i in state["entries"]}
    if not agents and action in {"repair","update","uninstall"}:
        agents = [i["agent"] for i in state["entries"] if i["project"]==str(root)]
    agents = list(dict.fromkeys(agents))
    if not agents or any(a not in relay.AGENTS for a in agents):
        raise AuditError("Choose at least one agent (--agent codex, claude, cursor or --auto)")
    engine = _managed_engine(False)
    plans=[]
    for agent in agents:
        key=(str(root),agent)
        old=existing.get(key)
        if action=="uninstall" and not old:
            raise AuditError("No managed installation for "+agent)
        if old and Path(old["config"]) != relay._config_path(agent):
            raise AuditError("Agent configuration location changed; review old setup manually")
        chosen_mode=old["mode"] if old and action in {"repair","update","uninstall"} else mode
        chosen_capture=old["capture"] if old and action in {"repair","update","uninstall"} else capture
        previous=tuple(old["commands"]) if old else ()
        if old is None:
            # Recognize older same-interpreter Relay commands, but never guess
            # ownership of arbitrary shell commands or another interpreter.
            previous=()
        preview=relay.hook_configuration(agent, root, remove=action=="uninstall",
                                        capture_context=chosen_capture, mode=chosen_mode,
                                        engine=engine, previous_commands=previous)
        plans.append((agent,key,old,chosen_mode,chosen_capture,previous,preview))
    result={"action":action,"project":str(root),"engine":engine,"applied":False,
            "plans":[{"agent":a,"config":p["config_path"],"commands":p["commands"],
                      "remove_exact_commands":p["removed_commands"],"mode":m,"capture":c,
                      "skill":str(_skill_dest(a))} for a,_,_,m,c,_,p in plans],
            "notice":"Preview first; --apply approves user-level changes. Native host approval remains required. Uninstall retains memory, engine and skill files."}
    if not apply:
        return result
    if action!="uninstall":
        engine=_managed_engine(True)
        if not _probe(engine):
            raise AuditError("Engine not reachable in isolated mode. Install the wheel or standalone executable in this environment.")
    # Persist each successful configuration independently to support recovery
    # after a partially completed multi-agent install.
    applied=[]
    for agent,key,old,chosen_mode,chosen_capture,previous,preview in plans:
        if action=="uninstall":
            skill={"status":"retained"}
        else:
            skill=_install_skill(agent,old or next((x for x in state["entries"] if x["agent"]==agent),None))
        changed=relay.modify_hooks(agent,root,apply=True,remove=action=="uninstall",
                                   capture_context=chosen_capture,mode=chosen_mode,
                                   engine=engine,previous_commands=previous)
        if action=="uninstall":
            existing.pop(key,None)
        else:
            existing[key]={"agent":agent,"project":str(root),"config":changed["config_path"],
                           "commands":changed["commands"],"engine":engine,"mode":chosen_mode,
                           "capture":chosen_capture,"skill_hashes":skill.get("hashes")}
        state["entries"]=list(existing.values())
        _atomic(state_path,state)
        applied.append({"agent":agent,"skill":skill["status"],"hooks_written":True})
    result.update({"applied":True,"results":applied,"diagnostics":diagnostics(root)})
    return result


def main(argv=None):
    p=argparse.ArgumentParser(prog="mirrormap",description="User-scope MirrorMap installation manager")
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("setup","repair","update","uninstall","installation-doctor"):
        cmd=sub.add_parser(name)
        cmd.add_argument("--project",default=".")
        if name!="installation-doctor":
            cmd.add_argument("--agent",choices=relay.AGENTS,action="append",default=[])
            cmd.add_argument("--auto",action="store_true",help="select detected local agents")
            cmd.add_argument("--mode",choices=MODES,default="eco")
            cmd.add_argument("--capture-context",action="store_true")
            cmd.add_argument("--apply",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.command=="installation-doctor":
            result=diagnostics(args.project)
        else:
            agents=args.agent
            if args.auto:
                agents=list(dict.fromkeys(agents+[x["agent"] for x in diagnostics()["agents"] if x["detected"]]))
            result=setup(args.project,agents,mode=args.mode,capture=args.capture_context,
                         apply=args.apply,action=args.command)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (AuditError,OSError,ValueError,TypeError,KeyError) as exc:
        print("MirrorMap setup: "+str(exc),file=sys.stderr)
        return 2
