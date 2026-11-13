"""Integration tests: real project fixture and real OS subprocesses, NOT native LLM E2E."""
from pathlib import Path
import json
import os
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.rotation import RotationManager, live_worker, _CHILDREN
from scaffold.agentflow_console.core import ManagementError

SLEEP = [sys.executable,'-c','import time; time.sleep(60)']

class RotationCoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root
        self.m=self.fixture.manager
        self.r=RotationManager(self.m)
        self.task_id='LOGIN-001'
        self.task=self.root/'docs/tasks/active'/self.task_id
        self.task.mkdir()
        self.task_state={'task_id':self.task_id,'state':'IN_PROGRESS','stage':'IMPLEMENT',
                         'gate1_approved':True,'gate2_approved':False}
        (self.task/'task-state.json').write_text(json.dumps(self.task_state))
        (self.task/'plan.md').write_text('plan agreed\n')
        (self.task/'approvals.md').write_text('Gate1 verified externally (fixture)\n')
        self.addCleanup(self._cleanup_worker)
    def _cleanup_worker(self):
        import signal
        record=self.r._load(self.task_id)
        if record and live_worker(record):
            try: os.killpg(record['pid'],signal.SIGKILL)
            except (ProcessLookupError,PermissionError):pass
        for pid,proc in list(_CHILDREN.items()):
            try: proc.wait(timeout=1)
            except Exception: pass
            _CHILDREN.pop(pid,None)
    def start(self):
        return self.r.start_managed(self.task_id,'IMPLEMENT',SLEEP)
    def ready_to_stop(self):
        self.start();self.r.request(self.task_id,'manual',['wrote tests'],['implement session expiry'])
        self.r.validate(self.task_id)
    def test_e2e_two_distinct_subprocesses_same_task(self):
        old=self.start();first=old['pid']
        self.assertTrue(old['worker_alive']);self.assertEqual(old['generation'],1)
        self.r.request(self.task_id,'manual',['wrote tests'],['implement session expiry'])
        self.assertEqual(self.r.status(self.task_id)['state'],'HANDOFF_VALIDATING')
        self.r.validate(self.task_id)
        self.r.stop(self.task_id)
        second=self.r.resume(self.task_id,SLEEP)
        self.assertNotEqual(first,second['pid']);self.assertEqual(second['generation'],2)
        self.assertEqual(self.m._task_record(self.task),self.task_state)
        self.assertEqual(len(self.r.history(self.task_id)),5)
        self.assertEqual(second['native_rotation'],'NOT_VERIFIED')
    def test_cannot_resume_before_old_stopped(self):
        self.ready_to_stop()
        with self.assertRaisesRegex(ManagementError,'ROTATION_NOT_READY'):
            self.r.resume(self.task_id,SLEEP)
    def test_cannot_double_start(self):
        self.start()
        with self.assertRaisesRegex(ManagementError,'ALREADY_REGISTERED'):
            self.start()
    def test_handoff_tampering_blocks(self):
        self.start();self.r.request(self.task_id,'manual',[],['next'])
        record=self.r._load(self.task_id)
        handoff=self.r.base/self.task_id/record['rotation_id']/'handoff.json'
        handoff.write_text(handoff.read_text()+'\n')
        with self.assertRaisesRegex(ManagementError,'TAMPERED'):
            self.r.validate(self.task_id)
    def test_plan_or_approval_change_blocks(self):
        self.start();self.r.request(self.task_id,'manual',[],['next'])
        (self.task/'approvals.md').write_text('approval changed')
        with self.assertRaisesRegex(ManagementError,'SNAPSHOT_CHANGED'):
            self.r.validate(self.task_id)
    def test_development_impl_without_gate1_evidence_is_blocked(self):
        self.task_state['gate1_approved']=False
        (self.task/'task-state.json').write_text(json.dumps(self.task_state))
        with self.assertRaisesRegex(ManagementError,'GATE1_EVIDENCE_MISSING'):
            self.start()

    def test_plan_ready_not_running(self):
        self.task_state['state']='PLAN_READY'
        (self.task/'task-state.json').write_text(json.dumps(self.task_state))
        with self.assertRaisesRegex(ManagementError,'NOT_RUNNING'):
            self.start()
    def test_rotation_does_not_fake_completion_or_approval(self):
        self.ready_to_stop();self.r.stop(self.task_id)
        self.assertEqual(json.loads((self.task/'task-state.json').read_text())['state'],'IN_PROGRESS')
        self.assertFalse(json.loads((self.task/'task-state.json').read_text())['gate2_approved'])
        self.assertFalse((self.root/'docs/tasks/completed'/self.task_id).exists())
    def test_invalid_handoff_reason_and_scope(self):
        self.start()
        with self.assertRaisesRegex(ManagementError,'REASON_INVALID'):
            self.r.request(self.task_id,'never',["x"],[])
        with self.assertRaisesRegex(ManagementError,'HANDOFF_INVALID'):
            self.r.request(self.task_id,'manual',[123],[])
    def test_history_and_no_registration(self):
        self.assertEqual(self.r.status(self.task_id)['state'],'NOT_REGISTERED')
        self.assertEqual(self.r.history(self.task_id),[])
        self.start()
        self.assertEqual(self.r.history(self.task_id)[0]['kind'],'WORKER_STARTED')
    def test_invalid_task_id(self):
        with self.assertRaisesRegex(ManagementError,'TASK_ID_INVALID'):
            self.r.status('../../secret')

