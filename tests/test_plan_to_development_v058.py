"""Real filesystem transitions: plan PASS -> active PLAN_READY -> development Gate 1 wait."""
import hashlib
import json
import unittest
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.core import ManagementError

class PlanToDevelopmentV058(unittest.TestCase):
    setUp=ThreeDefaultProfiles.setUp

    def task(self, name='LOGIN-001-login'):
        root=self.root/'docs/tasks/active'/name
        root.mkdir()
        (root/'spec.md').write_text('Login requirements and AC-1',encoding='utf-8')
        (root/'plan.md').write_text('Task 1 implementation and verification plan',encoding='utf-8')
        hashes={key:hashlib.sha256((root/key).read_bytes()).hexdigest() for key in ('spec.md','plan.md')}
        report={'task_id':name,'result':'PASS','verifier':'verifier','checks':['requirements','acceptance_criteria','dependencies','verification_plan'],'sha256':hashes}
        (root/'plan-verification.json').write_text(json.dumps(report),encoding='utf-8')
        return root

    def test_plan_complete_keeps_active_and_development_reuses_task(self):
        self.manager.activate('task-planning',1)
        scope=self.manager.runtime_contract()['execution_scope']
        self.assertTrue(scope['plan_ready_allowed_after_evidence'])
        self.assertFalse(scope['archive_to_completed_allowed'])
        self.assertEqual(scope['task_destination'],'docs/tasks/active/<TASK-ID>')
        task=self.task()
        answer=self.manager.mark_plan_ready(task.name)
        self.assertEqual(answer['state'],'PLAN_READY')
        self.assertTrue(task.exists())
        self.assertFalse((self.root/'docs/tasks/completed'/task.name).exists())
        self.assertEqual(self.manager.active_tasks(),[])
        self.assertEqual(self.manager.plan_ready_tasks(),[task.name])
        self.manager.activate('lifecycle-dev',2)
        answer=self.manager.begin_planned_task(task.name)
        self.assertEqual(answer['next_step'],'GATE1_USER_APPROVAL_REQUIRED')
        self.assertEqual(self.manager.active_tasks(),[task.name])
        self.assertEqual(json.loads((task/'task-state.json').read_text())['implementation_status'],'WAITING_GATE1')
        self.assertTrue((task/'plan.md').exists())
        self.manager.activate('task-planning',3)
        self.assertEqual(self.manager._task_record(task)['execution_profile'],'lifecycle-dev')
        with self.assertRaisesRegex(ManagementError,'DEVELOPMENT_PROFILE_REQUIRED'):
            self.manager.begin_planned_task(task.name)

    def test_missing_verification_blocks_without_writing_state(self):
        self.manager.activate('task-planning',1)
        task=self.task();(task/'plan-verification.json').unlink()
        with self.assertRaisesRegex(ManagementError,'PLAN_EVIDENCE_MISSING'):
            self.manager.mark_plan_ready(task.name)
        self.assertFalse((task/'task-state.json').exists())
        self.assertTrue(task.exists())

    def test_failed_verification_blocks(self):
        self.manager.activate('task-planning',1)
        task=self.task();path=task/'plan-verification.json'
        data=json.loads(path.read_text());data['result']='FAIL';path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ManagementError,'PLAN_VERIFICATION_NOT_PASS'):
            self.manager.mark_plan_ready(task.name)
        self.assertFalse((task/'task-state.json').exists())

    def test_plan_changed_after_verification_blocks(self):
        self.manager.activate('task-planning',1)
        task=self.task();(task/'plan.md').write_text('amended after verifier report')
        with self.assertRaisesRegex(ManagementError,'PLAN_VERIFICATION_STALE'):
            self.manager.mark_plan_ready(task.name)
        self.assertFalse((task/'task-state.json').exists())

    def test_changed_ready_plan_blocks_development(self):
        self.manager.activate('task-planning',1)
        task=self.task();self.manager.mark_plan_ready(task.name)
        self.manager.activate('lifecycle-dev',2)
        (task/'plan.md').write_text('unapproved changed task plan')
        with self.assertRaisesRegex(ManagementError,'PLAN_CHANGED_REQUIRES_REVERIFY'):
            self.manager.begin_planned_task(task.name)
        self.assertEqual(json.loads((task/'task-state.json').read_text())['state'],'PLAN_READY')

    def test_unknown_active_task_blocks_profile_switch(self):
        self.manager.activate('task-planning',1)
        path=self.root/'docs/tasks/active/LEGACY-001';path.mkdir()
        with self.assertRaisesRegex(ManagementError,'ACTIVE_TASK_CONTEXT_NOT_PINNED'):
            self.manager.activate('lifecycle-dev',2)

    def test_ready_only_requires_planning_profile(self):
        task=self.task()
        with self.assertRaisesRegex(ManagementError,'TASK_PLANNING_PROFILE_REQUIRED'):
            self.manager.mark_plan_ready(task.name)
        # A ready record is eligible for profile switch; begin is disallowed under planning.
        (task/'task-state.json').write_text(json.dumps({'task_id':task.name,'state':'PLAN_READY'}))
        self.manager.activate('task-planning',1)
        with self.assertRaisesRegex(ManagementError,'DEVELOPMENT_PROFILE_REQUIRED'):
            self.manager.begin_planned_task(task.name)

if __name__=='__main__':unittest.main()
