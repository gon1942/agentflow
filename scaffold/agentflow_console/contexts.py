"""Project-local session defaults and immutable TASK execution context.

These records coordinate agent configuration; they do NOT dispatch native workers.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
from pathlib import Path
from .core import Manager, ManagementError, atomic_json, json_load, reject_symlinks

SESSION_ID = re.compile(r'^[a-z][a-z0-9-]{0,63}$')
HOSTS = ('opencode', 'claude', 'codex')

class ContextRegistry:
    def __init__(self, manager: Manager):
        self.manager = manager
        self.base = manager.config / 'execution-contexts'
        reject_symlinks(self.base, manager.root)
        self.base.mkdir(mode=0o700, exist_ok=True)
        self.sessions = self.base / 'sessions'
        self.tasks = self.base / 'tasks'
        for folder in (self.sessions, self.tasks):
            reject_symlinks(folder, manager.root)
            folder.mkdir(mode=0o700, exist_ok=True)

    def _session(self, session_id):
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise ManagementError('SESSION_ID_INVALID')
        path = self.sessions / (session_id + '.json')
        reject_symlinks(path, self.manager.root)
        return path

    def bind_session(self, session_id, host, profile, expected_generation=None, source="MANUAL"):
        if source not in ("MANUAL", "NATIVE_HOOK_REPORTED"):
            raise ManagementError("SESSION_BIND_SOURCE_INVALID")
        if host not in HOSTS:
            raise ManagementError('HOST_INVALID')
        if profile == "development":
            raise ManagementError("LEGACY_PROFILE_USE_LIFECYCLE_DEV")
        with self.manager.locked():
            profile_obj = self.manager.profile(profile)
            self.manager.validate_profile(profile_obj)
            tree = self.manager.tree(profile_obj['skill_tree'])
            self.manager.validate_tree(tree, profile)
            if self.manager.missing_skills(tree, profile_obj):
                raise ManagementError('SKILLS_MISSING')
            path = self._session(session_id)
            old = json_load(path, self.manager.root) if path.exists() else None
            if old and old.get('host') != host:
                raise ManagementError('SESSION_HOST_IMMUTABLE')
            generation = old.get('generation', 0) if old else 0
            if expected_generation is not None and (type(expected_generation) is not int or generation != expected_generation):
                raise ManagementError('SESSION_VERSION_CONFLICT')
            obj = {'schema_version': 1, 'session_id': session_id, 'host': host,
                   'profile': profile, 'generation': generation + 1,
                   'scope': 'NEW_TASKS_ONLY', 'native_session_binding': 'HOOK_REPORTED_NOT_E2E_VERIFIED' if source == 'NATIVE_HOOK_REPORTED' else 'DECLARED_NOT_VERIFIED',
                   'discovery': old.get('discovery', source) if old else source}
            atomic_json(path, obj, self.manager.root)
            return obj

    def get_session(self, session_id):
        path = self._session(session_id)
        return json_load(path, self.manager.root) if path.is_file() else None

    def list_sessions(self):
        return [json_load(p, self.manager.root) for p in sorted(self.sessions.glob('*.json'))
                if not p.is_symlink() and p.is_file()]

    def resolved_profile(self, session_id=None, profile=None):
        if profile is not None:
            return self.manager.profile(profile)['id'], 'EXPLICIT'
        if session_id is not None:
            selected = self.get_session(session_id)
            if selected:
                return selected['profile'], 'SESSION_DEFAULT'
            raise ManagementError('SESSION_NOT_BOUND')
        return self.manager.active()['profile'], 'PROJECT_DEFAULT'

    def contract(self, session_id=None, profile=None):
        name, source = self.resolved_profile(session_id, profile)
        result = self.manager.runtime_contract(profile_id=name)
        result['selection'] = {'profile_source': source, 'session_id': session_id,
                               'profile': name, 'new_task_only': True}
        return result

    def _task_path(self, task_id):
        self.manager._task_dir(task_id)
        p = self.tasks / (task_id + '.json')
        reject_symlinks(p, self.manager.root)
        return p

    @staticmethod
    def _seal(payload):
        payload['record_sha256'] = hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k != 'record_sha256'}, sort_keys=True).encode()).hexdigest()
        return payload

    def pin_task(self, task_id, session_id=None, profile=None):
        with self.manager.locked():
            path = self._task_path(task_id)
            if path.is_file():
                # Idempotent pin never resets an existing contract, nor accepts tampering.
                return self.task_contract(task_id)
            task_path = self.manager._task_dir(task_id)
            record = self.manager._task_record(task_path)
            if record.get('state') not in ('PLAN_DRAFT', 'PLAN_BLOCKED'):
                raise ManagementError('TASK_ALREADY_STARTED_WITHOUT_PINNED_CONTRACT')
            # Never retroactively override a task that already owns an execution profile.
            selected, source = self.resolved_profile(session_id, profile)
            if selected == 'development-worker':
                raise ManagementError('WORKER_REQUIRES_VERIFIED_PLANNING_HANDOFF')
            existing = record.get('execution_profile') or record.get('planning_profile')
            if existing and existing != selected:
                raise ManagementError('TASK_PROFILE_CONFLICT')
            contract = self.manager.runtime_contract(profile_id=selected)
            payload = {'schema_version': 1, 'task_id': task_id, 'profile': selected,
                       'host': self.get_session(session_id)['host'] if session_id and self.get_session(session_id) else None,
                       'session_id': session_id, 'selection_source': source,
                       'contract': contract, 'contract_sha256': contract['configuration_sha256'],
                       'immutable': True, 'native_worker_dispatch': 'NOT_VERIFIED'}
            self._seal(payload)
            atomic_json(path, payload, self.manager.root)
            return payload

    def promote_to_development(self, task_id, session_id=None, target_profile="lifecycle-dev"):
        """Explicit PLAN_READY -> Development handoff; caller holds management lock."""
        path = self._task_path(task_id)
        existing = self.task_contract(task_id) if path.is_file() else None
        if existing and existing['profile'] != 'task-planning':
            raise ManagementError('DEVELOPMENT_HANDOFF_PROFILE_INVALID')
        if target_profile not in ('development', 'lifecycle-dev', 'development-worker'):
            raise ManagementError('DEVELOPMENT_PROFILE_REQUIRED')
        session = self.get_session(session_id) if session_id else None
        if session_id and (session is None or session['profile'] != target_profile):
            raise ManagementError('DEVELOPMENT_SESSION_REQUIRED')
        contract = self.manager.runtime_contract(profile_id=target_profile)
        result = {'schema_version': 1, 'task_id': task_id, 'profile': target_profile,
                  'host': session['host'] if session else None,
                  'session_id': session_id, 'selection_source': 'EXPLICIT_DEVELOPMENT_HANDOFF',
                  'contract': contract, 'contract_sha256': contract['configuration_sha256'],
                  'immutable': True, 'native_worker_dispatch': 'NOT_VERIFIED',
                  'planning_handoff': {'profile': 'task-planning',
                                       'contract_sha256': existing['contract_sha256']} if existing else None}
        self._seal(result)
        atomic_json(path, result, self.manager.root)
        return result

    def task_contract(self, task_id):
        path = self._task_path(task_id)
        if not path.is_file():
            raise ManagementError('TASK_CONTEXT_NOT_PINNED')
        data = json_load(path, self.manager.root)
        digest = hashlib.sha256(json.dumps({k:v for k,v in data.items() if k != 'record_sha256'},sort_keys=True).encode()).hexdigest()
        if data.get('record_sha256') != digest or data.get('task_id') != task_id:
            raise ManagementError('TASK_CONTEXT_INTEGRITY_FAILED')
        contract = data.get('contract')
        if not isinstance(contract, dict) or contract.get('configuration_sha256') != data.get('contract_sha256'):
            raise ManagementError('TASK_CONTEXT_INTEGRITY_FAILED')
        if contract.get('profile', {}).get('id') != data.get('profile'):
            raise ManagementError('TASK_CONTEXT_PROFILE_MISMATCH')
        # Validate serialized profile/tree against its original config digest, independent of live defaults.
        expected = hashlib.sha256(json.dumps([data.get('profile'), contract.get('profile'), contract.get('tree')],sort_keys=True).encode()).hexdigest()
        if expected != data['contract_sha256']:
            raise ManagementError('TASK_CONTEXT_INTEGRITY_FAILED')
        return data

    def task_views(self):
        records=[]
        for folder in sorted((self.manager.root/'docs/tasks/active').iterdir()):
            if folder.is_symlink() or not folder.is_dir():
                continue
            try:
                task=self._task_path(folder.name)
            except ManagementError:
                continue
            context=json_load(task,self.manager.root) if task.exists() else None
            task_record=self.manager._task_record(folder)
            records.append({'task_id': folder.name,'state':task_record.get('state'),
                            'profile': context['profile'] if context else (task_record.get('execution_profile') or task_record.get('planning_profile')),
                            'host': context.get('host') if context else None,
                            'session_id': context.get('session_id') if context else None,
                            'contract_pinned':context is not None})
        return records
