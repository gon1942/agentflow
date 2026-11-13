"""Git SHA diagnosis and explicit GitHub SHA resolution regression tests."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from scaffold.agentflow_console import external
from scaffold.agentflow_console.core import Manager, ManagementError
from scaffold.agentflow_console.server import make_handler
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import threading

class GitResolveTests(unittest.TestCase):
    def test_default_branch_sha_resolved_but_not_installed(self):
        sha='a'*40
        with patch.object(external,'_json',side_effect=[{'default_branch':'main'},{'sha':sha}]) as get:
            r=external.resolve_github_commit('https://github.com/example/repo.git')
        self.assertEqual(r['commit'],sha)
        self.assertEqual(r['source'],'GITHUB_DEFAULT_BRANCH_LOOKUP_NOT_SECURITY_AUDIT')
        self.assertEqual(get.call_count,2)

    def test_reject_untrusted_urls_before_network(self):
        for url in ('http://github.com/x/y','https://evil.com/x/y','https://github.com.evil.com/x/y',
                    'https://user:pass@github.com/x/y','file:///tmp/repo','https://github.com/x/y?token=secret',
                    'https://github.com/x/y/../../etc',''):
            with self.subTest(url=url),patch.object(external,'_json') as get:
                with self.assertRaises(ValueError):external.resolve_github_commit(url)
                get.assert_not_called()

    def test_reject_unpinned_inspection(self):
        with self.assertRaisesRegex(ManagementError,'PINNED_COMMIT_REQUIRED'):
            Manager._git_fields('https://github.com/example/repo.git','', 'skills/foo')

    def test_ui_has_explicit_sha_resolution_and_preflight(self):
        source=(Path(__file__).resolve().parents[1]/'scaffold/agentflow_console/ui.html').read_text()
        self.assertIn('onclick="resolveGitCommit()"',source)
        self.assertIn('40자리 Commit SHA가 필요합니다.',source)
        self.assertIn("show('skills');setGitCandidate(c.url,c.commit,c.subdir)",source)
        self.assertIn("resetGitInspection('새 스킬 후보를 선택했습니다.",source)
        self.assertIn("$('installGitBtn').disabled=true",source)

    def test_http_sha_resolution_and_reject_missing_commit(self):
        class Stub:
            def inspect_git(self,*args):
                return {'called':True}
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Stub(),'token'))
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            def post(path,payload):
                req=Request(base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-AgentFlow-Token':'token','Origin':base})
                with urlopen(req,timeout=3) as r:return r.status,json.load(r)
            with patch.object(external,'resolve_github_commit',return_value={'commit':'a'*40,'repository':'a/b','branch':'main'}) as fn:
                code,body=post('/api/skill/git/resolve',{'url':'https://github.com/a/b'})
            self.assertEqual(code,200)
            self.assertEqual(body['commit'],'a'*40)
            fn.assert_called_once()
        finally:
            server.shutdown();server.server_close();t.join(timeout=3)

if __name__=='__main__': unittest.main()
