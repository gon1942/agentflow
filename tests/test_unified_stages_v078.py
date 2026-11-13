"""v0.7.8 unified built-in stage/skill management and fail-closed task contract."""
import copy
import json
import unittest
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.core import ManagementError, configured_stages, branch_policy
from scaffold.agentflow_console.contexts import ContextRegistry

DEFAULTS=('lifecycle-dev','development-worker','project-architect','storyboard','task-planning')

class UnifiedStageManagementV078(unittest.TestCase):
    setUp=ThreeDefaultProfiles.setUp

    def test_all_five_have_same_editable_branch_contract(self):
        self.assertEqual({p['id'] for p in self.manager.list_profiles()}, set(DEFAULTS))
        for pid in DEFAULTS:
            with self.subTest(profile=pid):
                original=self.manager.profile(pid)
                updated=copy.deepcopy(original)
                updated['conditional_stages']=branch_policy(original)
                updated['conditional_stages']['BUG_FAIL']=not branch_policy(original)['BUG_FAIL']
                self.manager.save_profile(updated)
                self.assertEqual(self.manager.profile(pid)['conditional_stages'],updated['conditional_stages'])
                self.assertEqual(self.manager.runtime_contract(pid)['execution_scope']['conditional_stages'],updated['conditional_stages'])

    def test_all_five_can_edit_stages_with_same_schema(self):
        for pid in DEFAULTS:
            with self.subTest(profile=pid):
                current=self.manager.profile(pid)
                updated=copy.deepcopy(current)
                # Session is excluded; test addition/removal on a non-dependent stage.
                selected=set(configured_stages(updated))
                if pid=='development-worker': selected.add('ANALYZE')
                elif pid in ('lifecycle-dev','project-architect'): selected.discard('COMPLETE')
                else: selected.add('GATE1')
                updated['enabled_stages']=[s for s in ('ANALYZE','PLAN','GATE1','IMPLEMENT','VERIFY','REVIEW','GATE2','COMPLETE') if s in selected]
                updated['approval_gates']={g:g in selected for g in ('GATE1','GATE2')}
                self.manager.save_profile(updated)
                self.assertEqual(self.manager.runtime_contract(pid)['execution_scope']['user_selected_stages'],updated['enabled_stages'])

    def test_all_five_can_edit_skills_without_changing_agents(self):
        for pid in DEFAULTS:
            with self.subTest(profile=pid):
                tree=self.manager.tree(pid)
                stage=next(s for s in tree['stages'] if s['id']=='VERIFY')
                self.assertTrue(stage['skills'])
                old=stage['skills'][0]['required']
                stage['skills'][0]['required']=not old
                stage['skills'][0]['condition']='always' if not old else 'optional'
                self.manager.save_tree(tree)
                self.assertEqual(next(s for s in self.manager.tree(pid)['stages'] if s['id']=='VERIFY')['skills'][0]['required'],not old)

    def test_gate_independence_and_metadata_cannot_be_bypassed(self):
        p=self.manager.profile('project-architect')
        p['enabled_stages'].remove('GATE1');p['approval_gates']['GATE1']=False
        self.manager.save_profile(p)
        self.assertIn('IMPLEMENT_APPROVED_PLAN_REQUIRED',[w['code'] for w in self.manager.runtime_contract('project-architect')['execution_scope']['execution_prerequisite_warnings']])
        p=self.manager.profile('lifecycle-dev');p['skill_tree']='storyboard'
        with self.assertRaises(ManagementError):self.manager.save_profile(p)
        p=self.manager.profile('development-worker');p['name']='changed'
        with self.assertRaisesRegex(ManagementError,'METADATA_IMMUTABLE'):
            self.manager.save_profile(p)
        t=self.manager.tree('project-architect');next(s for s in t['stages'] if s['id']=='VERIFY')['agent']='implementer'
        with self.assertRaisesRegex(ManagementError,'PROTECTED_INDEPENDENCE'):
            self.manager.save_tree(t)

    def test_active_task_blocks_changes_and_rotation_preserves_contract(self):
        registry=ContextRegistry(self.manager)
        task=self.root/'docs/tasks/active/UNIFIED-001'; task.mkdir(parents=True)
        (task/'task-state.json').write_text(json.dumps({'task_id':'UNIFIED-001','state':'PLAN_DRAFT'}))
        original=registry.pin_task('UNIFIED-001',profile='project-architect')
        p=self.manager.profile('project-architect')
        p['conditional_stages']['BUG_FAIL']=False
        with self.assertRaisesRegex(ManagementError,'TASK_ACTIVE'):
            self.manager.save_profile(p)
        t=self.manager.tree('project-architect')
        with self.assertRaisesRegex(ManagementError,'TASK_ACTIVE'):
            self.manager.save_tree(t)
        self.assertEqual(original['contract_sha256'], registry.task_contract('UNIFIED-001')['contract_sha256'])

    def test_legacy_development_not_exposed_or_mutable(self):
        self.assertNotIn('development',[p['id'] for p in self.manager.list_profiles()])
        p=self.manager.profile('development')
        p['name']='changed'
        with self.assertRaises(ManagementError): self.manager.save_profile(p)

if __name__=='__main__': unittest.main()
