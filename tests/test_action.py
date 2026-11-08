"""GitHub composite action contract, including a local simulation of its shell step.

The action is tested without calling GitHub or executing target project code.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def action_script() -> str:
    content = (ROOT / "action.yml").read_text(encoding="utf-8")
    lines = content.splitlines()
    try:
        idx = next(i for i, ln in enumerate(lines) if ln.startswith("      run: |"))
    except StopIteration as e:
        raise AssertionError("Composite action needs an executable run step") from e
    script_lines = []
    for line in lines[idx+1:]:
        if line.strip() and not line.startswith("        "):
            break
        script_lines.append(line[8:] if line else "")
    return "\n".join(script_lines) + "\n"


class GitHubActionTests(unittest.TestCase):
    def test_action_declares_read_only_contract(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", text)
        self.assertIn("report-directory:", text)
        self.assertNotIn("pull_request_target", text)
        self.assertIn("${RUNNER_TEMP}", action_script())
        self.assertIn("python3 -m projectmirror", action_script())

    def test_composite_action_generates_reports_in_temp(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch)
            github_output = path / "github_output.txt"
            fixture = ROOT / "examples" / "demo-app"
            file_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.iterdir() if p.is_file()}
            env = dict(os.environ, GITHUB_WORKSPACE=str(fixture), RUNNER_TEMP=str(path),
                       GITHUB_OUTPUT=str(github_output), MIRRORMAP_MODE="deep",
                       MIRRORMAP_SPEC="requirements.md", MIRRORMAP_APPROVED_SPEC="true", MIRRORMAP_BASE="")
            script = action_script().replace("${{ github.action_path }}", str(ROOT))
            self.assertNotIn("${{", script, "Unexpected unevaluated GitHub expression in composite run step")
            proc = subprocess.run(["bash", "-c", script], env=env, text=True,
                                  capture_output=True, check=False, timeout=35)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            entry = github_output.read_text().strip()
            self.assertTrue(entry.startswith("report_directory="))
            report = Path(entry.split("=", 1)[1])
            self.assertEqual(report.parent, path)
            self.assertTrue((report / "dashboard.html").is_file())
            self.assertEqual(json.loads((report / "summary.json").read_text())["counts"], {"unknown": 3})
            file_after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.iterdir() if p.is_file()}
            self.assertEqual(file_before, file_after)

    def test_invalid_approved_spec_fails_closed(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch)
            env = dict(os.environ, GITHUB_WORKSPACE=str(ROOT / "examples" / "demo-app"),
                       RUNNER_TEMP=str(path), GITHUB_OUTPUT=str(path / "gh-out"),
                       MIRRORMAP_MODE="quick", MIRRORMAP_SPEC="", MIRRORMAP_APPROVED_SPEC="true", MIRRORMAP_BASE="")
            script = action_script().replace("${{ github.action_path }}", str(ROOT))
            proc = subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True, timeout=35)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("requires a specification", proc.stderr)


if __name__ == "__main__":
    unittest.main()
