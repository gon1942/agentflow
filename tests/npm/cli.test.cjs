'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const CLI = path.join(ROOT,'npm','cli.mjs');
function run(args, options={}) {
  return cp.spawnSync(process.execPath,[CLI,...args],{cwd:ROOT,encoding:'utf8',timeout:25000,...options});
}
test('package has stable version, bin and no lifecycle scripts',()=>{
  const pkg = require(path.join(ROOT,'package.json'));
  assert.equal(pkg.name,'@gon1942/agentflow');
  assert.equal(pkg.version,'1.0.1');
  assert.equal(pkg.bin.agentflow,'npm/cli.mjs');
  assert.equal(pkg.scripts?.postinstall,undefined);
  assert.equal(pkg.scripts?.preinstall,undefined);
  assert.equal(pkg.scripts?.prepare,undefined);
});
test('help and version do not invoke installer',()=>{
  let r=run(['--help']); assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/init <project>/);assert.match(r.stdout,/upgrade <project>/);assert.match(r.stdout,/doctor <project>/);
  r=run(['--version']);assert.equal(r.status,0);assert.equal(r.stdout.trim(),'1.0.1');
});
test('requires subcommand and project path, rejects unknown options',()=>{
  assert.equal(run([]).status,2);
  assert.equal(run(['init']).status,2);
  assert.equal(run(['upgrade']).status,2);
  assert.equal(run(['init','my-app','--risky-option']).status,2);
  assert.equal(run(['doctor','my-app','--apply']).status,2);
});
test('doctor is read only and provides actionable diagnostics',()=>{
  const p=fs.mkdtempSync(path.join(os.tmpdir(),'agentflow-cli-test-'));
  try{
    const r=run(['doctor',p]);assert.equal(r.status,2,r.stdout+' '+r.stderr);assert.match(r.stdout,/NOT_READY/);assert.match(r.stdout,/MISSING/);
    assert.deepEqual(fs.readdirSync(p),[]);
  }finally{fs.rmSync(p,{recursive:true,force:true});}
});
test('upgrade defaults to preview; no writes',()=>{
  const p=fs.mkdtempSync(path.join(os.tmpdir(),'agentflow-cli-upgrade-'));
  try{
    const put=(f,x)=>{const t=path.join(p,f);fs.mkdirSync(path.dirname(t),{recursive:true});fs.writeFileSync(t,x);};
    put('docs/workflow/WORKFLOW.md','test');
    put('.agentflow/skill-trees/project-architect.json',JSON.stringify({id:'project-architect',stages:[]}));
    put('.ai-dev/external-skills.lock.json','{}');
    const before=fs.readFileSync(path.join(p,'.agentflow/skill-trees/project-architect.json'),'utf8');
    const r=run(['upgrade',p]);assert.equal(r.status,0,r.stdout+' '+r.stderr);assert.match(r.stdout,/PREVIEW/);
    assert.equal(fs.readFileSync(path.join(p,'.agentflow/skill-trees/project-architect.json'),'utf8'),before);
  }finally{fs.rmSync(p,{recursive:true,force:true});}
});
test('init missing pinned offline archives does not create project',()=>{
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'agentflow-cli-block-'));
  const dest=path.join(base,'not-created');
  try{
    const r=run(['init',dest,'--upstream-zip',path.join(base,'missing.zip'),'--architect-archive-dir',base,'--skip-tools']);
    assert.equal(r.status,2,r.stdout+' '+r.stderr);
    assert.equal(fs.existsSync(dest),false);
    assert.match(r.stderr,/INSTALL_BLOCKED|PINNED_ARCHIVE_NOT_FOUND/);
  }finally{fs.rmSync(base,{recursive:true,force:true});}
});
