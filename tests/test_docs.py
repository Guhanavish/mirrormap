"""Documentation, HTML output, wheel skill bundle, and interface contract checks."""
from __future__ import annotations

import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from projectmirror.core import load
from projectmirror.experience import audit_project

ROOT = Path(__file__).resolve().parents[1]


class DocsTests(unittest.TestCase):
    def test_svg_is_valid_xml(self):
        doc = ET.parse(ROOT / "assets" / "mirrormap-atlas.svg")
        self.assertTrue(doc.getroot().tag.endswith("svg"))

    def test_readme_relative_links_exist(self):
        md = (ROOT / "README.md").read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)]+)\)", md)
        for dest in links:
            if dest.startswith(("#", "https://", "http://", "mailto:")):
                continue
            path = ROOT / dest.split("#", 1)[0]
            self.assertTrue(path.is_file(), f"Missing README linked file: {dest}")

    def test_skill_metadata_and_bundle_sync(self):
        main = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        bundle = (ROOT / "projectmirror/skill_bundle/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(main, bundle)
        self.assertIn("name: mirrormap", main)
        self.assertIn("version: \"0.2.0\"", main)

    def test_generated_html_escapes_untrusted_source_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report"
            # fixture itself has no HTML; verify an injection-like title cannot enter HTML as markup
            audit_project(ROOT / "examples/demo-app", out=out)
            from projectmirror.experience import _html_report
            report = {"counts": {"unknown": 1}, "findings": [{"id": "F-x", "classification": "unknown", "title": "<script>alert(1)</script>", "reason": "user data"}]}
            _html_report(out, "<script>", report, load(out / "audit-manifest.json"))
            page = (out / "dashboard.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>", page)
            self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
