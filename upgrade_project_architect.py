#!/usr/bin/env python3
"""Safe opt-in migration of Project Architect to eight pinned external skills.

All user stage selections, additional skills, other profiles, and Gate settings
are preserved. No original file is mutated before all source ZIPs are verified.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
import architect_sources as architect

TREE='.agentflow/skill-trees/project-architect.json'
LOCK='.ai-dev/external-skills.lock.json'
BACKUPS='.agentflow/backups'

def safe_path(root:Path,rel:str)->Path:
 parts=PurePosixPath(rel).parts
 if not parts or any(x in ('..','.') for x in parts) or rel.startswith('/') or '\\' in rel:
  raise ValueError('UNSAFE_DESTINATION: '+rel)
 cursor=root
 for part in parts:
  cursor=cursor/part
  if cursor.is_symlink():raise ValueError('SYMLINK_BLOCKED: '+str(cursor))
 return cursor

def check(root:Path):
 if not root.is_dir():raise ValueError('TARGET_PROJECT_NOT_FOUND: '+str(root))
 if not (root/'docs/workflow/WORKFLOW.md').is_file():raise ValueError('NOT_AN_AGENTFLOW_PROJECT')
 for rel in (TREE,LOCK):
  if not safe_path(root,rel).is_file():raise ValueError('AGENTFLOW_CONFIG_MISSING: '+rel)
 active=root/'docs/tasks/active'
 if active.exists() and (active.is_symlink() or any(active.iterdir())):
  raise ValueError('TASK_ACTIVE: cannot change pinned skill contract while an active task exists')

def _refs_other_profiles(root:Path)->set[str]:
 refs=set()
 trees=root/'.agentflow/skill-trees'
 for path in trees.glob('*.json'):
  if path.name=='project-architect.json':continue
  if path.is_symlink():raise ValueError('SYMLINK_BLOCKED: '+str(path))
  doc=json.loads(path.read_text(encoding='utf-8'))
  for stage in doc.get('stages',[]):
   for s in stage.get('skills',[]):refs.add(s.get('name',''))
 return refs

def prepare(root:Path,package:dict)->tuple[dict[str,bytes],list[str]]:
 check(root)
 tree=json.loads(safe_path(root,TREE).read_text(encoding='utf-8'))
 lock=json.loads(safe_path(root,LOCK).read_text(encoding='utf-8'))
 if tree.get('id')!='project-architect':raise ValueError('WRONG_ARCHITECT_TREE')
 architect.update_tree(tree)
 lock.setdefault('managed_skills',{}).update(architect.managed_entries(package))
 lock['project_architect_sources']=package['sources']
 writes={TREE:(json.dumps(tree,ensure_ascii=False,indent=2)+'\n').encode()}
 writes.update(package['licenses'])
 for rootname in architect.ROOTS:
  for key,data in package['files'].items():writes[f'{rootname}/{key}']=data
 for rel,data in writes.items():
  dest=safe_path(root,rel)
  if dest.exists() and rel not in (TREE,LOCK):
   if not dest.is_file() or dest.read_bytes()!=data:
    raise ValueError('EXISTING_FILE_CONFLICT: '+rel)
 # Remove only old own managed skill files when no other tree needs them
 # and bytes still match registered hashes; never touch user-modified skills.
 other=_refs_other_profiles(root)
 removals=[]
 for name in architect.LEGACY-other:
  meta=lock.get('managed_skills',{}).get(name)
  if not meta or meta.get('source')!='agentflow-local-bundled-v0.7.7':continue
  expected=meta.get('files_sha256',{}).get('SKILL.md')
  if not expected:continue
  paths=[f'{rt}/{name}/SKILL.md' for rt in architect.ROOTS]
  if all(safe_path(root,p).is_file() and hashlib.sha256(safe_path(root,p).read_bytes()).hexdigest()==expected for p in paths):
   removals+=paths
   lock['managed_skills'].pop(name,None)
 writes[LOCK]=(json.dumps(lock,ensure_ascii=False,indent=2)+'\n').encode()
 return writes,removals

def migrate(root:Path,apply:bool=False,archive_dir:Path|None=None,package:dict|None=None)->dict:
 root=root.expanduser().resolve()
 check(root)
 if not apply and package is None:
  return {'status':'PREVIEW','project':str(root),'profile':'project-architect',
          'skills':list(architect.SKILLS),'git_commits':{k:v['commit'] for k,v in architect.REPOS.items()},
          'stage_settings':'PRESERVE','user_skills':'PRESERVE','native_load':'NOT_VERIFIED'}
 if package is None:package=architect.load_package(archive_dir)
 writes,removals=prepare(root,package)
 if not apply:return {'status':'PRECHECK_PASS','writes':len(writes),'removed_legacy_files':len(removals)}
 backup=root/BACKUPS/('project-architect-v082-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
 backup.mkdir(parents=True,exist_ok=False)
 created=[]; replaced=[]; moved=[]
 try:
  for rel,data in sorted(writes.items()):
   dest=safe_path(root,rel)
   dest.parent.mkdir(parents=True,exist_ok=True)
   if dest.exists():
    prev=backup/'previous'/rel
    prev.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(dest,prev)
    replaced.append(rel)
   else:created.append(rel)
   fd,tmp=tempfile.mkstemp(prefix='.af082-',dir=dest.parent)
   try:
    with os.fdopen(fd,'wb') as out:
     out.write(data);out.flush();os.fsync(out.fileno())
    os.replace(tmp,dest)
   finally:Path(tmp).unlink(missing_ok=True)
  for rel in removals:
   dest=safe_path(root,rel)
   saved=backup/'removed'/rel
   saved.parent.mkdir(parents=True,exist_ok=True)
   os.replace(dest,saved)
   moved.append(rel)
 except BaseException:
  for rel in reversed(moved):
   restored=backup/'removed'/rel
   safe_path(root,rel).parent.mkdir(parents=True,exist_ok=True)
   os.replace(restored,safe_path(root,rel))
  for rel in reversed(created):safe_path(root,rel).unlink(missing_ok=True)
  for rel in reversed(replaced):
   os.replace(backup/'previous'/rel,safe_path(root,rel))
  raise
 return {'status':'INSTALLED','project':str(root),'external_skills':len(architect.SKILLS),
         'skill_files':len(package['files']),'copied_to_agent_roots':len(architect.ROOTS),
         'removed_unused_legacy_files':len(removals),'backup':str(backup),
         'license_warning':'eralmansouri/skills has no verified root license; confirm usage rights',
         'native_skill_load':'NOT_VERIFIED'}

def main(args=None):
 ap=argparse.ArgumentParser(description='AgentFlow v0.8.2 Project Architect upgrade (preview by default)')
 ap.add_argument('project',type=Path)
 ap.add_argument('--apply',action='store_true',help='Actually migrate after checks and backups')
 ap.add_argument('--architect-archive-dir',type=Path,help='Directory with 3 pinned source ZIP archives')
 ns=ap.parse_args(args)
 try:
  output=migrate(ns.project,ns.apply,ns.architect_archive_dir)
  print(json.dumps(output,indent=2,ensure_ascii=False));return 0
 except Exception as exc:
  print(f'UPGRADE_BLOCKED: {exc}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
