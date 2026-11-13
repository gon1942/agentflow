#!/usr/bin/env python3
"""Reviewable, project-local AgentFlow RC1->RC2 console UI update.

Only web UI and server shutdown handling change. Keeps profiles, locks, agents,
logs, projects, and all user-managed skills untouched.
"""
from __future__ import annotations
import argparse
import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile

FILES=('agentflow_console/ui.html','agentflow_console/server.py')

def update(source: Path, project: Path, apply: bool) -> int:
    project=project.resolve()
    source=source.resolve()
    if not project.is_dir() or not (project/'agentflow_console.py').is_file() or not (project/'.ai-dev').is_dir():
        print('ERROR: Not an installed AgentFlow project', file=sys.stderr)
        return 2
    if project == source or source in project.parents:
        print('ERROR: source and target must differ',file=sys.stderr)
        return 2
    paths=[]
    for name in FILES:
        src=source/'scaffold'/name
        dst=project/name
        if not src.is_file() or not dst.is_file() or dst.is_symlink() or dst.parent.is_symlink():
            print('ERROR: Invalid or missing target: '+name,file=sys.stderr)
            return 2
        paths.append((src,dst))
    print('Target:',project)
    print('Changes:')
    for src,dst in paths:
        print(' ',dst.relative_to(project),':', 'UNCHANGED' if src.read_bytes()==dst.read_bytes() else 'UPDATE')
    if not apply:
        print('DRY RUN only. Use --apply to create backups and install the changes.')
        return 0
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup=project/'.agentflow'/'backups'/('console-ui-'+stamp)
    backup.mkdir(parents=True,exist_ok=False)
    changed=[]
    try:
        for src,dst in paths:
            saved=backup/dst.relative_to(project)
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dst,saved)
        for src,dst in paths:
            if src.read_bytes()==dst.read_bytes():
                continue
            with tempfile.NamedTemporaryFile(dir=dst.parent,prefix='.agentflow-ui-',delete=False) as tmp:
                tmp_path=Path(tmp.name)
                tmp.write(src.read_bytes())
            try:
                os.chmod(tmp_path,dst.stat().st_mode)
                os.replace(tmp_path,dst)
                changed.append(dst)
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        for dst in changed:
            shutil.copy2(backup/dst.relative_to(project),dst)
        print('ERROR: rollback completed after:',exc,file=sys.stderr)
        return 2
    print('UI update completed. Backup:',backup)
    print('Restart the web console to load the new UI. Profiles, skills and tasks were not changed.')
    return 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project',help='Existing AgentFlow project directory')
    ap.add_argument('--apply',action='store_true',help='Apply after dry-run review')
    ns=ap.parse_args()
    return update(Path(__file__).resolve().parent,Path(ns.project),ns.apply)

if __name__=='__main__':raise SystemExit(main())
