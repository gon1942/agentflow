"""RC3 regression of real HTTP write paths, novice profile workflow, policy guards.
Tests use a temporary project and local fixture; they do not claim native host E2E.
"""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from test_skill_studio import ConsoleTests
from scaffold.agentflow_console.server import make_handler
from scaffold.agentflow_console.core import ManagementError

class RC3HTTPTests(ConsoleTests):
    def setUp(self):
        super().setUp()
        self.srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'test-token'))
        self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.srv.server_close);self.addCleanup(self.srv.shutdown)
        self.base=f'http://127.0.0.1:{self.srv.server_port}'

    def post(self,endpoint,data,headers=None):
        hdr={'X-AgentFlow-Token':'test-token','Content-Type':'application/json','Origin':self.base}
        hdr.update(headers or {})
        req=Request(self.base+endpoint,data=json.dumps(data).encode(),headers=hdr)
        try:
            with urlopen(req,timeout=4) as reply:return reply.status,json.load(reply)
        except HTTPError as e:return e.code,json.load(e)

    def test_failed_template_returns_json_409_not_network_disconnect(self):
        code,result=self.post('/api/profile/template',{'template':'no-such-template'})
        self.assertEqual(code,409);self.assertEqual(result['error'],'NOT_FOUND')

    def test_template_duplicate_returns_json_409(self):
        self.assertEqual(self.manager.profile('storyboard')['id'],'storyboard')
        code,result=self.post('/api/profile/template',{'template':'storyboard'})
        self.assertEqual(code,409);self.assertEqual(result['error'],'TEMPLATE_ALREADY_INSTALLED')

    def test_custom_profile_create_activates_and_preserves_gates(self):
        code,result=self.post('/api/profile/create',{'id':'my-storyboard','name':'내 스토리보드'})
        self.assertEqual(code,200);self.assertEqual(result['skill_tree'],'my-storyboard')
        tree=self.manager.tree('my-storyboard')
        self.assertEqual([s['id'] for s in tree['stages']],__import__('scaffold.agentflow_console.core',fromlist=['ORDER']).ORDER)
        self.assertEqual(next(x for x in tree['stages'] if x['id']=='GATE1')['agent'],'user')
        self.assertEqual(next(x for x in tree['stages'] if x['id']=='VERIFY')['agent'],'verifier')
        self.assertEqual(self.post('/api/profile/activate',{'profile':'my-storyboard','generation':1})[0],200)
        self.assertEqual(self.manager.runtime_contract()['profile']['id'],'my-storyboard')

    def test_profile_create_validation_and_busy_block_returns_error_json(self):
        self.assertEqual(self.post('/api/profile/create',{'id':'BAD ID','name':'oops'})[0],409)
        (self.root/'docs/tasks/active/BUSY-001').mkdir()
        code,data=self.post('/api/profile/create',{'id':'my-profile','name':'My profile'})
        self.assertEqual(code,409);self.assertTrue(data['error'].startswith('TASK_ACTIVE'))
        self.assertFalse((self.root/'.agentflow/profiles/my-profile.json').exists())

    def test_inspect_then_install_then_connect_to_custom_tree(self):
        src=self._local('my-custom-skill')
        code,manifest=self.post('/api/skill/inspect',{'kind':'local','source':str(src)})
        self.assertEqual(code,200);self.assertEqual(manifest['name'],'my-custom-skill')
        code,result=self.post('/api/skill/install',{'kind':'local','source':str(src),'approved':True})
        self.assertEqual(code,200);self.assertTrue(result['verified']['verified'])
        self.manager.create_profile('custom','Custom')
        tree=self.manager.tree('custom')
        tree['stages'][1]['skills'].append({'name':'my-custom-skill','required':False,'condition':'optional'})
        code,_=self.post('/api/tree/save',tree)
        self.assertEqual(code,200)
        self.assertEqual(self.post('/api/profile/activate',{'profile':'custom','generation':1})[0],200)

    def test_write_origin_denied_without_side_effect(self):
        code,result=self.post('/api/profile/create',{'id':'bad-origin','name':'Oops'}, {'Origin':'https://bad.test'})
        self.assertEqual(code,403)
        self.assertFalse((self.root/'.agentflow/profiles/bad-origin.json').exists())

    def test_short_query_with_profile_stage_reaches_host(self):
        from unittest.mock import patch
        from scaffold.agentflow_console import ai
        class HostResult:
            returncode = 0
            stdout = b'Candidate: brainstorming (verified locally)'
            stderr = b''
        self.manager.create_profile('ux-mngr', '화면설계전문가')
        with patch.object(ai.shutil,'which',return_value='/usr/bin/opencode'),patch.object(ai.subprocess,'run',return_value=HostResult()) as execute:
            code,result=self.post('/api/ai/suggest',{'host':'opencode','question':'분석','profile':'ux-mngr','stage':'ANALYZE'})
        self.assertEqual(code,200,result)
        self.assertEqual(result['profile'],'ux-mngr')
        self.assertEqual(result['stage'],'ANALYZE')
        prompt=execute.call_args.args[0][-1]
        self.assertIn('User request: 분석',prompt)
        self.assertIn('Profile ID: ux-mngr',prompt)
        self.assertIn('Target stage: ANALYZE',prompt)
        self.assertFalse(result['installation']=='RUN')

    def test_blank_query_and_non_skill_stage_are_rejected_without_host(self):
        from unittest.mock import patch
        from scaffold.agentflow_console import ai
        with patch.object(ai.subprocess,'run') as execute:
            code,body=self.post('/api/ai/suggest',{'host':'opencode','question':'  '})
            self.assertEqual(code,409)
            self.assertEqual(body['error'],'INVALID_AI_QUERY')
            code,body=self.post('/api/ai/suggest',{'host':'opencode','question':'UI','stage':'GATE1'})
            self.assertEqual(code,409)
            self.assertEqual(body['error'],'INVALID_AI_STAGE')
            execute.assert_not_called()

    def test_opencode_command_and_natural_language_contract(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]/'scaffold'
        cmd=(root/'.opencode/commands/agentflow-mngr.md').read_text()
        self.assertIn('python3 agentflow_console.py start --browser',cmd)
        for path in ('AGENTS.md','docs/workflow/WORKFLOW.md','.opencode/agents/coordinator.md'):
            value=(root/path).read_text()
            self.assertIn('python3 agentflow_console.py start --browser',value)
            self.assertNotIn('python3 agentflow_console.py open --browser',value)

