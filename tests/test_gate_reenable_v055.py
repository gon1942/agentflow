"""Gate may be reenabled after PLAN scope without enabling code implementation."""
import unittest
from pathlib import Path
from test_default_three_profiles import ThreeDefaultProfiles

class GateReenable(unittest.TestCase):
    def setUp(self):
        ThreeDefaultProfiles.setUp(self)
        for id in ('task-planning','storyboard'):
            profile=self.manager.profile(id)
            profile.pop('enabled_stages',None)
            profile.pop('conditional_stages',None)
            self.manager.save_profile(profile)

    def test_gate1_can_be_terminal_without_implementation(self):
        p=self.manager.profile('task-planning')
        p['stop_after_stage']='PLAN'
        p['approval_gates']['GATE1']=False
        self.manager.save_profile(p)
        p['stop_after_stage']='GATE1'
        p['approval_gates']['GATE1']=True
        self.manager.save_profile(p)
        self.manager.activate('task-planning',1)
        c=self.manager.runtime_contract()
        self.assertEqual(c['execution_scope']['enabled_stages'],['SESSION','ANALYZE','PLAN','GATE1'])
        self.assertEqual(c['protected_workflow']['human_gates'],['GATE1'])
        self.assertNotIn('IMPLEMENT',c['execution_scope']['enabled_stages'])
        self.assertEqual(c['execution_scope']['terminal_status'],'STOPPED_AFTER_GATE1')
        self.assertFalse(c['execution_scope']['full_completion_allowed'])
        self.assertFalse(c['execution_scope']['archive_to_completed_allowed'])

    def test_gate2_as_terminal_still_not_complete(self):
        p=self.manager.profile('storyboard')
        p['stop_after_stage']='GATE2'
        self.manager.save_profile(p)
        self.manager.activate('storyboard',1)
        c=self.manager.runtime_contract()
        self.assertIn('GATE2',c['execution_scope']['enabled_stages'])
        self.assertNotIn('COMPLETE',c['execution_scope']['enabled_stages'])
        self.assertEqual(c['execution_scope']['terminal_status'],'STOPPED_AFTER_GATE2')

    def test_development_stays_locked(self):
        p=self.manager.profile('development')
        p['stop_after_stage']='GATE1'
        with self.assertRaisesRegex(Exception,'PROTECTED_STAGE_REQUIRED'):
            self.manager.save_profile(p)

    def test_frontend_allows_gate_outside_scope_and_auto_expands(self):
        ui=(Path(__file__).resolve().parents[1]/'scaffold/agentflow_console/ui.html').read_text()
        self.assertIn('cb.disabled=locked||busy;',ui)
        self.assertIn('updated.enabled_stages=stageTerminals.filter(x=>set.has(x));',ui)
        self.assertIn('updated.approval_gates={GATE1:set.has(',ui)
        self.assertIn("const stageTerminals=['ANALYZE','PLAN','GATE1','IMPLEMENT','VERIFY','REVIEW','GATE2','COMPLETE']",ui)
