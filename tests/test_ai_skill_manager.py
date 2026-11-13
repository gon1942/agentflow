"""RC8 AI skill manager tests: use synthetic project, mocked native LLM/network."""
import json
from unittest.mock import patch
import unittest
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import test_skill_studio
from scaffold.agentflow_console.server import make_handler
from scaffold.agentflow_console import ai, external
from scaffold.agentflow_console.core import ManagementError

class AIManagerTests(unittest.TestCase):
    def setUp(self):
        test_skill_studio.ConsoleTests.setUp(self)
        self.srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'test-token'))
        self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.srv.server_close);self.addCleanup(self.srv.shutdown)
        self.base=f'http://127.0.0.1:{self.srv.server_port}'

    def post(self, endpoint, data):
        req=Request(self.base+endpoint,data=json.dumps(data).encode(),headers={'X-AgentFlow-Token':'test-token','Content-Type':'application/json','Origin':self.base})
        try:
            with urlopen(req,timeout=5) as reply:return reply.status,json.load(reply)
        except HTTPError as e:return e.code,json.load(e)

    def _response(self, names=None):
        names=names or [{'name':'brainstorming','origin':'local','stages':['ANALYZE'],'reason':'requirements'},
             {'name':'browser-qa','origin':'external','stages':['VERIFY'],'reason':'browser testing',
              'url':'https://github.com/example/skills.git', 'commit':'a'*40,'subdir':'skills/browser-qa'}]
        class Result:
            returncode=0
            stdout=json.dumps({'summary':'테스트 추천','recommendations':names},ensure_ascii=False).encode()
            stderr=b''
        return Result()

    def test_all_stages_and_verified_local_not_external(self):
        self.manager.create_profile('test1','Test 1')
        with patch.object(ai.shutil,'which',return_value='/usr/bin/opencode'),patch.object(ai.subprocess,'run',return_value=self._response()) as runner:
            code,result=self.post('/api/ai/suggest',{'host':'opencode','question':'브라우저 검증','profile':'test1','stage':'ALL'})
        self.assertEqual(code,200,result)
        self.assertEqual(result['stage'],'ALL')
        self.assertIn('VERIFY',result['stages'])
        self.assertEqual(result['recommendations'][0]['source_status'],'LOCAL_HASH_VERIFIED')
        self.assertFalse(result['recommendations'][1]['verified'])
        self.assertEqual(result['recommendations'][1]['source_status'],'SOURCE_NOT_VERIFIED')
        self.assertIn('Target stage: ALL',runner.call_args.args[0][-1])
        self.assertIn('Existing assignments:',runner.call_args.args[0][-1])

    def test_apply_local_requires_approval_and_validates(self):
        self.manager.create_profile('test1','Test 1')
        selection=[{'name':'brainstorming','stage':'VERIFY'}]
        self.assertEqual(self.post('/api/ai/apply-local',{'profile':'test1','assignments':selection})[0],409)
        code,result=self.post('/api/ai/apply-local',{'profile':'test1','assignments':selection,'approved':True})
        self.assertEqual(code,200,result)
        self.assertEqual(result['connected'],selection)
        self.assertIn('brainstorming',[s['name'] for s in next(x for x in self.manager.tree('test1')['stages'] if x['id']=='VERIFY')['skills']])
        code,again=self.post('/api/ai/apply-local',{'profile':'test1','assignments':selection,'approved':True})
        self.assertEqual(code,200)
        self.assertEqual(again['connected'],[])
        self.assertEqual(again['already_connected'],1)

    def test_invalid_batch_has_no_partial_writes(self):
        self.manager.create_profile('test1','Test 1')
        before=self.manager.tree('test1')
        payload={'profile':'test1','approved':True,'assignments':[{'name':'brainstorming','stage':'VERIFY'},{'name':'nonexistent','stage':'REVIEW'}]}
        code,data=self.post('/api/ai/apply-local',payload)
        self.assertEqual(code,409)
        self.assertEqual(before,self.manager.tree('test1'))
        payload['assignments']=[{'name':'brainstorming','stage':'GATE1'}]
        self.assertEqual(self.post('/api/ai/apply-local',payload)[0],409)
        self.assertEqual(before,self.manager.tree('test1'))

    def test_busy_blocks_apply(self):
        self.manager.create_profile('test1','Test 1')
        (self.root/'docs/tasks/active/BUSY').mkdir()
        code,data=self.post('/api/ai/apply-local',{'profile':'test1','assignments':[{'name':'brainstorming','stage':'VERIFY'}],'approved':True})
        self.assertEqual(code,409)
        self.assertIn('TASK_ACTIVE',data['error'])

    def test_parse_prevents_local_impersonation_and_gate(self):
        raw=json.dumps({'recommendations':[{'name':'not-installed','origin':'local','stages':['VERIFY','GATE1'],'reason':'unknown'},
                     {'name':'brainstorming','origin':'external','stages':['ANALYZE'],'reason':'verified'}]})
        rows,_=ai.parse_recommendations(raw,['brainstorming'],['VERIFY','ANALYZE'])
        self.assertEqual([(x['name'],x['origin'],x['stage']) for x in rows], [('not-installed','external','VERIFY'),('brainstorming','local','ANALYZE')])

    def test_external_search_uses_general_stage_not_user_request(self):
        self.manager.create_profile('test1','Test 1')
        with patch.object(ai.shutil,'which',return_value='/usr/bin/opencode'),patch.object(ai.subprocess,'run',return_value=self._response([])),patch.object(external,'_json',return_value={'items':[]}) as github:
            code,result=self.post('/api/ai/suggest',{'host':'opencode','question':'my PRIVATE internal specs','profile':'test1','stage':'VERIFY','search_external':True})
        self.assertEqual(code,200,result)
        self.assertEqual(result['external_search']['status'],'COMPLETED')
        self.assertNotIn('PRIVATE',str(github.call_args))
        self.assertIn('playwright',str(github.call_args))

    def test_external_pinning_requires_repository_path(self):
        def source(path):
            if path.startswith('/search/'):return {'items':[{'full_name':'trusted/repo','default_branch':'main'}]}
            if '/commits/' in path:return {'sha':'b'*40}
            return {'tree':[{'type':'blob','path':'skills/browser-check/SKILL.md'}]}
        with patch.object(external,'_json',side_effect=source):
            found=external.discover(['VERIFY'],set())
        self.assertEqual(found['status'],'COMPLETED')
        item=found['candidates'][0]
        self.assertEqual(item['commit'],'b'*40)
        self.assertEqual(item['subdir'],'skills/browser-check')
        self.assertFalse(item['verified'])
        self.assertEqual(item['source_status'],'GITHUB_REPO_PATH_PIN_VERIFIED_NOT_AUDITED')

    def test_native_cli_prefix_and_freetext_fallback(self):
        raw='> plan · model\n```json\n'+json.dumps({'recommendations':[{'name':'brainstorming','stages':['VERIFY'],'reason':'verified'}]})+'\n```'
        rows,_=ai.parse_recommendations(raw,['brainstorming'],['VERIFY'])
        self.assertEqual(rows[0]['name'],'brainstorming')
        rows,summary=ai.parse_recommendations('추천: brainstorming 및 testing', ['brainstorming'],['VERIFY'])
        self.assertEqual(rows[0]['name'],'brainstorming')
        self.assertEqual(rows[0]['origin'],'local')

    def test_pinned_git_install_then_approved_profile_connection(self):
        import subprocess
        from pathlib import Path
        repo=Path(self.temp.name)/'git-source'
        directory=repo/'skills/web-check';directory.mkdir(parents=True)
        (directory/'SKILL.md').write_text('---\nname: web-check\ndescription: browser verification\n---\nPerform web verification\n')
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid','add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','test'],check=True)
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        source={'url':repo.as_uri(),'commit':commit,'subdir':'skills/web-check'}
        self.manager.create_profile('test1','Test 1')
        inspected=self.post('/api/skill/git/inspect',source)
        self.assertEqual(inspected[0],200,inspected)
        code,data=self.post('/api/skill/git/install',{**source,'approved':True})
        self.assertEqual(code,200,data)
        self.assertTrue(data['verified']['verified'])
        code,data=self.post('/api/ai/apply-local',{'profile':'test1','assignments':[{'name':'web-check','stage':'VERIFY'}],'approved':True})
        self.assertEqual(code,200,data)
        self.assertEqual(data['connected'],[{'name':'web-check','stage':'VERIFY'}])
        self.assertEqual(data['native_skill_load'],'NOT_VERIFIED')

    def test_llm_natural_text_not_install_ready(self):
        rows,summary=ai.parse_recommendations('추천: 브라우저 테스트 스킬', ['brainstorming'],['VERIFY'])
        self.assertEqual(rows,[])

