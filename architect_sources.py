#!/usr/bin/env python3
"""Pinned, project-local Project Architect external skills acquisition.

Acquires complete selected skill *directories* at immutable source commits.
No fetched scripts are executed during installation. Original content is untrusted.
"""
from __future__ import annotations
import hashlib
import io
import json
import stat
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOTS = ('.opencode/skills', '.claude/skills', '.agents/skills')
LEGACY = {'af-project-discovery', 'af-design-plan', 'af-architecture-design',
          'af-design-verification', 'af-architecture-review'}
REPOS = {
 'MUSUBI': {'repo':'nahisaho/MUSUBI', 'commit':'d9c21f4529ca94f0f5d07d9c049198398a8e3a1f', 'license':'LICENSE', 'license_sha':'0dddbe26d010a4a7723e13a63a101a2639040c9d'},
 'skills': {'repo':'eralmansouri/skills', 'commit':'a0cad2c8755eccea344e4867d83a11e6d3652e69', 'license':None, 'license_sha':None},
 'ECC': {'repo':'affaan-m/ECC', 'commit':'d2ef2680594f9a17526a6e1a2e18b3d242c5d17b', 'license':'LICENSE', 'license_sha':'b832b6f642312312367c07688dc7426db40a82ed'},
}
SKILLS = {
 'requirements-analyst': ('MUSUBI','.claude/skills/requirements-analyst','e055b0d2ca64a86ccf51f0dd31bf62edf557380e'),
 'change-impact-analyzer': ('MUSUBI','.claude/skills/change-impact-analyzer','7df16fbf4d49a2aedeafd390a94bee14e72aa029'),
 'project-manager': ('MUSUBI','.claude/skills/project-manager','6810cbe8ad896e37c0e89fc7e64695a14309a39d'),
 'system-architect': ('MUSUBI','.claude/skills/system-architect','9dd1a970e863d249f3b4717201b9fdf51ed40c32'),
 'architecture-decision-records': ('ECC','skills/architecture-decision-records','84f2dd608b4589f7e74e876927ddce866e12a3d1'),
 'traceability-auditor': ('MUSUBI','.claude/skills/traceability-auditor','5b0683b3cd763e2ae0a7e89d220cf9270fb3ff43'),
 'design-review': ('skills','skills/design-review','e6746829e78d50d6cd1d761fdcaa30cb34108228'),
 'security-auditor': ('MUSUBI','.claude/skills/security-auditor','8d77a5e0ba0e5d035419d59f05993adf95e7bede'),
}
STAGE_MAP = {
 'ANALYZE':[('requirements-analyst',True),('change-impact-analyzer',False)],
 'PLAN':[('project-manager',True)],
 'IMPLEMENT':[('system-architect',True),('architecture-decision-records',False)],
 'VERIFY':[('traceability-auditor',True)],
 'REVIEW':[('design-review',True),('security-auditor',False)],
}
MAX_ARCHIVE=95_000_000
MAX_FILE=3_000_000
MAX_TOTAL=25_000_000
MAX_FILES=250

def git_blob_sha1(data:bytes)->str:
 return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest()

def archive_bytes(key:str, archive_dir:Path|None=None)->bytes:
 info=REPOS[key]
 if archive_dir is not None:
  p=Path(archive_dir)/f'{key}-{info["commit"]}.zip'
  if not p.is_file():raise ValueError(f'PINNED_ARCHIVE_NOT_FOUND: {p}')
  if p.stat().st_size>MAX_ARCHIVE:raise ValueError(f'ARCHIVE_TOO_LARGE: {key}')
  return p.read_bytes()
 url=f'https://codeload.github.com/{info["repo"]}/zip/{info["commit"]}'
 q=urllib.request.Request(url,headers={'User-Agent':'AgentFlow-Architect-Pinned-Installer/0.8.2'})
 with urllib.request.urlopen(q,timeout=45) as resp:return resp.read(MAX_ARCHIVE+1)

