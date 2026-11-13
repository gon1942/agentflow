"""v0.7.7 console, skills and legacy compatibility acceptance tests."""
import json,unittest
from pathlib import Path
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.core import ManagementError

class ProfileConsoleV077(unittest.TestCase):
    setUp=ThreeDefaultProfiles.setUp
    def test_visible_profiles_and_legacy_resolver(self):
        self.assertEqual({p['id'] for p in self.manager.list_profiles()}, {'lifecycle-dev','development-worker','project-architect','storyboard','task-planning'})
        self.assertEqual(self.manager.active()['profile'],'lifecycle-dev')
        self.assertEqual(self.manager.profile('development')['id'],'development')
        self.assertEqual(self.manager.runtime_contract('development')['profile']['id'],'development')
        with self.assertRaisesRegex(ManagementError,'LEGACY_PROFILE_USE_LIFECYCLE_DEV'):
            self.manager.activate('development',1)
        self.manager.activate('lifecycle-dev',1)
        self.assertEqual(self.manager.active()['profile'],'lifecycle-dev')
    def test_architect_default_stage_skills_present_and_verified(self):
        p=self.manager.profile('project-architect');t=self.manager.tree(p['skill_tree'])
        expected={'ANALYZE':['requirements-analyst','change-impact-analyzer'],'PLAN':['project-manager'],'IMPLEMENT':['system-architect','architecture-decision-records'],'VERIFY':['traceability-auditor'],'REVIEW':['design-review','security-auditor']}
        for stage in t['stages']:
            if stage['id'] in expected:
                self.assertEqual([i['name'] for i in stage['skills']],expected[stage['id']])
                for n in expected[stage['id']]:self.assertTrue(self.manager.verify_skill(n)['verified'])
        self.assertEqual(self.manager.missing_skills(t,p),[])
        self.manager.activate('project-architect',1)
        self.assertEqual(self.manager.runtime_contract()['profile']['id'],'project-architect')
    def test_console_commands_are_explicit_and_project_limited(self):
        root=self.root
        op=(root/'.opencode/commands/agentflow-mngr.md').read_text()
        self.assertIn('agentflow_console.py start --browser',op)
        self.assertIn('agentflow_console.py stop',op)
        self.assertIn('agentflow_console.py console-status',op)
        self.assertIn('인수가 없으면',op)
        for sub in ('.claude/skills','.agents/skills'):
            txt=(root/sub/'agentflow-mngr/SKILL.md').read_text()
            self.assertIn('agentflow_console.py stop',txt)
            self.assertIn('agentflow_console.py start --browser',txt)
        for verb in ('start','stop','status'):
            self.assertFalse((root/'.opencode/commands'/f'agentflow-mngr-{verb}.md').exists())
    def test_session_rotation_keeps_immutable_legacy_contract(self):
        from scaffold.agentflow_console.contexts import ContextRegistry
        reg=ContextRegistry(self.manager)
        task=self.root/'docs/tasks/active/LEGACY-001';task.mkdir()
        (task/'task-state.json').write_text(json.dumps({'task_id':'LEGACY-001','state':'PLAN_DRAFT'}))
        first=reg.pin_task('LEGACY-001', profile='development')
        self.manager.activate('project-architect',1)
        second=reg.task_contract('LEGACY-001')
        self.assertEqual(first['contract_sha256'],second['contract_sha256'])
        self.assertEqual(second['profile'],'development')

if __name__=='__main__':unittest.main()