class RC3WorkflowProtectionTests(ConsoleTests):
    def test_custom_profile_cannot_remove_gate_or_independent_verifier(self):
        self.manager.create_profile('ux-writer','UX Writer')
        original=self.manager.tree('ux-writer')
        tree=json.loads(json.dumps(original))
        tree['stages']=[s for s in tree['stages'] if s['id']!='GATE1']
        with self.assertRaisesRegex(Exception,'PROTECTED_STAGE_ORDER'):
            self.manager.save_tree(tree)
        tree=json.loads(json.dumps(original))
        next(s for s in tree['stages'] if s['id']=='VERIFY')['agent']='coordinator'
        with self.assertRaisesRegex(Exception,'PROTECTED_INDEPENDENCE_OR_GATE'):
            self.manager.save_tree(tree)

    def test_all_templates_preserve_common_workflow(self):
        from scaffold.agentflow_console.core import ORDER
        for name in self.manager.list_templates():
            profile=self.manager.profile(name) if name in ('storyboard','task-planning') else self.manager.add_template(name)
            tree=self.manager.tree(profile['skill_tree'])
            self.assertEqual([s['id'] for s in tree['stages']],ORDER)
        storyboard=self.manager.tree('storyboard')
        self.assertIn('STORYBOARD',next(s for s in storyboard['stages'] if s['id']=='IMPLEMENT')['activities'])

