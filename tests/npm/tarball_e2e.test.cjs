'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const ROOT = path.resolve(__dirname,'../..');
const realPython = cp.spawnSync('which',['python3'],{encoding:'utf8'}).stdout.trim()||'python3';
const npm = (args,cwd,opts={})=>cp.spawnSync('npm',args,{cwd,encoding:'utf8',timeout:90000,maxBuffer:4_000_000,...opts});

test('actual local npm tarball launches via npx and installs project using synthetic offline fixture', {timeout:90000},()=>{
  const sandbox=fs.mkdtempSync(path.join(os.tmpdir(),'agentflow-packed-e2e-'));
  try{
    const pack=npm(['pack','--json','--pack-destination',sandbox],ROOT);
    assert.equal(pack.status,0,pack.stderr);
    const info=JSON.parse(pack.stdout)[0];
    const tarball=path.join(sandbox,info.filename);
    const shim=path.join(sandbox,'python-fixture-shim.sh');
    const harness=path.join(ROOT,'tests/npm/fixture-runner.py');
    fs.writeFileSync(shim,'#!/bin/sh\n'+
      `if [ "$1" = "-c" ]; then exec ${JSON.stringify(realPython)} "$@"; fi\n`+
      `exec ${JSON.stringify(realPython)} ${JSON.stringify(harness)} "$@"\n`);
    fs.chmodSync(shim,0o755);
    const work=path.join(sandbox,'work');fs.mkdirSync(work);
    const opts={env:{...process.env,AGENTFLOW_PYTHON:shim,npm_config_cache:path.join(sandbox,'npm-cache')}};
    const invoke=args=>npm(['exec','--yes','--offline',`--package=${tarball}`,'--','agentflow',...args],work,opts);
    let r=invoke(['--version']);assert.equal(r.status,0,r.stderr);assert.equal(r.stdout.trim(),'1.0.1');
    const project=path.join(sandbox,'newproject');
    r=invoke(['init',project,'--skip-tools']);
    assert.equal(r.status,0,r.stdout+'\n'+r.stderr);
    const tree=JSON.parse(fs.readFileSync(path.join(project,'.agentflow/skill-trees/project-architect.json')));
    assert.ok(tree.stages.some(stage=>stage.skills.some(skill=>skill.name==='system-architect')));
    for(const runtime of ['.opencode','.claude','.agents']) {
      assert.ok(fs.existsSync(path.join(project,runtime,'skills/system-architect/SKILL.md')));
    }
    assert.equal(fs.readFileSync(path.join(project,'.ai-dev/.gitignore'),'utf8'),fs.readFileSync(path.join(ROOT,'scaffold/.ai-dev/.gitignore'),'utf8'));
    r=invoke(['doctor',project]);
    assert.equal(r.status,0,r.stdout+'\n'+r.stderr);
    const doctor=JSON.parse(r.stdout);
    assert.equal(doctor.status,'CONFIGURED_NOT_NATIVE_VERIFIED');
    assert.equal(doctor.native_agent_e2e,'NOT_VERIFIED');
    // Tampering with a previously installed skill must make doctor fail.
    fs.appendFileSync(path.join(project,'.claude/skills/system-architect/SKILL.md'),'\nTAMPERED\n');
    r=invoke(['doctor',project]);
    assert.equal(r.status,2,r.stdout+'\n'+r.stderr);
    assert.match(r.stdout,/HASH_MISMATCH/);
    const failedTarget=path.join(sandbox,'reject-conflict');
    fs.mkdirSync(failedTarget);
    fs.writeFileSync(path.join(failedTarget,'AGENTS.md'),'USER EDIT');
    r=invoke(['init',failedTarget,'--skip-tools']);
    assert.equal(r.status,2,r.stdout+'\n'+r.stderr);
    assert.equal(fs.readFileSync(path.join(failedTarget,'AGENTS.md'),'utf8'),'USER EDIT');
  }finally{fs.rmSync(sandbox,{recursive:true,force:true});}
});
