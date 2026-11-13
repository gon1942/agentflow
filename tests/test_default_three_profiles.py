"""Offline acceptance of the 3 shipped Profile/Tree combinations."""
from test_install import make_arch_fixture
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from test_install import make_fixture, installer
from scaffold.agentflow_console.core import Manager, ManagementError, ORDER

ROOT=Path(__file__).resolve().parents[1]

class ThreeDefaultProfiles(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'fresh';blob,skills,helpers,_=make_fixture()
        with patch.object(installer,'EXPECTED_SKILLS',skills),patch.object(installer,'EXPECTED_HELPERS',helpers):
            installer.install(self.root,ROOT,blob, architect_package=make_arch_fixture())
        self.manager=Manager(self.root)

    def test_all_profiles_installed_first_boot_development_active(self):
        self.assertEqual({p['id'] for p in self.manager.list_profiles()},{'lifecycle-dev','development-worker','project-architect','storyboard','task-planning'})
        self.assertTrue({'lifecycle-dev','development-worker','project-architect','storyboard','task-planning'}.issubset({t['id'] for t in self.manager.list_trees()}))
        self.assertEqual(self.manager.active()['profile'],'lifecycle-dev')
        self.assertEqual(len(self.manager.list_skills()),15)

    def test_tree_roles_and_real_skills_only(self):
        for name in ['development','storyboard','task-planning']:
            with self.subTest(name=name):
                profile=self.manager.profile(name);self.manager.validate_profile(profile)
                tree=self.manager.tree(name);self.manager.validate_tree(tree,name)
                self.assertEqual([x['id'] for x in tree['stages']], ORDER)
                self.assertEqual(self.manager.missing_skills(tree),[])
                self.assertEqual(next(x for x in tree['stages'] if x['id']=='VERIFY')['agent'],'verifier')
                self.assertEqual(next(x for x in tree['stages'] if x['id']=='REVIEW')['agent'],'reviewer')
                self.assertEqual(next(x for x in tree['stages'] if x['id']=='GATE1')['skills'],[])
        self.assertFalse(next(x for x in self.manager.tree('storyboard')['stages'] if x['id']=='IMPLEMENT')['skills'])
        self.assertEqual(next(x for x in self.manager.tree('task-planning')['stages'] if x['id']=='IMPLEMENT')['skills'][0]['name'],'writing-plans')

    def test_activate_and_edit_specialist_gates_but_not_development(self):
        for name in ['storyboard','task-planning']:
            current=self.manager.active()
            self.manager.activate(name,current['generation'])
            self.assertEqual(self.manager.runtime_contract()['profile']['id'],name)
            profile=self.manager.profile(name)
            profile['approval_gates']['GATE1']=False
            self.manager.save_profile(profile)
            self.assertFalse(self.manager.runtime_contract()['approval_gates']['GATE1'])
        bad=self.manager.profile('development');bad['approval_gates']={'GATE1':False,'GATE2':False}
        with self.assertRaises(ManagementError):self.manager.save_profile(bad)

    def test_reinstallation_idempotent_and_active_task_default_switch_keeps_task(self):
        blob,skills,helpers,_=make_fixture()
        with patch.object(installer,'EXPECTED_SKILLS',skills),patch.object(installer,'EXPECTED_HELPERS',helpers):
            self.assertEqual(installer.install(self.root,ROOT,blob, architect_package=make_arch_fixture())['written_files'],0)
        (self.root/'docs/tasks/active/TASK-001').mkdir()
        with self.assertRaisesRegex(ManagementError,'ACTIVE_TASK_CONTEXT_NOT_PINNED'):
            self.manager.activate('storyboard',1)

if __name__=='__main__':unittest.main()
