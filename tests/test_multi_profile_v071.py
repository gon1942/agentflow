"""Integration: same project, independent host session defaults and immutable task contract."""
import json
import unittest
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.contexts import ContextRegistry
from scaffold.agentflow_console.core import ManagementError

class MultiProfile071(unittest.TestCase):
    def setUp(self):
        self.fx=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.m=self.fx.manager;self.root=self.fx.root
        self.registry=ContextRegistry(self.m)
    def task(self,tid):
        folder=self.root/'docs/tasks/active'/tid;folder.mkdir()
        (folder/'task-state.json').write_text(json.dumps({'task_id':tid,'state':'PLAN_DRAFT'}))
        return folder
    def test_two_hosts_independent_same_project(self):
        self.registry.bind_session('opencode-dev','opencode','lifecycle-dev')
        self.registry.bind_session('claude-plan','claude','task-planning')
        self.assertEqual(self.registry.contract('opencode-dev')['profile']['id'],'lifecycle-dev')
        self.assertEqual(self.registry.contract('claude-plan')['profile']['id'],'task-planning')
        self.task('DEV-001');self.task('PLAN-001')
        d=self.registry.pin_task('DEV-001','opencode-dev')
        p=self.registry.pin_task('PLAN-001','claude-plan')
        self.assertNotEqual(d['contract_sha256'],p['contract_sha256'])
        self.m.activate('task-planning',1)
        self.assertEqual(self.registry.contract()['profile']['id'],'task-planning')
        self.assertEqual(self.registry.task_contract('DEV-001')['profile'],'lifecycle-dev')
        self.assertEqual(self.registry.task_contract('PLAN-001')['profile'],'task-planning')
        self.assertEqual(self.registry.contract('opencode-dev')['profile']['id'],'lifecycle-dev')
        self.assertEqual(len(self.registry.task_views()),2)
    def test_session_change_only_new_task_and_pin_is_idempotent(self):
        self.registry.bind_session('opencode-dev','opencode','lifecycle-dev')
        self.task('DEV-001')
        original=self.registry.pin_task('DEV-001','opencode-dev')
        self.registry.bind_session('opencode-dev','opencode','task-planning',1)
        self.assertEqual(self.registry.pin_task('DEV-001','opencode-dev'),original)
        self.task('PLAN-001')
        self.assertEqual(self.registry.pin_task('PLAN-001','opencode-dev')['profile'],'task-planning')
    def test_config_edit_does_not_change_pinned_contract(self):
        self.task('PLAN-001');a=self.registry.pin_task('PLAN-001',profile='task-planning')
        data=self.m.profile('task-planning');data['description']='new settings'
        with self.assertRaisesRegex(ManagementError,'TASK_ACTIVE'):
            self.m.save_profile(data)
        self.assertEqual(self.registry.task_contract('PLAN-001'),a)
    def test_pinned_contract_tampering_rejected(self):
        self.task('PLAN-001');self.registry.pin_task('PLAN-001',profile='task-planning')
        p=self.root/'.agentflow/execution-contexts/tasks/PLAN-001.json'
        record=json.loads(p.read_text());record['contract']['profile']['description']='tampered'
        p.write_text(json.dumps(record))
        with self.assertRaisesRegex(ManagementError,'TASK_CONTEXT_INTEGRITY_FAILED'):
            self.registry.task_contract('PLAN-001')
    def test_running_task_without_pin_cannot_be_reassigned(self):
        p=self.task('DEV-001')
        (p/'task-state.json').write_text(json.dumps({'task_id':'DEV-001','state':'IN_PROGRESS'}))
        with self.assertRaisesRegex(ManagementError,'ALREADY_STARTED'):
            self.registry.pin_task('DEV-001',profile='task-planning')
    def test_host_mismatch_and_stale_generation_blocked(self):
        self.registry.bind_session('dev-one','opencode','lifecycle-dev')
        with self.assertRaisesRegex(ManagementError,'HOST_IMMUTABLE'):
            self.registry.bind_session('dev-one','claude','task-planning')
        with self.assertRaisesRegex(ManagementError,'VERSION_CONFLICT'):
            self.registry.bind_session('dev-one','opencode','task-planning',0)
    def test_explicit_profile_override(self):
        self.registry.bind_session('dev-one','opencode','lifecycle-dev')
        self.assertEqual(self.registry.contract('dev-one','task-planning')['selection']['profile_source'],'EXPLICIT')
    def test_development_task_gate_persists_after_profile_switch(self):
        self.task('DEV-001');self.registry.pin_task('DEV-001',profile='lifecycle-dev')
        self.m.activate('task-planning',1)
        self.assertTrue(self.registry.task_contract('DEV-001')['contract']['approval_gates']['GATE1'])
    def test_invalid_session_id_rejected(self):
        with self.assertRaisesRegex(ManagementError,'SESSION_ID_INVALID'):
            self.registry.bind_session('../hack','opencode','lifecycle-dev')

if __name__=='__main__':unittest.main()

