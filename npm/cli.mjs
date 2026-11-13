#!/usr/bin/env node
/** AgentFlow npm entrypoint. All project writes happen in the existing Python installers. */
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import { existsSync, readFileSync, statSync, lstatSync } from 'node:fs';
import process from 'node:process';
import { createHash } from 'node:crypto';

const release = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const pkg = JSON.parse(readFileSync(join(release, 'package.json'), 'utf8'));
const help = `AgentFlow ${pkg.version} — project-local npm/npx installer

Usage:
  agentflow init <project> [--upstream-zip <zip>] [--architect-archive-dir <dir>]
                          [--skip-tools] [--no-browser]
  agentflow upgrade <project> [--apply] [--architect-archive-dir <dir>]
  agentflow doctor <project>
  agentflow --version | --help

init:    installs AgentFlow using the pinned-source Python installer.
upgrade: preview only unless --apply is explicitly supplied (Project Architect migration).
doctor:  read-only configuration and installed-file checks; not a native-agent E2E.

Requires Python 3.10+, Node.js 18+ and network for pinned upstream sources by default.
This npm package does not execute installation in npm postinstall.
`;
const usageError = message => { console.error(`AGENTFLOW_USAGE_ERROR: ${message}\n\n${help}`); process.exitCode=2; };

function parse(argv) {
  const [command, project, ...rest] = argv;
  if (!command || !['init','upgrade','doctor'].includes(command)) return null;
  if (!project || project.startsWith('--')) throw new Error('PROJECT_PATH_REQUIRED');
  const allowed = command==='init' ? new Set(['--upstream-zip','--architect-archive-dir','--skip-tools','--no-browser']) :
                  command==='upgrade' ? new Set(['--apply','--architect-archive-dir']) : new Set();
  const valueOptions=new Set(['--upstream-zip','--architect-archive-dir']);
  const opts=[];
  const seen=new Set();
  for (let i=0;i<rest.length;i++) {
    const flag=rest[i];
    if (!allowed.has(flag)) throw new Error('UNKNOWN_OR_UNSUPPORTED_OPTION: '+flag);
    if (seen.has(flag)) throw new Error('DUPLICATE_OPTION: '+flag);
    seen.add(flag);
    if (valueOptions.has(flag)) {
      const value=rest[++i];
      if (!value || value.startsWith('--')) throw new Error('MISSING_OPTION_VALUE: '+flag);
      opts.push(flag,resolve(value));
    } else opts.push(flag);
  }
  return {command,project:resolve(project),opts};
}

function findPython() {
  const choices=process.env.AGENTFLOW_PYTHON ? [process.env.AGENTFLOW_PYTHON] :
                process.platform==='win32' ? ['py','python','python3'] : ['python3','python'];
  for (const cmd of choices) {
    const prefix=cmd==='py' ? ['-3'] : [];
    const result=spawnSync(cmd,[...prefix,'-c','import sys; print("%d.%d" % sys.version_info[:2])'],{
      encoding:'utf8',timeout:6000,windowsHide:true
    });
    if (result.status===0) {
      const [maj,min]=result.stdout.trim().split('.').map(Number);
      if (maj===3 && min>=10) return {cmd,prefix,version:result.stdout.trim()};
    }
  }
  return null;
}

