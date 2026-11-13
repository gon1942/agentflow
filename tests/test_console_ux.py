"""RC2 web console UX regression and contract checks (not native agent E2E)."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'scaffold/agentflow_console/ui.html').read_text(encoding='utf-8')
SERVER=(ROOT/'scaffold/agentflow_console/server.py').read_text(encoding='utf-8')

class ConsoleUXTests(unittest.TestCase):
    def test_all_navigation_routes_have_sections(self):
        pages=re.findall(r'data-page="([a-z]+)"',UI)
        self.assertEqual(pages,['dashboard','profiles','trees','skills','agents','execution','settings'])
        for page in pages:
            self.assertIn(f'<section id="{page}"',UI)
    def test_skill_label_uses_available_key(self):
        self.assertIn("const value=o[field]??o.name??o.id",UI)
        self.assertNotIn("item.textContent=(o.name||o.id)+' ('+o.id+')'",UI)
    def test_skill_integrity_and_native_status_separated(self):
        for label in ['파일 무결성','네이티브 로딩','HASH_VERIFIED_NOT_NATIVE_LOADED','미확인']:
            self.assertIn(label,UI)
        self.assertIn('id="skillSearch"',UI)
    def test_advanced_editors_are_collapsible(self):
        self.assertIn('고급 사용자용 프로필 JSON 편집',UI)
        self.assertIn('고급 사용자용 JSON 편집 펼치기',UI)
        self.assertIn('id="treeStageOverview"',UI)
        self.assertIn('onclick="saveTree()"',UI)
    def test_server_ctrl_c_clean_shutdown(self):
        self.assertIn('except KeyboardInterrupt:',SERVER)
        self.assertIn('server.server_close()',SERVER)
    def test_no_remote_dependencies(self):
        self.assertNotIn('http://cdn.',UI)
        self.assertNotIn('https://cdn.',UI)
        self.assertNotIn('import(',UI)

if __name__=='__main__':unittest.main()
