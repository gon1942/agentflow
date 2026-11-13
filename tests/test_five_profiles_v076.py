"""Five-profile integration: immutable legacy contracts, new stage limits and plan handoff."""
import hashlib,json, unittest
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.core import ManagementError
from scaffold.agentflow_console.contexts import ContextRegistry

class FiveProfilesV076(unittest.TestCase):
    setUp=ThreeDefaultProfiles.setUp
    def test_five_and_legacy_unchanged(self):
        self.assertEqual(len(self.manager.list_profiles()),5)
        p=self.manager.profile('development')
        self.assertIn('Full Lifecycle',p['name'])
        self.assertEqual(p['id'],'development')
        self.assertTrue(self.manager.runtime_contract('development')['approval_gates']['GATE1'])
        self.assertTrue(self.manager.runtime_contract('development')['approval_gates']['GATE2'])
    def test_architect_and_worker_stage_contracts(self):
        architect=self.manager.runtime_contract('project-architect')
        self.assertEqual(architect['profile']['stage_labels']['IMPLEMENT'],'DESIGN')
        self.assertEqual(architect['approval_gates'],{'GATE1':True,'GATE2':True})
        self.assertIn('VERIFY',architect['execution_scope']['user_selected_stages'])
        worker=self.manager.runtime_contract('development-worker')
        self.assertEqual(worker['execution_scope']['user_selected_stages'],['IMPLEMENT','VERIFY','REVIEW'])
        self.assertEqual(worker['approval_gates'],{'GATE1':False,'GATE2':False})
        self.assertFalse(worker['execution_scope']['archive_to_completed_allowed'])
        self.assertEqual(worker['execution_scope']['terminal_status'],'STOPPED_AFTER_SELECTED_STAGES')
        self.assertEqual(worker['protected_workflow']['independent_roles'],['verifier','reviewer'])
    def test_worker_stage_edit_and_architect_gate_dependency(self):
        edit=self.manager.profile('development-worker'); edit['enabled_stages'].append('COMPLETE')
        self.manager.save_profile(edit)
        self.assertIn('COMPLETE',self.manager.profile('development-worker')['enabled_stages'])
        self.assertFalse(self.manager.runtime_contract('development-worker')['execution_scope']['archive_to_completed_allowed'])
        bad=self.manager.profile('project-architect');bad['approval_gates']['GATE1']=False
        with self.assertRaises(ManagementError): self.manager.save_profile(bad)
    def test_rotation_keeps_profile_contract(self):
        reg=ContextRegistry(self.manager)
        reg.bind_session('worker-a','opencode','project-architect')
        task=self.root/'docs/tasks/active/ARCH-001'; task.mkdir()
        (task/'task-state.json').write_text(json.dumps({'task_id':'ARCH-001','state':'PLAN_DRAFT'}))
        a=reg.pin_task('ARCH-001','worker-a')
        reg.bind_session('worker-a','opencode','development-worker',1)
        b=reg.task_contract('ARCH-001')
        self.assertEqual(b['profile'],'project-architect')
        self.assertEqual(b['contract_sha256'],a['contract_sha256'])
    def test_worker_cannot_pin_unapproved_draft(self):
        reg=ContextRegistry(self.manager)
        task=self.root/'docs/tasks/active/TEST-001';task.mkdir()
        (task/'task-state.json').write_text(json.dumps({'task_id':'TEST-001','state':'PLAN_DRAFT'}))
        with self.assertRaisesRegex(ManagementError,'WORKER_REQUIRES_VERIFIED_PLANNING_HANDOFF'):
            reg.pin_task('TEST-001',profile='development-worker')
        self.assertFalse((self.root/'.agentflow/execution-contexts/tasks/TEST-001.json').exists())

    def test_worker_handoff_not_approval(self):
        self.manager.activate('task-planning',1)
        task=self.root/'docs/tasks/active/BUILD-001';task.mkdir()
        (task/'spec.md').write_text('spec AC');(task/'plan.md').write_text('plan verify')
        sums={n:hashlib.sha256((task/n).read_bytes()).hexdigest() for n in ('spec.md','plan.md')}
        (task/'plan-verification.json').write_text(json.dumps({'task_id':'BUILD-001','result':'PASS','verifier':'verifier','checks':['requirements','acceptance_criteria','dependencies','verification_plan'],'sha256':sums}))
        self.manager.mark_plan_ready('BUILD-001')
        self.manager.activate('development-worker',2)
        result=self.manager.begin_planned_task('BUILD-001')
        self.assertEqual(result['state'],'WAITING_PLAN_APPROVAL')
        record=json.loads((task/'task-state.json').read_text())
        self.assertEqual(record['execution_profile'],'development-worker')
        self.assertFalse(result['gate1_approved'])
        self.assertEqual(ContextRegistry(self.manager).task_contract('BUILD-001')['profile'],'development-worker')
        self.assertEqual(self.manager.runtime_contract('development-worker')['execution_scope']['archive_to_completed_allowed'],False)
