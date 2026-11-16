"""Deterministic Relay behavior, privacy, fidelity, hook adapters, and safety."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror.core import AuditError
from projectmirror import relay
from projectmirror.mcp import dispatch


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'project'
        self.repo.mkdir()
        self.db = self.root / 'relay-private'
        self.env = patch.dict(os.environ, {'MIRRORMAP_RELAY_HOME': str(self.db)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self._git('init')
        self._git('config', 'user.name', 'Test')
        self._git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'code.py').write_text('pass\n')
        self._git('add', '.')
        self._git('commit', '-m', 'initial')

    def _git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def start(self, agent='claude', native='host-abc'):
        return relay.ingest_hook(agent, {'claude':'SessionStart', 'codex':'SessionStart',
                                        'cursor':'sessionStart'}[agent],
                                 {'session_id': native, 'cwd': str(self.repo)}, self.repo)['session_id']

    def test_automatic_hook_creates_session_without_invoking_skill(self):
        sid = self.start()
        sessions = relay.list_sessions(self.repo)
        self.assertEqual(sessions[0]['id'], sid)
        self.assertEqual(sessions[0]['status'], 'active')
        self.assertTrue(relay.verify(sid)['workspace_matches_checkpoint'])
        self.assertEqual(relay.verify(sid)['journal_integrity'], 'valid')

    def test_agent_handoff_includes_user_recorded_goal_and_cursor(self):
        sid = self.start()
        relay.record_note(sid, title='Music Player', goal='Build player', next_step='Write logout tests',
                          done=['Created login view'], decision=['Keep local-only storage'])
        package = relay.resume(sid)
        self.assertEqual(package['next_step'], 'Write logout tests')
        self.assertEqual(package['completed'], ['Created login view'])
        self.assertTrue(package['ready_for_review'])
        self.assertFalse(package['execution_authorized'])
        self.assertTrue(any('permissions' in x for x in package['resume_instructions']))

    def test_cross_agent_adoption_transfers_selected_task_not_permissions(self):
        prior = self.start('claude', 'old-agent')
        relay.record_note(prior, title='MirrorMap UI', goal='Polish the dashboard',
                          done=['Built sidebar'], next_step='Finish responsive layout')
        newer = self.start('codex', 'new-agent')
        with self.assertRaises(AuditError):
            relay.adopt_session(prior, newer)
        result = relay.adopt_session(prior, newer, source_stopped=True)
        self.assertFalse(result['execution_authorized'])
        new_session = relay.inspect(newer)
        self.assertEqual(new_session['parent_session'], prior)
        self.assertEqual(new_session['next_step'], 'Finish responsive layout')
        self.assertEqual(new_session['completed'], ['Built sidebar'])
        self.assertEqual(relay.verify(prior)['journal_integrity'], 'valid')
        self.assertEqual(relay.verify(newer)['journal_integrity'], 'valid')
        self.assertTrue(relay.resume(newer)['ready_for_review'])
        ignored = relay.ingest_hook('claude', 'PostToolUse',
                    {'session_id':'old-agent', 'cwd':str(self.repo)},self.repo)
        self.assertFalse(ignored['recorded'])
        with self.assertRaises(AuditError):
            relay.adopt_session(prior, newer, source_stopped=True)

    def test_parallel_hooks_keep_a_valid_single_event_chain(self):
        from concurrent.futures import ThreadPoolExecutor
        sid = self.start('codex', 'parallel')
        def one(i):
            return relay.ingest_hook('codex', 'PostToolUse',
                      {'session_id':'parallel', 'cwd':str(self.repo),
                       'tool_use_id':f'T{i}', 'tool_name':'Bash'}, self.repo)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(one, range(24)))
        self.assertTrue(all(x['recorded'] for x in results))
        self.assertEqual(relay.verify(sid)['journal_integrity'], 'valid')
        db = sqlite3.connect(str(self.db/'sessions.sqlite3'))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM events WHERE session_id=?',(sid,)).fetchone()[0],26)
        db.close()

    def test_adoption_refuses_drift_or_pending_unsafe_tools(self):
        a=self.start('claude','a')
        b=self.start('codex','b')
        relay.ingest_hook('claude','PreToolUse',{'session_id':'a','cwd':str(self.repo),
                             'tool_use_id':'uncertain','tool_name':'Bash'},self.repo)
        with self.assertRaises(AuditError):
            relay.adopt_session(a,b,source_stopped=True)
        (self.repo/'code.py').write_text('changed')
        with self.assertRaises(AuditError):
            relay.adopt_session(a,b,source_stopped=True)

    def test_auto_tracking_never_writes_store_into_target_project(self):
        with patch.dict(os.environ, {'MIRRORMAP_RELAY_HOME':str(self.repo/'unsafe-relay')}):
            with self.assertRaises(AuditError):
                relay.ingest_hook('claude','SessionStart',
                                  {'session_id':'test','cwd':str(self.repo)},self.repo)
        self.assertFalse((self.repo/'unsafe-relay').exists())

    def test_note_redacts_credential_assignments(self):
        sid = self.start()
        relay.record_note(sid, goal='token = abc123 private_key: deadbeef')
        item = relay.inspect(sid)
        self.assertNotIn('abc123', json.dumps(item))
        self.assertNotIn('deadbeef', json.dumps(item))
        self.assertIn('[REDACTED]', item['goal'])

    def test_no_raw_prompt_or_tool_data_is_stored(self):
        sid = self.start('codex')
        relay.ingest_hook('codex', 'PostToolUse', {'session_id':'host-abc', 'cwd':str(self.repo),
                          'tool_name':'Bash', 'tool_input':{'command':'echo secret'}} , self.repo)
        data = (self.db / 'sessions.sqlite3').read_bytes()
        self.assertNotIn(b'echo secret', data)
        self.assertTrue(relay.verify(sid)['workspace_matches_checkpoint'])

    def test_tool_tracking_marks_unfinished_as_uncertain(self):
        sid = self.start()
        relay.ingest_hook('claude','PreToolUse',{'session_id':'host-abc','cwd':str(self.repo),
                          'tool_use_id':'T1','tool_name':'Bash'},self.repo)
        self.assertEqual(len(relay.verify(sid)['pending_tools']),1)
        self.assertFalse(relay.resume(sid)['ready_for_review'])
        relay.ingest_hook('claude','PostToolUse',{'session_id':'host-abc','cwd':str(self.repo),
                          'tool_use_id':'T1','tool_name':'Bash'},self.repo)
        self.assertEqual(relay.verify(sid)['pending_tools'],[])
        relay.record_note(sid, next_step="Run the remaining tests")
        self.assertTrue(relay.resume(sid)['ready_for_review'])

    def test_changes_after_checkpoint_are_detected(self):
        sid = self.start()
        (self.repo / 'code.py').write_text('raise RuntimeError("changed")\n')
        self.assertFalse(relay.verify(sid)['workspace_matches_checkpoint'])
        self.assertFalse(relay.resume(sid)['ready_for_review'])
        relay.checkpoint(sid)
        self.assertTrue(relay.verify(sid)['workspace_matches_checkpoint'])

    def test_tampering_event_or_session_detected(self):
        sid = self.start()
        con = sqlite3.connect(str(self.db / 'sessions.sqlite3'))
        con.execute('UPDATE events SET detail=? WHERE session_id=?', ('{}',sid))
        con.commit();con.close()
        self.assertEqual(relay.verify(sid)['journal_integrity'],'invalid')
        # Also detect silent modification of materialized state.
        sid2 = self.start('codex')
        con = sqlite3.connect(str(self.db / 'sessions.sqlite3'))
        con.execute('UPDATE sessions SET goal=? WHERE id=?',('forged',sid2))
        con.commit();con.close()
        self.assertEqual(relay.verify(sid2)['journal_integrity'],'invalid')

    def test_missing_identity_not_attached_to_wrong_session(self):
        self.start()
        result=relay.ingest_hook('claude','PreCompact',{'cwd':str(self.repo)},self.repo)
        self.assertFalse(result['recorded'])
        self.assertEqual(len(relay.list_sessions()),1)

    def test_cursor_lifecycle_uses_session_start_env_id(self):
        sid=self.start('cursor', 'cursor-one')
        with patch.dict(os.environ,{'MIRRORMAP_RELAY_NATIVE_SESSION_ID':'cursor-one'}):
            res=relay.ingest_hook('cursor','preCompact',{'cwd':str(self.repo),'trigger':'auto'}, self.repo)
        self.assertEqual(res['session_id'],sid)
        self.assertTrue(relay.verify(sid)['workspace_matches_checkpoint'])

    def test_hook_denies_unapproved_other_workspace(self):
        self.start()
        other=self.root/'other';other.mkdir()
        result=relay.ingest_hook('claude','SessionStart',{'session_id':'stranger','cwd':str(other)},self.repo)
        self.assertFalse(result['recorded'])
        self.assertEqual(len(relay.list_sessions()),1)

    def test_sensitive_file_name_not_persisted(self):
        (self.repo / '.env').write_text('TOKEN=secret')
        sid=self.start()
        item=relay.inspect(sid)
        self.assertNotIn('.env',json.dumps(item['snapshot']))
        self.assertNotIn('secret',json.dumps(item['snapshot']))

    def test_install_hook_preview_preserves_unrelated_settings(self):
        cfg=self.root/'settings.json'
        cfg.write_text(json.dumps({'theme':'dark','hooks':{'SessionStart':[{'hooks':[{'type':'command','command':'other'}]}]}}))
        result=relay.modify_hooks('claude',self.repo,config_path=cfg)
        self.assertFalse(result['applied'])
        self.assertIn('other',cfg.read_text())
        self.assertEqual(len(result['configuration']['hooks']['SessionStart']),2)
        self.assertIn('-I',result['commands'][0])
        result=relay.modify_hooks('claude',self.repo,apply=True,config_path=cfg)
        self.assertTrue(result['applied'])
        relay.modify_hooks('claude',self.repo,apply=True,config_path=cfg)
        data=json.loads(cfg.read_text())
        self.assertEqual(len(data['hooks']['SessionStart']),2)
        relay.modify_hooks('claude',self.repo,remove=True,apply=True,config_path=cfg)
        self.assertEqual(json.loads(cfg.read_text())['hooks']['SessionStart'],[{'hooks':[{'type':'command','command':'other'}]}])

    def test_hook_install_cursor_and_codex_shapes(self):
        for agent in ('cursor','codex'):
            path=self.root/(agent+'.json')
            x=relay.modify_hooks(agent,self.repo,config_path=path)
            hooks=x['configuration']['hooks']
            self.assertIn('sessionStart' if agent=='cursor' else 'SessionStart',hooks)
            self.assertIn('command',hooks['sessionStart'][0] if agent=='cursor' else hooks['SessionStart'][0]['hooks'][0])

    def test_symlinked_agent_config_rejected(self):
        base=self.root/'regular.json';base.write_text('{}')
        alias=self.root/'alias.json';alias.symlink_to(base)
        with self.assertRaises(AuditError):
            relay.modify_hooks('codex',self.repo,config_path=alias)

    def test_mcp_filters_other_projects_and_requires_allowlist(self):
        sid=self.start()
        with patch.dict(os.environ,{'MIRRORMAP_ALLOWED_ROOTS':str(self.repo)}):
            req=lambda name,args:dispatch({'jsonrpc':'2.0','id':1,'method':'tools/call',
                                            'params':{'name':name,'arguments':args}})
            result=req('mirrormap_relay_sessions',{})
            self.assertIn(sid,result['result']['content'][0]['text'])
            result=req('mirrormap_relay_resume',{'session_id':sid})
            self.assertIn('read_only_context',result['result']['content'][0]['text'])
        with patch.dict(os.environ,{'MIRRORMAP_ALLOWED_ROOTS':str(self.root/'other')}):
            result=req('mirrormap_relay_resume',{'session_id':sid})
            self.assertTrue(result['result'].get('isError'))
            self.assertNotIn('Build player',result['result']['content'][0]['text'])

    def test_cli_entrypoints_and_hook_output(self):
        from projectmirror.experience import main as experience_main
        from projectmirror.__main__ import cmd_main
        self.assertEqual(experience_main(['relay','sessions']),0)
        self.assertEqual(cmd_main(['relay','sessions']),0)
        payload=json.dumps({'session_id':'hook-test','cwd':str(self.repo)})
        result=subprocess.run([sys.executable,'-m','projectmirror','relay','hook','--agent','cursor',
                               '--event','sessionStart','--project',str(self.repo)],
                              input=payload,text=True,capture_output=True,cwd=str(Path(__file__).resolve().parents[1]),
                              env={**os.environ,'MIRRORMAP_RELAY_HOME':str(self.db)})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('MIRRORMAP_RELAY_NATIVE_SESSION_ID',result.stdout)


if __name__=='__main__':
    unittest.main()
