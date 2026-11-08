"""End-to-end CLI smoke tests using only disposable temporary directories."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
REPO = SOURCE / "examples" / "demo-app"
SPEC = REPO / "requirements.md"


class CLITest(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([sys.executable, "-m", "projectmirror", *map(str, args)],
                              cwd=SOURCE, capture_output=True, text=True, timeout=25)

    def test_demo_safe_audit(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "audit"
            for args in (("init", "--repo", REPO, "--out", output),
                         ("intent", "--spec", SPEC, "--state", "approved", "--out", output),
                         ("index", "--repo", REPO, "--out", output),
                         ("diff", "--out", output), ("plan", "--out", output),
                         ("render", "--out", output), ("snapshot", "--out", output)):
                result = self.command(*args)
                self.assertEqual(result.returncode, 0, msg=f"{args[0]} failed: {result.stderr}\n{result.stdout}")
            for name in ("audit-manifest.json", "intent-map.json", "implementation-map.json", "findings.json", "plan.json", "audit-report.md", "remediation-plan.md", "mindmap.mmd"):
                self.assertTrue((output / name).is_file(), name)
            findings = json.loads((output / "findings.json").read_text(encoding="utf-8"))
            self.assertEqual(findings["counts"], {"unknown": 3})
            self.assertEqual(len(list((output / "snapshots").iterdir())), 1)

    def test_init_refuses_writes_inside_project(self):
        result = self.command("init", "--repo", REPO, "--out", REPO / "audit")
        self.assertEqual(result.returncode, 2)
        self.assertIn("OUTSIDE", result.stderr)
        self.assertFalse((REPO / "audit").exists())

    def test_intent_refuses_without_init(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.command("intent", "--spec", SPEC, "--out", Path(td) / "audit")
            self.assertEqual(result.returncode, 2)
            self.assertIn("Run init first", result.stderr)

    def test_two_snapshots_are_uniquely_named(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            self.assertEqual(self.command("init", "--repo", REPO, "--out", out).returncode, 0)
            self.assertEqual(self.command("snapshot", "--out", out).returncode, 0)
            self.assertEqual(self.command("snapshot", "--out", out).returncode, 0)
            self.assertEqual(len(list((out / "snapshots").iterdir())), 2)

    def test_index_refuses_without_init(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.command("index", "--repo", REPO, "--out", Path(td) / "audit")
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
