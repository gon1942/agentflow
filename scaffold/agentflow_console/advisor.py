"""Read-only, provenance-aware advisory. Never installs a skill.

Optional Vercel Skills CLI is ONLY invoked from a project-local executable.
Unpinned skills.sh candidates are NOT marked verified or install-ready.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
MATCH = re.compile(r'^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([a-z][a-z0-9-]{0,63})$')
STAGE_TERMS = {'ANALYZE':'requirements analysis','PLAN':'implementation planning','VERIFY':'verification testing','IMPLEMENT':'implementation development','REVIEW':'code review','BUG_FAIL':'debugging','REVIEW_FIX':'code review'}
RELEVANT = {
 'ANALYZE': {'requirement','analys','codebase','research','business','specification','discovery','architecture','impact'},
 'PLAN': {'plan','task','spec','ticket','implementation','roadmap','architect','design'},
 'VERIFY': {'verif','test','audit','quality','check','review'},
 'IMPLEMENT': {'implement','code','develop','build'},
 'REVIEW': {'review','audit','quality','security','code'},
 'BUG_FAIL': {'debug','diagnos','troubleshoot','fix'},
 'REVIEW_FIX': {'review','fix','debug','refactor'},
}
OFFTOPIC = {'image-generation','knowledge-wiki','sg-beat-reference'}


def new_run_id():
 return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]


def now_iso(): return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def save_trace(root, trace):
 """Atomic, restricted, local-only JSON trace; excludes prompt/stdout/secrets."""
 directory=Path(root)/'.agentflow/logs/skill-advisor/runs'
 directory.mkdir(parents=True, exist_ok=True, mode=0o700)
 try: directory.chmod(0o700)
 except OSError: pass
 run_id=trace['run_id']
 if not re.fullmatch(r'[0-9TZ-]+-[a-f0-9]{10}',run_id): raise ValueError('INVALID_TRACE_ID')
 temp=directory/(run_id+'.tmp'); final=directory/(run_id+'.json')
 blob=json.dumps(trace,ensure_ascii=False,indent=2).encode('utf-8')
 if len(blob)>250_000: raise ValueError('TRACE_TOO_LARGE')
 with temp.open('xb') as f:
  os.chmod(temp,0o600);f.write(blob)
 temp.replace(final)


def list_traces(root):
 directory=Path(root)/'.agentflow/logs/skill-advisor/runs'
 result=[]
 if directory.exists():
  for f in sorted(directory.glob('*.json'),reverse=True)[:40]:
   if f.is_symlink() or not re.fullmatch(r'[0-9TZ-]+-[a-f0-9]{10}\.json',f.name):continue
   try:
    obj=json.loads(f.read_text(encoding='utf-8'))
    result.append({k:obj.get(k) for k in ['run_id','created_at','host','profile','stages','status','candidate_count','engine_status']})
   except (OSError,ValueError,UnicodeError):continue
 return result


def read_trace(root, run_id):
 if not isinstance(run_id,str) or not re.fullmatch(r'[0-9TZ-]+-[a-f0-9]{10}',run_id):raise ValueError('INVALID_TRACE_ID')
 f=Path(root)/'.agentflow/logs/skill-advisor/runs'/(run_id+'.json')
 if f.is_symlink() or not f.is_file():raise ValueError('TRACE_NOT_FOUND')
 return json.loads(f.read_text(encoding='utf-8'))


def local_skills_cli(root):
 """Never resolve system PATH / auto-install npx; explicit project-local opt-in."""
 project=Path(root).resolve()
 for name in ('.agentflow/tools/skills-cli/node_modules/.bin/skills','.agentflow/tools/node_modules/.bin/skills'):
  item=project/name
  if not item.exists():continue
  target=item.resolve()
  if target.is_relative_to(project) and target.is_file():return str(item)
 return None


def search_terms(question,stage):
 """Use generic terms only so request text is not transmitted externally."""
 q=question.lower()
 terms=[STAGE_TERMS.get(stage,'agent skills')]
 mappings=[('요구사항','requirements analysis'),('분석','requirements analysis'),('코드','codebase analysis'),('계획','implementation planning'),('설계','software design'),('검증','verification testing'),('버그','debugging'),('테스트','testing'),('requirements','requirements analysis'),('codebase','codebase analysis'),('planning','implementation planning')]
 for trigger,term in mappings:
  if trigger in q and term not in terms:terms.append(term)
 return terms[:3]


def parse_cli_search(text, stage, query):
 lines=ANSI.sub('',text).splitlines()
 results=[];seen=set()
 for line in lines:
  match=MATCH.fullmatch(line.strip())
  if not match:continue
  full,name=match.groups()
  key=(full,name)
  if key in seen:continue
  seen.add(key)
  results.append({'name':name,'stage':stage,'origin':'external','verified':False,'source_status':'SKILLS_CLI_DISCOVERED_UNPINNED',
    'reason':'Skills CLI 검색 후보 · Git 커밋/하위 경로 및 보안 미검증','description':'',
    'url':'https://github.com/'+full+'.git','commit':'','subdir':'',
    'discovery_engine':'skills-cli','discovery_query':query})
 return results[:15]


def discover_cli(root, question, stages):
 exe=local_skills_cli(root)
 if exe is None:return {'status':'UNAVAILABLE','reason':'PROJECT_LOCAL_SKILLS_CLI_NOT_INSTALLED','candidates':[],'searches':[]}
 searches=[];candidates=[]
 for stage in stages[:4]:
  for query in search_terms(question,stage):
   started=time.monotonic()
   try:
    result=subprocess.run([exe,'find',query],cwd=root,stdin=subprocess.DEVNULL,capture_output=True,timeout=12,check=False,env={**os.environ,'NO_COLOR':'1','CI':'1'})
    duration=round((time.monotonic()-started)*1000)
    if result.returncode or len(result.stdout)>100_000:
     searches.append({'stage':stage,'query':query,'status':'FAILED','duration_ms':duration,'count':0});continue
    rows=parse_cli_search(result.stdout.decode('utf-8','replace'),stage,query)
    candidates.extend(rows)
    searches.append({'stage':stage,'query':query,'status':'COMPLETED','duration_ms':duration,'count':len(rows)})
   except (subprocess.TimeoutExpired,OSError):
    searches.append({'stage':stage,'query':query,'status':'TIMEOUT_OR_UNAVAILABLE','duration_ms':round((time.monotonic()-started)*1000),'count':0})
 unique={}
 for c in candidates:unique[(c['url'],c['name'],c['stage'])]=c
 status='COMPLETED' if searches and all(x['status']=='COMPLETED' for x in searches) else 'PARTIAL' if any(x['status']=='COMPLETED' for x in searches) else 'SEARCH_UNAVAILABLE'
 return {'status':status,'candidates':list(unique.values())[:25],'searches':searches,'reason':'SOURCE_DISCOVERY_ONLY_NOT_INSTALLED'}


def inspect_policy(item, profile_id, stage, source_text=''):
 name=str(item.get('name','')).lower()
 description=str(item.get('description',''))[:800]
 reason=str(item.get('reason',''))[:500]
 content=(name+' '+description).lower()
 termset=RELEVANT.get(stage,set())
 relevant=any(term in content for term in termset)
 off=name in OFFTOPIC or any(term in name for term in ('image-generation','knowledge-wiki','beat-reference'))
 conflict=bool(profile_id=='task-planning' and stage=='ANALYZE' and name=='brainstorming')
 # Explicit evidence only. Unknown external contents cannot be declared safe.
 if not conflict and source_text:
  snippet=source_text.lower()
  conflict=bool(profile_id=='task-planning' and ('approval' in snippet or '승인' in snippet) and ('before proceeding' in snippet or 'must get' in snippet or '승인받' in snippet))
 if conflict:grade='POLICY_CONFLICT';rationale='Task Planning 분석에서 설계 승인 강제 규칙과 충돌할 가능성'
 elif off:grade='NOT_RELEVANT';rationale='요청의 분석·계획 목적과 무관한 스킬'
 elif not relevant:grade='INSUFFICIENT_EVIDENCE';rationale='원본 내용에서 단계 적합성을 확인할 충분한 근거가 없음'
 elif item.get('origin')=='external':grade='REVIEW_REQUIRED';rationale='단계 관련성이 있으나 전체 SKILL.md·의존성·보안 미검증'
 else:grade='LIKELY_RELEVANT';rationale='단계와 관련된 로컬 스킬. 실행 적합성은 별도 테스트 필요'
 return {'verdict':grade,'reason':rationale,'evidence_level':'LOCAL_NAME_DESCRIPTION' if item.get('origin')=='local' else 'UNVERIFIED_METADATA','policy_conflict':conflict,'installation_allowed':False}


def validate_candidates(items, profile, root):
 result=[]
 for item in items:
  row=dict(item)
  # Avoid relying on any LLM claim of verified sources.
  source=''
  if row.get('origin')=='local':
   file=Path(root)/'.opencode/skills'/str(row.get('name'))/'SKILL.md'
   try:
    if file.is_file() and not file.is_symlink() and file.stat().st_size<100_000:source=file.read_text(encoding='utf-8')
   except (OSError,UnicodeError):pass
  row['assessment']=inspect_policy(row,profile,row.get('stage',''),source)
  result.append(row)
 return result
