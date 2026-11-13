"""Opt-in public GitHub skill search; no user request/project data sent.

Repository metadata + exact SKILL.md path + pinned commit are checked.
This is NOT a security audit or installation approval.
"""
from __future__ import annotations
import json
import re
import base64
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import URLError, HTTPError

KEYWORDS = {
    'VERIFY': 'playwright browser testing agent skills',
    'ANALYZE': 'requirements analysis agent skills',
    'PLAN': 'planning agent skills',
    'IMPLEMENT': 'frontend agent skills',
    'REVIEW': 'code review agent skills',
    'BUG_FAIL': 'debugging agent skills',
    'REVIEW_FIX': 'code review agent skills',
}
API='https://api.github.com'

def _json(path):
    if not path.startswith('/') or '..' in path or len(path)>350:
        raise ValueError('BAD_GITHUB_PATH')
    req=Request(API+path,headers={'User-Agent':'AgentFlow-SkillStudio/0.5','Accept':'application/vnd.github+json'})
    with urlopen(req,timeout=5) as response:
        if response.status!=200 or int(response.headers.get('Content-Length','0'))>2_500_000:
            raise ValueError('GITHUB_RESPONSE_UNAVAILABLE')
        payload=response.read(2_500_001)
        if len(payload)>2_500_000:
            raise ValueError('GITHUB_RESPONSE_TOO_LARGE')
        return json.loads(payload)

def _skill_description(full, sha, path):
    """Bounded, read-only frontmatter inspection at a pinned GitHub commit.

    GitHub file existence is not evidence of safety or stage fit. Never execute.
    """
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', full):
        return ''
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        return ''
    if not path.endswith('/SKILL.md') or '..' in path.split('/') or len(path)>180:
        return ''
    try:
        result=_json('/repos/'+full+'/contents/'+quote(path,safe='/')+'?ref='+sha)
        if result.get('type')!='file' or result.get('size',0)>100_000 or result.get('encoding')!='base64':
            return ''
        content=base64.b64decode(result.get('content',''),validate=False).decode('utf-8')
        if not content.startswith('---'):
            return ''
        front=content.split('---',2)[1]
        lines=front.splitlines()
        for i,line in enumerate(lines):
            if not line.lower().startswith('description:'):
                continue
            value=line.split(':',1)[1].strip()
            if value in ('>','>-','|','|-','>+','|+'):
                chunks=[]
                for part in lines[i+1:]:
                    if not part.startswith((' ','\t')):break
                    if part.strip():chunks.append(part.strip())
                value=' '.join(chunks)
            return value.strip('"\' ')[:420]
    except (ValueError,KeyError,TypeError,HTTPError,URLError,TimeoutError,UnicodeError):
        pass
    return ''

def _discover_stage(stage, installed):
    query=KEYWORDS.get(stage,'agent skills')
    result=_json('/search/repositories?q='+quote(query)+'&per_page=4')
    output=[]
    for repo in result.get('items',[])[:4]:
        full=repo.get('full_name','')
        branch=repo.get('default_branch','')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',full) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',branch):
            continue
        try:
            sha=_json('/repos/'+full+'/commits/'+quote(branch))['sha']
            if not re.fullmatch(r'[0-9a-f]{40}',sha):continue
            tree=_json('/repos/'+full+'/git/trees/'+sha+'?recursive=1')
            if tree.get('truncated'):continue
            paths=[x['path'] for x in tree.get('tree',[]) if x.get('type')=='blob' and x.get('path','').endswith('/SKILL.md') and len(x['path'])<180]
            for path in paths[:2]:
                subdir=path[:-len('/SKILL.md')]
                name=subdir.rsplit('/',1)[-1]
                if name in installed or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',name):continue
                output.append({'name':name,'stage':stage,'origin':'external','verified':False,
                    'source_status':'GITHUB_REPO_PATH_PIN_VERIFIED_NOT_AUDITED',
                    'reason':'GitHub 검색에서 발견한 후보입니다. 단계 적합성 및 보안은 미검증입니다.',
                    'description':_skill_description(full,sha,path),
                    'description_status':'PINNED_SKILL_MD_FRONTMATTER' ,
                    'url':'https://github.com/'+full+'.git','commit':sha,'subdir':subdir})
                if len(output)>=3:break
        except (ValueError,KeyError,TypeError,HTTPError,URLError,TimeoutError):
            continue
        if len(output)>=3:break
    return output

def discover(stages, installed):
    """Search each selected skill stage, never send user request or project secrets."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    to_search=[x for x in stages if x in KEYWORDS][:8]
    results=[]
    failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(_discover_stage,stage,installed):stage for stage in to_search}
        for future in as_completed(futures):
            stage=futures[future]
            try:
                results.extend(future.result())
            except (ValueError,KeyError,TypeError,HTTPError,URLError,TimeoutError):
                failures.append(stage)
    ordering={stage:i for i,stage in enumerate(to_search)}
    results.sort(key=lambda x:(ordering.get(x['stage'],99),x['name']))
    status='COMPLETED' if not failures else 'PARTIAL' if len(failures)<len(to_search) else 'SEARCH_UNAVAILABLE'
    return {'status':status,'candidates':results[:20],
            'searched_stages':to_search,'failed_stages':failures,
            'search_scope':'public stage-generic keywords only','source':'GitHub public API'}


def resolve_github_commit(url):
    """Explicit, read-only GitHub default-branch SHA lookup, never install from an unpinned ref."""
    from urllib.parse import urlparse
    if not isinstance(url, str) or len(url) > 500:
        raise ValueError('GITHUB_URL_REQUIRED')
    parsed=urlparse(url.strip())
    if parsed.scheme!='https' or parsed.netloc.lower()!='github.com' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('GITHUB_HTTPS_URL_REQUIRED')
    match=re.fullmatch(r'/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?',parsed.path)
    if not match:
        raise ValueError('GITHUB_REPOSITORY_URL_REQUIRED')
    full=match.group(1)+'/'+match.group(2)
    try:
        info=_json('/repos/'+full)
        branch=info.get('default_branch')
        if not isinstance(branch,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',branch):
            raise ValueError('GITHUB_BRANCH_UNAVAILABLE')
        commit=_json('/repos/'+full+'/commits/'+quote(branch))['sha']
        if not isinstance(commit,str) or not re.fullmatch(r'[0-9a-fA-F]{40}',commit):
            raise ValueError('GITHUB_COMMIT_UNAVAILABLE')
        return {'repository':full, 'branch':branch, 'commit':commit.lower(), 'source':'GITHUB_DEFAULT_BRANCH_LOOKUP_NOT_SECURITY_AUDIT'}
    except (HTTPError, URLError, TimeoutError, KeyError, TypeError) as exc:
        raise ValueError('GITHUB_COMMIT_LOOKUP_FAILED') from exc
