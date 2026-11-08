"""JUnit import: no execution, no invented bindings, safe outputs."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from projectmirror.core import AuditError, compare, load, save, SCHEMA
from projectmirror.evidence import collect_junit
from projectmirror.experience import audit_project


REQ = {'schema_version': SCHEMA, 'nodes': [{
    'id': 'REQ.auth.login', 'map': 'intent', 'kind': 'requirement',
    'title': 'Login', 'requirement_state': 'approved',
    'acceptance_criteria': [{'id': 'AC.auth.valid', 'statement': 'Valid login succeeds'}]}]}
REPORT = '''<?xml version="1.0"?><testsuite name="auth" tests="2">
<testcase classname="tests.Auth" name="test_login" time="0.1"/>
<testcase classname="tests.Auth" name="test_wrong_password"><failure message="Wrong result">SECRET TRACE OMITTED</failure></testcase>
</testsuite>'''


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.xml = self.root / 'results.xml'
        self.xml.write_text(REPORT, encoding='utf-8')
        self.mapping = {'reviewed': True, 'revision': 'feedf00d', 'tests': [
            {'key': 'tests.Auth::test_login', 'requirement_id': 'REQ.auth.login', 'criteria_ids': ['AC.auth.valid']}]}

    def test_unreviewed_reports_only_generate_candidates(self):
        inv, verification = collect_junit([self.xml], manifest_revision='feedf00d', intent=REQ)
        self.assertEqual(len(inv['cases']), 2)
        self.assertEqual(inv['mapped_cases'], 0)
        self.assertEqual(len(verification['nodes']), 0)
        self.assertEqual(inv['cases'][1]['result'], 'failed')
        self.assertNotIn('SECRET TRACE OMITTED', json.dumps(inv))

    def test_reviewed_mapping_creates_revision_bound_observation(self):
        inv, obj = collect_junit([self.xml], manifest_revision='feedf00d', intent=REQ, reviewed_mapping=self.mapping)
        self.assertEqual(inv['mapped_cases'], 1)
        node = obj['nodes'][0]
        self.assertEqual(node['criteria_ids'], ['AC.auth.valid'])
        self.assertEqual(node['result'], 'passed')
        self.assertEqual(node['revision'], 'feedf00d')
        implementation = {'schema_version': SCHEMA, 'nodes': [{
            'id':'impl.login','map':'implementation','title':'Login handler','implementation_state':'present'}]}
        links = {'links':[{'requirement_id':'REQ.auth.login','implementation_id':'impl.login','basis':'reviewed'}]}
        findings = compare(REQ, implementation, obj, links, {'confirmations':[]},
                           {'project': {'revision':'feedf00d'}})
        self.assertEqual(findings['counts'], {'complete':1})

    def test_no_unlinked_pass_becomes_complete(self):
        _, obj = collect_junit([self.xml], manifest_revision='feedf00d', intent=REQ, reviewed_mapping=self.mapping)
        findings = compare(REQ, {'schema_version':SCHEMA,'nodes':[]}, obj, {'links':[]}, {'confirmations':[]},
                           {'project':{'revision':'feedf00d'}})
        self.assertEqual(findings['counts'], {'unknown': 1})

    def test_failing_reviewed_test_reports_failure_without_raw_trace(self):
        mapping = {**self.mapping, 'tests': [{'key':'tests.Auth::test_wrong_password','requirement_id':'REQ.auth.login','criteria_ids':['AC.auth.valid']}]}
        _, obj = collect_junit([self.xml], manifest_revision='feedf00d', intent=REQ, reviewed_mapping=mapping)
        self.assertEqual(obj['nodes'][0]['result'], 'failed')
        self.assertNotIn('SECRET TRACE OMITTED', json.dumps(obj))

    def test_invalid_review_and_stale_revision_fail_closed(self):
        for bad in [{**self.mapping,'revision':'old'}, {**self.mapping,'reviewed':False},
                    {**self.mapping,'tests':[{'key':'not-found','requirement_id':'REQ.auth.login','criteria_ids':['AC.auth.valid']}]},
                    {**self.mapping,'tests':[{'key':'tests.Auth::test_login','requirement_id':'REQ.auth.login','criteria_ids':['AC.something.invented']}]}]:
            with self.subTest(bad=bad),self.assertRaises(AuditError):
                collect_junit([self.xml], manifest_revision='feedf00d', intent=REQ, reviewed_mapping=bad)

    def test_reject_dtd_and_broken_report(self):
        self.xml.write_text('<!DOCTYPE foo [<!ENTITY x "hello">]><testsuite><testcase name="&x;" /></testsuite>',encoding='utf-8')
        with self.assertRaisesRegex(AuditError,'DTD'):
            collect_junit([self.xml], manifest_revision=None, intent=REQ)
        self.xml.write_text('<testsuite><testcase',encoding='utf-8')
        with self.assertRaisesRegex(AuditError,'Malformed'):
            collect_junit([self.xml], manifest_revision=None, intent=REQ)

    def test_reject_duplicate_test_keys_across_files(self):
        second=self.root/'second.xml'
        second.write_text(REPORT,encoding='utf-8')
        with self.assertRaisesRegex(AuditError,'Ambiguous'):
            collect_junit([self.xml,second],manifest_revision='feedf00d',intent=REQ,reviewed_mapping=self.mapping)

    def test_integrated_audit_without_mapping_remains_unknown(self):
        repo=self.root/'repo';repo.mkdir()
        spec=repo/'spec.md';spec.write_text('- [REQ.auth.login] Login\n  - [AC.auth.valid] Valid login succeeds\n')
        out=self.root/'out'
        result=audit_project(repo,spec=spec,out=out,spec_approved=True,mode='deep',junit_sources=[self.xml])
        self.assertEqual(result['counts'],{'unknown':1})
        self.assertEqual(len(load(out/'junit-candidates.json')['cases']),2)
        self.assertFalse((out/'verification-map.json').exists())
        self.assertIn('atlas-data', (out/'dashboard.html').read_text())

    def test_integrated_audit_with_mapping_and_links(self):
        repo=self.root/'repo';repo.mkdir()
        spec=repo/'spec.md';spec.write_text('- [REQ.auth.login] Login\n  - [AC.auth.valid] Valid login succeeds\n')
        (repo/'auth.py').write_text('def login():\n    return True\n')
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.email=unit@test.local','-c','user.name=Fixture','commit','-qm','init'],check=True)
        rev=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        mapping={**self.mapping,'revision':rev};mp=self.root/'mapping.json';save(mp,mapping)
        # Use structural scan to locate stable implementation symbol ID without guessing.
        from projectmirror.core import index_repo
        impl,_=index_repo(repo,150)
        symbol=next(x for x in impl['nodes'] if x['kind']=='functiondef' and x['title']=='login')
        links=self.root/'links.json';save(links,{'links':[{'requirement_id':'REQ.auth.login','implementation_id':symbol['id'],'basis':'reviewed'}]})
        out=self.root/'audit'
        result=audit_project(repo,spec=spec,out=out,mode='deep',spec_approved=True,junit_sources=[self.xml],test_map=mp,links=links)
        self.assertEqual(result['counts'],{'complete':1})
        self.assertEqual(len(load(out/'verification-map.json')['nodes']),1)
        self.assertEqual(len(load(out/'junit-candidates.json')['cases']),2)
        self.assertIn('script-src', (out/'dashboard.html').read_text())


if __name__ == '__main__': unittest.main()
