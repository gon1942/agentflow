#!/usr/bin/env python3
"""Upgrade RC8 AI candidate descriptions and GitHub links only.

Dry-run by default; retains profiles, trees, tasks, and other runtime files.
"""
from pathlib import Path
import argparse, datetime, shutil, sys
p=argparse.ArgumentParser()
p.add_argument('project')
p.add_argument('--apply',action='store_true')
a=p.parse_args()
project=Path(a.project).expanduser().resolve()
source=Path(__file__).resolve().parent/'scaffold/agentflow_console'
target=project/'agentflow_console'
files=['external.py','ui.html']
if not (project/'agentflow_console.py').is_file() or not target.is_dir():
 sys.exit('ERROR: Not an AgentFlow console project')
for name in files:
 if not (target/name).is_file() or (target/name).is_symlink():sys.exit('ERROR: invalid target '+name)
 if not (source/name).is_file():sys.exit('ERROR: missing source '+name)
print('Project:',project)
for name in files: print('Update:',target/name)
if not a.apply:
 print('DRY_RUN: no changes. Use --apply with console stopped.');sys.exit(0)
backup=project/'.agentflow/backups'/('skill-details-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
backup.mkdir(parents=True,exist_ok=False)
for name in files:
 shutil.copy2(target/name,backup/name)
 shutil.copy2(source/name,target/name)
print('APPLIED. Backup:',backup)
print('Restart web console to apply changes.')
