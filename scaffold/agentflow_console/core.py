"""AgentFlow project-local profile/skill management.

No workflow state transitions, no LLM execution, no global installs. This module
keeps agent settings distinct from observed native agent use.
"""
from __future__ import annotations
import contextlib
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import urllib.parse
import stat
import subprocess
import tempfile
import zipfile

USER_STAGES = ("ANALYZE", "PLAN", "GATE1", "IMPLEMENT", "VERIFY", "REVIEW", "GATE2", "COMPLETE")
BRANCH_STAGES = ("BUG_FAIL", "REVIEW_FIX")
DEFAULT_BRANCH_POLICY = {"BUG_FAIL": True, "REVIEW_FIX": True}

def configured_stages(profile):
    """Return the actual executable stages; SESSION is infrastructure, not user-configurable."""
    selection = profile.get("enabled_stages")
    if selection is None:
        legacy = effective_stage_ids(profile.get("stop_after_stage", "COMPLETE"))
        gates = profile.get("approval_gates", {"GATE1": True, "GATE2": True})
        return [x for x in USER_STAGES if x in legacy and (x not in GATE_IDS or gates.get(x, True))]
    return [x for x in USER_STAGES if x in selection]

def branch_policy(profile):
    return {**DEFAULT_BRANCH_POLICY, **profile.get("conditional_stages", {})}

def executable_stages(profile):
    if "enabled_stages" not in profile:
        return effective_stage_ids(profile.get("stop_after_stage", "COMPLETE"))
    selected = configured_stages(profile)
    branches = branch_policy(profile)
    result = ["SESSION"]
    for st in ORDER[1:]:
        if st in selected:
            result.append(st)
        elif st == "BUG_FAIL" and branches[st] and any(x in selected for x in ("ANALYZE", "PLAN", "IMPLEMENT", "VERIFY")):
            result.append(st)
        elif st == "REVIEW_FIX" and branches[st] and "REVIEW" in selected:
            result.append(st)
    return result

NON_SKILL_STAGES = frozenset({"SESSION", "GATE1", "GATE2", "COMPLETE"})
GATE_IDS = ("GATE1", "GATE2")
# Only contiguous, dependency-safe prefixes are supported; branch stages follow parent stages.
TERMINAL_STAGES = ("ANALYZE", "PLAN", "GATE1", "IMPLEMENT", "VERIFY", "REVIEW", "GATE2", "COMPLETE")
def effective_stage_ids(stop_after):
    if stop_after == "COMPLETE":
        return list(ORDER)
    if stop_after not in TERMINAL_STAGES:
        raise ManagementError("STOP_AFTER_STAGE_INVALID")
    return ORDER[:ORDER.index(stop_after) + 1]


STAGE_IDS = {"SESSION", "ANALYZE", "PLAN", "GATE1", "IMPLEMENT", "BUG_FAIL", "VERIFY", "REVIEW", "REVIEW_FIX", "GATE2", "COMPLETE", "REQUIREMENTS", "CODEBASE", "ARCHITECTURE", "IMPACT", "REPORT", "MENU_ANALYSIS", "UX_DESIGN", "UI_DESIGN", "STORYBOARD", "VALIDATION"}
REQUIRED = {"ANALYZE": ("coordinator", "brainstorming"), "PLAN": ("coordinator", "writing-plans"), "IMPLEMENT": ("implementer", "test-driven-development"), "VERIFY": ("verifier", "verification-before-completion"), "REVIEW": ("reviewer", "requesting-code-review"), "BUG_FAIL": ("current_worker", "systematic-debugging"), "REVIEW_FIX": ("implementer", "receiving-code-review")}
ORDER = ["SESSION", "ANALYZE", "PLAN", "GATE1", "IMPLEMENT", "BUG_FAIL", "VERIFY", "REVIEW", "REVIEW_FIX", "GATE2", "COMPLETE"]
SLUG = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SKILL_ROOTS = (".opencode/skills", ".claude/skills", ".agents/skills")
MAX_ZIP = 30_000_000
MAX_FILE = 3_000_000
MAX_TOTAL = 15_000_000
MAX_FILES = 250

class ManagementError(ValueError):
    pass


def reject_symlinks(path: Path, root: Path):
    """Reject symlinks at any part of a path below project root."""
    root = root.resolve()
    try:
        relative = path.absolute().relative_to(root)
    except ValueError:
        raise ManagementError("PATH_OUTSIDE_PROJECT")
    current = root
    for item in relative.parts:
        current = current / item
        if current.is_symlink():
            raise ManagementError("SYMLINK_PATH_REJECTED")


def identifier(value: str) -> str:
    if not isinstance(value, str) or not SLUG.fullmatch(value) or "--" in value or value.endswith("-"):
        raise ManagementError("INVALID_ID")
    return value


