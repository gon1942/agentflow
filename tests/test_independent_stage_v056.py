"""Independent selected stages, not a native agent simulation."""
import unittest
from pathlib import Path
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.core import ManagementError

class IndependentStageV056(unittest.TestCase):
    setUp=ThreeDefaultProfiles.setUp

    def test_default_task_plan_generate_verify_finalize_only(self):
        p=self.manager.profile('task-planning')
        self.assertEqual(p['enabled_stages'],['ANALYZE','PLAN','VERIFY','COMPLETE'])
        self.manager.activate('task-planning',1)
        c=self.manager.runtime_contract();scope=c['execution_scope']
        self.assertEqual(scope['user_selected_stages'],['ANALYZE','PLAN','VERIFY','COMPLETE'])
        self.assertNotIn('IMPLEMENT',scope['enabled_stages'])
        self.assertNotIn('REVIEW',scope['enabled_stages'])
        self.assertNotIn('REVIEW_FIX',scope['enabled_stages'])
        self.assertNotIn('BUG_FAIL',scope['enabled_stages'])
        self.assertFalse(scope['archive_to_completed_allowed'])
        self.assertTrue(scope['plan_ready_allowed_after_evidence'])
        self.assertEqual(scope['completion_subject'],'PLANNING_DELIVERABLE_PLAN_READY')

    def test_plan_only_and_no_branches(self):
        p=self.manager.profile('task-planning');p['enabled_stages']=['ANALYZE','PLAN'];p['conditional_stages']={'BUG_FAIL':False,'REVIEW_FIX':False};self.manager.save_profile(p)
        self.manager.activate('task-planning',1)
        c=self.manager.runtime_contract()
        self.assertEqual(c['execution_scope']['enabled_stages'],['SESSION','ANALYZE','PLAN'])
        self.assertFalse(c['execution_scope']['archive_to_completed_allowed'])
        self.assertNotIn('GATE1',c['protected_workflow']['human_gates'])

    def test_review_branch_is_unreachable_without_review(self):
        p=self.manager.profile('task-planning');p['conditional_stages']['REVIEW_FIX']=True;self.manager.save_profile(p)
        self.manager.activate('task-planning',1)
        self.assertNotIn('REVIEW_FIX',self.manager.runtime_contract()['execution_scope']['enabled_stages'])

    def test_review_with_verifier_branches(self):
        p=self.manager.profile('task-planning');p['enabled_stages']=['ANALYZE','PLAN','VERIFY','REVIEW','COMPLETE'];p['conditional_stages']['REVIEW_FIX']=True;self.manager.save_profile(p)
        self.manager.activate('task-planning',1)
        self.assertIn('REVIEW_FIX',self.manager.runtime_contract()['execution_scope']['enabled_stages'])

    def test_dependency_and_rejection(self):
        p=self.manager.profile('task-planning');p['enabled_stages']=['ANALYZE','GATE1'];p['approval_gates']['GATE1']=True
        self.manager.save_profile(p)
        self.assertIn('GATE1_NO_PLAN_IN_PROFILE',[w['code'] for w in self.manager.runtime_contract('task-planning')['execution_scope']['execution_prerequisite_warnings']])
        p=self.manager.profile('task-planning');p['enabled_stages']=['ANALYZE','PLAN','GATE1'];p['approval_gates']['GATE1']=False
        with self.assertRaisesRegex(ManagementError,'GATE_STAGE_POLICY_MISMATCH'):self.manager.save_profile(p)
        p=self.manager.profile('development');p['enabled_stages']=['ANALYZE','PLAN'];p['approval_gates']={'GATE1':False,'GATE2':False}
        with self.assertRaisesRegex(ManagementError,'LEGACY_PROFILE_IMMUTABLE'):self.manager.save_profile(p)

    def test_missing_required_skill_in_inactive_stage_ignored(self):
        t=self.manager.tree('task-planning');next(x for x in t['stages'] if x['id']=='IMPLEMENT')['skills']=[{'name':'uninstalled-test','required':True,'condition':'always'}];self.manager.save_tree(t)
        self.manager.activate('task-planning',1)
        self.assertEqual(self.manager.runtime_contract()['execution_scope']['user_selected_stages'],['ANALYZE','PLAN','VERIFY','COMPLETE'])
        p=self.manager.profile('task-planning');p['enabled_stages']=['ANALYZE','PLAN','IMPLEMENT','VERIFY','COMPLETE'];self.manager.save_profile(p)
        with self.assertRaisesRegex(ManagementError,'SKILLS_MISSING'):self.manager.runtime_contract()

    def test_change_blocked_with_active_task(self):
        (self.root/'docs/tasks/active/TEST-01').mkdir()
        p=self.manager.profile('task-planning');p['enabled_stages']=['ANALYZE','PLAN']
        with self.assertRaisesRegex(ManagementError,'TASK_ACTIVE'):self.manager.save_profile(p)

    def test_session_hidden_and_skills_visible_in_ui(self):
        ui=(Path(__file__).resolve().parents[1]/'scaffold/agentflow_console/ui.html').read_text()
        for needle in ('if(st.id===\'SESSION\')continue','selectedStages(p)','branchesFor(p)','studio-stage-row','studio-flow-summary','const stageTerminals='):
            self.assertIn(needle,ui)

if __name__=='__main__':unittest.main()
