#!/usr/bin/env python3
"""Install-only, project-local RTK + CRG + browser runtimes.

No teamdev, no global hook modification, no global binary fallbacks.
No project runtime CLI is copied into installed projects.
An installed binary is not evidence of its hook/MCP or native usage.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

RTK_VERSION = '1.1.0'
CRG_VERSION = '2.3.9'
BROWSER_VERSIONS = {'playwright': '1.65.0', 'agent-browser': '0.41.2'}
RTK_TARGETS = {
 ('Linux', 'x86_64'): 'x86_64-unknown-linux-musl',
 ('Linux', 'aarch64'): 'aarch64-unknown-linux-gnu',
 ('Darwin', 'x86_64'): 'x86_64-apple-darwin',
 ('Darwin', 'arm64'): 'aarch64-apple-darwin',
}


def executable_version(path: Path, timeout=12):
    if not path.is_file():
        return None
    try:
        result = subprocess.run([str(path), '--version'], capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return (result.stdout or result.stderr).strip()[:180]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def paths(root: Path):
    tools = root / '.ai-dev' / 'tools'
    return {'tools':tools, 'rtk':tools/'rtk/bin/rtk', 'crg':tools/'crg-venv/bin/code-review-graph',
            'browser':tools/'browser', 'lock':tools/'tools-lock.json'}


def symlink_escape(root: Path):
    """Reject symlinks along every project-local tool destination before any install/write."""
    root = Path(root).expanduser().resolve()
    checks = ('.ai-dev', '.ai-dev/tools', '.ai-dev/tools/rtk', '.ai-dev/tools/rtk/bin',
              '.ai-dev/tools/rtk/bin/rtk', '.ai-dev/tools/crg-venv',
              '.ai-dev/tools/crg-venv/bin', '.ai-dev/tools/crg-venv/bin/code-review-graph',
              '.ai-dev/tools/browser', '.ai-dev/tools/browser/node_modules',
              '.ai-dev/tools/tools-lock.json')
    for rel in checks:
        if (root / rel).is_symlink():
            return rel
    return None

def chrome_path():
    for candidate in ('google-chrome-stable', 'google-chrome'):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def install_rtk(root: Path, *, offline=False, timeout=60):
    path = paths(root)['rtk']
    found = executable_version(path)
    if found and RTK_VERSION in found:
        return {'status':'READY', 'version':found, 'reused':True, 'hook_verified':False}
    if offline:
        return {'status':'BLOCKED','reason':'RTK_NOT_CACHED'}
    target = RTK_TARGETS.get((platform.system(), platform.machine()))
    if target is None:
        return {'status':'BLOCKED','reason':'RTK_PLATFORM_UNSUPPORTED'}
    artifact = f'rtk-{target}.tar.gz'
    url = f'https://github.com/rtk-ai/rtk/releases/download/v{RTK_VERSION}/'
    try:
        with urllib.request.urlopen(url+'checksums.txt',timeout=timeout) as r:
            lines = r.read(100_000).decode('utf-8').splitlines()
        matches = [line.split()[0] for line in lines if len(line.split()) >= 2 and line.split()[-1].lstrip('*') == artifact]
        if len(matches) != 1 or len(matches[0]) != 64:
            return {'status':'BLOCKED','reason':'RTK_CHECKSUM_NOT_FOUND'}
        with urllib.request.urlopen(url+artifact, timeout=timeout) as r:
            archive = r.read(40_000_001)
        if len(archive) > 40_000_000 or hashlib.sha256(archive).hexdigest() != matches[0]:
            return {'status':'BLOCKED','reason':'RTK_CHECKSUM_MISMATCH'}
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tf:
            members = [m for m in tf.getmembers() if m.isfile() and Path(m.name).name == 'rtk']
            if len(members) != 1 or members[0].size > 40_000_000:
                return {'status':'BLOCKED','reason':'RTK_ARCHIVE_UNEXPECTED'}
            binary = tf.extractfile(members[0]).read()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.partial')
        try:
            with temp.open('xb') as f:
                f.write(binary);f.flush();os.fsync(f.fileno())
            temp.chmod(0o755)
            actual = executable_version(temp)
            if not actual or RTK_VERSION not in actual:
                return {'status':'BLOCKED','reason':'RTK_VERSION_FAILED'}
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        return {'status':'READY','version':actual, 'sha256':hashlib.sha256(binary).hexdigest(), 'hook_verified':False}
    except Exception as exc:
        return {'status':'BLOCKED','reason':'RTK_INSTALL_FAILED', 'error_type':type(exc).__name__}


def install_crg(root: Path, *, offline=False, timeout=240):
    p = paths(root)
    found = executable_version(p['crg'])
    if found and CRG_VERSION in found:
        return {'status':'READY','version':found,'reused':True,'mcp_verified':False}
    venv = p['tools']/'crg-venv'
    python = venv/'bin/python'
    try:
        if not python.is_file():
            result = subprocess.run([sys.executable,'-m','venv',str(venv)],text=True,capture_output=True,timeout=60)
            if result.returncode:
                return {'status':'BLOCKED','reason':'CRG_VENV_FAILED','error_tail':result.stderr[-300:]}
        args = [str(python),'-m','pip','install','--disable-pip-version-check','--no-input', '--no-cache-dir',
                f'code-review-graph=={CRG_VERSION}']
        if offline:
            args.insert(4,'--no-index')
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                env={**os.environ, 'PIP_REQUIRE_VIRTUALENV':'true'})
        if result.returncode:
            return {'status':'BLOCKED','reason':'CRG_PIP_FAILED','error_tail':result.stderr[-400:]}
        found = executable_version(p['crg'])
        if not found or CRG_VERSION not in found:
            return {'status':'BLOCKED','reason':'CRG_VERSION_FAILED'}
        return {'status':'READY','version':found,'mcp_verified':False}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status':'BLOCKED','reason':'CRG_INSTALL_FAILED','error_type':type(exc).__name__}


def browser_state(home: Path):
    installed = {}
    for pkg in BROWSER_VERSIONS:
        try:
            installed[pkg] = json.loads((home/'node_modules'/pkg/'package.json').read_text())['version']
        except (OSError, KeyError, ValueError):
            installed[pkg] = None
    return {'installed_versions':installed, 'versions_match':installed == BROWSER_VERSIONS,
            'chrome_path':chrome_path(), 'node':shutil.which('node'), 'npm':shutil.which('npm')}


def browser_smoke(home: Path):
    state = browser_state(home)
    if not (state['versions_match'] and state['chrome_path'] and state['node']):
        return {'pass':False,'reason':'MISSING_RUNTIME'}
    code = """const {chromium}=require(process.argv[1]); (async()=>{let b; try {b=await chromium.launch({executablePath:process.argv[2],headless:true});const p=await b.newPage();await p.setContent('<title>af-smoke</title>');if(await p.title()!=='af-smoke')throw Error('BAD_TITLE'); console.log('PASS')}finally{if(b)await b.close()}})().catch(e=>{console.error(e.message);process.exit(2)});"""
    try:
        p = subprocess.run([str(state['node']),'-e',code,str(home/'node_modules/playwright'),str(state['chrome_path'])],
                           capture_output=True,text=True,timeout=40)
        if p.returncode:
            return {'pass':False,'reason':'CHROME_LAUNCH_FAILED','exit_code':p.returncode, 'error_tail':p.stderr[-250:]}
        agent = home/'node_modules/.bin/agent-browser'
        r = subprocess.run([str(agent),'--version'],capture_output=True,text=True,timeout=15)
        return {'pass':r.returncode==0 and 'PASS' in p.stdout,'reason':'PASS' if r.returncode==0 else 'AGENT_BROWSER_FAILED'}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'pass':False,'reason':type(exc).__name__}


def install_browser(root: Path, *, offline=False, timeout=240):
    home=paths(root)['browser']
    s=browser_state(home)
    if not (s['chrome_path'] and s['node'] and s['npm']):
        return {'status':'BLOCKED','reason':'BROWSER_PREREQUISITES_MISSING'}
    if not s['versions_match']:
        if offline:
            return {'status':'BLOCKED','reason':'BROWSER_NOT_CACHED'}
        home.mkdir(parents=True,exist_ok=True)
        package = home/'package.json'
        if not package.is_file():
            package.write_text(json.dumps({'name':'agentflow-project-browser-tools','private':True,'version':'0.0.0'})+'\n')
        result=subprocess.run([str(s['npm']),'install','--save-exact','--ignore-scripts','--no-audit','--no-fund',
                               *[f'{k}@{v}' for k,v in BROWSER_VERSIONS.items()]],
                              cwd=home,capture_output=True,text=True,timeout=timeout)
        if result.returncode:
            return {'status':'BLOCKED','reason':'NPM_INSTALL_FAILED','error_tail':result.stderr[-400:]}
    smoke=browser_smoke(home)
    return {'status':'READY' if smoke['pass'] else 'BLOCKED','versions':browser_state(home)['installed_versions'],
            'smoke':smoke,'reason':smoke['reason']}


def provision(root: Path, *, offline=False, browser=True):
    """Run only during installation. No global fallback; no hooks or MCP config change."""
    root=Path(root).resolve()
    escape=symlink_escape(root)
    if escape:
        return {'status':'BLOCKED','reason':'PROJECT_TOOL_SYMLINK', 'path':escape}
    if not (root/'.ai-dev/external-skills.lock.json').is_file():
        return {'status':'BLOCKED','reason':'UPSTREAM_SKILLS_NOT_INSTALLED'}
    results={'rtk':install_rtk(root,offline=offline), 'crg':install_crg(root,offline=offline)}
    if browser:
        results['browser']=install_browser(root,offline=offline)
    status='READY' if all(v.get('status')=='READY' for v in results.values()) else 'BLOCKED'
    manifest={'schema':1,'scope':'PROJECT_ONLY','version_locks':{'rtk':RTK_VERSION,'crg':CRG_VERSION,'browser':BROWSER_VERSIONS},
              'results':results,'status':status,
              'note':'Hook, MCP, graph freshness, actual native skill/worker use NOT_VERIFIED'}
    lock=paths(root)['lock'];lock.parent.mkdir(parents=True,exist_ok=True)
    lock.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return {'status':status,'scope':'PROJECT_ONLY','results':results,'lock':str(lock)}
