"""Native task persistence: actual filesystem + Node plugin; no workflow engine or native Worker claims."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT/'scaffold/.opencode/lib/session-status.js'

def js(root, statement):
    script = f'import {{readProjectStatus,scanTasks,suggestTaskName}} from {json.dumps(PLUGIN.as_uri())};\nconst root={json.dumps(str(root))};\n'+statement
    result = subprocess.run(['node','--input-type=module','-e',script],text=True,capture_output=True,timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr+result.stdout)
    return json.loads(result.stdout)

def write_task(root, bucket, name, status, *, gate2=False, task_id=None):
    task=root/'docs/tasks'/bucket/name
    task.mkdir(parents=True,exist_ok=False)
    if task_id is None: task_id='-'.join(name.split('-')[:2])
    (task/'progress.md').write_text(f'---\ntask_id: {task_id}\nstatus: {status}\n---\n')
    (task/'plan.md').write_text('Immutable example Plan')
    (task/'spec.md').write_text('AC-1')
    (task/'verification.md').write_text('SIMULATED_ONLY')
    (task/'review.md').write_text('SIMULATED_ONLY')
    (task/'approvals.md').write_text(gate2_approval(task) if gate2 else '## Gate 1\n- 상태: APPROVED\n## Gate 2\n- 상태: PENDING\n')
    return task


def gate2_approval(task, marker='SIMULATED_OFFLINE_APPROVAL'):
    # Synthetic fixture ONLY, not a real person approving a workflow.
    import hashlib
    lines=['## Gate 1', '- 상태: APPROVED', '## Gate 2', '- 상태: APPROVED', f'- 사용자 원문: {marker}']
    for label, filename in [('Spec','spec.md'),('Plan','plan.md'),('verification','verification.md'),('review','review.md')]:
        lines.append(f'- 승인 대상 {label} SHA-256: {hashlib.sha256((task/filename).read_bytes()).hexdigest()}')
    return '\n'.join(lines)+'\n'

class TaskLifecycleTests(unittest.TestCase):
    def test_empty_project_status_and_first_semantic_name(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            result=js(root,"const status=await readProjectStatus(root);const id=await suggestTaskName(root,'AUTH','User Login Page'); console.log(JSON.stringify({status,id}));")
            self.assertIn('진행 0',result['status']['summary'])
            self.assertEqual(result['id']['folder'],'AUTH-001-user-login-page')

    def test_new_session_counts_active_completed_and_legacy(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            write_task(root,'active','AUTH-001-user-login-page','IMPLEMENT')
            write_task(root,'active','PRODUCT-001-product-crud','WAITING_PLAN_APPROVAL')
            write_task(root,'active','APP-001-admin-console','WAITING_FINAL_APPROVAL')
            write_task(root,'active','BUG-001-fix-timeout','BLOCKED')
            write_task(root,'completed','AUTH-002-user-signup','COMPLETED',gate2=True)
            legacy=root/'docs/tasks/LEGACY-009';legacy.mkdir()
            (legacy/'progress.md').write_text('---\nstatus: VERIFY\n---\n')
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertEqual(result['summary'],'진행 2 / 계획 승인 대기 1 / 최종 승인 대기 1 / 차단 1 / 완료 1')
            self.assertIn('PRODUCT-001-product-crud',result['next'])
            self.assertIn('APP-001-admin-console',result['next'])

    def test_semantic_number_scans_both_buckets_and_legacy(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            write_task(root,'active','AUTH-001-user-login-page','PLAN')
            write_task(root,'completed','AUTH-015-user-signup','COMPLETED',gate2=True)
            legacy=root/'docs/tasks/AUTH-020';legacy.mkdir();(legacy/'progress.md').write_text('---\nstatus: PLAN\n---\n')
            result=js(root,"console.log(JSON.stringify(await suggestTaskName(root,'AUTH','fix login 401 error')));")
            self.assertEqual(result['folder'],'AUTH-021-fix-login-401-error')

    def test_completed_without_gate2_is_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            write_task(root,'completed','AUTH-001-user-login-page','COMPLETED',gate2=False)
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1 / 완료 0',result['summary'])
            self.assertIn('Gate 2',result['next'])

    def test_custom_profile_explicit_gate2_skip_can_archive_with_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            task=write_task(root,'completed','UX-001-screen-design','COMPLETED',gate2=True)
            digest='a'*64
            progress=(task/'progress.md').read_text()+f'\nprofile: ux-mngr\nconfiguration_sha256: {digest}\n'
            (task/'progress.md').write_text(progress)
            approval=(task/'approvals.md').read_text().replace('- 상태: APPROVED\n- 사용자 원문:', '- 상태: SKIPPED_BY_PROFILE_POLICY\n- Profile ID: ux-mngr\n- configuration_sha256: '+digest+'\n- 사용자 원문:')
            (task/'approvals.md').write_text(approval)
            status=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('완료 1',status['summary'])

    def test_gate2_skip_rejected_for_development_and_tampered_snapshot(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            task=write_task(root,'completed','AUTH-001-login','COMPLETED',gate2=True)
            digest='a'*64
            (task/'progress.md').write_text((task/'progress.md').read_text()+f'\nprofile: development\nconfiguration_sha256: {digest}\n')
            approval=(task/'approvals.md').read_text().replace('- 상태: APPROVED\n- 사용자 원문:', '- 상태: SKIPPED_BY_PROFILE_POLICY\n- Profile ID: development\n- configuration_sha256: '+digest+'\n- 사용자 원문:')
            (task/'approvals.md').write_text(approval)
            status=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1',status['summary'])
            (task/'approvals.md').write_text(approval.replace('development','ux-mngr'))
            status=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1',status['summary'])

    def test_misfiled_active_completed_is_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            write_task(root,'active','AUTH-001-user-login-page','COMPLETED',gate2=True)
            write_task(root,'completed','PRODUCT-001-product-crud','VERIFY')
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 2',result['summary'])
            self.assertIn('완료 0',result['summary'])

    def test_duplicate_id_across_buckets_block_both(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            write_task(root,'active','AUTH-001-user-login-page','VERIFY')
            write_task(root,'completed','AUTH-001-user-signup','COMPLETED',gate2=True)
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 2',result['summary'])
            self.assertEqual([x['reason'] for x in result['items']],['중복 TASK ID','중복 TASK ID'])

    def test_invalid_title_or_id_does_not_silently_allocate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            write_task(root,'active','AUTH-003-login-page','PLAN',task_id='AUTH-004')
            result=js(root,"let err='';try{await suggestTaskName(root,'AUTH','한글만')}catch(e){err=e.message}; console.log(JSON.stringify({err,s:await readProjectStatus(root)}));")
            self.assertIn('INVALID_SLUG',result['err'])
            self.assertIn('차단 1',result['s']['summary'])

    def test_actual_archive_preserves_full_evidence_and_reopens_new_session(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            task=write_task(root,'active','AUTH-001-user-login-page','WAITING_FINAL_APPROVAL')
            ev=task/'evidence/round-01';ev.mkdir(parents=True);(ev/'raw.log').write_bytes(b'raw log from real subprocess\n')
            before=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('최종 승인 대기 1',before['summary'])
            # Explicitly synthetic approval; no agent or person was actually invoked.
            (task/'approvals.md').write_text(gate2_approval(task))
            (task/'progress.md').write_text('---\ntask_id: AUTH-001\nstatus: COMPLETED\n---\n')
            incomplete=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1',incomplete['summary'])
            destination=root/'docs/tasks/completed'/task.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            # Native file move; equivalent to Coordinator's rename, no custom CLI.
            task.rename(destination)
            after=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('완료 1',after['summary'])
            self.assertEqual((destination/'evidence/round-01/raw.log').read_bytes(),b'raw log from real subprocess\n')
            self.assertEqual((destination/'plan.md').read_text(),'Immutable example Plan')
            self.assertFalse(task.exists())

    def test_missing_progress_is_blocked_not_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'docs/tasks/active/AUTH-001-user-login-page').mkdir(parents=True)
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1',result['summary'])

    def test_gate2_hash_tamper_blocks_previously_completed_task(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            task=write_task(root,'completed','AUTH-001-user-login-page','COMPLETED',gate2=True)
            self.assertIn('완료 1',js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')['summary'])
            (task/'verification.md').write_text('Changed test results after approval')
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1',result['summary'])
            self.assertIn('verification 해시 불일치',result['next'])

    def test_gate2_missing_hash_blocks_completion_even_if_approved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            task=write_task(root,'completed','AUTH-001-user-login-page','COMPLETED',gate2=True)
            (task/'approvals.md').write_text('## Gate 2\n- 상태: APPROVED\n')
            result=js(root,'console.log(JSON.stringify(await readProjectStatus(root)));')
            self.assertIn('차단 1',result['summary'])
            self.assertIn('Spec 해시 누락',result['next'])

    def test_policy_forbids_cli_and_requires_whole_archive(self):
        s=ROOT/'scaffold'
        w=(s/'docs/workflow/WORKFLOW.md').read_text()
        session=(s/'docs/workflow/SESSION-START.md').read_text()
        for word in ('active/','completed/','AREA-NNN','Gate 2'):
            self.assertIn(word,w)
            self.assertIn(word,session)
        self.assertIn('전체 TASK',w)
        self.assertIn('BLOCKED',session)
        self.assertIn('teamdev',w)
        self.assertFalse((s/'teamdev').exists())

if __name__=='__main__':unittest.main()
