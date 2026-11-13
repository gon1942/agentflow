'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const ROOT = path.resolve(__dirname,'../..');
test('npm tarball file list contains full runtime, skills contract and Git-ignore template',()=>{
  const r=cp.spawnSync('npm',['pack','--dry-run','--json'],{cwd:ROOT,encoding:'utf8',timeout:30000});
  assert.equal(r.status,0,r.stderr);
  const files=new Set(JSON.parse(r.stdout)[0].files.map(f=>f.path));
  const topLevelMarkdown=[...files].filter(f=>!f.includes('/') && f.endsWith('.md')).sort();
  assert.deepEqual(topLevelMarkdown,['README.md']);
  assert.ok(!files.has('README-NPX.md'));
  assert.ok(!files.has('RELEASE-NOTES-0.8.2.md'));
  for(const rel of ['npm/cli.mjs','install.py','tool_provision.py','architect_sources.py',
    'upgrade_project_architect.py','scaffold/.agentflow/skill-trees/project-architect.json',
    'scaffold/.opencode/commands/agentflow-mngr.md',
    'scaffold/.claude/skills/agentflow-mngr/SKILL.md',
    'scaffold/docs/workflow/WORKFLOW.md','scaffold/.ai-dev/gitignore-template.txt']) {
    assert.ok(files.has(rel),`missing from npm tarball: ${rel}`);
  }
  const source=fs.readFileSync(path.join(ROOT,'scaffold/.agentflow/skill-trees/project-architect.json'),'utf8');
  assert.ok(source.includes('system-architect'));
  assert.ok(!source.includes('af-architecture-design'));
});
