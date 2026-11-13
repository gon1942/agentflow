"""Integrated regression for documentation routing, slash entrypoints and profile hook."""
import unittest
import tempfile
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'scaffold'

class IntegratedV074(unittest.TestCase):
    def test_project_local_command_entrypoints(self):
        self.assertTrue((S/'.opencode/commands/agentflow-mngr.md').is_file())
        for rel in ['.claude/skills/agentflow-mngr/SKILL.md','.agents/skills/agentflow-mngr/SKILL.md']:
            value=(S/rel).read_text()
            self.assertIn('name: agentflow-mngr',value)
            self.assertIn('python3 agentflow_console.py start --browser',value)
            self.assertIn('python3 agentflow_console.py stop',value)
        self.assertFalse((S/'.codex/prompts/agentflow-mngr.md').exists(), 'Codex project-local custom prompts unsupported')

    def test_document_scaffold_and_routing(self):
        for rel in ['requirements','architecture','architecture/decisions','design','storyboards','tasks','templates','workflow']:
            self.assertTrue((S/'docs'/rel).is_dir(),rel)
        policy=(S/'docs/README.md').read_text()
        for kind in ['requirements','architecture','design','storyboards','tasks','templates','workflow']:
            self.assertIn('docs/'+kind,policy)
        for rel in ['AGENTS.md','CLAUDE.md','docs/workflow/WORKFLOW.md','.opencode/agents/coordinator.md','.claude/agents/coordinator.md']:
            self.assertIn('docs/README.md',(S/rel).read_text())

    def test_dashboard_document_counts_real(self):
        import sys
        sys.path.insert(0,str(S))
        from agentflow_console.core import Manager
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)
            (project/'docs/workflow').mkdir(parents=True)
            (project/'docs/workflow/WORKFLOW.md').write_text('workflow')
            (project/'.agentflow').mkdir()
            (project/'.agentflow/active-profile.json').write_text('{"profile": "development", "generation": 1}')
            manager=Manager(project)
            for kind in ['requirements','architecture','design','storyboards']:
                target=project/'docs'/kind;target.mkdir(parents=True)
                (target/'README.md').write_text('documentation')
                (target/'one.md').write_text('artifact')
                (target/'.gitkeep').write_text('')
            counts=manager.dashboard_snapshot()['document_counts']
            self.assertEqual(counts,{'requirements':1,'architecture':1,'design':1,'storyboards':1})

    def test_opencode_system_transform_single_block_and_idempotent(self):
        path=(S/'.opencode/plugins/agentflow-profile.js').as_uri()
        script='''
const {AgentFlowProfile}=await import(process.argv[1]);
const plugin=await AgentFlowProfile({directory:'/does-not-exist'});
const h=plugin['experimental.chat.system.transform'];
const output={system:['original']};
await h({sessionID:''},output);
if(output.system.length!==1||output.system[0]!=='original') throw Error('hook regression');
const src=await (await import('node:fs/promises')).readFile(new URL(process.argv[1]),'utf8');
if(src.includes('output.system.push(\\'AgentFlow session='))throw Error('old separate block');
console.log('PASS');'''
        r=subprocess.run(['node','--input-type=module','-e',script,path],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('PASS',r.stdout)


    def test_opencode_system_transform_real_contract_one_system(self):
        path=(S/'.opencode/plugins/agentflow-profile.js').as_uri()
        js=r"""
import {mkdirSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const project=mkdtempSync(join(tmpdir(),'agentflow-hook-v074-'));
try {
  writeFileSync(join(project,'agentflow_console.py'),`import json,sys\nprint(json.dumps({'session_id':'S1','profile':'development','configuration_sha256':'abc','instruction':'FOLLOW PINNED CONTRACT'}))\n`);
  const {AgentFlowProfile}=await import(process.argv[1]);
  const plugin=await AgentFlowProfile({directory:project});
  const hook=plugin['experimental.chat.system.transform'];
  const output={system:['System preface']};
  await hook({sessionID:'S1'},output);
  if(output.system.length!==1)throw Error('created a second system block');
  if(!output.system[0].startsWith('System preface'))throw Error('modified original prefix');
  if(!output.system[0].includes('FOLLOW PINNED CONTRACT'))throw Error('missing contract');
  const first=output.system[0];
  await hook({sessionID:'S1'},output);
  if(output.system.length!==1||output.system[0]!==first)throw Error('duplicate contract injection');
  console.log('PASS');
} finally { rmSync(project,{recursive:true,force:true}); }
"""
        r=subprocess.run(['node','--input-type=module','-e',js,path],capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('PASS',r.stdout)

if __name__=='__main__': unittest.main()
