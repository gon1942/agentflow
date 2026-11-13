"""User-owned independent stage selection and human-owned approval checkpoints."""
import unittest
from pathlib import Path
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.core import USER_STAGES

class StageChoiceV080(unittest.TestCase):
    setUp=ThreeDefaultProfiles.setUp

    def test_every_stage_individually_selectable_for_every_visible_profile(self):
        for pid in ('lifecycle-dev','development-worker','project-architect','storyboard','task-planning'):
            for stage in USER_STAGES:
                with self.subTest(profile=pid,stage=stage):
                    p=self.manager.profile(pid)
                    p['enabled_stages']=[stage]
                    p['approval_gates']={'GATE1':stage=='GATE1','GATE2':stage=='GATE2'}
                    self.manager.save_profile(p)
                    self.assertEqual(self.manager.profile(pid)['enabled_stages'],[stage])
                    self.assertEqual(self.manager.runtime_contract(pid)['execution_scope']['user_selected_stages'],[stage])

    def test_all_stages_can_be_disabled_without_implicit_activation(self):
        p=self.manager.profile('development-worker')
        p['enabled_stages']=[]
        p['approval_gates']={'GATE1':False,'GATE2':False}
        self.manager.save_profile(p)
        self.assertEqual(self.manager.runtime_contract('development-worker')['execution_scope']['enabled_stages'],['SESSION'])

    def test_no_automatic_dependency_changes_and_detailed_warning(self):
        p=self.manager.profile('task-planning')
        p['enabled_stages']=['VERIFY']
        p['approval_gates']={'GATE1':False,'GATE2':False}
        self.manager.save_profile(p)
        contract=self.manager.runtime_contract('task-planning')
        self.assertEqual(contract['execution_scope']['user_selected_stages'],['VERIFY'])
        warning=next(w for w in contract['execution_scope']['execution_prerequisite_warnings'] if w['code']=='VERIFY_REQUIRES_ARTIFACT_STAGE')
        self.assertIn('artifact',warning['detail'])

    def test_one_canonical_opencode_manager_command(self):
        commands=Path(__file__).resolve().parents[1]/'scaffold/.opencode/commands'
        names=sorted(p.name for p in commands.glob('*mngr*'))
        self.assertEqual(names,['agentflow-mngr.md'])
        self.assertFalse((commands/'agentflow-magr.md').exists())

if __name__=='__main__':unittest.main()
