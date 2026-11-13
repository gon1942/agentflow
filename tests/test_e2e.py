"""Offline integration test: real project copy and real Node app tests; native workers/approvals simulated."""
from test_install import make_arch_fixture
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_install import installer, ROOT, make_fixture

APP_JS = r'''
const http = require('node:http');
const {URLSearchParams} = require('node:url');
function createServer() {return http.createServer((req,res)=>{
  if (req.method==='GET' && req.url==='/') {res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});return res.end('<form action="/login" method="post"><input name="user"><input name="password" type="password"><button>Log in</button></form>');}
  if (req.method==='POST' && req.url==='/login') {
    let input='';req.on('data',c=>{input+=c;if(input.length>2048)req.destroy();});
    req.on('end',()=>{
      const data=new URLSearchParams(input);
      const ok = data.get('user')==='demo' && data.get('password')==='local-only-test';
      res.writeHead(ok?200:401,{'Content-Type':'application/json'});
      res.end(JSON.stringify({ok}));
    });return;
  }
  res.writeHead(404);res.end('not found');
});}
module.exports={createServer};
'''
TEST_JS = r'''
const {test}=require('node:test');const assert=require('node:assert/strict');
const {createServer}=require('./server');
async function withServer(fn){const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));try{await fn(`http://127.0.0.1:${server.address().port}`);}finally{await new Promise(r=>server.close(r));}}
test('login form returns password input',async()=>{await withServer(async u=>{const r=await fetch(u);assert.equal(r.status,200);assert.match(await r.text(),/type="password"/);});});
test('valid user/password accepted',async()=>{await withServer(async u=>{const r=await fetch(u+'/login',{method:'POST',body:new URLSearchParams({user:'demo',password:'local-only-test'})});assert.equal(r.status,200);assert.equal((await r.json()).ok,true);});});
test('incorrect password rejected',async()=>{await withServer(async u=>{const r=await fetch(u+'/login',{method:'POST',body:new URLSearchParams({user:'demo',password:'wrong'})});assert.equal(r.status,401);});});
test('unknown path 404',async()=>{await withServer(async u=>{const r=await fetch(u+'/other');assert.equal(r.status,404);});});
'''


def gate2_approval(task, marker='SIMULATED_OFFLINE_APPROVAL'):
    # Synthetic fixture ONLY, not a real person approving a workflow.
    import hashlib
    lines=['## Gate 1', '- 상태: APPROVED', '## Gate 2', '- 상태: APPROVED', f'- 사용자 원문: {marker}']
    for label, filename in [('Spec','spec.md'),('Plan','plan.md'),('verification','verification.md'),('review','review.md')]:
        lines.append(f'- 승인 대상 {label} SHA-256: {hashlib.sha256((task/filename).read_bytes()).hexdigest()}')
    return '\n'.join(lines)+'\n'