def json_load(path: Path, root: Path) -> dict:
    reject_symlinks(path, root)
    if not path.is_file():
        raise ManagementError("NOT_FOUND")
    if path.stat().st_size > 1_000_000:
        raise ManagementError("CONFIG_TOO_LARGE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as e:
        raise ManagementError("INVALID_JSON") from e
    if not isinstance(value, dict):
        raise ManagementError("INVALID_OBJECT")
    return value


def atomic_json(path: Path, data: dict, root: Path):
    reject_symlinks(path, root)
    if not path.parent.is_dir():
        raise ManagementError("MISSING_CONFIG_DIRECTORY")
    payload = (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".agentflow-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Manager:
    def __init__(self, project: str | Path):
        self.root = Path(project).expanduser().resolve(strict=True)
        if not (self.root / "docs/workflow/WORKFLOW.md").is_file() or not (self.root / ".agentflow/active-profile.json").is_file():
            raise ManagementError("NOT_AGENTFLOW_PROJECT")
        self.config = self.root / ".agentflow"

    @contextlib.contextmanager
    def locked(self):
        path = self.config / ".management.lock"
        reject_symlinks(path, self.root)
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def active_tasks(self):
        task_root = self.root / "docs/tasks/active"
        reject_symlinks(task_root, self.root)
        if not task_root.is_dir():
            raise ManagementError("TASK_STATE_UNAVAILABLE")
        tasks = []
        for p in task_root.iterdir():
            if p.name == ".gitkeep":
                continue
            if p.is_symlink() or not p.is_dir() or self._task_record(p).get("state") != "PLAN_READY":
                tasks.append(p.name)
        # Legacy flat tasks cannot be assumed complete; block uncertain state.
        legacy_root = self.root / "docs/tasks"
        for child in legacy_root.iterdir():
            if child.name not in {"active", "completed", "handoffs"} and child.is_dir() and (child / "progress.md").exists():
                tasks.append("LEGACY_UNVERIFIED:" + child.name)
        return tasks

    def _task_dir(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Z][A-Z0-9]{1,12}-[0-9]{3,5}(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?", task_id):
            raise ManagementError("TASK_ID_INVALID")
        path = self.root / "docs/tasks/active" / task_id
        reject_symlinks(path, self.root)
        if not path.is_dir():
            raise ManagementError("ACTIVE_TASK_NOT_FOUND")
        return path

    def _task_record(self, path):
        state_file = path / "task-state.json"
        reject_symlinks(state_file, self.root)
        if state_file.is_file():
            record = json_load(state_file, self.root)
            if record.get("task_id") != path.name:
                raise ManagementError("TASK_STATE_ID_MISMATCH")
            return record
        return {"task_id": path.name, "state": "LEGACY_UNVERIFIED"}

    def plan_ready_tasks(self):
        root = self.root / "docs/tasks/active"
        reject_symlinks(root, self.root)
        return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.is_symlink()
                      and self._task_record(p).get("state") == "PLAN_READY")

    def mark_plan_ready(self, task_id):
        """Finalize verified planning deliverable, retaining same task in active/.

        Require a local verifier report with content digest checks, not mere profile-stage toggles.
        A PASS claim in a file is evidence provided by the agent, NOT proof of a native worker call.
        """
        with self.locked():
            from importlib import import_module
            ContextRegistry = import_module((__package__ + ".contexts") if __package__ else "agentflow_console.contexts").ContextRegistry
            pinned = ContextRegistry(self).task_contract(task_id) if (self.config / "execution-contexts" / "tasks" / (task_id + ".json")).is_file() else None
            if (pinned["profile"] if pinned else self.active().get("profile")) != "task-planning":
                raise ManagementError("TASK_PLANNING_PROFILE_REQUIRED")
            profile = self.profile("task-planning")
            if not all(s in configured_stages(profile) for s in ("ANALYZE","PLAN","VERIFY","COMPLETE")):
                raise ManagementError("PLANNING_STAGES_REQUIRED")
            task = self._task_dir(task_id)
            previous = self._task_record(task)
            if previous.get("state") not in ("LEGACY_UNVERIFIED","PLAN_DRAFT","PLAN_BLOCKED"):
                raise ManagementError("PLAN_STATE_NOT_DRAFT")
            spec, plan, evidence = (task / name for name in ("spec.md","plan.md","plan-verification.json"))
            for file in (spec,plan,evidence):
                reject_symlinks(file,self.root)
                if not file.is_file() or not file.read_bytes().strip():
                    raise ManagementError("PLAN_EVIDENCE_MISSING: "+file.name)
            report = json_load(evidence,self.root)
            if (report.get("result") != "PASS" or report.get("task_id") != task_id
                or report.get("verifier") != "verifier" or not isinstance(report.get("checks"),list)
                or not all(x in report["checks"] for x in ("requirements","acceptance_criteria","dependencies","verification_plan"))):
                raise ManagementError("PLAN_VERIFICATION_NOT_PASS")
            digests = {name:hashlib.sha256((task/name).read_bytes()).hexdigest() for name in ("spec.md","plan.md")}
            if any(report.get("sha256",{}).get(name)!=value for name,value in digests.items()):
                raise ManagementError("PLAN_VERIFICATION_STALE")
            record={"schema_version":1,"task_id":task_id,"state":"PLAN_READY",
                    "planning_profile":"task-planning", "plan_hashes":digests,
                    "verification_sha256":hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    "implementation_status":"NOT_STARTED","native_verifier_observed":"NOT_VERIFIED"}
            atomic_json(task / "task-state.json",record,self.root)
            return {"task_id":task_id,"state":"PLAN_READY","location":str(task.relative_to(self.root)),
                    "development_status":"NOT_STARTED","native_verifier_observed":"NOT_VERIFIED"}

    def begin_planned_task(self, task_id, session_id=None):
        """Claim the exact planned task for development; do not fake Gate 1 approval."""
        with self.locked():
            active = self.active()
            from importlib import import_module
            ContextRegistry = import_module((__package__ + ".contexts") if __package__ else "agentflow_console.contexts").ContextRegistry
            pinned_path = self.config / "execution-contexts" / "tasks" / (task_id + ".json")
            pinned = ContextRegistry(self).task_contract(task_id) if pinned_path.is_file() else None
            # A PLAN_READY planning TASK may be claimed into Development only when explicitly selected.
            registry = ContextRegistry(self)
            if session_id:
                session = registry.get_session(session_id)
                if not session or session.get('profile') not in ('development', 'lifecycle-dev', 'development-worker'):
                    raise ManagementError('DEVELOPMENT_SESSION_REQUIRED')
                target_profile = session['profile']
            else:
                target_profile = active.get('profile')
            if target_profile not in ('development', 'lifecycle-dev', 'development-worker'):
                raise ManagementError("DEVELOPMENT_PROFILE_REQUIRED")
            task=self._task_dir(task_id)
            record=self._task_record(task)
            if record.get("state")!="PLAN_READY":
                raise ManagementError("TASK_NOT_PLAN_READY")
            for name,digest in record.get("plan_hashes",{}).items():
                file=task/name
                reject_symlinks(file,self.root)
                if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
                    raise ManagementError("PLAN_CHANGED_REQUIRES_REVERIFY")
            verification=task/'plan-verification.json'
            if not verification.is_file() or hashlib.sha256(verification.read_bytes()).hexdigest()!=record.get("verification_sha256"):
                raise ManagementError("PLAN_VERIFICATION_CHANGED")
            record["state"]="WAITING_PLAN_APPROVAL"
            record["execution_profile"]=target_profile
            record["implementation_status"]="WAITING_GATE1"
            record["development_configuration_sha256"]=self.runtime_contract(profile_id=target_profile)["configuration_sha256"]
            registry.promote_to_development(task_id, session_id, target_profile=target_profile)
            atomic_json(task/'task-state.json',record,self.root)
            return {"task_id":task_id,"state":"WAITING_PLAN_APPROVAL","location":str(task.relative_to(self.root)),
                    "next_step":"GATE1_USER_APPROVAL_REQUIRED", "gate1_approved":False}

    def handoff_drafts(self):
        path = self.root / "docs/tasks/handoffs"
        reject_symlinks(path, self.root)
        if not path.is_dir():
            return []
        return sorted(item.name for item in path.iterdir() if item.is_dir() and not item.is_symlink())

    def ensure_idle(self):
        tasks = self.active_tasks()
        if tasks:
            raise ManagementError("TASK_ACTIVE: " + ", ".join(tasks[:8]))

    def profile(self, id: str):
        return json_load(self.config / "profiles" / (identifier(id) + ".json"), self.root)

    def tree(self, id: str):
        return json_load(self.config / "skill-trees" / (identifier(id) + ".json"), self.root)

    def list_profiles(self):
        path = self.config / "profiles"
        return [self.profile(p.stem) for p in sorted(path.glob("*.json")) if p.stem != "development"]

    def list_trees(self):
        path = self.config / "skill-trees"
        return [self.tree(p.stem) for p in sorted(path.glob("*.json")) if p.stem != "development"]

    def active(self):
        return json_load(self.config / "active-profile.json", self.root)

    def validate_tree(self, obj: dict, profile: str | None = None):
        if not isinstance(obj, dict) or obj.get("schema_version") != 1:
            raise ManagementError("TREE_SCHEMA_INVALID")
        identifier(obj.get("id"))
        stages = obj.get("stages")
        if not isinstance(stages, list) or not stages or len(stages) > 60:
            raise ManagementError("TREE_STAGES_INVALID")
        seen = set()
        for stage in stages:
            if not isinstance(stage, dict) or not isinstance(stage.get("id"), str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", stage["id"]):
                raise ManagementError("STAGE_UNKNOWN")
            sid = stage["id"]
            if sid in seen:
                raise ManagementError("STAGE_DUPLICATE")
            seen.add(sid)
            if not isinstance(stage.get("agent"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", stage["agent"]):
                raise ManagementError("AGENT_INVALID")
            skills = stage.get("skills")
            if sid in NON_SKILL_STAGES and skills:
                raise ManagementError("SYSTEM_STAGE_SKILLS_FORBIDDEN: " + sid)
            if not isinstance(skills, list) or len(skills) > 60:
                raise ManagementError("SKILLS_INVALID")
            names = set()
            for skill in skills:
                if not isinstance(skill, dict):
                    raise ManagementError("SKILL_INVALID")
                name = identifier(skill.get("name"))
                if name in names or type(skill.get("required")) is not bool or skill.get("condition") not in {"always", "on_failure", "on_review_changes", "on_ui_task", "optional"}:
                    raise ManagementError("SKILL_CONTRACT_INVALID")
                names.add(name)
        # Every Profile must preserve the same protected Workflow lifecycle.
        # Specialist activity names live inside a common stage, never replace gates.
        if [s['id'] for s in stages if s['id'] in ORDER] != ORDER:
            raise ManagementError('PROTECTED_STAGE_ORDER')
        for sid, expected_agent in (('GATE1','user'),('GATE2','user'),('VERIFY','verifier'),('REVIEW','reviewer')):
            st = next(s for s in stages if s['id'] == sid)
            if st['agent'] != expected_agent:
                raise ManagementError('PROTECTED_INDEPENDENCE_OR_GATE')
            if sid.startswith('GATE') and st['skills']:
                raise ManagementError('PROTECTED_HUMAN_GATE')
        for st in stages:
            if 'activities' in st and (not isinstance(st['activities'],list) or len(st['activities']) > 30 or not all(isinstance(a,str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}',a) for a in st['activities'])):
                raise ManagementError('ACTIVITIES_INVALID')
        if profile == "development":
            if [s["id"] for s in stages] != ORDER:
                raise ManagementError("PROTECTED_STAGE_ORDER")
            for sid, (agent, skill_name) in REQUIRED.items():
                stage = next(s for s in stages if s["id"] == sid)
                if stage["agent"] != agent or not any(s["name"] == skill_name and s["required"] for s in stage["skills"]):
                    raise ManagementError("PROTECTED_SKILL_OR_AGENT")
            for sid in ("GATE1", "GATE2"):
                stage = next(s for s in stages if s["id"] == sid)
                if stage["agent"] != "user" or stage["skills"]:
                    raise ManagementError("PROTECTED_HUMAN_GATE")
            if next(s for s in stages if s["id"] == "SESSION")["agent"] != "coordinator" or next(s for s in stages if s["id"] == "COMPLETE")["agent"] != "coordinator":
                raise ManagementError("PROTECTED_COORDINATOR")
        return True

    def validate_profile(self, obj):
        if not isinstance(obj, dict) or obj.get("schema_version") != 1:
            raise ManagementError("PROFILE_SCHEMA_INVALID")
        identifier(obj.get("id"))
        identifier(obj.get("skill_tree"))
        identifier(obj.get("workflow"))
        if obj.get("primary_agent") != "coordinator":
            raise ManagementError("COORDINATOR_REQUIRED")
        if obj.get("workflow") != "development" or obj.get("policy") != "protected-development":
            raise ManagementError("PROTECTED_WORKFLOW_REQUIRED")
        if not isinstance(obj.get("name"), str) or not 1 <= len(obj["name"]) <= 100:
            raise ManagementError("PROFILE_NAME_INVALID")
        stop_after = obj.get("stop_after_stage", "COMPLETE")
        if stop_after not in TERMINAL_STAGES:
            raise ManagementError("STOP_AFTER_STAGE_INVALID")
        stages = obj.get("enabled_stages")
        if stages is not None:
            if not isinstance(stages,list) or len(stages)>len(USER_STAGES) or len(set(map(str,stages)))!=len(stages) or any(x not in USER_STAGES for x in stages):
                raise ManagementError("ENABLED_STAGES_INVALID")
            if stages != [s for s in USER_STAGES if s in stages]:
                raise ManagementError("ENABLED_STAGES_ORDER_INVALID")
            # Stage selection is a user preference, not an implicit dependency closure.
            # Missing prerequisites are reported at runtime, not by mutating other toggles.
        branches = obj.get("conditional_stages", DEFAULT_BRANCH_POLICY)
        if not isinstance(branches,dict) or set(branches)!=set(BRANCH_STAGES) or any(type(branches[k]) is not bool for k in BRANCH_STAGES):
            raise ManagementError("CONDITIONAL_STAGES_INVALID")
        gates = obj.get("approval_gates", {"GATE1": True, "GATE2": True})
        if not isinstance(gates,dict) or set(gates)!=set(GATE_IDS) or any(type(gates[k]) is not bool for k in GATE_IDS):
            raise ManagementError("APPROVAL_GATES_INVALID")
        if stages is not None and any(gates[g] != (g in stages) for g in GATE_IDS):
            raise ManagementError("GATE_STAGE_POLICY_MISMATCH")
        # Every profile uses the same editable stage contract.  Identity, gate
        # authority and independent verifier/reviewer remain protected separately.
        if obj["id"] == "development":
            if stop_after != "COMPLETE" or not all(gates.values()) or (stages is not None and stages != list(USER_STAGES)) or not all(branches.values()):
                raise ManagementError("LEGACY_PROFILE_IMMUTABLE")
        if obj["id"] in ("development", "lifecycle-dev", "development-worker", "project-architect"):
            if obj.get("skill_tree") != obj["id"]:
                raise ManagementError("BUILTIN_SKILL_TREE_ID_LOCKED")
        # Worker Gate selection means a human checkpoint is requested; the worker
        # never becomes the approval actor.  The workflow engine must obtain
        # explicit user evidence, regardless of which profile selected the Gate.
        if obj["id"] == "development" and obj.get("policy") != "protected-development":
            raise ManagementError("LEGACY_PROFILE_IMMUTABLE")
        return True

    def save_profile(self, obj):
        self.validate_profile(obj)
        with self.locked():
            self.ensure_idle()
            path = self.config / "profiles" / (obj["id"] + ".json")
            if not path.is_file():
                raise ManagementError("PROFILE_NOT_FOUND_USE_CREATE")
            previous = self.profile(obj["id"])
            if obj["id"] == "development":
                if obj != previous:
                    raise ManagementError("LEGACY_PROFILE_IMMUTABLE")
            elif obj["id"] in ("lifecycle-dev", "development-worker", "project-architect", "storyboard", "task-planning"):
                mutable = {"enabled_stages", "approval_gates", "conditional_stages", "stop_after_stage"}
                if {k:v for k,v in obj.items() if k not in mutable} != {k:v for k,v in previous.items() if k not in mutable}:
                    raise ManagementError("BUILTIN_PROFILE_METADATA_IMMUTABLE")
            self.validate_tree(self.tree(obj["skill_tree"]), obj["id"])
            atomic_json(path, obj, self.root)
        return obj

    def save_tree(self, obj):
        if not isinstance(obj,dict) or "id" not in obj:
            raise ManagementError("TREE_SCHEMA_INVALID")
        with self.locked():
            self.ensure_idle()
            tree_id = identifier(obj["id"])
            path = self.config / "skill-trees" / (tree_id + ".json")
            if not path.is_file():
                raise ManagementError("TREE_NOT_FOUND")
            if tree_id == "development":
                if obj != self.tree(tree_id):
                    raise ManagementError("LEGACY_TREE_IMMUTABLE")
            self.validate_tree(obj, "development" if tree_id == "development" else None)
            previous = self.tree(tree_id)
            # Skill editing must not mutate the stage actors or control-flow
            # structure, even for built-in profiles.
            for old,new in zip(previous["stages"],obj["stages"]):
                if old["id"] != new["id"] or old["agent"] != new["agent"]:
                    raise ManagementError("STAGE_AGENT_IMMUTABLE")
            atomic_json(path, obj, self.root)
        return obj

    def apply_local_recommendations(self, profile_id: str, assignments: list, approved: bool = False):
        """Explicitly approved, atomic linkage of verified local skills to one Profile tree.

        LLM proposals are not trusted; every name, stage and installed file is
        checked against current on-disk project state under the project lock.
        """
        if not approved:
            raise ManagementError('EXPLICIT_APPLY_APPROVAL_REQUIRED')
        if not isinstance(assignments, list) or not 1 <= len(assignments) <= 50:
            raise ManagementError('INVALID_AI_ASSIGNMENTS')
        with self.locked():
            self.ensure_idle()
            profile = self.profile(profile_id)
            tree = self.tree(profile['skill_tree'])
            mapping = {stage['id']: stage for stage in tree['stages']}
            usable = set(mapping) - NON_SKILL_STAGES
            usable &= set(executable_stages(profile))
            verified = {item['name'] for item in self.list_skills() if item['verified']}
            changes = []
            for entry in assignments:
                if not isinstance(entry, dict):
                    raise ManagementError('INVALID_AI_ASSIGNMENTS')
                name = identifier(entry.get('name'))
                stage_id = entry.get('stage')
                if stage_id not in usable:
                    raise ManagementError('INVALID_AI_STAGE')
                if name not in verified:
                    raise ManagementError('AI_SKILL_NOT_VERIFIED: ' + name)
                stage = mapping[stage_id]
                if any(item['name'] == name for item in stage['skills']):
                    continue
                stage['skills'].append({'name':name,'required':False,'condition':'optional'})
                changes.append({'name':name,'stage':stage_id})
            self.validate_tree(tree, 'development' if tree['id'] == 'development' else None)
            if changes:
                atomic_json(self.config / 'skill-trees' / (tree['id'] + '.json'),tree,self.root)
        return {'profile':profile['id'],'tree':tree['id'],'connected':changes,
                'already_connected':len(assignments)-len(changes),'native_skill_load':'NOT_VERIFIED'}

    def activate(self, name: str, generation: int):
        with self.locked():
            # Existing TASKs MUST have verified immutable contracts before the mutable
            # project default may change; legacy/unpinned running tasks fail closed.
            from importlib import import_module
            ContextRegistry = import_module((__package__ + ".contexts") if __package__ else "agentflow_console.contexts").ContextRegistry
            registry = ContextRegistry(self)
            pinned_tasks = {item['task_id'] for item in registry.task_views() if item['contract_pinned']}
            for task_id in self.active_tasks():
                if task_id not in pinned_tasks:
                    raise ManagementError('ACTIVE_TASK_CONTEXT_NOT_PINNED: ' + task_id)
                registry.task_contract(task_id)
            if name == "development":
                raise ManagementError("LEGACY_PROFILE_USE_LIFECYCLE_DEV")
            p = self.profile(name)
            self.validate_profile(p)
            tree = self.tree(p["skill_tree"])
            self.validate_tree(tree, p["id"])
            missing = self.missing_skills(tree, p)
            if missing:
                raise ManagementError("SKILLS_MISSING: " + ", ".join(missing))
            old = self.active()
            if type(generation) is not int or old.get("generation") != generation:
                raise ManagementError("CONFIG_VERSION_CONFLICT")
            new = {"schema_version": 1, "profile": name, "generation": generation + 1}
            atomic_json(self.config / "active-profile.json", new, self.root)
            return new

    def missing_skills(self, tree, profile=None):
        missing = []
        if isinstance(profile, dict):
            allowed = set(executable_stages(profile))
        else:
            allowed = set(effective_stage_ids(profile or "COMPLETE"))
        for stage in tree["stages"]:
            if stage["id"] not in allowed:
                continue
            for s in stage["skills"]:
                if s["required"] and not self.verify_skill(s["name"])['verified']:
                    missing.append(s["name"])
        return sorted(set(missing))

    def _managed_lock(self):
        path = self.root / ".ai-dev/external-skills.lock.json"
        return json_load(path, self.root)

    def verify_skill(self, name):
        name = identifier(name)
        lock = self._managed_lock()
        managed = lock.get("managed_skills", {}).get(name)
        if managed:
            for root in SKILL_ROOTS:
                for relative, digest in managed["files_sha256"].items():
                    path = self.root / root / name / relative
                    try:
                        reject_symlinks(path, self.root)
                        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                            return {"name": name, "verified": False, "reason": "HASH_OR_FILE_MISMATCH"}
                    except (OSError, ManagementError):
                        return {"name": name, "verified": False, "reason": "HASH_OR_FILE_MISMATCH"}
            return {"name": name, "verified": True, "reason": "HASH_VERIFIED_NOT_NATIVE_LOADED"}
        files = lock.get("installed_files_sha256", {})
        expected = {k: v for k, v in files.items() if k.startswith(name + "/")}
        if not expected:
            return {"name": name, "verified": False, "reason": "NOT_INSTALLED"}
        for root in SKILL_ROOTS:
            for rel, digest in expected.items():
                path = self.root / root / rel
                try:
                    reject_symlinks(path, self.root)
                    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                        return {"name": name, "verified": False, "reason": "HASH_OR_FILE_MISMATCH"}
                except (OSError, ManagementError):
                    return {"name": name, "verified": False, "reason": "HASH_OR_FILE_MISMATCH"}
        return {"name": name, "verified": True, "reason": "HASH_VERIFIED_NOT_NATIVE_LOADED"}

    def list_skills(self):
        lock = self._managed_lock()
        names = set(lock.get("verified_skill_sha1", {})) | set(lock.get("managed_skills", {}))
        return [self.verify_skill(n) for n in sorted(names)]

    def dashboard_snapshot(self):
        """Local file-backed dashboard metrics; never fabricate history or native calls."""
        root=self.root / "docs/tasks"
        counts={"PLAN_READY":0,"WAITING_PLAN_APPROVAL":0,"IN_PROGRESS":0,"COMPLETED":0,"LEGACY_UNVERIFIED":0}
        recent=[]
        active=root / "active"
        reject_symlinks(active,self.root)
        if active.is_dir():
            for p in active.iterdir():
                if not p.is_dir() or p.is_symlink():
                    continue
                record=self._task_record(p)
                state=record.get("state","LEGACY_UNVERIFIED")
                if state not in counts:state="IN_PROGRESS"
                counts[state]+=1
                recent.append({"id":p.name,"status":state,"modified":p.stat().st_mtime})
        completed=root / "completed"
        reject_symlinks(completed,self.root)
        if completed.is_dir():
            for p in completed.iterdir():
                if p.is_dir() and not p.is_symlink():
                    counts["COMPLETED"]+=1
                    recent.append({"id":p.name,"status":"COMPLETED","modified":p.stat().st_mtime})
        doc_counts={}
        for kind in ('requirements','architecture','design','storyboards'):
            folder=self.root / 'docs' / kind
            reject_symlinks(folder,self.root)
            count=0
            if folder.is_dir():
                for doc in folder.rglob('*.md'):
                    if doc.is_file() and not doc.is_symlink() and doc.name.lower() != 'readme.md':
                        count+=1
            doc_counts[kind]=count
        design_count=doc_counts['design']
        recent.sort(key=lambda x:x['modified'],reverse=True)
        return {"status_counts":counts,"completed_count":counts['COMPLETED'],"design_doc_count":design_count,"document_counts":doc_counts,
                "recent_tasks":[{"id":x['id'],"status":x['status']} for x in recent[:8]]}

    def status(self):
        active = self.active()
        from importlib import import_module
        ContextRegistry = import_module((__package__ + ".contexts") if __package__ else "agentflow_console.contexts").ContextRegistry
        contexts = ContextRegistry(self)
        return {"session_defaults":contexts.list_sessions(),"task_contexts":contexts.task_views(),"project_default_profile":active["profile"], "project": str(self.root), "active_profile": active, "dashboard": self.dashboard_snapshot(), "tasks": self.active_tasks(), "plan_ready_tasks": self.plan_ready_tasks(), "handoff_drafts": self.handoff_drafts(), "profiles": len(self.list_profiles()), "trees": len(self.list_trees()), "skills": self.list_skills(), "native_worker_dispatch": "NOT_VERIFIED", "native_skill_load": "NOT_VERIFIED"}

    def runtime_contract(self, profile_id=None):
        active = self.active()
        selected = profile_id if profile_id is not None else active["profile"]
        profile = self.profile(selected)
        tree = self.tree(profile["skill_tree"])
        self.validate_tree(tree, profile["id"])
        execution = executable_stages(profile)
        chosen = configured_stages(profile)
        conditional = branch_policy(profile)
        missing = self.missing_skills(tree, profile)
        if missing:
            raise ManagementError("SKILLS_MISSING: " + ", ".join(missing))
        effective_tree = copy.deepcopy(tree)
        for stage in effective_tree["stages"]:
            stage["enabled"] = stage["id"] in execution and (stage["id"] not in GATE_IDS or stage["id"] in chosen)
            stage["conditional"] = stage["id"] in BRANCH_STAGES
        # Diagnose execution prerequisites without modifying the saved selection.
        # A selected stage is never evidence that its prerequisites were performed.
        stage_warnings = []
        if "GATE1" in chosen and "PLAN" not in chosen:
            stage_warnings.append({"code":"GATE1_NO_PLAN_IN_PROFILE","stage":"GATE1","detail":"Gate 1 requires an approved plan artifact from this or a prior task; do not infer approval from stage selection."})
        if "IMPLEMENT" in chosen and "PLAN" in chosen and "GATE1" not in chosen:
            stage_warnings.append({"code":"IMPLEMENT_APPROVED_PLAN_REQUIRED","stage":"IMPLEMENT","detail":"Implementation must not begin until a human-approved plan exists, even when Gate 1 is not selected in this profile."})
        if "VERIFY" in chosen and not any(x in chosen for x in ("ANALYZE","PLAN","IMPLEMENT")):
            stage_warnings.append({"code":"VERIFY_REQUIRES_ARTIFACT_STAGE","stage":"VERIFY","detail":"VERIFY needs an existing artifact from the current or another task; selected stages contain no artifact-producing step."})
        if "REVIEW" in chosen and "VERIFY" not in chosen:
            stage_warnings.append({"code":"REVIEW_NEEDS_VERIFICATION_EVIDENCE","stage":"REVIEW","detail":"REVIEW requires prior verification evidence; absence of VERIFY in this profile does not waive that requirement."})
        if "GATE2" in chosen and "REVIEW" not in chosen:
            stage_warnings.append({"code":"GATE2_NEEDS_REVIEW_EVIDENCE","stage":"GATE2","detail":"Gate 2 requires review evidence and an explicit user decision before final completion."})
        if "COMPLETE" in chosen and not any(x in chosen for x in ("ANALYZE","PLAN","IMPLEMENT")):
            stage_warnings.append({"code":"COMPLETE_REQUIRES_ARTIFACT_STAGE","stage":"COMPLETE","detail":"Completion requires an existing deliverable and applicable verification/approval evidence."})
        used_gates = [g for g in GATE_IDS if g in chosen]
        skipped_gates = [g for g in GATE_IDS if g not in chosen]
        complete_selected = "COMPLETE" in chosen
        quality_verified = "VERIFY" in chosen
        # Completion means completion of the selected profile deliverable, not downstream development.
        planning_deliverable = profile["id"] == "task-planning"
        can_archive = complete_selected and quality_verified and not planning_deliverable and profile["id"] != "development-worker"
        can_plan_ready = planning_deliverable and complete_selected and quality_verified
        legacy = "enabled_stages" not in profile
        last_stage = profile.get("stop_after_stage", "COMPLETE") if legacy else (chosen[-1] if chosen else "SESSION")
        terminal = "PLAN_READY_ELIGIBLE_AFTER_EVIDENCE" if can_plan_ready else ("COMPLETED_ELIGIBLE_AFTER_EVIDENCE" if can_archive else ("DELIVERABLE_UNVERIFIED" if complete_selected else ("STOPPED_AFTER_"+last_stage if legacy else "STOPPED_AFTER_SELECTED_STAGES")))
        return {"active_profile": copy.deepcopy(active), "profile": copy.deepcopy(profile), "tree": effective_tree,
                "approval_gates": {g: g in chosen for g in GATE_IDS},
                "execution_scope": {"mode": "LEGACY_PREFIX" if legacy else "INDEPENDENT_STAGES", "stop_after_stage": profile.get("stop_after_stage", "COMPLETE") if legacy else None, "enabled_stages": execution,
                    "user_selected_stages": chosen,
                    "execution_prerequisite_warnings": stage_warnings,
                    "conditional_stages": conditional,
                    "inactive_stages": [sid for sid in ORDER if sid not in execution],
                    "terminal_status": terminal,
                    "full_completion_allowed": can_archive,
                    "archive_to_completed_allowed": can_archive,
                    "completion_subject": "PLANNING_DELIVERABLE_PLAN_READY" if can_plan_ready else ("DEVELOPMENT_TASK_COMPLETED" if can_archive else "NOT_COMPLETED"),
                    "plan_ready_allowed_after_evidence": can_plan_ready,
                    "task_destination": "docs/tasks/active/<TASK-ID>" if can_plan_ready else ("docs/tasks/completed/<TASK-ID>" if can_archive else "docs/tasks/handoffs/<TASK-ID>"),
                    "partial_task_destination": None if can_plan_ready or can_archive else "docs/tasks/handoffs/<TASK-ID>",
                    "handoff_requires_new_development_task": False if can_plan_ready else profile["id"] not in ("development", "lifecycle-dev", "development-worker")},
                "protected_workflow": {"source": "docs/workflow/WORKFLOW.md", "stages": ORDER,
                    "human_gates": used_gates, "skipped_gates": [g for g in GATE_IDS if g not in used_gates and g in effective_stage_ids(profile.get("stop_after_stage", "COMPLETE"))] if legacy else skipped_gates,
                    "not_reached_gates": [g for g in GATE_IDS if g not in effective_stage_ids(profile.get("stop_after_stage", "COMPLETE"))] if legacy else [],
                    "independent_roles": [r for r,sid in (("verifier","VERIFY"),("reviewer","REVIEW")) if sid in chosen],
                    "skill_tree_role": "stage-skill-routing-overlay_only"},
                "configuration_sha256": hashlib.sha256(json.dumps([selected, profile, effective_tree], sort_keys=True).encode()).hexdigest(),
                "native_skills_loaded": "NOT_VERIFIED"}

    def inspect_local(self, source: str, kind: str):
        if kind not in {"local", "zip"}:
            raise ManagementError("UNSUPPORTED_SOURCE")
        src = Path(source).expanduser().resolve(strict=True)
        if kind == "local":
            if not src.is_dir():
                raise ManagementError("SOURCE_NOT_DIRECTORY")
            data = self._read_local(src)
        else:
            if not src.is_file() or src.stat().st_size > MAX_ZIP:
                raise ManagementError("ZIP_TOO_LARGE_OR_INVALID")
            data = self._read_zip(src.read_bytes())
        return self._manifest(data, kind, str(src))

    def _read_local(self, src: Path):
        result = {}
        total = 0
        for directory, dirs, files in os.walk(src, followlinks=False):
            if any((Path(directory) / name).is_symlink() for name in dirs + files):
                raise ManagementError("SYMLINK_SOURCE_REJECTED")
            for name in files:
                p = Path(directory) / name
                rel = p.relative_to(src).as_posix()
                self._validate_relative(rel)
                if not stat.S_ISREG(p.stat().st_mode) or len(result) >= MAX_FILES or p.stat().st_size > MAX_FILE:
                    raise ManagementError("SOURCE_SIZE_OR_TYPE_LIMIT")
                total += p.stat().st_size
                if total > MAX_TOTAL:
                    raise ManagementError("SOURCE_SIZE_LIMIT")
                result[rel] = p.read_bytes()
        return result

    @staticmethod
    def _validate_relative(name):
        if not name or "\\" in name or "\x00" in name or name.startswith("/") or any(part in {".", "..", ""} for part in name.split("/")):
            raise ManagementError("UNSAFE_ARCHIVE_ENTRY")
        if len(name) > 240:
            raise ManagementError("PATH_TOO_LONG")

    def _read_zip(self, blob):
        result = {}
        total = 0
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for info in z.infolist():
                self._validate_relative(info.filename.rstrip("/"))
                if info.is_dir():
                    continue
                mode = info.external_attr >> 16
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ManagementError("ZIP_NONREGULAR_REJECTED")
                if info.file_size > MAX_FILE or len(result) >= MAX_FILES or info.flag_bits & 1:
                    raise ManagementError("ZIP_SIZE_OR_ENCRYPTION")
                total += info.file_size
                if total > MAX_TOTAL:
                    raise ManagementError("ZIP_TOTAL_SIZE_LIMIT")
                if info.filename in result:
                    raise ManagementError("ZIP_DUPLICATE_ENTRY")
                result[info.filename] = z.read(info)
        # Either SKILL.md is at root or one common enclosing folder.
        if "SKILL.md" not in result:
            tops = {p.split("/")[0] for p in result}
            if len(tops) != 1:
                raise ManagementError("ZIP_ROOT_AMBIGUOUS")
            root = next(iter(tops)) + "/"
            result = {k[len(root):]: v for k, v in result.items() if k.startswith(root)}
        return result

    def _manifest(self, data, kind, source):
        if "SKILL.md" not in data:
            raise ManagementError("SKILL_MD_MISSING")
        try:
            text = data["SKILL.md"].decode("utf-8")
        except UnicodeError:
            raise ManagementError("SKILL_MD_NOT_UTF8")
        match = re.search(r"(?m)^name:\s*['\"]?([a-z][a-z0-9-]*)['\"]?\s*$", text)
        if not text.startswith("---\n") or not match:
            raise ManagementError("SKILL_FRONTMATTER_INVALID")
        name = identifier(match.group(1))
        return {"name": name, "source_type": kind, "source": source, "files_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(data.items())}, "size": sum(len(v) for v in data.values()), "file_count": len(data), "execution": "NOT_RUN", "security_review": "REQUIRED"}

    def _commit_skill(self, name: str, data: dict[str, bytes], origin: dict):
        """Install to three project roots, then publish a SINGLE combined lock.

        Roll back any committed directories on errors before lock publication.
        """
        lock = self._managed_lock()
        existing = set(lock.get("verified_skill_sha1", {})) | set(lock.get("managed_skills", {}))
        if name in existing:
            raise ManagementError("SKILL_ALREADY_EXISTS")
        entries = []
        for skill_root in SKILL_ROOTS:
            dest = self.root / skill_root / name
            reject_symlinks(dest, self.root)
            if dest.exists():
                raise ManagementError("SKILL_DESTINATION_EXISTS")
            entries.append(dest)
        fresh = self._manifest(data, origin["source_type"], origin["source"])
        staged, committed = [], []
        try:
            for dest in entries:
                dest.parent.mkdir(parents=True, exist_ok=True)
                temp = Path(tempfile.mkdtemp(prefix=".skill-stage-", dir=dest.parent))
                staged.append(temp)
                for rel, content in data.items():
                    path = temp / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                for rel, digest in fresh["files_sha256"].items():
                    if hashlib.sha256((temp / rel).read_bytes()).hexdigest() != digest:
                        raise ManagementError("STAGING_HASH_MISMATCH")
            for temp, dest in zip(staged, entries):
                os.replace(temp, dest)
                committed.append(dest)
            lock.setdefault("managed_skills", {})[name] = {
                **origin,
                "files_sha256": fresh["files_sha256"],
                "scope": "PROJECT_ONLY",
                "execution": "NOT_RUN",
                "native_skill_load": "NOT_VERIFIED",
            }
            atomic_json(self.root / ".ai-dev/external-skills.lock.json", lock, self.root)
        except Exception:
            for dest in committed:
                shutil.rmtree(dest)
            raise
        finally:
            for temp in staged:
                if temp.exists():
                    shutil.rmtree(temp)

    def install_skill(self, kind: str, source: str, approved: bool = False):
        if not approved:
            raise ManagementError("EXPLICIT_INSTALL_APPROVAL_REQUIRED")
        manifest = self.inspect_local(source, kind)
        name = manifest["name"]
        with self.locked():
            self.ensure_idle()
            src = Path(source).expanduser().resolve(strict=True)
            data = self._read_local(src) if kind == "local" else self._read_zip(src.read_bytes())
            fresh = self._manifest(data, kind, str(src))
            if fresh["files_sha256"] != manifest["files_sha256"]:
                raise ManagementError("SOURCE_CHANGED")
            self._commit_skill(name, data, {"source_type": kind, "source": str(src)})
        return {"name": name, "installed": True, "verified": self.verify_skill(name), "native_skill_load": "NOT_VERIFIED"}

    def inspect_uploaded_zip(self, blob: bytes):
        """Inspect a browser-uploaded ZIP, without executing any included scripts."""
        if not isinstance(blob, bytes) or len(blob) > MAX_ZIP:
            raise ManagementError('ZIP_TOO_LARGE_OR_INVALID')
        files = self._read_zip(blob)
        manifest = self._manifest(files, 'zip-upload', 'browser-upload')
        manifest['archive_sha256'] = hashlib.sha256(blob).hexdigest()
        return manifest

    def install_uploaded_zip(self, blob: bytes, expected_sha256: str, approved: bool = False):
        if not approved:
            raise ManagementError('EXPLICIT_INSTALL_APPROVAL_REQUIRED')
        manifest = self.inspect_uploaded_zip(blob)
        if not isinstance(expected_sha256,str) or expected_sha256 != manifest['archive_sha256']:
            raise ManagementError('SOURCE_CHANGED')
        files = self._read_zip(blob)
        with self.locked():
            self.ensure_idle()
            self._commit_skill(manifest['name'], files, {'source_type':'zip-upload','source':'browser-upload','archive_sha256':expected_sha256})
        return {'name':manifest['name'],'installed':True,'verified':self.verify_skill(manifest['name']),'native_skill_load':'NOT_VERIFIED'}

    def inspect_created_skill(self, name: str, description: str, instructions: str):
        """Preview a self-authored SKILL.md without executing model output.

        Only one markdown file is staged. Arbitrary scripts/other files use the
        separately reviewed local/Git/ZIP flow.
        """
        name = identifier(name)
        if not isinstance(description, str) or not 5 <= len(description.strip()) <= 350 or '\n' in description or '\r' in description:
            raise ManagementError('SKILL_DESCRIPTION_INVALID')
        if not isinstance(instructions, str) or not 20 <= len(instructions.strip()) <= 30000:
            raise ManagementError('SKILL_INSTRUCTIONS_INVALID')
        data = self._created_skill_data(name, description, instructions)
        result = self._manifest(data, 'editor', 'local-editor')
        result['preview'] = data['SKILL.md'].decode('utf-8')
        return result

    @staticmethod
    def _created_skill_data(name: str, description: str, instructions: str):
        # Quoted YAML scalar prevents crafted frontmatter injection.
        frontmatter = '---\nname: ' + name + '\ndescription: ' + json.dumps(description.strip(), ensure_ascii=False) + '\n---\n\n'
        return {'SKILL.md': (frontmatter + instructions.strip() + '\n').encode('utf-8')}

    def install_created_skill(self, name: str, description: str, instructions: str, approved: bool = False):
        if not approved:
            raise ManagementError('EXPLICIT_INSTALL_APPROVAL_REQUIRED')
        self.inspect_created_skill(name, description, instructions)
        with self.locked():
            self.ensure_idle()
            self._commit_skill(name, self._created_skill_data(name, description, instructions), {'source_type':'editor','source':'local-editor'})
        return {'name':name, 'installed':True, 'verified':self.verify_skill(name), 'native_skill_load':'NOT_VERIFIED'}

    @staticmethod
    def _git_fields(url: str, commit: str, subdir: str):
        if not isinstance(url, str) or len(url) > 500 or not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
            raise ManagementError("PINNED_COMMIT_REQUIRED")
        if not isinstance(subdir, str) or len(subdir) > 240 or subdir.startswith("/") or "\\" in subdir or any(x in {".", "..", ""} for x in subdir.split("/")):
            raise ManagementError("INVALID_GIT_SKILL_SUBDIR")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == "file":
            if parsed.netloc not in ("", "localhost") or not parsed.path.startswith("/"):
                raise ManagementError("GIT_LOCAL_URL_INVALID")
        elif parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
            raise ManagementError("GIT_HTTPS_OR_LOCAL_URL_REQUIRED")
        return url, commit.lower(), subdir

    def _fetch_git(self, url: str, commit: str, subdir: str):
        """Read pinned git tree into memory, without checking out or executing scripts.

        Git itself is system CLI, not a tool installed globally by this framework.
        Any git credential prompts and global/user git configuration are disabled.
        """
        url, commit, subdir = self._git_fields(url, commit, subdir)
        # No git hooks, checkout, credential helpers, or user config; fetch is read-only.
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="https:file")
        with tempfile.TemporaryDirectory(prefix=".git-import-", dir=self.config) as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            base = ["git", "-c", "core.hooksPath=/dev/null", "-c", "credential.helper=", "-C", str(repo)]
            for args in (["init", "--quiet"], ["remote", "add", "origin", url], ["fetch", "--quiet", "--depth=1", "origin", commit]):
                result = subprocess.run(base + args, env=env, capture_output=True, timeout=45)
                if result.returncode:
                    raise ManagementError("GIT_FETCH_FAILED")
            resolved = subprocess.run(base + ["rev-parse", "FETCH_HEAD^{commit}"], env=env, capture_output=True, timeout=10)
            if resolved.returncode or resolved.stdout.decode().strip() != commit:
                raise ManagementError("GIT_COMMIT_NOT_MATCHED")
            archive = Path(tmp) / "skill.zip"
            with archive.open('wb') as output:
                try:
                    completed = subprocess.run(base + ["archive", "--format=zip", commit, subdir], env=env, stdout=output, stderr=subprocess.PIPE, timeout=30)
                except subprocess.TimeoutExpired as exc:
                    raise ManagementError("GIT_ARCHIVE_TIMEOUT") from exc
            if completed.returncode or archive.stat().st_size > MAX_ZIP:
                raise ManagementError("GIT_ARCHIVE_INVALID_OR_TOO_LARGE")
            with zipfile.ZipFile(archive) as z:
                prefix = subdir.rstrip("/") + "/"
                normalized = io.BytesIO()
                with zipfile.ZipFile(normalized, "w") as dest:
                    for item in z.infolist():
                        if item.is_dir():
                            continue
                        if not item.filename.startswith(prefix):
                            raise ManagementError("GIT_ARCHIVE_PREFIX_MISMATCH")
                        rel = item.filename[len(prefix):]
                        self._validate_relative(rel)
                        if item.file_size > MAX_FILE:
                            raise ManagementError("GIT_ARCHIVE_SIZE_LIMIT")
                        mode = item.external_attr >> 16
                        if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                            raise ManagementError("GIT_ARCHIVE_NONREGULAR")
                        dest.writestr(rel, z.read(item))
            return self._read_zip(normalized.getvalue())

    def inspect_git(self, url: str, commit: str, subdir: str):
        data = self._fetch_git(url, commit, subdir)
        return self._manifest(data, "git", url + "@" + commit + ":" + subdir)

    def install_git(self, url: str, commit: str, subdir: str, approved: bool = False):
        if not approved:
            raise ManagementError("EXPLICIT_INSTALL_APPROVAL_REQUIRED")
        url, commit, subdir = self._git_fields(url, commit, subdir)
        data = self._fetch_git(url, commit, subdir)
        name = self._manifest(data, "git", url)["name"]
        with self.locked():
            self.ensure_idle()
            self._commit_skill(name, data, {"source_type": "git", "source": url, "commit": commit, "subdir": subdir})
        return {"name": name, "installed": True, "verified": self.verify_skill(name), "native_skill_load": "NOT_VERIFIED"}

    def remove_skill(self, name: str, approved: bool = False):
        name = identifier(name)
        if not approved:
            raise ManagementError("EXPLICIT_REMOVE_APPROVAL_REQUIRED")
        with self.locked():
            self.ensure_idle()
            lock = self._managed_lock()
            if name not in lock.get("managed_skills", {}):
                raise ManagementError("ONLY_MANAGED_SKILLS_REMOVABLE")
            for tree in self.list_trees():
                if any(s["name"] == name for stage in tree["stages"] for s in stage["skills"]):
                    raise ManagementError("SKILL_REFERENCED_IN_TREE: " + tree["id"])
            if not self.verify_skill(name)["verified"]:
                raise ManagementError("MODIFIED_SKILL_REFUSE_DELETE")
            moved = []
            with tempfile.TemporaryDirectory(prefix=".skill-remove-", dir=self.config) as tmp:
                try:
                    for index, root in enumerate(SKILL_ROOTS):
                        source = self.root / root / name
                        reject_symlinks(source, self.root)
                        dest = Path(tmp) / str(index)
                        os.replace(source, dest)
                        moved.append((source, dest))
                    del lock["managed_skills"][name]
                    atomic_json(self.root / ".ai-dev/external-skills.lock.json", lock, self.root)
                except Exception:
                    for source, dest in reversed(moved):
                        os.replace(dest, source)
                    raise
        return {"name": name, "removed": True}

    def list_templates(self):
        return sorted(p.stem for p in (self.config / "templates/profiles").glob("*.json"))

    def add_template(self, template: str):
        template = identifier(template)
        profile = json_load(self.config / "templates/profiles" / (template + ".json"), self.root)
        tree = json_load(self.config / "templates/skill-trees" / (template + ".json"), self.root)
        self.validate_profile(profile)
        self.validate_tree(tree)
        with self.locked():
            self.ensure_idle()
            ppath = self.config / "profiles" / (template + ".json")
            tpath = self.config / "skill-trees" / (template + ".json")
            if ppath.exists() or tpath.exists():
                raise ManagementError("TEMPLATE_ALREADY_INSTALLED")
            missing = self.missing_skills(tree)
            if missing:
                raise ManagementError("TEMPLATE_SKILLS_MISSING: " + ",".join(missing))
            atomic_json(tpath, tree, self.root)
            try:
                atomic_json(ppath, profile, self.root)
            except Exception:
                tpath.unlink(missing_ok=True)
                raise
        return profile

    def create_profile(self, name: str, label: str):
        """Create a user profile from protected Workflow skeleton, never a policy-less tree.

        The author may add specialist skills later, but approval and independent
        verification stages remain present in every new tree.
        """
        name = identifier(name)
        if name in ('development', 'lifecycle-dev'):
            raise ManagementError('PROTECTED_PROFILE_IMMUTABLE')
        baseline = copy.deepcopy(self.tree('lifecycle-dev'))
        baseline['id'] = name
        # Keep required baseline skills and all protected stages. Remove any extra
        # optional additions present in a customized development Tree.
        for stage in baseline['stages']:
            stage['skills'] = [s for s in stage['skills'] if s.get('required')]
        profile = {
            'schema_version': 1, 'id': name, 'name': label,
            'primary_agent': 'coordinator', 'workflow': 'development',
            'skill_tree': name, 'policy': 'protected-development',
            'built_in': False, 'approval_gates': {'GATE1': True, 'GATE2': True}, 'stop_after_stage': 'COMPLETE', 'enabled_stages': list(USER_STAGES), 'conditional_stages': dict(DEFAULT_BRANCH_POLICY)
        }
        self.validate_profile(profile)
        self.validate_tree(baseline)
        with self.locked():
            self.ensure_idle()
            ppath = self.config / 'profiles' / (name + '.json')
            tpath = self.config / 'skill-trees' / (name + '.json')
            if ppath.exists() or tpath.exists():
                raise ManagementError('PROFILE_ALREADY_EXISTS')
            atomic_json(tpath, baseline, self.root)
            try:
                atomic_json(ppath, profile, self.root)
            except Exception:
                tpath.unlink(missing_ok=True)
                raise
        return profile

    def clone_profile(self, source: str, name: str, label: str):
        name = identifier(name)
        original = self.profile(source)
        tree = self.tree(original["skill_tree"])
        new_tree = copy.deepcopy(tree)
        new_tree["id"] = name
        new_profile = copy.deepcopy(original)
        new_profile.update({"id": name, "name": label, "skill_tree": name, "built_in": False, "policy": "protected-development" if original["id"] in ("development", "lifecycle-dev") else original.get("policy", "protected-development"), "approval_gates": copy.deepcopy(original.get("approval_gates", {"GATE1": True, "GATE2": True})), "stop_after_stage": original.get("stop_after_stage", "COMPLETE"), "enabled_stages": configured_stages(original), "conditional_stages": branch_policy(original)})
        self.validate_profile(new_profile)
        self.validate_tree(new_tree)
        with self.locked():
            self.ensure_idle()
            ppath = self.config / "profiles" / (name + ".json")
            tpath = self.config / "skill-trees" / (name + ".json")
            if ppath.exists() or tpath.exists():
                raise ManagementError("PROFILE_ALREADY_EXISTS")
            atomic_json(tpath, new_tree, self.root)
            try:
                atomic_json(ppath, new_profile, self.root)
            except Exception:
                tpath.unlink(missing_ok=True)
                raise
        return new_profile
