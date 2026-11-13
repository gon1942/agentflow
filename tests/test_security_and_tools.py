from pathlib import Path
import json, hashlib, importlib.util, io, tarfile, os, tempfile, subprocess, sys, tomllib, unittest
from unittest.mock import patch
from test_install import ROOT, installer, make_fixture, make_arch_fixture

# Load installer-only project-provisioning code without requiring global installation.
tools = installer.tool_provision
SCAFFOLD = ROOT / 'scaffold'

class PolicyAndToolsTests(unittest.TestCase):
    def test_implementer_task_approval_edit_guard_and_claude_tools(self):
        impl = (SCAFFOLD/'.opencode/agents/implementer.md').read_text()
        self.assertIn('"docs/tasks/**": deny',impl)
        self.assertIn('"**/docs/tasks/**": deny',impl)
        for name in ('verifier','reviewer'):
            claude=(SCAFFOLD/f'.claude/agents/{name}.md').read_text()
            self.assertIn('disallowedTools: Write, Edit, NotebookEdit',claude)
        self.assertIn('tools: Read, Grep, Glob',(SCAFFOLD/'.claude/agents/improver.md').read_text())
        self.assertIn('edit: deny',(SCAFFOLD/'.opencode/agents/improver.md').read_text())
        self.assertIn('improver: allow',(SCAFFOLD/'.opencode/agents/coordinator.md').read_text())

    def test_workflow_single_source_and_gate2_hash_recheck(self):
        a=(SCAFFOLD/'AGENTS.md').read_text()
        w=(SCAFFOLD/'docs/workflow/WORKFLOW.md').read_text()
        approval=(SCAFFOLD/'docs/workflow/APPROVALS.md').read_text()
        self.assertIn('유일한 정본',a)
        self.assertIn('유일한 진행 순서',w)
        self.assertIn('다시 계산',approval)
        progress=(SCAFFOLD/'docs/templates/task/progress.md').read_text()
        self.assertEqual(progress.count('stage: ANALYZE'),0)
        self.assertEqual(progress.count('status: ANALYZE'),1)
        self.assertIn('NOT_MEASURED',progress)

    def test_codex_agent_config_not_duplicate_agents_mapping(self):
        cfg=tomllib.loads((SCAFFOLD/'.codex/config.toml').read_text())
        self.assertTrue(cfg['features']['multi_agent'])
        self.assertNotIn('agents',cfg)
        for role in ('implementer','verifier','reviewer','improver'):
            config=tomllib.loads((SCAFFOLD/f'.codex/agents/{role}.toml').read_text())
            self.assertEqual(config['name'],role)
            self.assertTrue(config['developer_instructions'])

    def test_rtk_only_project_local_even_if_fake_global_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'proj';root.mkdir()
            p=tools.paths(root)['rtk'];p.parent.mkdir(parents=True)
            p.write_text('#!/bin/sh\necho "rtk 1.1.0"\n');p.chmod(0o755)
            result=tools.install_rtk(root,offline=True)
            self.assertEqual(result['status'],'READY')
            self.assertTrue(result['reused'])
            p.unlink()
            with patch.dict(os.environ,{'PATH':str(p.parent)+os.pathsep+os.environ.get('PATH','')}):
                self.assertEqual(tools.install_rtk(root,offline=True)['status'],'BLOCKED')

    def test_crg_local_and_manifest_marks_unverified_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'proj';root.mkdir()
            (root/'.ai-dev').mkdir()
            (root/'.ai-dev/external-skills.lock.json').write_text('{}')
            rtk=tools.paths(root)['rtk'];rtk.parent.mkdir(parents=True)
            rtk.write_text('#!/bin/sh\necho "rtk 1.1.0"\n');rtk.chmod(0o755)
            crg=tools.paths(root)['crg'];crg.parent.mkdir(parents=True)
            crg.write_text('#!/bin/sh\necho "code-review-graph 2.3.9"\n');crg.chmod(0o755)
            result=tools.provision(root,offline=True,browser=False)
            self.assertEqual(result['status'],'READY')
            content=json.loads(tools.paths(root)['lock'].read_text())
            self.assertEqual(content['scope'],'PROJECT_ONLY')
            self.assertFalse(content['results']['rtk']['hook_verified'])
            self.assertFalse(content['results']['crg']['mcp_verified'])
            self.assertFalse((root/'teamdev').exists())

    def test_project_tools_symlink_escape_blocked_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'proj';root.mkdir()
            (root/'.ai-dev').mkdir()
            (root/'.ai-dev/external-skills.lock.json').write_text('{}')
            outside=Path(tmp)/'outside';outside.mkdir()
            (root/'.ai-dev/tools').symlink_to(outside,target_is_directory=True)
            result=tools.provision(root,offline=True)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertEqual(result['reason'],'PROJECT_TOOL_SYMLINK')
            self.assertEqual(list(outside.iterdir()),[])

    def test_rtk_checksum_mismatch_blocks_before_binary_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'proj';root.mkdir()
            class FakeResponse:
                def __init__(self,b):self.b=b
                def __enter__(self):return self
                def __exit__(self,*args):return None
                def read(self,*args):return self.b
            def fake_url(url,timeout=None):
                if url.endswith('checksums.txt'):
                    return FakeResponse(b'0'*64+b'  rtk-x86_64-unknown-linux-musl.tar.gz\n')
                return FakeResponse(b'not-real')
            with patch.object(tools.platform,'system',return_value='Linux'),patch.object(tools.platform,'machine',return_value='x86_64'),patch.object(tools.urllib.request,'urlopen',fake_url):
                x=tools.install_rtk(root)
            self.assertEqual(x['status'],'BLOCKED')
            self.assertFalse(tools.paths(root)['rtk'].exists())

    def test_browser_offline_no_global_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'proj';root.mkdir()
            with patch.object(tools,'browser_state',return_value={'chrome_path':'/usr/bin/google-chrome-stable','node':'/usr/bin/node','npm':'/usr/bin/npm','versions_match':False}):
                ret=tools.install_browser(root,offline=True)
            self.assertEqual(ret['status'],'BLOCKED')
            self.assertEqual(ret['reason'],'BROWSER_NOT_CACHED')

    def test_install_cli_provisions_tools_without_global_fallback(self):
        blob,hashes,helper_hashes,_=make_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(installer,'EXPECTED_SKILLS',hashes),patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
            root=Path(tmp)/'proj';zipfile=Path(tmp)/'upstream.zip';zipfile.write_bytes(blob)
            import contextlib
            with patch.object(installer.architect,'load_package',return_value=make_arch_fixture()),patch.object(tools,'provision',return_value={'status':'BLOCKED','results':{'rtk':{'status':'BLOCKED'}}}) as mock_provision,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                code=installer.main([str(root),'--upstream-zip',str(zipfile)])
            self.assertEqual(code,2)
            mock_provision.assert_called_once()
            self.assertTrue((root/'.ai-dev/external-skills.lock.json').is_file())
            with patch.object(installer.architect,'load_package',return_value=make_arch_fixture()),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(installer.main([str(root),'--upstream-zip',str(zipfile),'--skip-tools']),0)

    def test_session_detects_global_skill_shadowing_without_writing_global(self):
        src=(SCAFFOLD/'.opencode/lib/session-status.js')
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);project=base/'project';home=base/'home'
            loc=project/'.opencode/skills/brainstorming/SKILL.md';loc.parent.mkdir(parents=True);loc.write_text('original')
            glob=home/'.config/opencode/skills/brainstorming/SKILL.md';glob.parent.mkdir(parents=True);glob.write_text('different global')
            js=f"""import {{findGlobalSkillConflicts}} from {json.dumps(src.as_uri())};
            const found=await findGlobalSkillConflicts({json.dumps(str(project))},{json.dumps(str(home))});
            if(JSON.stringify(found)!=='[\"brainstorming\"]')throw Error(JSON.stringify(found));"""
            res=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True,timeout=20)
            self.assertEqual(res.returncode,0,res.stderr)
            self.assertEqual(glob.read_text(),'different global')

    def test_native_skill_observer_records_only_metadata(self):
        src=(SCAFFOLD/'.opencode/plugins/skill-observer.js')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f=root/'.opencode/skills/brainstorming/SKILL.md';f.parent.mkdir(parents=True)
            f.write_text('fixture-original')
            js=f'''import {{AgentFlowSkillObserver}} from {json.dumps(src.as_uri())};
            const hooks=await AgentFlowSkillObserver({{directory:{json.dumps(str(root))}}});
            await hooks['tool.execute.after']({{tool:'skill',sessionID:'sess-1',callID:'call-1',args:{{name:'brainstorming',secret:'LEAK-NOT-ALLOWED'}}}},{{}});
            '''
            run=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            out=(root/'.ai-dev/observations/skill-tool-events.jsonl').read_text()
            self.assertIn('NATIVE_SKILL_TOOL_CALL_OBSERVED',out)
            self.assertNotIn('LEAK-NOT-ALLOWED',out)
            record=json.loads(out)
            self.assertEqual(record['source_resolution'],'NOT_VERIFIED')
            self.assertEqual(record['project_local_sha256'],hashlib.sha256(b'fixture-original').hexdigest())

if __name__=='__main__':unittest.main()
