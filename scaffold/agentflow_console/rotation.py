"""Project-local, fail-closed Worker session rotation core.

Only subprocesses launched by this module are managed. Native OpenCode/Claude/Codex
session rotation must use a verified host adapter; this module does NOT implement it.
TASK/approval state remains authoritative; handoff records are derived evidence.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path
import signal
import subprocess
import time
import uuid

from .core import ManagementError, Manager, atomic_json, reject_symlinks

TERMINAL = {'BLOCKED', 'STOPPED', 'RUNNING'}
SCHEMA = 1
MAX_HANDOFF = 80_000
_CHILDREN = {}  # Keep Popen handles alive in the parent process for deterministic reaping.

def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def proc_identity(pid):
    """Only Linux /proc identities are accepted; missing data => no process claim."""
    if not isinstance(pid,int) or pid <= 1: return None
    try:
        line=Path(f'/proc/{pid}/stat').read_text()
        tail=line.rsplit(')',1)[1].strip().split()
        # Linux /proc stat starttime is field 22; tail begins at field 3.
        start=tail[19]
        pgrp=int(tail[2])
        state=tail[0]
        return {'pid':pid,'start_ticks':start,'pgrp':pgrp,'state':state}
    except (OSError,ValueError,IndexError):
        return None

def group_members(pgrp):
    """Linux best-effort check for live members in the managed process group."""
    if not isinstance(pgrp,int) or pgrp <= 1: return []
    live=[]
    for item in Path('/proc').iterdir():
        if not item.name.isdigit(): continue
        ident=proc_identity(int(item.name))
        if ident and ident['pgrp']==pgrp and ident['state'] not in ('Z','X','x'):
            live.append(ident['pid'])
    return live

def live_worker(record):
    pid=record.get('pid'); identity=proc_identity(pid)
    return bool(identity and identity['start_ticks']==record.get('start_ticks') and identity['state'] != 'Z')

class RotationManager:
    def __init__(self, manager: Manager):
        self.m=manager
        self.root=manager.root
        self.base=self.root/'.agentflow'/'rotations'
        reject_symlinks(self.base,self.root)
        self.base.mkdir(mode=0o700,exist_ok=True)

    def paths(self, task_id):
        task=self.m._task_dir(task_id)
        p=self.base/task_id
        reject_symlinks(p,self.root)
        return task,p

    def _load(self, task_id):
        from .core import json_load
        _task,p=self.paths(task_id)
        file=p/'current.json'
        return json_load(file,self.root) if file.is_file() else None

    def _save(self, task_id, record):
        task,p=self.paths(task_id)
        reject_symlinks(p,self.root)
        p.mkdir(mode=0o700,exist_ok=True)
        atomic_json(p/'current.json',record,self.root)

    def _event(self, task_id, kind, data):
        _task,p=self.paths(task_id)
        p.mkdir(mode=0o700,exist_ok=True)
        file=p/'events.jsonl'
        reject_symlinks(file,self.root)
        event={'at':timestamp(),'kind':kind,'task_id':task_id,
               'rotation_id':data.get('rotation_id'), 'generation':data.get('generation'),
               'state':data.get('state')}
        payload=json.dumps(event,ensure_ascii=False,sort_keys=True)+'\n'
        fd=os.open(file,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a',encoding='utf-8') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())

    def capabilities(self):
        """Executable presence is not evidence of native session-control support."""
        return {
            'platform': 'linux-procfs' if Path('/proc/self/stat').exists() else 'UNSUPPORTED',
            'managed_subprocess': Path('/proc/self/stat').exists(),
            'native_rotation': 'NOT_VERIFIED',
            'auto_context_rotation': 'NOT_IMPLEMENTED',
            'hosts': {name: {'executable_present':bool(shutil.which(name)),
                             'native_session_stop_resume':'NOT_VERIFIED'}
                      for name in ('opencode','claude','codex')}
        }

    def status(self, task_id):
        record=self._load(task_id)
        if record is None: return {'task_id':task_id,'state':'NOT_REGISTERED','native_rotation':'NOT_VERIFIED'}
        view={key:value for key,value in record.items() if key != 'command'}
        view['worker_alive']=live_worker(record)
        view['native_rotation']='NOT_VERIFIED'
        return view

    def _snapshot(self, task):
        # Existing TASK state and approvals are the authority; do not infer approvals.
        names=('task-state.json','spec.md','plan.md','plan-verification.json','approvals.md')
        result={}
        for name in names:
            file=task/name
            reject_symlinks(file,self.root)
            if file.is_file(): result[name]=digest(file)
        return result

    def _verify_snapshot(self, task, expected):
        if self._snapshot(task) != expected:
            raise ManagementError('ROTATION_TASK_SNAPSHOT_CHANGED')

    def start_managed(self, task_id, stage, command):
        """Explicit local subprocess test/worker launch; not native agent session control."""
        if stage not in ('ANALYZE','PLAN','IMPLEMENT','VERIFY','REVIEW'):
            raise ManagementError('ROTATION_STAGE_INVALID')
        if not isinstance(command,list) or not command or len(command)>30 or any(not isinstance(x,str) or not x or len(x)>2048 for x in command):
            raise ManagementError('ROTATION_COMMAND_INVALID')
        with self.m.locked():
            task,p=self.paths(task_id)
            task_record=self.m._task_record(task)
            state=task_record.get('state')
            if task_record.get('stage') and task_record['stage']!=stage:
                raise ManagementError('ROTATION_STAGE_MISMATCH')
            if state != 'IN_PROGRESS':
                raise ManagementError('ROTATION_TASK_NOT_RUNNING')
            from .contexts import ContextRegistry
            ctx_path=self.m.config/'execution-contexts'/'tasks'/(task_id+'.json')
            pinned=ContextRegistry(self.m).task_contract(task_id) if ctx_path.is_file() else None
            task_profile=(pinned['profile'] if pinned else task_record.get('execution_profile') or task_record.get('planning_profile') or self.m.active().get('profile'))
            if pinned and task_record.get('execution_profile') and task_record['execution_profile'] != task_profile:
                raise ManagementError('ROTATION_PROFILE_CONFLICT')
            if stage in ('IMPLEMENT','VERIFY','REVIEW') and task_profile in ('development','lifecycle-dev') and task_record.get('gate1_approved') is not True:
                raise ManagementError('ROTATION_GATE1_EVIDENCE_MISSING')
            old=self._load(task_id)
            if old is not None and old.get('state') != 'STOPPED':
                raise ManagementError('ROTATION_WORKER_ALREADY_REGISTERED')
            if old is not None and live_worker(old):
                raise ManagementError('ROTATION_OLD_WORKER_STILL_ALIVE')
            p.mkdir(mode=0o700,exist_ok=True)
            # Do not persist arbitrary worker stdout (may contain secrets).
            proc=subprocess.Popen(command,cwd=self.root,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,
                env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TMPDIR')})
            _CHILDREN[proc.pid]=proc
            identity=proc_identity(proc.pid)
            if identity is None or identity['pgrp'] != proc.pid:
                proc.terminate()
                raise ManagementError('ROTATION_PROCESS_IDENTITY_UNAVAILABLE')
            role={'ANALYZE':'coordinator','PLAN':'coordinator','IMPLEMENT':'implementer',
                  'VERIFY':'verifier','REVIEW':'reviewer'}[stage]
            record={'schema_version':SCHEMA,'task_id':task_id,'stage':stage,'worker_role':role,
                'profile':task_profile,
                'worktree':str(self.root),'state':'RUNNING',
                'rotation_id':None,'generation':(old.get('generation',0)+1 if old else 1),
                'pid':proc.pid,'start_ticks':identity['start_ticks'],
                'snapshot':self._snapshot(task),'started_at':timestamp(),
                'engine':'managed-subprocess','native_rotation':'NOT_VERIFIED'}
            self._save(task_id,record);self._event(task_id,'WORKER_STARTED',record)
            return self.status(task_id)

    def request(self,task_id,reason,completed,remaining):
        if reason not in ('manual','context-pressure','stage-boundary','retry-limit'):
            raise ManagementError('ROTATION_REASON_INVALID')
        for seq in (completed,remaining):
            if not isinstance(seq,list) or len(seq)>30 or any(not isinstance(x,str) or len(x)>250 for x in seq):
                raise ManagementError('ROTATION_HANDOFF_INVALID')
        with self.m.locked():
            record=self._load(task_id);task,p=self.paths(task_id)
            if not record or record['state']!='RUNNING': raise ManagementError('ROTATION_WORKER_NOT_RUNNING')
            if not live_worker(record):raise ManagementError('ROTATION_WORKER_NOT_ALIVE')
            if record.get('rotation_count',0)>=3:raise ManagementError('ROTATION_LIMIT_REACHED')
            self._verify_snapshot(task,record['snapshot'])
            # Freeze the managed process group before producing a consistent handoff.
            identity=proc_identity(record['pid'])
            if not identity or identity['start_ticks']!=record['start_ticks'] or identity['pgrp']!=record['pid']:
                raise ManagementError('ROTATION_PID_IDENTITY_MISMATCH')
            os.killpg(record['pid'],signal.SIGSTOP)
            until=time.monotonic()+1.5
            while time.monotonic()<until:
                identity=proc_identity(record['pid'])
                if identity and identity['state'] in ('T','t'):break
                time.sleep(.02)
            if not identity or identity['state'] not in ('T','t'):
                os.killpg(record['pid'],signal.SIGCONT)
                raise ManagementError('ROTATION_SAFE_PAUSE_FAILED')
            try:
                self._verify_snapshot(task,record['snapshot'])
                rot='ROT-'+uuid.uuid4().hex[:12]
                handoff={'schema_version':1,'task_id':task_id,'rotation_id':rot,'stage':record['stage'],
                  'reason':reason,'reported_completed_work':completed,'remaining_work':remaining,
              'completed_work_verified':False,'worker_role':record['worker_role'],
              'profile':record['profile'],'worktree':record['worktree'],
                  'snapshot':record['snapshot'],'worker_generation':record['generation'],
                  'verification':'NOT_COMPLETED','created_at':timestamp(),
                  'next_action':'Confirm authoritative task and evidence; resume remaining work only'}
                folder=p/rot;folder.mkdir(mode=0o700)
                atomic_json(folder/'handoff.json',handoff,self.root)
                digest_value=digest(folder/'handoff.json')
                record.update(state='HANDOFF_VALIDATING',rotation_id=rot,handoff_sha256=digest_value,
                              rotation_count=record.get('rotation_count',0)+1)
                self._save(task_id,record);self._event(task_id,'HANDOFF_CREATED',record)
                return self.status(task_id)
            except Exception:
                # Restore original worker when handoff preparation fails before the persisted transition.
                current=self._load(task_id)
                if current and current.get('state')=='RUNNING' and live_worker(current):
                    os.killpg(current['pid'],signal.SIGCONT)
                raise

    def validate(self,task_id):
        with self.m.locked():
            record=self._load(task_id);task,p=self.paths(task_id)
            if not record or record['state']!='HANDOFF_VALIDATING':raise ManagementError('ROTATION_WRONG_STATE')
            self._verify_snapshot(task,record['snapshot'])
            file=p/record['rotation_id']/'handoff.json'
            reject_symlinks(file,self.root)
            if not file.is_file() or digest(file)!=record['handoff_sha256']:
                raise ManagementError('ROTATION_HANDOFF_TAMPERED')
            handoff=json.loads(file.read_text())
            if (handoff.get('task_id'),handoff.get('stage'),handoff.get('snapshot'))!=(task_id,record['stage'],record['snapshot']):
                raise ManagementError('ROTATION_HANDOFF_ID_MISMATCH')
            record['state']='STOPPING_OLD';self._save(task_id,record);self._event(task_id,'HANDOFF_VALIDATED',record)
            return self.status(task_id)

    def stop(self,task_id,timeout=3):
        """Signal only a registered managed process group whose /proc identity still matches."""
        with self.m.locked():
            record=self._load(task_id)
            if not record or record['state']!='STOPPING_OLD':raise ManagementError('ROTATION_WRONG_STATE')
            pid=record['pid']; ident=proc_identity(pid)
            if ident and (ident['start_ticks']!=record['start_ticks'] or ident['pgrp']!=pid):
                raise ManagementError('ROTATION_PID_IDENTITY_MISMATCH')
            if live_worker(record):
                os.killpg(pid,signal.SIGTERM)
                os.killpg(pid,signal.SIGCONT)  # allow graceful exit of paused worker
                until=time.monotonic()+min(float(timeout),10)
                while live_worker(record) and time.monotonic()<until:time.sleep(.04)
            if live_worker(record) or group_members(pid):
                record['state']='BLOCKED';self._save(task_id,record);self._event(task_id,'OLD_WORKER_STOP_FAILED',record)
                raise ManagementError('ROTATION_OLD_WORKER_NOT_STOPPED')
            handle=_CHILDREN.pop(pid,None)
            if handle: handle.wait(timeout=1)
            try:
                self._verify_snapshot(self.paths(task_id)[0],record['snapshot'])
            except ManagementError:
                record['state']='BLOCKED';self._save(task_id,record);self._event(task_id,'TASK_CHANGED_DURING_STOP',record)
                raise
            record['state']='OLD_STOPPED';record['old_stopped_at']=timestamp()
            self._save(task_id,record);self._event(task_id,'OLD_WORKER_STOPPED',record)
            return self.status(task_id)

    def cancel(self,task_id):
        """Abort handoff before old worker termination; safely unfreeze the original."""
        with self.m.locked():
            record=self._load(task_id);task,p=self.paths(task_id)
            if not record or record['state'] not in ('HANDOFF_VALIDATING','STOPPING_OLD'):
                raise ManagementError('ROTATION_CANNOT_CANCEL')
            self._verify_snapshot(task,record['snapshot'])
            ident=proc_identity(record['pid'])
            if not ident or ident['start_ticks']!=record['start_ticks'] or ident['pgrp']!=record['pid'] or not live_worker(record):
                raise ManagementError('ROTATION_OLD_WORKER_NOT_ALIVE')
            os.killpg(record['pid'],signal.SIGCONT)
            record.update(state='RUNNING',rotation_id=None,handoff_sha256=None)
            self._save(task_id,record);self._event(task_id,'ROTATION_CANCELLED',record)
            return self.status(task_id)

    def resume(self,task_id,command):
        # Resume is explicit: no arbitrary hidden agent invocation or silent auto-completion.
        if not isinstance(command,list) or not command:raise ManagementError('ROTATION_COMMAND_INVALID')
        with self.m.locked():
            record=self._load(task_id);task,p=self.paths(task_id)
            if not record or record['state']!='OLD_STOPPED':raise ManagementError('ROTATION_NOT_READY_TO_RESUME')
            if live_worker(record) or group_members(record['pid']):raise ManagementError('ROTATION_OLD_WORKER_STILL_ALIVE')
            self._verify_snapshot(task,record['snapshot'])
            file=p/record['rotation_id']/'handoff.json'
            reject_symlinks(file,self.root)
            if digest(file)!=record['handoff_sha256']:raise ManagementError('ROTATION_HANDOFF_TAMPERED')
            if len(command)>30 or any(not isinstance(x,str) or not x or len(x)>2048 for x in command):raise ManagementError('ROTATION_COMMAND_INVALID')
            proc=subprocess.Popen(command,cwd=self.root,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,
                env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TMPDIR')})
            _CHILDREN[proc.pid]=proc
            ident=proc_identity(proc.pid)
            if ident is None or ident['pgrp']!=proc.pid:
                proc.terminate();raise ManagementError('ROTATION_NEW_PROCESS_IDENTITY_UNAVAILABLE')
            record.update(state='RUNNING',generation=record['generation']+1,pid=proc.pid,start_ticks=ident['start_ticks'],
                          started_at=timestamp(),rotation_id=None,handoff_sha256=None)
            self._save(task_id,record);self._event(task_id,'TASK_RESUMED',record)
            return self.status(task_id)

    def history(self,task_id):
        _task,p=self.paths(task_id)
        path=p/'events.jsonl';reject_symlinks(path,self.root)
        if not path.is_file(): return []
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line][:200]
