"""Profile-scoped contiguous stage execution. Tests never claim native agent execution."""
import copy
import json
import unittest
from pathlib import Path
from test_default_three_profiles import ThreeDefaultProfiles
from test_console_rc3 import RC3HTTPTests
from test_skill_studio import ConsoleTests
from scaffold.agentflow_console.server import make_handler
import threading
from http.server import ThreadingHTTPServer
from scaffold.agentflow_console.core import ManagementError

class StageScopePolicy(unittest.TestCase):
    def setUp(self):
        ThreeDefaultProfiles.setUp(self)
        for id in ('task-planning','storyboard'):
            profile=self.manager.profile(id)
            profile.pop('enabled_stages',None)
            profile.pop('conditional_stages',None)
            self.manager.save_profile(profile)
    def test_plan_only_contract(self):
        p=self.manager.profile('task-planning');p['stop_after_stage']='PLAN'
        self.manager.save_profile(p)
        self.manager.activate('task-planning',1)
        c=self.manager.runtime_contract()
        self.assertEqual(c['execution_scope']['enabled_stages'],['SESSION','ANALYZE','PLAN'])
        self.assertEqual(c['execution_scope']['inactive_stages'][0],'GATE1')
        self.assertEqual(c['execution_scope']['terminal_status'],'STOPPED_AFTER_PLAN')
        self.assertFalse(c['execution_scope']['full_completion_allowed'])
        self.assertFalse(c['execution_scope']['archive_to_completed_allowed'])
        self.assertEqual(c['protected_workflow']['not_reached_gates'],['GATE1','GATE2'])
        self.assertEqual(c['protected_workflow']['skipped_gates'],[])
        self.assertEqual(c['protected_workflow']['independent_roles'],[])
        self.assertFalse(next(s for s in c['tree']['stages'] if s['id']=='VERIFY')['enabled'])
        self.assertEqual([x['id'] for x in self.manager.tree('task-planning')['stages']], c['protected_workflow']['stages'])

    def test_all_supported_terminals_and_legacy(self):
        self.manager.activate('storyboard',1)
        expected={'ANALYZE':['SESSION','ANALYZE'],'PLAN':['SESSION','ANALYZE','PLAN'],
                  'IMPLEMENT':['SESSION','ANALYZE','PLAN','GATE1','IMPLEMENT'],
                  'VERIFY':['SESSION','ANALYZE','PLAN','GATE1','IMPLEMENT','BUG_FAIL','VERIFY'],
                  'REVIEW':['SESSION','ANALYZE','PLAN','GATE1','IMPLEMENT','BUG_FAIL','VERIFY','REVIEW'],
                  'COMPLETE':list(self.manager.runtime_contract()['protected_workflow']['stages'])}
        for stop,stages in expected.items():
            p=self.manager.profile('storyboard');p['stop_after_stage']=stop;self.manager.save_profile(p)
            c=self.manager.runtime_contract()
            self.assertEqual(c['execution_scope']['enabled_stages'],stages)
        p=self.manager.profile('storyboard');p.pop('stop_after_stage');self.manager.save_profile(p)
        self.assertTrue(self.manager.runtime_contract()['execution_scope']['full_completion_allowed'])

    def test_development_protected_and_invalid_terminal(self):
        p=self.manager.profile('development');p['stop_after_stage']='PLAN'
        with self.assertRaisesRegex(ManagementError,'PROTECTED_STAGE_REQUIRED'):self.manager.save_profile(p)
        p=self.manager.profile('task-planning');p['stop_after_stage']='SESSION'
        with self.assertRaisesRegex(ManagementError,'STOP_AFTER_STAGE_INVALID'):self.manager.save_profile(p)
        p['stop_after_stage']='FOO'
        with self.assertRaisesRegex(ManagementError,'STOP_AFTER_STAGE_INVALID'):self.manager.save_profile(p)

    def test_active_task_prevents_scope_change(self):
        (self.root/'docs/tasks/active/TASK-001').mkdir()
        p=self.manager.profile('task-planning');p['stop_after_stage']='PLAN'
        with self.assertRaisesRegex(ManagementError,'TASK_ACTIVE'):self.manager.save_profile(p)
        self.assertNotIn('stop_after_stage',self.manager.profile('development'))

    def test_clone_inherits_execution_scope(self):
        p=self.manager.profile('task-planning');p['stop_after_stage']='PLAN';self.manager.save_profile(p)
        clone=self.manager.clone_profile('task-planning','myplan','My Plan')
        self.assertEqual(clone['stop_after_stage'],'PLAN')

    def test_handoff_draft_is_not_an_active_task(self):
        handoff=self.root/'docs/tasks/handoffs/PLAN-001'
        handoff.mkdir(parents=True)
        (handoff/'progress.md').write_text('상태: STOPPED_AFTER_PLAN')
        self.assertEqual(self.manager.handoff_drafts(),['PLAN-001'])
        self.assertEqual(self.manager.active_tasks(),[])
        self.manager.activate('task-planning',1)
        self.assertEqual(self.manager.status()['handoff_drafts'],['PLAN-001'])
        # An active, not-yet-handed-off task still blocks config mutations.
        (self.root/'docs/tasks/active/PLAN-002').mkdir()
        with self.assertRaisesRegex(ManagementError,'ACTIVE_TASK_CONTEXT_NOT_PINNED'):
            self.manager.activate('development',2)

    def test_short_scope_missing_inactive_skill_does_not_block(self):
        tree=self.manager.tree('task-planning')
        next(x for x in tree['stages'] if x['id']=='VERIFY')['skills']=[{'name':'uninstalled-test','required':True,'condition':'always'}]
        self.manager.save_tree(tree)
        p=self.manager.profile('task-planning');p['stop_after_stage']='PLAN';self.manager.save_profile(p)
        self.manager.activate('task-planning',1)
        self.assertEqual(self.manager.runtime_contract()['execution_scope']['stop_after_stage'],'PLAN')
        p['stop_after_stage']='COMPLETE';self.manager.save_profile(p)
        with self.assertRaisesRegex(ManagementError,'SKILLS_MISSING'):self.manager.runtime_contract()

