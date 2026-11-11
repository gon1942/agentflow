'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const exe = path.resolve(__dirname, '..', 'bin/agentflow.cjs');
const cwd = path.resolve(__dirname, '..');
function run(args, options={}) {return spawnSync(process.execPath,[exe,...args],{cwd,encoding:'utf8', timeout:30000,...options})}
test('prints version only on --version',()=>{
 const p=run(['--version']);assert.equal(p.status,0,p.stderr);assert.equal(p.stdout.trim(),'0.5.0-rc.1');
});
test('help names Python and explicitly excludes teamdev',()=>{
 const p=run(['--help']);assert.equal(p.status,0);assert.match(p.stdout,/Python 3.10\+/);assert.match(p.stdout,/no teamdev\/workflow CLI/);
});
test('invalid commands fail instead of falling through',()=>{
 for(const args of [['review'],['verify','X'],['init'],['init','./x','--typo'],['init','./x','--upstream-zip']]){
  const p=run(args);assert.equal(p.status,2,args.join(' '));
 }
});
test('test-only skip cannot bypass required tools in ordinary install',()=>{
 const p=run(['init','./x','--skip-tools']);assert.equal(p.status,2);assert.match(p.stderr,/TEST_ONLY_OPTION/);
});
test('missing Python is reported cleanly, not as success',()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'af-no-python-'));
 try {const p=run(['init',tmp],{env:{...process.env,PATH:''}});assert.equal(p.status,2);assert.match(p.stderr,/PYTHON_REQUIRED/);}
 finally {fs.rmSync(tmp,{recursive:true,force:true});}
});
