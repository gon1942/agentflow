import sys, json, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scaffold.agentflow_console.core import Manager
from test_default_three_profiles import ThreeDefaultProfiles

class DashboardV060(unittest.TestCase):
    def setUp(self):
        self.fixture=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.m=self.fixture.manager
        self.root=self.m.root

    def test_empty_dashboard_has_all_fields(self):
        result=self.m.status()['dashboard']
        self.assertEqual(result['completed_count'],0)
        self.assertEqual(result['design_doc_count'],0)
        self.assertEqual(result['recent_tasks'],[])
        self.assertEqual(sum(result['status_counts'].values()),0)

    def test_plan_ready_remains_active_not_development_complete(self):
        path=self.root/'docs/tasks/active/LOGIN-001'
        path.mkdir(parents=True)
        (path/'task-state.json').write_text(json.dumps({'task_id':'LOGIN-001','state':'PLAN_READY'}))
        report=self.m.status()['dashboard']
        self.assertEqual(report['status_counts']['PLAN_READY'],1)
        self.assertEqual(report['completed_count'],0)
        self.assertEqual(report['recent_tasks'][0]['status'],'PLAN_READY')

    def test_completed_docs_and_in_progress_counts(self):
        completed=self.root/'docs/tasks/completed/DONE-001';completed.mkdir(parents=True)
        active=self.root/'docs/tasks/active/LOGIN-002';active.mkdir(parents=True)
        (active/'task-state.json').write_text(json.dumps({'task_id':'LOGIN-002','state':'WAITING_PLAN_APPROVAL'}))
        design=self.root/'docs/design';design.mkdir(parents=True,exist_ok=True)
        (design/'architecture.md').write_text('# Architecture')
        report=self.m.status()['dashboard']
        self.assertEqual(report['completed_count'],1)
        self.assertEqual(report['design_doc_count'],1)
        self.assertEqual(report['status_counts']['WAITING_PLAN_APPROVAL'],1)
        self.assertEqual(report['status_counts']['COMPLETED'],1)

    def test_legacy_task_visible_not_silently_dropped(self):
        (self.root/'docs/tasks/active/LEGACY-001').mkdir(parents=True)
        report=self.m.status()['dashboard']
        self.assertEqual(report['status_counts']['LEGACY_UNVERIFIED'],1)

if __name__=='__main__':unittest.main()
