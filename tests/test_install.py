import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_skills_installer', ROOT / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def make_fixture():
    fake = {}
    for name in installer.EXPECTED_SKILLS:
        fake[name + '/SKILL.md'] = f'---\nname: {name}\n---\nOriginal-for-test-only\n'.encode()
    for name in installer.EXPECTED_HELPERS:
        fake[name] = f'Original fixture companion: {name}\n'.encode()
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        for rel, content in fake.items():
            z.writestr('superpowers-' + installer.COMMIT + '/skills/' + rel, content)
    hashes = {name:installer.git_blob_sha1(fake[name + '/SKILL.md']) for name in installer.EXPECTED_SKILLS}
    helper_hashes={name:installer.git_blob_sha1(fake[name]) for name in installer.EXPECTED_HELPERS}
    return data.getvalue(), hashes, helper_hashes, fake


def make_arch_fixture():
    """Synthetic in-memory test package; NEVER shipped as original third-party skills."""
    import architect_sources as arch
    files={name+'/SKILL.md':f'---\nname: {name}\n---\nTEST ONLY\n'.encode() for name in arch.SKILLS}
    sources={key:{'repo':cfg['repo'],'commit':cfg['commit'],'license_status':'TEST_FIXTURE'} for key,cfg in arch.REPOS.items()}
    return {'files':files,'licenses':{},'sources':sources}


def gate2_approval(task, marker='SIMULATED_OFFLINE_APPROVAL'):
    # Synthetic fixture ONLY, not a real person approving a workflow.
    import hashlib
    lines=['## Gate 1', '- 상태: APPROVED', '## Gate 2', '- 상태: APPROVED', f'- 사용자 원문: {marker}']
    for label, filename in [('Spec','spec.md'),('Plan','plan.md'),('verification','verification.md'),('review','review.md')]:
        lines.append(f'- 승인 대상 {label} SHA-256: {hashlib.sha256((task/filename).read_bytes()).hexdigest()}')
    return '\n'.join(lines)+'\n'

