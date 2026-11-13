"""v0.8.1 command compatibility tests after v0.8.2 migration; old opt-in API replaced."""
import json, tempfile, unittest
from pathlib import Path
from contextlib import redirect_stdout
import io
import project_architect_external as cli
from upgrade_project_architect import main

class LegacyEntryPoint(unittest.TestCase):
 def test_shim_delegates_to_new_migrator(self):
  self.assertIs(cli.main, main)
 def test_fails_for_non_project_no_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'missing'
   self.assertEqual(cli.main([str(root)]),2)
   self.assertFalse(root.exists())
 def test_v081_command_preview_does_not_mutate(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for f,data in [('docs/workflow/WORKFLOW.md','fixture'),('.agentflow/skill-trees/project-architect.json',json.dumps({'id':'project-architect','stages':[]})),('.ai-dev/external-skills.lock.json','{}')]:
    p=root/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
   before=(root/'.agentflow/skill-trees/project-architect.json').read_bytes()
   with redirect_stdout(io.StringIO()):self.assertEqual(cli.main([str(root)]),0)
   self.assertEqual((root/'.agentflow/skill-trees/project-architect.json').read_bytes(),before)
if __name__=='__main__':unittest.main()
