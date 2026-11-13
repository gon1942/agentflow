#!/usr/bin/env python3
"""Conservative v0.8.0 update: preview by default, exact-hash legacy command cleanup.

Never overwrites profiles, task data, approval records, skill trees, or custom commands.
"""
from __future__ import annotations
import argparse
import hashlib
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
LEGACY = {
    'agentflow-magr.md': '24b010bc02a41a6fb508b448069851e1eb2b88f78ecf75e3b57097eaabb97bd6',
    'agentflow-mngr-start.md': '62446b6ac5f0f1d0615fdf49e105427e274695f61fba6af35adbcc249c8d3024',
    'agentflow-mngr-status.md': '7f125d07dd354d46549c2a9373f89c66e7c2291fd8c4912891b6e3f9aeda92de',
    'agentflow-mngr-stop.md': 'f9d00515f9dc4017d45db16c8c97d89641ca4e04aa555f90a918ee99032eb64b',
}
FILES = ('agentflow_console/core.py','agentflow_console/ui.html','.opencode/commands/agentflow-mngr.md')

def update(root: Path, apply=False):
    if not (root/'agentflow_console/core.py').is_file() or not (root/'.opencode/commands').is_dir():
        raise SystemExit('Not an installed AgentFlow project; nothing changed')
    if (root/'docs/tasks/active').exists() and any((root/'docs/tasks/active').iterdir()):
        raise SystemExit('TASK_ACTIVE: upgrade blocked until active tasks finish')
    for rel in FILES:
        source = BASE/'scaffold'/rel
        dest = root/rel
        if not dest.exists():
            raise SystemExit(f'Missing existing path: {dest}')
        if dest.is_symlink():
            raise SystemExit(f'Symlink refused: {dest}')
        print(('APPLY' if apply else 'PREVIEW')+' replace '+str(dest))
        if apply:
            backup=dest.with_name(dest.name+'.pre-v080.bak')
            if backup.exists():
                raise SystemExit(f'Backup already exists: {backup}')
            shutil.copy2(dest,backup)
            shutil.copy2(source,dest)
    for name, digest in LEGACY.items():
        dest=root/'.opencode/commands'/name
        if not dest.exists():continue
        if dest.is_symlink() or hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:
            print('PRESERVE customized legacy command:',dest)
            continue
        print(('APPLY' if apply else 'PREVIEW')+' remove duplicate '+str(dest))
        if apply:dest.unlink()
    print('Finished.' if apply else 'Dry run only; pass --apply to modify files.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('project',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    update(args.project.expanduser().resolve(),args.apply)