class InstallerTests(unittest.TestCase):
    def test_pin_definitions_match_independently_fetched_sha(self):
        # These values are pinned upstream Git blob hashes, not our test-fixture hashes.
        self.assertEqual(installer.EXPECTED_SKILLS['requesting-code-review'],'68d338a58ecdd8b77bfbb519b781ef223dbbb842')
        self.assertEqual(installer.EXPECTED_SKILLS['verification-before-completion'],'7d45333cc4a49c57a80df6c1fe2fa777a207afbc')
        self.assertEqual(len(installer.EXPECTED_SKILLS),7)

    def test_install_fresh_project_with_all_helpers_and_runtimes(self):
        blob, fake_hashes, helper_hashes, expected_files = make_fixture()
        with tempfile.TemporaryDirectory() as temp, patch.object(installer,'EXPECTED_SKILLS',fake_hashes), patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            root = Path(temp)/'project'
            report = installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            self.assertEqual(report['skills'],15)
            self.assertEqual(report['runtimes'],3)
            self.assertEqual(report['workflow_cli'],'NONE')
            self.assertEqual(report['native_skill_load'],'NOT_VERIFIED')
            self.assertFalse((root/'teamdev').exists())
            self.assertFalse((root/'src/teamdev').exists())
            self.assertFalse((root/'install.py').exists())
            for base in installer.SKILL_ROOTS:
                for rel, data in expected_files.items():
                    self.assertEqual((root/base/rel).read_bytes(),data)
            lock = json.loads((root/'.ai-dev/external-skills.lock.json').read_text())
            self.assertEqual(lock['scope'],'PROJECT_ONLY')
            self.assertEqual(len(lock['installed_files_sha256']),len(expected_files))
            self.assertEqual(len(lock['verified_companion_sha1']),len(helper_hashes))
            self.assertTrue((root/'.opencode/skills/brainstorming/scripts/start-server.sh').stat().st_mode & 0o111)
            self.assertEqual((root/'opencode.json').is_file(),True)
            self.assertEqual((root/'docs/workflow/SESSION-START.md').is_file(),True)
            self.assertFalse(any((root/p).exists() for p in ('.ai-dev/venv','.ai-dev/tools/rtk','teamdev')))
            # Re-running with exact same files is idempotent.
            rerun = installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            self.assertEqual(rerun['written_files'],0)

    def test_modified_existing_user_file_refuses_all_writes(self):
        blob, fake_hashes, helper_hashes, _ = make_fixture()
        with tempfile.TemporaryDirectory() as temp, patch.object(installer,'EXPECTED_SKILLS',fake_hashes), patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            root=Path(temp)/'project'
            root.mkdir()
            (root/'AGENTS.md').write_text('USER CONFIG')
            with self.assertRaisesRegex(ValueError,'CONFLICT'):
                installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            self.assertEqual((root/'AGENTS.md').read_text(),'USER CONFIG')
            self.assertFalse((root/'.ai-dev').exists())

    def test_wrong_upstream_blob_blocks_before_creation(self):
        blob, fake_hashes, helper_hashes, _=make_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'project'
            with self.assertRaisesRegex(ValueError,'UPSTREAM_HASH_MISMATCH'):
                installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            self.assertFalse(root.exists())

    def test_missing_helper_blocks(self):
        blob, fake_hashes, helper_hashes, files=make_fixture()
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            for rel,content in files.items():
                if rel=='requesting-code-review/code-reviewer.md':continue
                z.writestr('superpowers-'+installer.COMMIT+'/skills/'+rel,content)
        with patch.object(installer,'EXPECTED_SKILLS',fake_hashes), patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            with self.assertRaisesRegex(ValueError,'Missing upstream original or companion'):
                installer.extract_skills(data.getvalue())

    def test_symlink_and_traversal_rejected(self):
        blob, fake_hashes, helper_hashes, _=make_fixture()
        with tempfile.TemporaryDirectory() as temp, patch.object(installer,'EXPECTED_SKILLS',fake_hashes), patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            root=Path(temp)/'project'
            root.mkdir()
            (root/'.opencode').symlink_to(Path(temp),target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'SYMLINK'):
                installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            self.assertFalse((root/'AGENTS.md').exists())
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('superpowers-123/skills/brainstorming/../../escape',b'bad')
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            installer.extract_skills(data.getvalue())

    def test_unauthorized_no_network_results_in_blocked_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'project'
            with patch('urllib.request.urlopen',side_effect=OSError('network unavailable')):
                exitcode=installer.main([str(root)])
            self.assertEqual(exitcode,2)
            self.assertFalse(root.exists())

    def test_project_no_teamdev_dependencies_in_agent_runtime(self):
        for path in (ROOT/'scaffold').rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc','.pyo'):continue
            text=path.read_text()
            self.assertNotIn('./teamdev ',text,f'{path} refers to workflow CLI')
        self.assertFalse((ROOT/'scaffold/teamdev').exists())

    def test_node_plugin_shows_session_status(self):
        source=ROOT/'scaffold/.opencode/plugins/session-status.js'
        helper=ROOT/'scaffold/.opencode/lib/session-status.js'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for task,status in [('LOGIN-001','VERIFY'),('CALC-002','WAITING_PLAN_APPROVAL'),('CALC-003','COMPLETED'),('BUG-004','BLOCKED'),('APP-005','WAITING_FINAL_APPROVAL')]:
                folder=root/'docs/tasks'/task
                folder.mkdir(parents=True)
                (folder/'progress.md').write_text(f'---\nstatus: {status}\n---\n')
                if status == 'COMPLETED':
                    for f in ('spec.md','plan.md','verification.md','review.md'): (folder/f).write_text('synthetic fixture')
                    (folder/'approvals.md').write_text(gate2_approval(folder))
            # Node can import the plugin as ES module from a file:// URL.
            js=f'''import {{readProjectStatus}} from {json.dumps(helper.as_uri())};
             import {{AgentFlowSessionStatus}} from {json.dumps(source.as_uri())};
             const s=await readProjectStatus({json.dumps(str(root))});
             if(!s.summary.includes('진행 1 / 계획 승인 대기 1 / 최종 승인 대기 1 / 차단 1 / 완료 1')) throw new Error(s.summary);
             let message=''; const hook=await AgentFlowSessionStatus({{directory:{json.dumps(str(root))},client:{{tui:{{showToast:async args=>{{message=args.body.message;}}}}}}}});
             await hook.event({{event:{{type:'session.created'}}}});
             if(!message.includes('작업 상태:')) throw new Error('Session toast missing');
             console.log(s.summary);'''
            p=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)

if __name__ == '__main__':unittest.main()