if __name__=='__main__':unittest.main()

# Additional safety conditions are tested by RotationCoreSafety below.
class RotationCoreSafety(RotationCoreTests):
    def test_cancel_unfreezes_existing_worker_without_spawn(self):
        old=self.start();self.r.request(self.task_id,'manual',[],['continue'])
        self.assertEqual(self.r.status(self.task_id)['state'],'HANDOFF_VALIDATING')
        again=self.r.cancel(self.task_id)
        self.assertEqual(again['pid'],old['pid']);self.assertEqual(again['generation'],1)
        self.assertTrue(again['worker_alive'])
        self.assertEqual(self.r.history(self.task_id)[-1]['kind'],'ROTATION_CANCELLED')

    def test_blocked_rotation_cannot_be_bypassed_by_start(self):
        self.start();self.r.request(self.task_id,'manual',[],['continue'])
        self.r.validate(self.task_id)
        (self.task/'approvals.md').write_text('modified approval')
        with self.assertRaisesRegex(ManagementError,'SNAPSHOT_CHANGED'):
            self.r.stop(self.task_id)
        self.assertEqual(self.r.status(self.task_id)['state'],'BLOCKED')
        with self.assertRaisesRegex(ManagementError,'ALREADY_REGISTERED'):
            self.start()

class RotationCapabilities(unittest.TestCase):
    def test_native_host_presence_not_claimed_to_be_verified(self):
        fixture=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        result=RotationManager(fixture.manager).capabilities()
        self.assertEqual(result['native_rotation'],'NOT_VERIFIED')
        self.assertEqual(result['auto_context_rotation'],'NOT_IMPLEMENTED')
        self.assertEqual(set(result['hosts']),{'opencode','claude','codex'})
        self.assertTrue(all(row['native_session_stop_resume']=='NOT_VERIFIED' for row in result['hosts'].values()))

class RotationPinnedProfile071(RotationCoreTests):
    def test_rotation_keeps_task_profile_after_project_default_change(self):
        from scaffold.agentflow_console.contexts import ContextRegistry
        from scaffold.agentflow_console.core import atomic_json
        # Register before moving to IN_PROGRESS; beginning work without pin is legacy/unverified.
        draft={**self.task_state,'state':'PLAN_DRAFT','execution_profile':'development'}
        atomic_json(self.task/'task-state.json',draft,self.root)
        ContextRegistry(self.m).pin_task(self.task_id,profile='development')
        atomic_json(self.task/'task-state.json',self.task_state,self.root)
        self.m.activate('task-planning',1)
        result=self.start()
        self.assertEqual(result['profile'],'development')
        self.assertEqual(self.m.active()['profile'],'task-planning')
        self.assertEqual(ContextRegistry(self.m).task_contract(self.task_id)['profile'],'development')