function isFile(p){try{return lstatSync(p).isFile();}catch{return false;}}
function inspect(project) {
  const checks=[];
  const add=(label,good,details)=>checks.push({label,status:good?'PASS':'MISSING',details});
  let root=false;
  try{root=statSync(project).isDirectory();}catch{}
  add('project_directory',root,project);
  const python=findPython();
  add('python_3_10_plus',Boolean(python),python?.version ?? 'Python 3.10+ required');
  if(root) {
    for(const rel of [
      'docs/workflow/WORKFLOW.md','agentflow_console.py',
      '.agentflow/skill-trees/project-architect.json',
      '.ai-dev/external-skills.lock.json',
      '.opencode/skills','.claude/skills','.agents/skills'
    ]){
      const p=join(project,rel);
      add(rel,existsSync(p) && !lstatSync(p).isSymbolicLink(),rel);
    }
    let managed=[];
    let lockedSkills={};
    const lock=join(project,'.ai-dev/external-skills.lock.json');
    try {
      const data=JSON.parse(readFileSync(lock,'utf8'));
      lockedSkills=data.managed_skills||{};
      managed=Object.keys(lockedSkills).filter(n=>[
        'requirements-analyst','change-impact-analyzer','project-manager',
        'system-architect','architecture-decision-records','traceability-auditor',
        'design-review','security-auditor'
      ].includes(n));
      add('architect_source_lock',managed.length===8,`${managed.length}/8 external skills tracked`);
    }catch{add('architect_source_lock',false,'lock missing, unreadable or malformed');}
    for(const runtime of ['.opencode','.claude','.agents']) {
      const issues=[];
      for (const name of managed) {
        const expected=lockedSkills[name]?.files_sha256;
        if (!expected || !Object.hasOwn(expected,'SKILL.md')) {
          issues.push(`HASH_NOT_RECORDED: ${name}`);
          continue;
        }
        for (const [rel,digest] of Object.entries(expected)) {
          const parts=rel.split('/');
          if(parts.some(p=>!p || p==='.' || p==='..') || rel.includes('\\') ||
             !/^[0-9a-f]{64}$/.test(digest)) {
            issues.push(`UNSAFE_OR_INVALID_LOCK: ${name}/${rel}`);
            continue;
          }
          const skillFile=join(project,runtime,'skills',name,...parts);
          if(!isFile(skillFile)) {
            issues.push(`MISSING: ${name}/${rel}`);
            continue;
          }
          const actual=createHash('sha256').update(readFileSync(skillFile)).digest('hex');
          if(actual!==digest) issues.push(`HASH_MISMATCH: ${name}/${rel}`);
        }
      }
      add(`${runtime}_architect_skills`,managed.length===8 && issues.length===0,
          issues.length ? issues.join('; ') : `${managed.length}/8 skills match installed lock hashes`);
    }
  }
  const ok=checks.every(c=>c.status==='PASS');
  console.log(JSON.stringify({status:ok?'CONFIGURED_NOT_NATIVE_VERIFIED':'NOT_READY',project,
    checks,native_agent_e2e:'NOT_VERIFIED', browser_e2e:'NOT_VERIFIED',
    note:'Doctor is read-only. It cannot assert native skill loading or approved workflow completion.'},null,2));
  process.exitCode=ok?0:2;
}

async function execPython(parsed) {
  const py=findPython();
  if(!py){ console.error('AGENTFLOW_PYTHON_MISSING: Python 3.10+ is required (set AGENTFLOW_PYTHON to an executable).');process.exitCode=2;return; }
  const script=join(release,parsed.command==='init'?'install.py':'upgrade_project_architect.py');
  if(!isFile(script)){console.error(`AGENTFLOW_PACKAGE_INCOMPLETE: ${script}`);process.exitCode=2;return;}
  console.log(`[AgentFlow ${pkg.version}] ${parsed.command} ${parsed.project}`);
  const child=spawn(py.cmd,[...py.prefix,script,parsed.project,...parsed.opts],{stdio:'inherit',windowsHide:true});
  const code=await new Promise(resolveExit=>{
    child.once('error',err=>{console.error(`AGENTFLOW_RUN_FAILED: ${err.message}`);resolveExit(2);});
    child.once('close',(code,signal)=>resolveExit(code===null?(signal?130:2):code));
  });
  process.exitCode=code;
}

const argv=process.argv.slice(2);
if(argv.length===1 && ['--help','-h','help'].includes(argv[0])) console.log(help);
else if(argv.length===1 && ['--version','-v','version'].includes(argv[0])) console.log(pkg.version);
else {
  try {
    const parsed=parse(argv);
    if(!parsed) usageError('Expected init, upgrade, or doctor.');
    else if(parsed.command==='doctor') inspect(parsed.project);
    else await execPython(parsed);
  } catch(err){ usageError(err.message); }
}
