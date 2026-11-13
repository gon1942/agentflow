"""Optional native-host LLM skill suggestions. Never installs or executes skills.

Backend availability and native safety depend on the installed host version.
The adapter is opt-in, bounded, and returns untrusted proposal text only.
"""
from __future__ import annotations
import os
import json
import re
from pathlib import Path
import shutil
import subprocess
from .core import ManagementError, Manager, executable_stages

AVAILABLE = ('opencode', 'claude', 'codex')


def _suggest_core(manager: Manager, host: str, question: str, profile_id: str | None = None, stage_id: str | None = None, search_external: bool = False):
    if host not in AVAILABLE:
        raise ManagementError('UNSUPPORTED_AGENT_HOST')
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
        raise ManagementError('INVALID_AI_QUERY')
    question = question.strip()
    if profile_id is not None and (not isinstance(profile_id, str) or len(profile_id) > 64):
        raise ManagementError('INVALID_AI_PROFILE')
    if stage_id is not None and (not isinstance(stage_id, str) or len(stage_id) > 64):
        raise ManagementError('INVALID_AI_STAGE')
    selected_profile = manager.profile(profile_id) if profile_id else manager.profile(manager.active()['profile'])
    selected_tree = manager.tree(selected_profile['skill_tree'])
    allowed_stages = ({item['id'] for item in selected_tree['stages']} - {'SESSION','GATE1','GATE2','COMPLETE'}) & set(executable_stages(selected_profile))
    if stage_id and stage_id != 'ALL' and stage_id not in allowed_stages:
        raise ManagementError('INVALID_AI_STAGE')
    target_stage = stage_id or 'ANALYZE'
    selected_stages = [s['id'] for s in selected_tree['stages'] if s['id'] in allowed_stages] if target_stage == 'ALL' else [target_stage]
    exe = shutil.which(host)
    if not exe:
        raise ManagementError('AGENT_HOST_UNAVAILABLE: ' + host)
    skills = manager.list_skills()
    verified = [item['name'] for item in skills if item['verified']]
    # Read only short, local, verified SKILL.md metadata; never run a skill.
    catalog=[]
    for name in verified:
        path=manager.root/'.opencode/skills'/name/'SKILL.md'
        try:
            if path.is_symlink() or path.stat().st_size>250_000:
                continue
            content=path.read_text(encoding='utf-8')
            description=''
            if content.startswith('---'):
                for line in content.split('---',2)[1].splitlines():
                    if line.lower().startswith('description:'):
                        description=line.split(':',1)[1].strip().strip('\"\'')[:250]
                        break
            catalog.append({'name':name,'description':description})
        except (OSError,UnicodeError,IndexError):
            catalog.append({'name':name,'description':''})
    names=', '.join(verified)
    assignments = {st['id']: [x['name'] for x in st['skills']] for st in selected_tree['stages'] if st['id'] in selected_stages}
    prompt = (
        'You are a read-only skill architecture advisor. Do NOT change files, '
        'install packages, execute tools, or claim that suggested skills were installed. '
        'Recommend LOCAL skill names from the supplied verified list, and separately propose external skill candidates. '
        'Do not claim external repositories or commits are verified without independent source inspection. '
        'Label external suggestions UNVERIFIED_CANDIDATE. Reply only valid JSON: '
        '{"summary":"Korean summary","recommendations":[{"name":"skill-name","origin":"local|external","stages":["VERIFY"],"reason":"Korean reason","url":"optional verified source repo URL","commit":"optional 40-char SHA","subdir":"optional skill path"}]}. '
        'Do not invent verified Git URLs or commits; if external sources are unknown, '
        'clearly state SOURCE_NOT_VERIFIED. Never treat an AI recommendation as a verified installation. '
        f'Profile ID: {selected_profile["id"]}; Profile name: {selected_profile["name"]}; '
        f'Target stage: {target_stage}; Target stages: {selected_stages}; Existing assignments: {assignments}; Available locally: {names}; Verified local skill descriptions: {json.dumps(catalog,ensure_ascii=False)}. User request: {question}'
    )
    if host == 'opencode':
        # The project does not ship a 'skill-advisor' agent. Use OpenCode's
        # built-in read-only planning agent instead. Avoid optional --archived
        # for compatibility with older locally installed CLI versions.
        argv = [exe, 'run', '--agent', 'plan', prompt]
    elif host == 'claude':
        argv = [exe, '-p', '--tools', '', '--max-turns', '1', '--output-format', 'text', prompt]
    else:
        argv = [exe, 'exec', '--sandbox', 'read-only', '--ephemeral', '--skip-git-repo-check', prompt]
    # Agent-specific auth lives with the host. Never copy tokens/keys into the console.
    # Run in project directory so skill availability and the native host are consistent.
    try:
        outcome = subprocess.run(argv, cwd=manager.root, capture_output=True, timeout=90, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ManagementError('AGENT_HOST_TIMEOUT: '+host+' (90s)') from exc
    except OSError as exc:
        raise ManagementError('AGENT_HOST_START_FAILED: '+host) from exc
    if outcome.returncode:
        # Never expose raw stderr: it may contain provider URLs, tokens,
        # user prompts or filesystem content. Show a useful bounded code.
        detail = outcome.stderr.decode('utf-8', errors='replace').lower()[-12000:]
        if any(x in detail for x in ('unauthorized', 'unauthenticated', 'authentication', 'invalid api key', 'not logged in', 'login required')):
            reason = 'AUTH_CHECK_REQUIRED'
        elif any(x in detail for x in ('model not found', 'model unavailable', 'provider not found', 'no model', 'model is required')):
            reason = 'MODEL_CHECK_REQUIRED'
        elif any(x in detail for x in ('unknown agent', 'agent not found', 'agent does not exist')):
            reason = 'AGENT_CHECK_REQUIRED'
        elif any(x in detail for x in ('unknown option', 'unknown flag', 'unrecognized option', 'invalid option')):
            reason = 'CLI_VERSION_CHECK_REQUIRED'
        else:
            reason = 'HOST_DIAGNOSTICS_REQUIRED'
        raise ManagementError(f'AGENT_HOST_FAILED: {host}, exit={outcome.returncode}, {reason}. Run the host CLI directly for details.')
    if len(outcome.stdout) > 100_000:
        raise ManagementError('AGENT_OUTPUT_TOO_LARGE')
    try:
        response = outcome.stdout.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ManagementError('AGENT_OUTPUT_NOT_UTF8') from exc
    if not response.strip():
        raise ManagementError('AGENT_EMPTY_RESPONSE')
    recommendations, summary = parse_recommendations(response, verified, selected_stages)
    external_search = {'status':'NOT_REQUESTED','candidates':[]}
    if search_external is True:
        from .external import discover
        external_search=discover(selected_stages, set(verified))
        existing={(x['name'],x['stage']) for x in recommendations}
        for external in external_search['candidates']:
            if (external['name'],external['stage']) not in existing:
                recommendations.append(external)

    return {
        'host': host,
        'profile': selected_profile['id'],
        'stage': target_stage,
        'stages': selected_stages,
        'suggestion': response.strip(),
        'summary': summary,
        'external_search': external_search,
        'recommendations': recommendations,
        'status': 'UNTRUSTED_SUGGESTION_ONLY',
        'installation': 'NOT_RUN',
        'native_tool_use': 'NOT_VERIFIED',
        'external_source_verification': 'NOT_RUN',
    }


def parse_recommendations(response: str, verified: list[str], stages: list[str]):
    """Untrusted LLM output -> strictly bounded display-only candidates.

    Only server-verified local names can be marked local. External proposals
    never receive an install-ready status based on LLM claims.
    """
    candidate = response.strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```(?:json)?\s*|\s*```$', '', candidate, flags=re.I).strip()
    document = {}
    # Some native CLIs prepend model/status output before the JSON result.
    decoder = json.JSONDecoder()
    for match in list(re.finditer(r'\{', candidate))[:10]:
        try:
            obj,_ = decoder.raw_decode(candidate[match.start():])
            if isinstance(obj,dict) and isinstance(obj.get('recommendations'),list):
                document=obj
                break
        except (ValueError,TypeError):
            pass
    output = []
    seen = set()
    for item in (document.get('recommendations', []) if isinstance(document, dict) else [])[:30]:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name):
            continue
        requested = item.get('stages', [])
        if not isinstance(requested, list):
            continue
        matches = [sid for sid in stages if sid in requested]
        if not matches:
            continue
        origin = 'local' if name in verified else 'external'
        reason = item.get('reason', '')
        reason = str(reason)[:500]
        url = item.get('url', '') if origin == 'external' else ''
        commit = item.get('commit', '') if origin == 'external' else ''
        subdir = item.get('subdir', '') if origin == 'external' else ''
        if not isinstance(url, str) or not url.startswith('https://github.com/') or len(url) > 250:
            url = ''
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-fA-F]{40}',commit):
            commit = ''
        if not isinstance(subdir, str) or len(subdir) > 180 or '..' in subdir.split('/'):
            subdir = ''
        for stage in matches:
            if (name,stage) in seen:
                continue
            seen.add((name,stage))
            output.append({'name':name,'stage':stage,'origin':origin,'reason':reason,
                           'verified':origin=='local','source_status':'LOCAL_HASH_VERIFIED' if origin=='local' else 'SOURCE_NOT_VERIFIED',
                           'url':url,'commit':commit,'subdir':subdir})
    summary = str(document.get('summary', ''))[:1500] if isinstance(document, dict) else ''
    if not output and not document:
        # Conservative fallback for legacy free-text native responses: only
        # already hash-verified local names. No external installation claim.
        for name in verified:
            if re.search(r'(?<![a-z0-9-])'+re.escape(name)+r'(?![a-z0-9-])', candidate, re.I):
                for stage in stages:
                    output.append({'name':name,'stage':stage,'origin':'local',
                        'reason':'AI 자유 형식 응답에서 이름 발견 · 연결 전 검토 필요',
                        'verified':True,'source_status':'LOCAL_HASH_VERIFIED',
                        'url':'','commit':'','subdir':''})
        summary = 'AI가 구조화된 형식으로 답하지 않아 설치된 스킬 이름만 추출했습니다. 외부 후보는 원문을 확인하세요.'
    return output, summary


