import re
import unittest
from pathlib import Path

UI = (Path(__file__).resolve().parents[1] / 'scaffold/agentflow_console/ui.html').read_text()

class DashboardLayoutV075(unittest.TestCase):
    def test_operational_panels_precede_document_tiles_and_flow(self):
        section = UI.split('<section id="dashboard"',1)[1].split('</section>',1)[0]
        positions = [section.index('<h2>'+title+'</h2>') for title in ('작업 상태 현황','최근 작업 활동','프로필 구성 현황','빠른 작업')]
        self.assertEqual(positions,sorted(positions))
        self.assertLess(positions[-1],section.index('id="dashboardDocumentCounts"'))
        self.assertLess(section.index('id="dashboardDocumentCounts"'),section.index('사용자 요청 → 실행 단계'))
    def test_redundant_kpis_removed(self):
        section=UI.split('<section id="dashboard"',1)[1].split('</section>',1)[0]
        self.assertNotIn('dashboard-kpis',section)
        for id in ('profileCount','skillTotalKpi','currentTasks','completedCount','designCount'):
            self.assertNotIn('id="'+id+'"',section)
            self.assertNotIn("$('"+id+"')",UI)
    def test_document_counts_are_data_backed(self):
        self.assertIn('state.dashboard?.document_counts', UI)
        for kind in ('requirements','architecture','design','storyboards'):
            self.assertIn("'"+kind+"'",UI)
        self.assertIn("String(dc[key]??0)+'건'",UI)
        self.assertIn('dashboard-document-grid',UI)

if __name__=='__main__':unittest.main()
