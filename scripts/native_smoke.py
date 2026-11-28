"""Exercise the native executable in a fresh home without a Python CLI invocation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

exe = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as temp:
    home = Path(temp) / "user"
    home.mkdir()
    project = Path(temp) / "project"
    project.mkdir()
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
           "CODEX_HOME": str(home / ".codex"), "MIRRORMAP_RELAY_HOME": str(home / ".mirrormap" / "relay")}
    def run(*args, executable=exe, payload=None):
        result = subprocess.run([str(executable), *args], env=env, cwd=project, input=payload,
                                text=True, capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr + result.stdout)
        return result.stdout
    assert "relay" in run("relay", "--help")
    assert "BOLT" in run("bolt", "--help")
    preview=json.loads(run("setup","--agent","codex","--project",str(project)))
    assert not preview["applied"]
    assert not (home/".codex"/"hooks.json").exists()
    installed=json.loads(run("setup","--agent","codex","--project",str(project),"--apply"))
    assert installed["applied"]
    assert (home/".agents"/"skills"/"mirrormap"/"SKILL.md").is_file()
    managed=Path(installed["engine"][0])
    assert managed.is_file()
    assert len(installed["engine"])==1
    command=installed["plans"][0]["commands"][0]
    assert "-m projectmirror" not in command and str(managed) in command
    payload=json.dumps({"session_id":"native-smoke","cwd":str(project)})
    run("relay","hook","--agent","codex","--event","SessionStart","--project",str(project),
        executable=managed,payload=payload)
    sessions=json.loads(run("relay","sessions","--workspace",str(project),executable=managed))
    assert len(sessions)==1
    assert json.loads(run("installation-doctor","--project",str(project),executable=managed))["managed_installations"][0]["hooks_present"]
    run("uninstall","--agent","codex","--project",str(project),"--apply",executable=managed)
    assert not json.loads((home/".codex"/"hooks.json").read_text()).get("hooks")
    assert json.loads(run("relay","sessions","--workspace",str(project),executable=managed))
print("Standalone setup, hook, recovery and uninstall smoke passed")
