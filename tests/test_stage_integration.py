"""Whole-contract release checks. Native agent calls/approvals are explicitly simulated."""
from test_install import make_arch_fixture
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_install import ROOT, installer, make_fixture
from test_e2e import APP_JS, TEST_JS

S = ROOT / 'scaffold'



def gate2_approval(task, marker='SIMULATED_OFFLINE_APPROVAL'):
    # Synthetic fixture ONLY, not a real person approving a workflow.
    import hashlib
    lines=['## Gate 1', '- 상태: APPROVED', '## Gate 2', '- 상태: APPROVED', f'- 사용자 원문: {marker}']
    for label, filename in [('Spec','spec.md'),('Plan','plan.md'),('verification','verification.md'),('review','review.md')]:
        lines.append(f'- 승인 대상 {label} SHA-256: {hashlib.sha256((task/filename).read_bytes()).hexdigest()}')
    return '\n'.join(lines)+'\n'

class StageIntegrationTests(unittest.TestCase):
    def test_exact_skill_matrix_and_no_workflow_cli_or_global_fallback(self):
        w = (S/'docs/workflow/WORKFLOW.md').read_text()
        for stage, skill in (
            ('ANALYZE', 'brainstorming'),('PLAN', 'writing-plans'),
            ('IMPLEMENT', 'test-driven-development'),
            ('VERIFY', 'verification-before-completion'),
            ('REVIEW', 'requesting-code-review'),
            ('REVIEW 수정', 'receiving-code-review'),
            ('BUG/FAIL', 'systematic-debugging'),
        ):
            self.assertIn(f'| {stage} |', w)
            row = next(line for line in w.splitlines() if line.startswith(f'| {stage} |'))
            self.assertIn(f'`{skill}`', row)
        for gate in ('| Gate 1 |', '| Gate 2 |'):
            self.assertIn(gate,w)
        self.assertIn('COMPLETE 후', w)
        self.assertIn('SKIP_NOT_NEEDED',w)
        self.assertIn('SKIP_EMPTY',w)
        self.assertIn('원본 비압축',w)
        self.assertNotIn('teamdev verify',w)
        self.assertFalse((S/'teamdev').exists())
        self.assertFalse((S/'cli.py').exists())
        self.assertEqual(len(installer.EXPECTED_SKILLS),7)
        for path in (S/'AGENTS.md',S/'.opencode/agents/coordinator.md'):
            t=path.read_text()
            self.assertIn('WORKFLOW.md',t)
            self.assertIn('CRG',t)
            self.assertIn('RTK',t)
            self.assertIn('Improver' if path.name=='AGENTS.md' else 'improver',t)

    def test_upstream_license_is_preserved_and_fail_closed_if_tampered(self):
        archive, skill, helpers, _ = make_fixture()
        src = S/'.ai-dev/licenses/obra-superpowers-LICENSE'
        self.assertEqual(installer.git_blob_sha1(src.read_bytes()), installer.ORIGINAL_LICENSE_BLOB_SHA1)
        with tempfile.TemporaryDirectory() as td, patch.object(installer,'EXPECTED_SKILLS',skill), patch.object(installer,'EXPECTED_HELPERS',helpers):
            root = Path(td)/'new-project'
            installer.install(root,ROOT,archive, architect_package=make_arch_fixture())
            license_copy = root/installer.ORIGINAL_LICENSE_REL
            self.assertEqual(license_copy.read_bytes(),src.read_bytes())
            lock=json.loads((root/'.ai-dev/external-skills.lock.json').read_text())
            self.assertEqual(lock['license']['git_blob_sha1'],installer.ORIGINAL_LICENSE_BLOB_SHA1)
            fake=installer._scaffold_files(ROOT)
            fake[installer.ORIGINAL_LICENSE_REL] = b'Fake license notice'
            other=Path(td)/'should-not-exist'
            with patch.object(installer,'_scaffold_files',return_value=fake):
                with self.assertRaisesRegex(ValueError,'UPSTREAM_LICENSE_MISSING_OR_TAMPERED'):
                    installer.install(other,ROOT,archive, architect_package=make_arch_fixture())
            self.assertFalse(other.exists())

    def test_readonly_independent_workers_and_compressed_output_not_proof(self):
        verify=(S/'.opencode/agents/verifier.md').read_text()
        review=(S/'.opencode/agents/reviewer.md').read_text()
        implement=(S/'.opencode/agents/implementer.md').read_text()
        improver=(S/'.opencode/agents/improver.md').read_text()
        a=(S/'.ai-dev/TOOLS-AND-OBSERVABILITY.md').read_text()
        self.assertIn('비압축 원본',a)
        self.assertIn('code-review-graph status',a)
        self.assertIn('detect-changes --brief',a)
        self.assertIn('exit_code',a)
        self.assertIn('never for the authoritative test command',verify)
        self.assertIn('complete changed source/diff',review)
        self.assertIn('SKIP',review)
        self.assertIn('RED test first',implement)
        self.assertIn('Never declare VERIFY PASS',implement)
        self.assertIn('NOT_MEASURED',improver)
        self.assertIn('No `teamdev`',improver)
        self.assertIn('read-only',improver)

    def test_project_observer_captures_rtk_and_crg_only_metadata(self):
        plugin=(S/'.opencode/plugins/tool-usage-observer.js').as_uri()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            js=f'''import {{ AgentFlowToolUsageObserver }} from {json.dumps(plugin)};
                const h = await AgentFlowToolUsageObserver({{directory:{json.dumps(d)}}});
                const hook = h['tool.execute.after'];
                for(const [id,cmd] of [
                  ['a','./.ai-dev/tools/rtk/bin/rtk git diff SECRET_NEVER_WRITE'],
                  ['b','./.ai-dev/tools/crg-venv/bin/code-review-graph build'],
                  ['c','rtk git diff GLOBAL_TOOL_SHOULD_NOT_COUNT'],
                  ['d','echo .ai-dev/tools/rtk/bin/rtk FAKE']
                ]) await hook({{tool:'bash',sessionID:'sess-A',callID:id,args:{{command:cmd}}}},{{output:'SECRET_OUTPUT_NOT_ALLOWED'}});
                await hook({{tool:'skill',args:{{command:'./.ai-dev/tools/rtk/bin/rtk git diff'}}}},{{}});
            '''
            p=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True,timeout=15)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            observed=(root/'.ai-dev/observations/project-tool-events.jsonl').read_text()
            parsed=[json.loads(v) for v in observed.splitlines()]
            self.assertEqual(len(parsed),2)
            self.assertEqual([x['type'] for x in parsed],['RTK_DIRECT_COMMAND_OBSERVED','CRG_DIRECT_COMMAND_OBSERVED'])
            self.assertNotIn('SECRET_NEVER_WRITE',observed)
            self.assertNotIn('SECRET_OUTPUT_NOT_ALLOWED',observed)
            self.assertNotIn('GLOBAL_TOOL_SHOULD_NOT_COUNT',observed)
            self.assertEqual({v['outcome'] for v in parsed},{'NOT_VERIFIED'})

    def test_real_failed_probe_is_not_pass_tee_and_correct_raw_exit(self):
        # Actual subprocess exercise, not a mocked return code.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'bad.cjs').write_text('process.stderr.write("REAL_TEST_FAILURE\\n"); process.exit(7)')
            piped=subprocess.run(['bash','-c','node bad.cjs 2>&1 | tee piped.log; echo pipeline_exit=$?'],cwd=root,capture_output=True,text=True)
            self.assertEqual(piped.returncode,0)
            self.assertIn('pipeline_exit=0',piped.stdout)
            self.assertIn('REAL_TEST_FAILURE',(root/'piped.log').read_text())
            actual=subprocess.run(['node','bad.cjs'],cwd=root,capture_output=True,text=True)
            self.assertEqual(actual.returncode,7)
            raw=root/'raw.log';raw.write_text(actual.stdout+actual.stderr)
            self.assertIn('REAL_TEST_FAILURE',raw.read_text())
            pipefail=subprocess.run(['bash','-o','pipefail','-c','node bad.cjs 2>&1 | tee fixed.log'],cwd=root,capture_output=True,text=True)
            self.assertEqual(pipefail.returncode,7)

    def test_full_install_real_login_tests_synthetic_gates_and_improver_evidence(self):
        archive,skill,helpers,_=make_fixture()
        with tempfile.TemporaryDirectory() as td,patch.object(installer,'EXPECTED_SKILLS',skill),patch.object(installer,'EXPECTED_HELPERS',helpers):
            root=Path(td)/'new-project'
            out=installer.install(root,ROOT,archive, architect_package=make_arch_fixture())
            self.assertEqual(out['workflow_cli'],'NONE')
            self.assertTrue((root/'.opencode/plugins/tool-usage-observer.js').exists())
            task=root/'docs/tasks/LOGIN-001';task.mkdir(parents=True)
            for n in ('spec.md','plan.md','progress.md','verification.md','review.md','approvals.md','tool-evidence.md','improvement.md'):
                shutil.copy(root/'docs/templates/task'/n,task/n)
            # This is a contract simulation, NOT a native user approval or worker invocation.
            (task/'plan.md').write_text('Synthetic plan: node --test; login good/bad and 404')
            (task/'spec.md').write_text('Synthetic AC: GET login, valid login 200, bad login 401, 404')
            plan_hash=hashlib.sha256((task/'plan.md').read_bytes()).hexdigest()
            (task/'approvals.md').write_text('Gate1: SIMULATED_OFFLINE_APPROVAL; plan_sha256: '+plan_hash+'\nGate2: PENDING\n')
            (root/'server.cjs').write_text(APP_JS)
            (root/'test.cjs').write_text(TEST_JS.replace("require('./server')", "require('./server.cjs')"))
            run=subprocess.run(['node','--test','test.cjs'],cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            ev=task/'evidence/round-01';ev.mkdir(parents=True)
            (ev/'raw-node-test.log').write_text(run.stdout+run.stderr)
            (task/'verification.md').write_text('SIMULATED verifier; actual node --test child exit=0; raw log evidence/round-01/raw-node-test.log; native worker NOT_VERIFIED\n')
            (task/'tool-evidence.md').write_text('| VERIFY/01 | RTK_NOT_USED | evidence/round-01/raw-node-test.log / child exit=0 | NOT_RUN | SKIP_EMPTY | NOT_RUN | NATIVE_WORKER_NOT_VERIFIED |\n')
            (task/'review.md').write_text('SIMULATED REVIEW, native reviewer NOT_VERIFIED, blocking findings NOT_VERIFIED')
            (task/'progress.md').write_text('---\nstatus: WAITING_FINAL_APPROVAL\n---\n')
            self.assertIn('WAITING_FINAL_APPROVAL',(task/'progress.md').read_text())
            (task/'approvals.md').write_text(gate2_approval(task))
            (task/'progress.md').write_text('---\nstatus: COMPLETED\n---\n')
            (task/'improvement.md').write_text('IMPROVER_NOT_RUN (native agent unavailable); no automated change\n')
            self.assertIn('IMPROVER_NOT_RUN',(task/'improvement.md').read_text())
            self.assertFalse((root/'teamdev').exists())
            js=f'import {{readProjectStatus}} from {json.dumps((root/".opencode/lib/session-status.js").as_uri())}; console.log((await readProjectStatus({json.dumps(str(root))})).summary)'
            got=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True,timeout=10)
            self.assertEqual(got.returncode,0,got.stderr)
            self.assertIn('완료 1',got.stdout)

if __name__=='__main__':
    unittest.main()