class StageScopeHTTP(unittest.TestCase):
    def setUp(self):
        ConsoleTests.setUp(self)
        self.srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'test-token'))
        self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.srv.server_close);self.addCleanup(self.srv.shutdown)
        self.base=f'http://127.0.0.1:{self.srv.server_port}'
    post = RC3HTTPTests.post
    def test_save_profile_and_contract_over_http(self):
        p=self.manager.profile('task-planning');p['stop_after_stage']='PLAN'
        status,data=self.post('/api/profile/save',p)
        self.assertEqual(status,200)
        status,data=self.post('/api/profile/activate',{'profile':'task-planning','generation':1})
        self.assertEqual(status,200)
        contract=self.manager.runtime_contract()['execution_scope']
        # v0.5.6+: an independent-stage profile ignores legacy stop_after_stage.
        self.assertEqual(contract['mode'],'INDEPENDENT_STAGES')
        self.assertIsNone(contract['stop_after_stage'])
        self.assertIn('VERIFY',contract['enabled_stages'])

    def test_http_reject_protected_development_and_malformed_scope(self):
        p=self.manager.profile('development');p['stop_after_stage']='PLAN'
        status,data=self.post('/api/profile/save',p)
        self.assertEqual(status,409)
        self.assertEqual(data['error'],'PROTECTED_STAGE_REQUIRED')

class StageScopeUI(unittest.TestCase):
    def setUp(self):
        ThreeDefaultProfiles.setUp(self)
        for id in ('task-planning','storyboard'):
            profile=self.manager.profile(id)
            profile.pop('enabled_stages',None)
            profile.pop('conditional_stages',None)
            self.manager.save_profile(profile)
    def test_ui_guidance_and_mandatory_session(self):
        data=(Path(__file__).resolve().parents[1]/'scaffold/agentflow_console/ui.html').read_text()
        for phrase in ('setStageScope(', 'selectedStages(p)', '단계 사용', 'stageInScope(', 'SESSION', '미사용'):
            self.assertIn(phrase,data)
        doc=(Path(__file__).resolve().parents[1]/'scaffold/docs/workflow/WORKFLOW.md').read_text()
        self.assertIn('STOPPED_AFTER_PLAN',doc)
        self.assertIn('NOT_REACHED_BY_STAGE_SCOPE',doc)
