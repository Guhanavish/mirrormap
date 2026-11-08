"""Security and integrity of self-contained interactive dashboard output."""
import html
import tempfile
import unittest
import json
import hashlib
import base64
from pathlib import Path

from projectmirror.dashboard import write_dashboard, _JS
from projectmirror.experience import audit_project

ROOT = Path(__file__).resolve().parents[1]


class InteractiveDashboardTests(unittest.TestCase):
    def test_offline_dashboard_contains_graph_controls_and_no_cdn(self):
        with tempfile.TemporaryDirectory() as scratch:
            dest = Path(scratch)/'audit'
            audit_project(ROOT/'examples/demo-app',spec=ROOT/'examples/demo-app/requirements.md',spec_approved=True,out=dest,mode='deep')
            page = (dest/'dashboard.html').read_text(encoding='utf-8')
            for marker in ('id="filters"','id="zoom"','id="search"','id="atlas-data"','aria-label="Interactive evidence map"',"connect-src 'none'"):
                self.assertIn(marker,html.unescape(page))
            self.assertNotIn('https://',page)
            self.assertNotIn('<iframe',page)
            digest=base64.b64encode(hashlib.sha256(_JS.encode('utf-8')).digest()).decode('ascii')
            self.assertIn(f"script-src 'sha256-{digest}'",html.unescape(page))

    def test_injected_source_never_becomes_executable_markup(self):
        with tempfile.TemporaryDirectory() as scratch:
            out=Path(scratch)
            malicious='</script><img src=x onerror=alert(1)>'
            findings={'counts':{'unknown':1},'findings':[{'id':'F-foo','title':malicious,'classification':'unknown','reason':malicious,'scope':'approved','evidence':[malicious], 'implementation_ids': [], 'verification_ids': []}]}
            write_dashboard(out,malicious,findings,{'project':{'repo':malicious,'revision':None}})
            page=(out/'dashboard.html').read_text(encoding='utf-8')
            self.assertNotIn('</script><img',page)
            self.assertNotIn('<img src=x',page)
            self.assertIn('&lt;img src=x',page)
            self.assertIn('\\u003cimg',page)
            self.assertIn(malicious.replace('<','&lt;').replace('>','&gt;'),page)

    def test_graph_payload_limits_linked_data_and_excludes_full_source(self):
        with tempfile.TemporaryDirectory() as scratch:
            out=Path(scratch)
            findings={'counts':{'unverified':1},'findings':[{'id':'F-foo','title':'Login','classification':'unverified','reason':'Missing tests','scope':'approved','implementation_ids':['impl.a'], 'verification_ids':[], 'evidence':[]}]}
            imp={'nodes':[{'id':'impl.a','title':'Known code','locator':'src/auth.py:1'},{'id':'impl.secret','title':'should-not-appear','locator':'private_file.py'}]}
            write_dashboard(out,'Atlas',findings,{'project':{'repo':'fixture','revision':'abc'}},implementation=imp)
            page=(out/'dashboard.html').read_text()
            self.assertIn('src/auth.py:1',page)
            self.assertNotIn('private_file.py',page)
            self.assertIn('No trackers or external scripts',page)

if __name__ == '__main__': unittest.main()
