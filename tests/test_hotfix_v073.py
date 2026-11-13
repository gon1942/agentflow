"""Regression: OpenCode V1 plugin loader and visible Skill Advisor progress."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLUGINS=ROOT/'scaffold/.opencode/plugins'
UI=ROOT/'scaffold/agentflow_console/ui.html'

class HotfixTests(unittest.TestCase):
    def test_every_plugin_export_is_plugin_factory_only(self):
        modules=[str(p.as_uri()) for p in sorted(PLUGINS.glob('*.js'))]
        js='''const modules=JSON.parse(process.argv[1]);for(const url of modules){const mod=await import(url);for(const [k,v] of Object.entries(mod)){if(typeof v!=="function")throw new Error(url+":"+k+" is "+typeof v);if(!/^AgentFlow/.test(k))throw new Error(url+":"+k+" is a helper exposed as a plugin factory");}}'''
        r=subprocess.run(['node','--input-type=module','-e',js,json.dumps(modules)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_advisor_button_has_status_and_deduplication(self):
        ui=UI.read_text()
        for fragment in ['id="aiSuggestButton"','id="aiSuggestStatus"','aria-live="polite"',
                         'if(aiSuggestInFlight)return;',"setAiSuggestState('running'", 
                         "setAiSuggestState('done'", "setAiSuggestState('failed'",'finally{']:
            self.assertIn(fragment,ui)

if __name__=='__main__': unittest.main()
