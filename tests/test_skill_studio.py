"""Real unit/integration tests with synthetic upstream fixture (not native worker E2E)."""
from test_install import make_arch_fixture
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_install import make_fixture, installer

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('skillcore',ROOT/'scaffold/agentflow_console/core.py')
core=importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project'
        archive, skills, helpers, _=make_fixture()
        with patch.object(installer,'EXPECTED_SKILLS',skills), patch.object(installer,'EXPECTED_HELPERS',helpers):
            installer.install(self.root,ROOT,archive, architect_package=make_arch_fixture())
        self.manager=core.Manager(self.root)

    def _local(self,name='example-skill'):
        dest=Path(self.temp.name)/name
        dest.mkdir()
        (dest/'SKILL.md').write_text(f'---\nname: {name}\ndescription: test\n---\nHello\n')
        (dest/'helper.txt').write_text('A helper file')
        return dest

    def test_default_profile_contract_and_hash_verified(self):
        result=self.manager.runtime_contract()
        self.assertEqual(result['profile']['id'],'development')
        self.assertEqual(result['profile']['primary_agent'],'coordinator')
        self.assertEqual(len(self.manager.list_skills()),7)
        self.assertEqual(result['native_skills_loaded'],'NOT_VERIFIED')
        self.assertEqual([s['id'] for s in result['tree']['stages']],core.ORDER)
        self.assertFalse(self.manager.missing_skills(result['tree']))

    def test_clone_profile_and_activate(self):
        profile=self.manager.clone_profile('development','storyboard-copy','Storyboard Copy')
        self.assertEqual(profile['skill_tree'],'storyboard-copy')
        old=self.manager.active()
        active=self.manager.activate('storyboard-copy',old['generation'])
        self.assertEqual(active['generation'],2)
        with self.assertRaisesRegex(core.ManagementError,'CONFIG_VERSION_CONFLICT'):
            self.manager.activate('development',1)

    def test_protected_stages_skills_and_human_gates(self):
        t=self.manager.tree('development')
        for sid in ['GATE1','GATE2','VERIFY','REVIEW','IMPLEMENT']:
            modified=json.loads(json.dumps(t))
            stage=next(x for x in modified['stages'] if x['id']==sid)
            if sid.startswith('GATE'):
                stage['agent']='coordinator'
            else:
                stage['skills']=[]
            with self.subTest(sid=sid),self.assertRaises(core.ManagementError):
                self.manager.save_tree(modified)
        bad=json.loads(json.dumps(t));bad['stages'].reverse()
        with self.assertRaisesRegex(core.ManagementError,'PROTECTED_STAGE_ORDER'):
            self.manager.save_tree(bad)

    def test_optional_extension_to_development(self):
        src=self._local()
        self.manager.install_skill('local',str(src),True)
        t=self.manager.tree('development')
        t['stages'][1]['skills'].append({'name':'example-skill','required':False,'condition':'optional'})
        self.manager.save_tree(t)
        self.assertEqual(self.manager.tree('development')['stages'][1]['skills'][-1]['name'],'example-skill')

    def test_active_task_blocks_config_mutations_but_allows_default_switch(self):
        (self.root/'docs/tasks/active/TEST-001').mkdir()
        with self.assertRaisesRegex(core.ManagementError,'ACTIVE_TASK_CONTEXT_NOT_PINNED'):
            self.manager.activate('development',1)
        with self.assertRaisesRegex(core.ManagementError,'TASK_ACTIVE'):
            self.manager.clone_profile('development','new-profile','New')
        with self.assertRaisesRegex(core.ManagementError,'TASK_ACTIVE'):
            self.manager.install_skill('local',str(self._local()),True)
        with self.assertRaisesRegex(core.ManagementError,'TASK_ACTIVE'):
            self.manager.save_tree(self.manager.tree('development'))

    def test_install_local_three_agents_and_lock(self):
        src=self._local()
        inspect=self.manager.inspect_local(str(src),'local')
        self.assertEqual(inspect['file_count'],2)
        with self.assertRaisesRegex(core.ManagementError,'EXPLICIT_INSTALL_APPROVAL_REQUIRED'):
            self.manager.install_skill('local',str(src))
        result=self.manager.install_skill('local',str(src),True)
        self.assertTrue(result['verified']['verified'])
        self.assertEqual(result['native_skill_load'],'NOT_VERIFIED')
        for folder in core.SKILL_ROOTS:
            self.assertEqual((self.root/folder/'example-skill/helper.txt').read_text(),'A helper file')
        lock=json.loads((self.root/'.ai-dev/external-skills.lock.json').read_text())
        self.assertIn('example-skill',lock['managed_skills'])
        with self.assertRaisesRegex(core.ManagementError,'SKILL_ALREADY_EXISTS'):
            self.manager.install_skill('local',str(src),True)
        (self.root/'.claude/skills/example-skill/helper.txt').write_text('tamper')
        self.assertFalse(self.manager.verify_skill('example-skill')['verified'])

    def test_zip_import_and_unsafe_zip_entries(self):
        path=Path(self.temp.name)/'skill.zip'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('folder/SKILL.md','---\nname: zipped-skill\n---\nHello\n')
            z.writestr('folder/templates/x.txt','x')
        self.assertEqual(self.manager.inspect_local(str(path),'zip')['name'],'zipped-skill')
        self.manager.install_skill('zip',str(path),True)
        self.assertTrue(self.manager.verify_skill('zipped-skill')['verified'])
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('../outside','bad')
            z.writestr('SKILL.md','---\nname: oops\n---\n')
        with self.assertRaisesRegex(core.ManagementError,'UNSAFE_ARCHIVE_ENTRY'):
            self.manager.inspect_local(str(path),'zip')
        self.assertFalse((self.root/'outside').exists())

    def test_local_symlinks_and_untrusted_directory_rejected(self):
        src=self._local()
        (src/'linked').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(core.ManagementError,'SYMLINK_SOURCE_REJECTED'):
            self.manager.inspect_local(str(src),'local')

    def test_existing_user_skill_never_overwritten(self):
        src=self._local()
        dest=self.root/'.opencode/skills/example-skill'
        dest.mkdir()
        (dest/'SKILL.md').write_text('DO NOT ALTER')
        with self.assertRaisesRegex(core.ManagementError,'SKILL_DESTINATION_EXISTS'):
            self.manager.install_skill('local',str(src),True)
        self.assertEqual((dest/'SKILL.md').read_text(),'DO NOT ALTER')
        self.assertFalse((self.root/'.claude/skills/example-skill').exists())

    def test_profile_requires_installed_skills(self):
        self.manager.clone_profile('development','storyboard-copy','Storyboard Copy')
        t=self.manager.tree('storyboard-copy')
        t['stages'][1]['skills'].append({'name':'not-installed','required':True,'condition':'always'})
        self.manager.save_tree(t)
        with self.assertRaisesRegex(core.ManagementError,'SKILLS_MISSING'):
            self.manager.activate('storyboard-copy',1)
        self.assertEqual(self.manager.active()['profile'],'development')

    def test_symlinked_config_rejected(self):
        p=self.root/'.agentflow/active-profile.json'
        p.unlink();p.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(core.ManagementError,'SYMLINK_PATH_REJECTED'):
            self.manager.active()

    def test_optional_templates_and_storyboard_contract(self):
        self.assertEqual(self.manager.list_templates(),['analysis','bugfix','storyboard','task-planning'])
        result=self.manager.profile('storyboard')
        self.assertEqual(result['primary_agent'],'coordinator')
        tree=self.manager.tree('storyboard')
        self.assertEqual([s['id'] for s in tree['stages']],core.ORDER)
        self.assertIn('UI_DESIGN',next(s for s in tree['stages'] if s['id']=='IMPLEMENT')['activities'])
        self.assertIn('VALIDATION',next(s for s in tree['stages'] if s['id']=='VERIFY')['activities'])
        self.assertEqual(self.manager.activate('storyboard',1)['profile'],'storyboard')
        with self.assertRaisesRegex(core.ManagementError,'TEMPLATE_ALREADY_INSTALLED'):
            self.manager.add_template('storyboard')

    def test_legacy_task_blocks_profile_change(self):
        task=self.root/'docs/tasks/LEGACY-001'
        task.mkdir()
        (task/'progress.md').write_text('# Previous task status unknown')
        with self.assertRaisesRegex(core.ManagementError,'ACTIVE_TASK_CONTEXT_NOT_PINNED'):
            self.manager.activate('development',1)

    def test_workflow_policy_cannot_be_overridden(self):
        self.manager.clone_profile('development','custom-policy','Custom Policy')
        profile=self.manager.profile('custom-policy')
        profile['policy']='no-human-gates'
        with self.assertRaisesRegex(core.ManagementError,'PROTECTED_WORKFLOW_REQUIRED'):
            self.manager.save_profile(profile)
        contract=self.manager.runtime_contract()
        self.assertEqual(contract['protected_workflow']['human_gates'],['GATE1','GATE2'])
        self.assertIn('verifier',contract['protected_workflow']['independent_roles'])

    def test_custom_profile_can_add_new_specialized_stages(self):
        self.manager.clone_profile('development','custom-stage','Custom Stage')
        t=self.manager.tree('custom-stage')
        t['stages'].append({'id':'DOMAIN_EXPERT_RESEARCH','agent':'coordinator','skills':[]})
        self.manager.save_tree(t)
        self.assertEqual(self.manager.tree('custom-stage')['stages'][-1]['id'],'DOMAIN_EXPERT_RESEARCH')

    def test_ai_advisor_readonly_mock_and_unsupported_host(self):
        import importlib.util
        ai_path=ROOT/'scaffold/agentflow_console/ai.py'
        # Load the package through sys.path just like installed projects.
        sys.path.insert(0,str(ROOT/'scaffold'))
        try:
            from agentflow_console.ai import suggest
            with self.assertRaisesRegex(Exception,'UNSUPPORTED_AGENT_HOST'):
                suggest(self.manager,'unknown','recommend skills for design')
        finally:
            sys.path.remove(str(ROOT/'scaffold'))

    def test_unknown_stage_blocked(self):
        t=self.manager.tree('development');t['stages'].append({'id':'DO_ANYTHING','agent':'coordinator','skills':[]})
        with self.assertRaisesRegex(core.ManagementError,'PROTECTED_STAGE_ORDER'):
            self.manager.save_tree(t)
        t=self.manager.tree('development');t['stages'].append({'id':'evil/spoof','agent':'coordinator','skills':[]})
        with self.assertRaisesRegex(core.ManagementError,'STAGE_UNKNOWN'):
            self.manager.save_tree(t)

    def test_server_auth_and_state_transitions(self):
        from http.server import ThreadingHTTPServer
        from scaffold.agentflow_console.server import make_handler
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.manager,'test-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}'
        with self.assertRaises(HTTPError) as denied:
            urlopen(base+'/api/status')
        self.assertEqual(denied.exception.code,403)
        req=Request(base+'/api/status',headers={'X-AgentFlow-Token':'test-token'})
        self.assertEqual(json.loads(urlopen(req).read())['active_profile']['profile'],'development')
        payload=json.dumps({'profile':'development','generation':1}).encode()
        req=Request(base+'/api/profile/activate',data=payload,headers={'X-AgentFlow-Token':'test-token','Content-Type':'application/json','Origin':'https://attacker.example'})
        with self.assertRaises(HTTPError) as denied:
            urlopen(req)
        self.assertEqual(denied.exception.code,403)
        req=Request(base+'/api/profile/activate',data=payload,headers={'X-AgentFlow-Token':'test-token','Content-Type':'application/json','Origin':base})
        self.assertEqual(json.loads(urlopen(req).read())['generation'],2)

