#!/usr/bin/env node
'use strict';
// Distribution/install entrypoint ONLY. No workflow CLI is copied into target projects.
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const installer = path.resolve(__dirname, '..', 'install.py');

function usage() {
  console.log(`AgentFlow npm installer (no teamdev/workflow CLI)\n\nUsage:\n  agentflow init <project-path> [--upstream-zip <file>] [--no-browser]\n  agentflow --version\n  agentflow --help\n\nPrerequisites: Node.js 20+, Python 3.10+, and internet for first install.\nRTK/CRG/browser tools install inside the target project; Chrome may be system-wide.\nExisting conflicting files are never overwritten.\n`);
}
function findPython() {
  const candidates = process.platform === 'win32' ? [['py', ['-3']]] : [['python3', []], ['python', []]];
  for (const [name, prefix] of candidates) {
    const p = spawnSync(name, [...prefix, '-c', 'import sys;sys.exit(0 if sys.version_info >= (3, 10) else 2)'], {encoding:'utf8', timeout:8000});
    if (!p.error && p.status === 0) return [name, prefix];
  }
  return null;
}
function main(args) {
  if (args.length === 1 && ['--version', '-v'].includes(args[0])) {
    console.log(require('../package.json').version); return 0;
  }
  if (args.length === 0 || (args.length === 1 && ['--help','-h','help'].includes(args[0]))) {
    usage(); return 0;
  }
  if (args[0] !== 'init' || args.length < 2 || args[1].startsWith('--')) {
    console.error('INVALID_COMMAND: use agentflow init <project-path>');usage();return 2;
  }
  if (!fs.existsSync(installer)) { console.error('PACKAGE_CORRUPT: installer missing'); return 2; }
  const allowed = new Set(['--upstream-zip','--no-browser','--skip-tools']);
  const argsOut = [path.resolve(args[1])];
  for (let i=2; i<args.length; i++) {
    const opt=args[i];
    if (!allowed.has(opt)) { console.error(`UNKNOWN_OPTION: ${opt}`);return 2; }
    if (opt === '--skip-tools') {
      if (process.env.AGENTFLOW_TEST_ONLY_SKIP_TOOLS !== '1') {
        console.error('TEST_ONLY_OPTION: --skip-tools may only be used with AGENTFLOW_TEST_ONLY_SKIP_TOOLS=1; this never establishes production READY');return 2;
      }
      argsOut.push(opt);
    } else if (opt === '--upstream-zip') {
      const zip=args[++i];
      if (!zip || zip.startsWith('--')) { console.error('MISSING_UPSTREAM_ZIP');return 2; }
      argsOut.push(opt,path.resolve(zip));
    } else argsOut.push(opt);
  }
  const py=findPython();
  if (!py) { console.error('PYTHON_REQUIRED: install Python 3.10+ and retry (project installer is Python-based).'); return 2; }
  console.log(`Installing AgentFlow into ${argsOut[0]} (PROJECT_ONLY)`);
  const result=spawnSync(py[0], [...py[1], installer, ...argsOut], {stdio:'inherit',timeout:900000, env:process.env});
  if (result.error) { console.error(`INSTALL_FAILED: ${result.error.code || result.error.message}`);return 2; }
  return result.status === null ? 2 : result.status;
}
process.exitCode=main(process.argv.slice(2));
