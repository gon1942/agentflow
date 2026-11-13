"""TDD acceptance: default Architect no longer routes to bundled af-* skills."""
import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DefaultArchitectContract(unittest.TestCase):
 def test_fresh_scaffold_has_external_skill_map(self):
  tree=json.loads((ROOT/'scaffold/.agentflow/skill-trees/project-architect.json').read_text())
  mapping={s['id']:{x['name'] for x in s['skills']} for s in tree['stages']}
  self.assertEqual(mapping['ANALYZE'],{'requirements-analyst','change-impact-analyzer'})
  self.assertEqual(mapping['PLAN'],{'project-manager'})
  self.assertEqual(mapping['IMPLEMENT'],{'system-architect','architecture-decision-records'})
  self.assertEqual(mapping['VERIFY'],{'traceability-auditor'})
  self.assertEqual(mapping['REVIEW'],{'design-review','security-auditor'})
  self.assertFalse(any(x.startswith('af-') for names in mapping.values() for x in names))
if __name__=='__main__':unittest.main()