if __name__=='__main__':unittest.main()

class GitAndRemovalTests(ConsoleTests):
    """Inherits base cases as regression + extra destructive/pinned git scenarios."""
    def test_managed_removal_requires_approval_and_no_references(self):
        src=self._local('temporary-skill')
        self.manager.install_skill('local',str(src),True)
        with self.assertRaisesRegex(core.ManagementError,'EXPLICIT_REMOVE_APPROVAL_REQUIRED'):
            self.manager.remove_skill('temporary-skill')
        clone=self.manager.clone_profile('development','testing','Testing')
        tree=self.manager.tree('testing')
        tree['stages'][1]['skills'].append({'name':'temporary-skill','required':False,'condition':'optional'})
        self.manager.save_tree(tree)
        with self.assertRaisesRegex(core.ManagementError,'SKILL_REFERENCED_IN_TREE'):
            self.manager.remove_skill('temporary-skill',True)
        tree['stages'][1]['skills'].pop()
        self.manager.save_tree(tree)
        self.assertTrue(self.manager.remove_skill('temporary-skill',True)['removed'])
        self.assertFalse((self.root/'.opencode/skills/temporary-skill').exists())
        self.assertFalse(self.manager.verify_skill('temporary-skill')['verified'])
        with self.assertRaisesRegex(core.ManagementError,'ONLY_MANAGED_SKILLS_REMOVABLE'):
            self.manager.remove_skill('brainstorming',True)

    def test_managed_removal_preserves_modified_files(self):
        src=self._local('temporary-skill')
        self.manager.install_skill('local',str(src),True)
        target=self.root/'.claude/skills/temporary-skill/helper.txt'
        target.write_text('user edited')
        with self.assertRaisesRegex(core.ManagementError,'MODIFIED_SKILL_REFUSE_DELETE'):
            self.manager.remove_skill('temporary-skill',True)
        self.assertEqual(target.read_text(),'user edited')

    def test_pinned_local_git_archive_install_and_commit_validation(self):
        import subprocess
        repo=Path(self.temp.name)/'repo'
        skill=repo/'skills/my-git-skill'
        skill.mkdir(parents=True)
        (skill/'SKILL.md').write_text('---\nname: my-git-skill\n---\nTest\n')
        (skill/'guide.md').write_text('Guide')
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid','add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','test'],check=True)
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        source=repo.as_uri()
        info=self.manager.inspect_git(source,commit,'skills/my-git-skill')
        self.assertEqual(info['name'],'my-git-skill')
        with self.assertRaisesRegex(core.ManagementError,'EXPLICIT_INSTALL_APPROVAL_REQUIRED'):
            self.manager.install_git(source,commit,'skills/my-git-skill')
        self.manager.install_git(source,commit,'skills/my-git-skill',True)
        self.assertTrue(self.manager.verify_skill('my-git-skill')['verified'])
        with self.assertRaisesRegex(core.ManagementError,'PINNED_COMMIT_REQUIRED'):
            self.manager.inspect_git(source,'main','skills/my-git-skill')
        with self.assertRaisesRegex(core.ManagementError,'GIT_HTTPS_OR_LOCAL_URL_REQUIRED'):
            self.manager.inspect_git('http://example.com/evil',commit,'skills/my-git-skill')