def suggest(manager: Manager, host: str, question: str, profile_id: str | None = None, stage_id: str | None = None, search_external: bool = False):
    """Preserves existing API, adding bounded discovery, policy checks, trace provenance."""
    from . import advisor
    import time
    trace={'run_id':advisor.new_run_id(),'created_at':advisor.now_iso(),'host':str(host)[:40],
           'profile':str(profile_id or '')[:64], 'stages':[str(stage_id or 'ANALYZE')[:40]],
           'status':'RUNNING','engine_status':'NOT_STARTED','steps':[],'candidate_count':0,
           'privacy':'NO_USER_PROMPT_OR_MODEL_STDOUT_STORED'}
    start=time.monotonic()
    def step(name,status,**kwargs):
        trace['steps'].append({'step':name,'status':status,'at':advisor.now_iso(),**kwargs})
    try:
        step('REQUEST_RECEIVED','COMPLETED',request_length=len(question) if isinstance(question,str) else 0)
        result=_suggest_core(manager,host,question,profile_id,stage_id,search_external=False)
        trace['profile']=result['profile'];trace['stages']=result['stages']
        step('HOST_SUGGESTION','COMPLETED',host=host,candidates=len(result['recommendations']),native_tool_use='NOT_VERIFIED')
        external={'status':'NOT_REQUESTED','candidates':[],'searches':[]}
        if search_external:
            external=advisor.discover_cli(manager.root,question,result['stages'])
            trace['engine_status']=external['status']
            step('SKILLS_CLI_SEARCH',external['status'],reason=external.get('reason',''), searches=external.get('searches',[]),found=len(external.get('candidates',[])))
            if external['status']=='UNAVAILABLE' or external['status']=='SEARCH_UNAVAILABLE':
                # Existing API search remains fallback, never silently mislabeled as Skills CLI.
                from .external import discover
                github=discover(result['stages'],{s['name'] for s in manager.list_skills() if s.get('verified')})
                step('GITHUB_FALLBACK',github['status'],searched_stages=github.get('searched_stages',[]),failed_stages=github.get('failed_stages',[]),found=len(github.get('candidates',[])))
                external={'status':github['status'],'source':'GitHub public API fallback','candidates':github['candidates'],'searches':external.get('searches',[]),
                          'skills_cli_status':'UNAVAILABLE' if trace['engine_status']=='UNAVAILABLE' else trace['engine_status']}
                trace['engine_status']='GITHUB_FALLBACK_'+github['status']
        items=result['recommendations']+external['candidates']
        distinct={}
        for item in items:
            key=(item['name'],item['stage'])
            if key not in distinct or distinct[key].get('source_status')=='SOURCE_NOT_VERIFIED' and item.get('commit'):
                distinct[key]=item
        result['recommendations']=advisor.validate_candidates(list(distinct.values())[:45],result['profile'],manager.root)
        step('POLICY_ASSESSMENT','COMPLETED',verdict_counts={v:sum(x['assessment']['verdict']==v for x in result['recommendations']) for v in ('LIKELY_RELEVANT','REVIEW_REQUIRED','POLICY_CONFLICT','NOT_RELEVANT','INSUFFICIENT_EVIDENCE')},
             limitations='HEURISTIC_RELEVANCE_NOT_COMPLETE_OR_SECURITY_AUDIT')
        trace['candidate_count']=len(result['recommendations'])
        trace['candidate_assessments']=[{
            'name':str(c.get('name',''))[:64], 'stage':str(c.get('stage',''))[:20],
            'origin':c.get('origin'), 'source_status':str(c.get('source_status',''))[:70],
            'verdict':c['assessment']['verdict'], 'reason':c['assessment']['reason'],
            'provenance':str(c.get('discovery_engine','native-host-or-github'))[:32],
        } for c in result['recommendations']]
        trace['installation']='NOT_RUN'
        trace['status']='COMPLETED'
        result['external_search']=external
        result['recommendation_validation']='HEURISTIC_PRELIMINARY_NOT_EXECUTION_TESTED'
        result['run_id']=trace['run_id']
        result['trace_status']='NOT_SAVED'
        result['skills_cli_status']=external.get('skills_cli_status',external['status']) if search_external else 'NOT_REQUESTED'
        return result
    except Exception as exc:
        trace['status']='FAILED'
        step('ERROR','FAILED',code=type(exc).__name__) # no raw error text
        raise
    finally:
        trace['duration_ms']=round((time.monotonic()-start)*1000)
        try:
            advisor.save_trace(manager.root,trace)
            if 'result' in locals() and isinstance(result,dict): result['trace_status']='STORED'
        except (OSError,ValueError):
            if 'result' in locals() and isinstance(result,dict): result['trace_status']='LOG_WRITE_FAILED'