def load_package(archive_dir:Path|None=None, blobs:dict[str,bytes]|None=None)->dict:
 """Return checked {files, source_manifest, licenses}; raises before target writes."""
 files={}; license_files={}; manifest={}; total=0; count=0
 for key,info in REPOS.items():
  blob=blobs[key] if blobs is not None else archive_bytes(key,archive_dir)
  if len(blob)>MAX_ARCHIVE:raise ValueError('ARCHIVE_TOO_LARGE: '+key)
  prefixes={directory.rstrip('/')+'/':name for name,(source,directory,sha) in SKILLS.items() if source==key}
  names={name for name,(source,_,_) in SKILLS.items() if source==key}
  selected={}; license_data=None
  with zipfile.ZipFile(io.BytesIO(blob)) as zipf:
   for z in zipf.infolist():
    path=z.filename
    if '\\' in path or '\x00' in path or path.startswith('/'):
     raise ValueError('UNSAFE_ARCHIVE_PATH: '+path)
    parts=PurePosixPath(path).parts
    if any(x in ('.','..') for x in parts) or len(parts)<2:
     if z.is_dir():continue
     raise ValueError('UNSAFE_ARCHIVE_PATH: '+path)
    rel='/'.join(parts[1:])
    if z.is_dir():continue
    mode=z.external_attr>>16
    if stat.S_IFMT(mode) in (stat.S_IFLNK,stat.S_IFCHR,stat.S_IFBLK,stat.S_IFIFO,stat.S_IFSOCK):
     raise ValueError('UNSAFE_ARCHIVE_FILE_TYPE: '+path)
    match=next(((prefix,name) for prefix,name in prefixes.items() if rel.startswith(prefix)),None)
    license_match=info['license'] is not None and rel==info['license']
    if match is None and not license_match:continue
    if z.file_size>MAX_FILE:raise ValueError('SKILL_FILE_TOO_LARGE: '+path)
    count+=1;total+=z.file_size
    if count>MAX_FILES or total>MAX_TOTAL:raise ValueError('ARCHITECT_PACKAGE_LIMIT_EXCEEDED')
    data=zipf.read(z)
    if len(data)!=z.file_size:raise ValueError('ARCHIVE_FILE_SIZE_MISMATCH')
    if license_match:
     if license_data is not None:raise ValueError('DUPLICATE_LICENSE: '+key)
     license_data=data
    else:
     prefix,name=match
     sub=rel[len(prefix):]
     if not sub or sub.startswith('/') or sub in ('.','..'):raise ValueError('UNSAFE_SKILL_PATH')
     final=f'{name}/{sub}'
     if final in files:raise ValueError('DUPLICATE_SKILL_FILE: '+final)
     files[final]=data
     selected.setdefault(name,set()).add(sub)
  for name in names:
   original=files.get(f'{name}/SKILL.md')
   expected=SKILLS[name][2]
   if original is None:raise ValueError('MISSING_PINNED_SKILL: '+name)
   if git_blob_sha1(original)!=expected:raise ValueError('EXTERNAL_SKILL_HASH_MISMATCH: '+name)
   if not original.startswith(b'---\n') or b'name: '+name.encode() not in original[:512]:
    raise ValueError('EXTERNAL_SKILL_METADATA_INVALID: '+name)
  if info['license']:
   if license_data is None or git_blob_sha1(license_data)!=info['license_sha']:
    raise ValueError('EXTERNAL_LICENSE_MISMATCH: '+key)
   license_files[f'.ai-dev/licenses/architect-{key}-LICENSE']=license_data
   license_state='PINNED_ORIGINAL'
  else:
   license_state='NO_EXPLICIT_REPOSITORY_LICENSE_CHECKED'
  manifest[key]={'repo':info['repo'],'commit':info['commit'],'license_status':license_state,
                 'skills':sorted(names)}
 return {'files':files, 'licenses':license_files, 'sources':manifest}

def managed_entries(package):
 out={}
 for name,(key,path,sha) in SKILLS.items():
  info=REPOS[key]
  related={p[len(name)+1:]:hashlib.sha256(data).hexdigest() for p,data in package['files'].items() if p.startswith(name+'/')}
  out[name]={'source':f'github:{info["repo"]}','source_path':path,'commit':info['commit'],
             'git_blob_sha1':sha,'files_sha256':related,'native_skill_load':'NOT_VERIFIED',
             'license_status':package['sources'][key]['license_status']}
 return out

def stage_skills(stage):
 return [{'name':name,'required':required,'condition':'always' if required else 'optional'} for name,required in STAGE_MAP[stage]]

def update_tree(tree:dict):
 if tree.get('id')!='project-architect':raise ValueError('NOT_PROJECT_ARCHITECT_TREE')
 for stage in tree.get('stages',[]):
  if stage.get('id') not in STAGE_MAP:continue
  # Do not change enabled, activities, agent or other stage's configuration.
  original=stage.get('skills',[])
  existing=[s for s in original if s.get('name') not in LEGACY and s.get('name') not in SKILLS]
  stage['skills']=existing+stage_skills(stage['id'])
 return tree