class WorkflowArtifactE2ETests(unittest.TestCase):
    def test_clean_install_to_completed_task_with_real_program_tests(self):
        blob, skill_hashes, helper_hashes, _ = make_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(installer,'EXPECTED_SKILLS',skill_hashes),patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            root=Path(tmp)/'new-project'
            installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            task=root/'docs/tasks/active/AUTH-001-user-login-page'
            task.mkdir(parents=True)
            for name in ['progress.md','spec.md','plan.md','verification.md','review.md','approvals.md']:
                shutil.copy(root/'docs/templates/task'/name,task/name)
            progress=task/'progress.md'
            progress.write_text('---\ntask_id: AUTH-001\nstage: PLAN\nstatus: WAITING_PLAN_APPROVAL\n---\n')
            # Synthetic human approval for offline contract test only (not real Gate 1).
            (task/'spec.md').write_text('AC1 HTML login; AC2 success; AC3 reject; AC4 404')
            (task/'plan.md').write_text('Node HTTP server; node --test test.cjs')
            h=hashlib.sha256((task/'plan.md').read_bytes()).hexdigest()
            (task/'approvals.md').write_text('Gate1: SIMULATED_TEST_APPROVAL\nplan_sha256: '+h+'\nGate2: PENDING\n')
            progress.write_text('---\ntask_id: AUTH-001\nstage: IMPLEMENT\nstatus: IMPLEMENT\n---\n')
            (root/'server.cjs').write_text(APP_JS)
            (root/'test.cjs').write_text(TEST_JS)
            (root/'test.cjs').write_text((root/'test.cjs').read_text().replace("require('./server')", "require('./server.cjs')"))
            # Real product test process (not a mocked exit status).
            run=subprocess.run(['node','--test','test.cjs'],cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn('tests 4',run.stdout)
            progress.write_text('---\ntask_id: AUTH-001\nstage: VERIFY\nstatus: VERIFY\n---\n')
            (task/'verification.md').write_text(f'Native verifier: SIMULATED_NOT_VERIFIED\nDirect node test exit: {run.returncode}\n4/4 PASS\n')
            (task/'review.md').write_text('Native reviewer: SIMULATED_NOT_VERIFIED\nBlocking findings: NOT_VERIFIED\n')
            progress.write_text('---\ntask_id: AUTH-001\nstage: REVIEW\nstatus: WAITING_FINAL_APPROVAL\n---\n')
            # No automatic Gate2: status remains pending until synthetic user approval in test.
            self.assertIn('WAITING_FINAL_APPROVAL', progress.read_text())
            (task/'approvals.md').write_text(gate2_approval(task))
            progress.write_text('---\ntask_id: AUTH-001\nstage: COMPLETE\nstatus: COMPLETED\n---\n')
            # Simulate Coordinator native filesystem archive after synthetic approval.
            completed = root/'docs/tasks/completed'/task.name
            task.rename(completed)
            self.assertFalse(task.exists())
            self.assertTrue((completed/'plan.md').is_file())
            # A fresh session sees the archived TASK, not an empty active state.
            js=(f'import {{readProjectStatus}} from {json.dumps((root/".opencode/lib/session-status.js").as_uri())};'
                f'const v=await readProjectStatus({json.dumps(str(root))});'
                f'if(!v.summary.includes("완료 1"))throw new Error(v.summary);console.log(v.summary);')
            result=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('완료 1',result.stdout)
            self.assertFalse((root/'teamdev').exists())

    def test_review_request_changes_same_task_and_reverify_real_node(self):
        blob, skill_hashes, helper_hashes, _=make_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(installer,'EXPECTED_SKILLS',skill_hashes),patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            root=Path(tmp)/'project'
            installer.install(root,ROOT,blob, architect_package=make_arch_fixture())
            task=root/'docs/tasks/active/AUTH-001-user-login-page'
            task.mkdir(parents=True)
            (task/'approvals.md').write_text('Gate1: SIMULATED_TEST_APPROVAL\nGate2: PENDING\n')
            (root/'server.cjs').write_text(APP_JS.replace("const ok = data.get('user')==='demo' && data.get('password')==='local-only-test';",'const ok = true;'))
            (root/'test.cjs').write_text(TEST_JS.replace("require('./server')","require('./server.cjs')"))
            r1=subprocess.run(['node','--test','test.cjs'],cwd=root,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(r1.returncode,0,'bad auth must fail tests')
            ev1=task/'evidence/round-01'
            ev1.mkdir(parents=True)
            (ev1/'verify.log').write_text(r1.stdout+r1.stderr)
            (task/'review.md').write_text('SIMULATED REVIEW: REQUEST_CHANGES. Bad password accepted.\n')
            (task/'progress.md').write_text('---\nstatus: IMPLEMENT\n---\n')
            # Same task, no new TASK. Fix then run independent test command again.
            (root/'server.cjs').write_text(APP_JS)
            r2=subprocess.run(['node','--test','test.cjs'],cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(r2.returncode,0,r2.stdout+r2.stderr)
            ev2=task/'evidence/round-02'
            ev2.mkdir(parents=True)
            (ev2/'verify.log').write_text(r2.stdout+r2.stderr)
            self.assertNotEqual((ev1/'verify.log').read_text(),(ev2/'verify.log').read_text())
            self.assertEqual(len([p for p in (root/'docs/tasks/active').iterdir() if p.is_dir()]),1)
            # Gate 2 remains required after fixes, no accidental COMPLETE.
            (task/'progress.md').write_text('---\nstatus: WAITING_FINAL_APPROVAL\n---\n')
            self.assertNotIn('COMPLETED',(task/'progress.md').read_text())

if __name__=='__main__':unittest.main()
