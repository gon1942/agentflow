import importlib.util
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class UpgradeV080(unittest.TestCase):
    def test_upgrade_dryrun_and_hash_guard(self):
        spec=importlib.util.spec_from_file_location('upgrade_v080',ROOT/'upgrade_v080.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)
            for name in module.FILES:
                dest=project/name;dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text('old content')
            legacy=project/'.opencode/commands/agentflow-mngr-start.md'
            legacy.write_text('modified by user')
            module.update(project,False)
            self.assertEqual(legacy.read_text(),'modified by user')
            module.update(project,True)
            self.assertEqual(legacy.read_text(),'modified by user')
            self.assertEqual((project/'agentflow_console/core.py').read_bytes(),(ROOT/'scaffold/agentflow_console/core.py').read_bytes())
            self.assertTrue((project/'agentflow_console/core.py.pre-v080.bak').exists())

if __name__=='__main__':unittest.main()
