"""Local per-prompt adapter: native session identity -> persisted Profile default.

No native dispatch, file edits or TASK approval. Never stores prompt or credentials.
"""
from __future__ import annotations
import hashlib
import re
from .contexts import ContextRegistry, HOSTS
from .core import ManagementError

# Fixed command grammar only; do not infer an approval or Profile switch from arbitrary text.
PROFILE_COMMAND = re.compile(r'^\s*(?:/agentflow-profile\s+|(?:프로필|profile)(?:을|를)?\s*(?:변경|설정|전환)(?:해줘|해|하세요)?\s*[:：]?\s*)([\w가-힣-]+)\s*$', re.IGNORECASE)
KOREAN_CHANGE = re.compile(r'^\s*([\w가-힣-]+)\s*(?:프로필)?(?:로|으로)\s*(?:변경|설정|전환|바꿔)(?:해줘|해|하세요|해 주세요|해주세요|줘)?[.!]?\s*$')
KOREAN_OBJECT = re.compile(r'^\s*프로필(?:을|를)?\s*([\w가-힣-]+)(?:로|으로)\s*(?:변경|설정|전환|바꿔)(?:해줘|해|하세요|해 주세요|해주세요|줘)?[.!]?\s*$')
PROFILE_ALIASES = {'개발':'development-worker','개발전문가':'development-worker','development':'development-worker',
                   'development-worker':'development-worker','구현':'development-worker',
                   '전체개발':'lifecycle-dev','전체개발관리':'lifecycle-dev','lifecycle-dev':'lifecycle-dev',
                   '계획':'task-planning','작업계획':'task-planning','작업계획전문가':'task-planning',
                   'task-planning':'task-planning'}

def session_key(host, native_session_id):
    if host not in HOSTS:
        raise ManagementError('HOST_INVALID')
    if not isinstance(native_session_id,str) or not 1 <= len(native_session_id) <= 256:
        raise ManagementError('NATIVE_SESSION_ID_INVALID')
    return host + '-' + hashlib.sha256((host+'\0'+native_session_id).encode()).hexdigest()[:24]

def prompt_event(manager, host, native_session_id, prompt=None):
    """Return short context for native prompt hooks, and register session on first use.

    Existing TASK is never repinned; Coordinator must load its immutable contract.
    """
    sid=session_key(host,native_session_id)
    registry=ContextRegistry(manager)
    match=(PROFILE_COMMAND.fullmatch(prompt or '') or KOREAN_CHANGE.fullmatch(prompt or '') or KOREAN_OBJECT.fullmatch(prompt or '')) if isinstance(prompt,str) else None
    requested=PROFILE_ALIASES.get(match.group(1).lower()) if match else None
    if match and not requested:
        return {'session_id':sid,'status':'PROFILE_UNKNOWN','instruction':'Profile 이름을 확인하세요. 기존 설정은 변경되지 않았습니다.'}
    if requested:
        selected=registry.bind_session(sid,host,requested,source="NATIVE_HOOK_REPORTED")
        outcome='SESSION_PROFILE_UPDATED'
    else:
        selected=registry.get_session(sid)
        if selected is None:
            initial=manager.active()['profile']
            # First prompt snapshots the project default. Concurrent first-use is serialized in bind_session.
            selected=registry.bind_session(sid,host,initial,source="NATIVE_HOOK_REPORTED")
        elif selected['host']!=host:
            raise ManagementError('SESSION_HOST_IMMUTABLE')
        outcome='SESSION_PROFILE_RESOLVED'
    contract=registry.contract(sid)
    scope=contract.get('execution_scope') or {}
    instruction = ('해당 요청은 Profile 기본값 변경만 수행했으며 신규 TASK를 생성하지 않습니다. ' if requested else '')
    instruction += ('AgentFlow: 기존 TASK 후속 요청이면 해당 TASK의 고정 계약을 먼저 조회하고, '
                    '신규 TASK일 때만 이 세션 Profile을 적용하세요. TASK를 생성하면 task-context --pin --session '
                    + sid + ' 로 계약을 고정하세요. 승인·검증 절차를 생략하지 마세요.')
    return {'status':outcome,'host':host,'session_id':sid,'profile':selected['profile'],
            'generation':selected['generation'],'configuration_sha256':contract['configuration_sha256'],
            'enabled_stages':scope.get('enabled_stages',[]),
            'instruction':instruction,'native_execution':'NOT_VERIFIED'}
