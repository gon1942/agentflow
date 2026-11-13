#!/usr/bin/env python3
"""Non-destructive RC5 -> RC6 console-runtime upgrade; dry-run unless --apply.

Preserves AI adapter patch, user UI, workflows, profiles, skill trees and task records.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parent
ORIGINAL = BASE.parent / 'agentflow-native-skills-tools-improver-v0.5.0-rc5' / 'scaffold'
# Hashes are generated from the known pristine RC5 source, so an upgrade cannot
# silently overwrite local hand edits. Inline values independent of RC5 folder.
EXPECTED_RC5_SHA256 = {
    'agentflow_console.py': 'c9c76d8ab14eab2117e9389451c9c1c1e50a94a63c18b6079c5310e97038503c',
    'agentflow_console/server.py': 'f59d30e3bf1ec1743f2074ba104d8339e722d85af0ba88ad07aa5b8d04afae67',
}
SOURCES = ('agentflow_console.py', 'agentflow_console/server.py',
           'agentflow_console/lifecycle.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description='RC5 console runtime updater; safe dry-run default')
    ap.add_argument('project')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    project = Path(args.project).expanduser().resolve()
    if not (project/'agentflow_console.py').is_file():
        raise SystemExit('BLOCKED: Not an installed AgentFlow project')
    # Only touch 3 console management files. Existing AI advisor stays untouched.
    for rel in SOURCES:
        target = project / rel
        if target.is_symlink() or any(part.is_symlink() for part in list(target.parents) if part == project or project in part.parents):
            raise SystemExit('BLOCKED: Symlink in runtime target path: ' + rel)
        if rel in EXPECTED_RC5_SHA256 and target.exists():
            current = sha(target)
            if current not in (EXPECTED_RC5_SHA256[rel], sha(BASE/'scaffold'/rel)):
                raise SystemExit('BLOCKED: Existing runtime is modified: '+rel)
        if rel == 'agentflow_console/lifecycle.py' and target.exists() and sha(target) != sha(BASE/'scaffold'/rel):
            raise SystemExit('BLOCKED: Existing lifecycle.py is modified')
    print('Project:', project)
    print('Files:', ', '.join(SOURCES))
    if not args.apply:
        print('DRY_RUN: no files changed. Stop running console and pass --apply to proceed.')
        return
    # Refuse updating a currently managed runtime.
    # Check managed runtime if already present; legacy foreground processes must be stopped manually.
    if (project/'agentflow_console/lifecycle.py').is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location('agentflow_runtime_updater_lifecycle', project/'agentflow_console/lifecycle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if module.info(project)['running']:
            raise SystemExit('BLOCKED: Stop managed console before upgrade')
    backup = project/'.agentflow'/'backups'/('runtime-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True, exist_ok=False)
    for rel in SOURCES:
        target = project/rel
        if target.exists():
            old = backup/rel
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target,old)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE/'scaffold'/rel,target)
    print('APPLIED; backup:', backup)
    print('Existing AI adapter, profiles, skill trees, tasks and approvals unchanged.')

if __name__ == '__main__':
    main()
