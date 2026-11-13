"""Project-local hook contract, per-instance isolation and TASK immutability."""
import io
from pathlib import Path
import json
import unittest
from unittest.mock import patch
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.contexts import ContextRegistry
from scaffold.agentflow_console.sessionbridge import prompt_event,session_key
from scaffold.agentflow_console.core import ManagementError

class SessionBridge072(unittest.TestCase):
    def setUp(self):
        self.fx=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.m=self.fx.manager;self.root=self.fx.root
    def test_two_opencode_sessions_isolated_and_web_change_visible(self):
        a=prompt_event(self.m,'opencode','native-A','첫 요청')
        b=prompt_event(self.m,'opencode','native-B','첫 요청')
        self.assertNotEqual(a['session_id'],b['session_id'])
        r=ContextRegistry(self.m)
        r.bind_session(a['session_id'],'opencode','task-planning',1)
        self.assertEqual(prompt_event(self.m,'opencode','native-A','계획을 작성해줘')['profile'],'task-planning')
        self.assertEqual(prompt_event(self.m,'opencode','native-B','개발해줘')['profile'],'lifecycle-dev')
    def test_claude_and_opencode_different_identity(self):
        a=prompt_event(self.m,'opencode','the-same-native-id')
        b=prompt_event(self.m,'claude','the-same-native-id')
        self.assertNotEqual(a['session_id'],b['session_id'])
    def test_chat_switch_and_existing_task_protected(self):
        initial=prompt_event(self.m,'claude','claude-A')
        d=self.root/'docs/tasks/active/DEV-001';d.mkdir()
        (d/'task-state.json').write_text(json.dumps({'task_id':'DEV-001','state':'PLAN_DRAFT'}))
        r=ContextRegistry(self.m)
        original=r.pin_task('DEV-001',initial['session_id'])
        changed=prompt_event(self.m,'claude','claude-A','작업계획전문가로 변경해줘')
        self.assertEqual(changed['profile'],'task-planning')
        self.assertIn('신규 TASK를 생성하지 않습니다',changed['instruction'])
        again=prompt_event(self.m,'claude','claude-A','프로필을 개발전문가로 변경해줘')
        self.assertEqual(again['profile'],'development-worker')
        self.assertEqual(r.task_contract('DEV-001'),original)
    def test_project_default_change_does_not_mutate_existing_session(self):
        first=prompt_event(self.m,'opencode','native-A')
        self.m.activate('task-planning',1)
        self.assertEqual(prompt_event(self.m,'opencode','native-A')['profile'],'lifecycle-dev')
        self.assertEqual(prompt_event(self.m,'opencode','native-B')['profile'],'task-planning')
    def test_unknown_profile_no_change(self):
        a=prompt_event(self.m,'opencode','a')
        x=prompt_event(self.m,'opencode','a','/agentflow-profile alien')
        self.assertEqual(x['status'],'PROFILE_UNKNOWN')
        self.assertEqual(prompt_event(self.m,'opencode','a')['profile'],a['profile'])
    def test_not_accidentally_switch_on_general_prompt(self):
        x=prompt_event(self.m,'opencode','a','개발 전문가와 작업계획전문가를 비교해줘')
        self.assertEqual(x['profile'],'lifecycle-dev')
    def test_invalid_native_identifier_rejected(self):
        for bad in ('',None,'x'*300):
            with self.assertRaises(ManagementError):session_key('opencode',bad)
    def test_id_is_deterministic_and_does_not_store_raw_id(self):
        x=session_key('claude','personal-native-session-value')
        self.assertNotIn('personal-native-session-value',x)
        self.assertEqual(x,session_key('claude','personal-native-session-value'))

if __name__=='__main__':unittest.main()

class NativeAdapterIntegration072(unittest.TestCase):
    def setUp(self):
        self.fx=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.root=self.fx.root
    def test_real_cli_roundtrip_and_separate_processes(self):
        import subprocess,sys
        cli=self.root/'agentflow_console.py'
        def call(host,sid,prompt):
            p=subprocess.run([sys.executable,str(cli),'agent-event','--host',host,'--session-id',sid,'--stdin-json'],
                input=json.dumps({'prompt':prompt}),capture_output=True,text=True,cwd=self.root,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            return json.loads(p.stdout)
        a=call('opencode','first','로그인 구현')
        b=call('opencode','second','계획 작성')
        self.assertEqual(a['profile'],'lifecycle-dev')
        ContextRegistry(self.fx.manager).bind_session(b['session_id'],'opencode','task-planning',1)
        self.assertEqual(call('opencode','second','계획 작성')['profile'],'task-planning')
        self.assertEqual(call('opencode','first','로그인 구현')['profile'],'lifecycle-dev')
    def test_real_claude_hook_stdin(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,str(self.root/'.claude/agentflow-profile-hook.py')],
            input=json.dumps({'session_id':'claude-unit-native','cwd':str(self.root),'prompt':'작업계획전문가로 변경해줘'}),
            cwd=self.root,text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('task-planning',result.stdout)
        self.assertNotIn('작업계획전문가로 변경해줘',result.stdout)
    def test_opencode_v2_mock_hook_registers_and_injects_profile(self):
        import subprocess,sys,tempfile,shutil
        plugin=Path(__file__).resolve().parents[1]/'scaffold/.opencode/plugins/agentflow-profile.js'
        with tempfile.TemporaryDirectory() as tmp:
            module=Path(tmp)/'agentflow-profile.mjs'
            shutil.copyfile(plugin,module)
            script=Path(tmp)/'probe.mjs'
            script.write_text('''import {AgentFlowProfile} from './agentflow-profile.mjs';
let hooks={};await AgentFlowProfile({directory:process.argv[2],session:{hook:async(n,fn)=>{hooks[n]=fn}}});
if(!hooks.prompt)throw new Error('prompt hook missing');
const event={sessionID:'session-opencode-test',prompt:{text:'테스트 신규 작업'}};
await hooks.prompt(event);
if(!event.prompt.text.includes('Profile: lifecycle-dev')) throw new Error(event.prompt.text);
console.log('OPENCODE_PROMPT_ADAPTER_MOCK_PASS');''')
            p=subprocess.run(['node',str(script),str(self.root)],cwd=self.root,capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('MOCK_PASS',p.stdout)