class MultiProfileHTTP071(unittest.TestCase):
    def setUp(self):
        from http.server import ThreadingHTTPServer
        from scaffold.agentflow_console.server import make_handler
        import threading
        self.fx=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.m=self.fx.manager;self.root=self.fx.root
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.m,'private-test-token'))
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
    def req(self,endpoint,payload=None):
        import urllib.request,urllib.error
        url=f'http://127.0.0.1:{self.server.server_port}'+endpoint
        headers={'X-AgentFlow-Token':'private-test-token','Content-Type':'application/json','Origin':f'http://127.0.0.1:{self.server.server_port}'}
        req=urllib.request.Request(url,headers=headers,data=json.dumps(payload).encode() if payload is not None else None)
        try:
            with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_web_switch_and_session_defaults_during_active_task(self):
        code,s=self.req('/api/session-profile/bind',{'session_id':'claude-plan','host':'claude','profile':'task-planning'})
        self.assertEqual(code,200)
        code,s=self.req('/api/session-profile/bind',{'session_id':'opencode-dev','host':'opencode','profile':'lifecycle-dev'})
        self.assertEqual(code,200)
        (self.root/'docs/tasks/active/DEV-001').mkdir()
        (self.root/'docs/tasks/active/DEV-001/task-state.json').write_text(json.dumps({'task_id':'DEV-001','state':'PLAN_DRAFT'}))
        code,s=self.req('/api/task-context/pin',{'task_id':'DEV-001','session_id':'opencode-dev'})
        self.assertEqual(code,200);self.assertEqual(s['profile'],'lifecycle-dev')
        code,s=self.req('/api/profile/activate',{'profile':'task-planning','generation':1})
        self.assertEqual(code,200)
        code,c=self.req('/api/contract?session=opencode-dev')
        self.assertEqual(code,200);self.assertEqual(c['profile']['id'],'lifecycle-dev')
        code,c=self.req('/api/contract?session=claude-plan')
        self.assertEqual(code,200);self.assertEqual(c['profile']['id'],'task-planning')
        code,c=self.req('/api/task-contexts')
        self.assertEqual(code,200);self.assertEqual(c[0]['profile'],'lifecycle-dev')
        code,c=self.req('/api/status')
        self.assertEqual(code,200);self.assertEqual(c['project_default_profile'],'task-planning')
    def test_web_rejects_unbound_session_and_invalid_origin(self):
        code,s=self.req('/api/contract?session=unknown')
        self.assertEqual(code,409);self.assertEqual(s['error'],'SESSION_NOT_BOUND')
        code,s=self.req('/api/session-profile/bind',{'session_id':'../x','host':'claude','profile':'task-planning'})
        self.assertEqual(code,409)

class MultiProfileHandoff071(MultiProfile071):
    def test_plan_ready_to_dev_session_without_project_default_switch(self):
        from hashlib import sha256
        self.registry.bind_session('planning','claude','task-planning')
        self.registry.bind_session('lifecycle-dev','opencode','lifecycle-dev')
        task=self.task('PLAN-001');self.registry.pin_task(task.name,'planning')
        (task/'spec.md').write_text('requirements')
        (task/'plan.md').write_text('plan and AC')
        hashes={key:sha256((task/key).read_bytes()).hexdigest() for key in ('spec.md','plan.md')}
        report={'task_id':task.name,'result':'PASS','verifier':'verifier','checks':['requirements','acceptance_criteria','dependencies','verification_plan'],'sha256':hashes}
        (task/'plan-verification.json').write_text(json.dumps(report))
        self.m.mark_plan_ready(task.name)
        # Project default remains development, but planning session owns original plan.
        self.assertEqual(self.registry.task_contract(task.name)['profile'],'task-planning')
        result=self.m.begin_planned_task(task.name,session_id='lifecycle-dev')
        self.assertEqual(result['state'],'WAITING_PLAN_APPROVAL')
        context=self.registry.task_contract(task.name)
        self.assertEqual(context['profile'],'lifecycle-dev')
        self.assertEqual(context['session_id'],'lifecycle-dev')
        self.assertTrue(context['planning_handoff']['contract_sha256'])
        self.assertTrue(context['contract']['approval_gates']['GATE1'])
        self.assertFalse(self.m._task_record(task).get('gate1_approved',False))
    def test_planning_session_cannot_begin_development(self):
        task=self.task('PLAN-001')
        (task/'task-state.json').write_text(json.dumps({'task_id':task.name,'state':'PLAN_READY'}))
        self.registry.bind_session('planning','claude','task-planning')
        with self.assertRaisesRegex(ManagementError,'DEVELOPMENT_SESSION_REQUIRED'):
            self.m.begin_planned_task(task.name,session_id='planning')

class MultiProfileCLI071(MultiProfile071):
    def run_cli(self,*args):
        import subprocess,sys,os
        return subprocess.run([sys.executable,str(self.root/'agentflow_console.py'),*args],
                              cwd=self.root,env={**os.environ,'PYTHONPATH':str(self.root)},
                              text=True,capture_output=True,timeout=15)
    def test_real_two_cli_processes_resolve_independent_profiles(self):
        self.registry.bind_session('opencode-dev','opencode','lifecycle-dev')
        self.registry.bind_session('claude-plan','claude','task-planning')
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.run_cli,'contract','--session','opencode-dev')
            b=pool.submit(self.run_cli,'contract','--session','claude-plan')
            aa=a.result();bb=b.result()
        self.assertEqual(aa.returncode,0,aa.stderr)
        self.assertEqual(bb.returncode,0,bb.stderr)
        self.assertEqual(json.loads(aa.stdout)['profile']['id'],'lifecycle-dev')
        self.assertEqual(json.loads(bb.stdout)['profile']['id'],'task-planning')
    def test_cli_fails_when_session_unbound_and_pins_task(self):
        bad=self.run_cli('contract','--session','missing-session')
        self.assertEqual(bad.returncode,2);self.assertIn('SESSION_NOT_BOUND',bad.stderr)
        self.registry.bind_session('claude-plan','claude','task-planning')
        self.task('PLAN-001')
        result=self.run_cli('task-context','PLAN-001','--pin','--session','claude-plan')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['profile'],'task-planning')
        pinned=self.run_cli('task-context','PLAN-001')
        self.assertEqual(pinned.returncode,0,pinned.stderr)
        self.assertEqual(json.loads(pinned.stdout)['contract_sha256'],json.loads(result.stdout)['contract_sha256'])