class RC3DirectSkillTests(ConsoleTests):
    def test_editor_skill_preview_install_hash_and_approval(self):
        payload={'name':'my-ui-skill','description':'기본 스토리보드 제작과 검증을 돕는 자체 스킬', 'instructions':'## 역할\n화면 단위로 사용자 흐름을 분석하고 검증 기준을 작성합니다.'}
        preview=self.manager.inspect_created_skill(**payload)
        self.assertEqual(preview['name'],'my-ui-skill')
        self.assertIn('name: my-ui-skill',preview['preview'])
        with self.assertRaisesRegex(Exception,'EXPLICIT_INSTALL_APPROVAL_REQUIRED'):
            self.manager.install_created_skill(**payload)
        installed=self.manager.install_created_skill(**payload,approved=True)
        self.assertTrue(installed['verified']['verified'])
        self.assertEqual(installed['native_skill_load'],'NOT_VERIFIED')
        with self.assertRaisesRegex(Exception,'SKILL_ALREADY_EXISTS'):
            self.manager.install_created_skill(**payload,approved=True)

    def test_editor_frontmatter_and_size_validation(self):
        payload={'name':'bad-skill','description':'safe description\nname: malicious','instructions':'## Role\nThis instruction is long enough to pass minimum size.'}
        with self.assertRaisesRegex(Exception,'SKILL_DESCRIPTION_INVALID'):
            self.manager.inspect_created_skill(**payload)
        payload['description']='Clean description for skill'
        payload['instructions']='too short'
        with self.assertRaisesRegex(Exception,'SKILL_INSTRUCTIONS_INVALID'):
            self.manager.inspect_created_skill(**payload)

    def test_direct_skill_http_full_roundtrip(self):
        from http.server import ThreadingHTTPServer
        from scaffold.agentflow_console.server import make_handler
        srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'test-token'))
        th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
        self.addCleanup(srv.server_close);self.addCleanup(srv.shutdown)
        base=f'http://127.0.0.1:{srv.server_port}'
        payload={'name':'example-ui-skill','description':'Build accessible friendly interfaces','instructions':'## Instructions\nEvaluate UI flows and capture evidence for each test.'}
        def post(url,data):
            req=Request(base+url,data=json.dumps(data).encode(),headers={'X-AgentFlow-Token':'test-token','Content-Type':'application/json','Origin':base})
            with urlopen(req,timeout=5) as response:return json.load(response)
        self.assertIn('preview',post('/api/skill/create/inspect',payload))
        self.assertTrue(post('/api/skill/create/install',{**payload,'approved':True})['installed'])
        self.assertTrue(self.manager.verify_skill('example-ui-skill')['verified'])

class RC3ZipUploadTests(ConsoleTests):
    def test_upload_zip_inspect_and_install_digest_binding(self):
        import base64
        with __import__('io').BytesIO() as out:
            with __import__('zipfile').ZipFile(out,'w') as z:
                z.writestr('SKILL.md','---\nname: uploaded-skill\ndescription: uploaded zip\n---\n## Instruction\nDo good work.\n')
            archive=out.getvalue()
        preview=self.manager.inspect_uploaded_zip(archive)
        self.assertEqual(preview['name'],'uploaded-skill')
        with self.assertRaisesRegex(Exception,'SOURCE_CHANGED'):
            self.manager.install_uploaded_zip(archive,'0'*64,True)
        result=self.manager.install_uploaded_zip(archive,preview['archive_sha256'],True)
        self.assertTrue(result['verified']['verified'])
        self.assertEqual(result['native_skill_load'],'NOT_VERIFIED')

    def test_zip_upload_http_endpoints(self):
        import base64,io,zipfile
        mem=io.BytesIO()
        with zipfile.ZipFile(mem,'w') as z:
            z.writestr('my-skill/SKILL.md','---\nname: ui-upload\ndescription: zip from browser\n---\n## Purpose\nAnalyze UI results.\n')
        payload={'archive_base64':base64.b64encode(mem.getvalue()).decode()}
        from scaffold.agentflow_console.server import make_handler
        srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'test-token'))
        th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
        self.addCleanup(srv.server_close);self.addCleanup(srv.shutdown)
        base=f'http://127.0.0.1:{srv.server_port}'
        def post(path,data):
            req=Request(base+path,data=json.dumps(data).encode(),headers={'X-AgentFlow-Token':'test-token','Content-Type':'application/json','Origin':base})
            with urlopen(req,timeout=5) as res:return json.load(res)
        inspected=post('/api/skill/upload/inspect',payload)
        self.assertEqual(inspected['name'],'ui-upload')
        installed=post('/api/skill/upload/install',{**payload,'archive_sha256':inspected['archive_sha256'],'approved':True})
        self.assertTrue(installed['verified']['verified'])

