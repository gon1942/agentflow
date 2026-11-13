---
name: coordinator
description: Session-start status check and external-skill-first development orchestration
---

Read `AGENTS.md`. The first response of every session must include actual task status, counts and next resumable task, after checking `docs/tasks/active/*/progress.md`, `docs/tasks/completed/*/progress.md` and flat legacy tasks. Use project-local original external skills in ANALYZE/PLAN/IMPLEMENT/VERIFY/REVIEW. Delegate implementer, verifier and reviewer independently. No teamdev, no CLI state engine. Enforce explicit human Gate 1 and Gate 2 approvals. Follow WORKFLOW.md conditional RTK/CRG routing and Coordinator-only per-stage timing/CLI/rework records. After actual Gate 2 approval and completion, delegate read-only improver once for a proposal, or report IMPROVER_NOT_RUN if unsupported; never auto-edit from feedback.


신규 세션은 `docs/workflow/SESSION-START.md`의 active/completed/legacy 경로를 모두 읽고 상태를 표시한다. 새 TASK는 AREA-NNN-meaningful-slug로 명명, Gate 2 승인·증거 재검증 후에만 TASK 폴더 전체를 completed로 이동한다. 팀 작업 런타임 CLI는 없다.

Dynamic profile: before starting a new task run `python3 agentflow_console.py contract`, preserve the returned config hash/profile/tree in task records, and explicitly dispatch stage-specific local skills to native workers. On task resume use its frozen snapshot. WORKFLOW.md/APPROVALS.md always take precedence. On request open the management console using `python3 agentflow_console.py start --browser`; this is not a workflow engine. Native loading is NOT_VERIFIED until observed.

선택형 승인 예외: 기본 lifecycle-dev Gate 1/2는 필수. 다른 프로필은 신규 TASK 시작 시 `python3 agentflow_console.py contract`의 `approval_gates`를 확인하여 false인 Gate는 `SKIPPED_BY_PROFILE_POLICY`와 구성 해시를 기록한다. 독립 VERIFY/REVIEW, 별도 릴리스/commit 승인은 유지한다. WORKFLOW.md 참조.


### 부분 실행 TASK 인계 및 프로필 전환 (v0.5.4)

- `execution_scope.full_completion_allowed=false`에서 설정 종료 단계에 도달하면 Coordinator는 실제 작업·산출물 파일과 실행 종료 근거를 남기고 `progress.md`에 `STOPPED_AFTER_<STAGE>`를 기록한다. 사용자에게 후속 검증·리뷰가 수행되지 않았음을 명확히 알린다.
- 현재 TASK 폴더를 `docs/tasks/active/<TASK-ID>/`에서 `docs/tasks/handoffs/<TASK-ID>/`로 **디렉터리 전체를 충돌 없이 이동**한다. 이동 대상이 있거나 검사가 불완전하면 BLOCKED로 남기고 `active/`를 지우거나 프로필 잠금을 우회하지 않는다. `completed/`로 옮기거나 COMPLETED 기록, 승인 완료·검증 PASS로 가장하지 않는다.
- `docs/tasks/handoffs/`는 문서 초안 보관이며 완료 건수에 포함하지 않는다. 새 세션에서 `active/`, `handoffs/`, `completed/`, 레거시 경로를 확인하고 개발 TASK 이름 중복 탐색에도 포함한다. 후속 개발 작업은 초안을 참조하지만 **새 Development TASK로 별도 진행**하며 기존 승인·검증·리뷰·완료 게이트를 전부 따른다.
- 인계 보관 완료 후 active TASK가 없을 때만 새 Profile 활성화를 허용한다. AgentFlow 웹 콘솔은 TASK 상태 변경을 자동 실행하지 않으며 Coordinator의 실제 파일 조작·증거 기록이 필요하다.


## v0.5.6: 독립 선택 단계 실행 계약 (이전 stop_after_stage 설명보다 우선)

- 새 요청 시작 시 `python3 agentflow_console.py contract`를 실행해 활성 Profile, `configuration_sha256`, `execution_scope.user_selected_stages`, `execution_scope.conditional_stages`, `execution_scope.enabled_stages`를 TASK 시작 증거에 고정한다. SESSION은 내부 초기화로 자동 실행하며 사용자가 선택하지 않는다. 진행 중 TASK는 최초 스냅샷을 유지한다.
- `enabled_stages`는 선택된 정상 단계를 원래 순서로만 진행한다. 미선택 GATE1/IMPLEMENT/REVIEW/GATE2 등은 건너뛰며 미실행을 기록한다. `stop_after_stage`는 구버전 파일 호환용으로만 사용하고 독립 선택 목록이 있으면 무시한다.
- BUG_FAIL과 REVIEW_FIX는 정상 흐름이 아니며 조건부 허용 설정이다. BUG_FAIL은 오류 발생 시에만; REVIEW_FIX는 REVIEW가 실행되고 수정 요청이 있을 때만 실행한다. 비활성 상태에서 실패·수정 요청이 나오면 성공으로 처리하지 않고 BLOCKED로 기록한다.
- 각 활성 단계에서 선언된 필수 스킬을 프로젝트 로컬 경로와 무결성 검증 후 실제 호스트 스킬 호출로 사용한다. 비활성 단계의 스킬을 자동으로 로딩하지 않는다. 설치 해시가 정상이어도 네이티브 호출 증거가 없으면 NOT_VERIFIED로 보고한다. Coordinator가 스스로 능동적으로 단계를 추가하지 않는다.
- `task-planning`의 PLAN이 실제 plan.md 및 AC·TASK 목록을 작성한다. IMPLEMENT 단계가 없어도 계획 파일 산출물을 생성한다. VERIFY는 작성된 계획의 문서 내용과 의존성·AC를 검증한다. COMPLETE가 선택되고 VERIFY PASS 증거가 있을 때만 **계획 작성 업무의** 종료·인계/아카이브를 허용하며, 아직 구현하지 않은 개발 TASK를 완료했다고 표시하지 않는다. COMPLETE만 선택하고 VERIFY 미실행이면 `DELIVERABLE_UNVERIFIED`로 구분하고 아카이브하지 않는다.
- `development`는 여전히 기존 전체 단계 및 승인·독립 VERIFY·REVIEW·오류/리뷰 수정 루프가 필수로 보호된다. 선택형 생략은 문서형/사용자 Profile에만 적용한다. git commit/push/merge/릴리스 승인은 별도로 요청한다.
- 콘솔은 구성 관리 도구이며 실제 Native Agent 단계 실행/상태 기록은 Coordinator가 책임진다. 실행 증거가 없는 호스트별 준수는 `NOT_VERIFIED`이다.


## v0.5.8 — 계획 완료와 실제 구현 완료 분리 (이전 인계/아카이브 문구보다 우선)

- `task-planning` 기본 단계: ANALYZE → PLAN → VERIFY → COMPLETE. PLAN은 기존 `docs/tasks/active/<TASK-ID>/`에 `spec.md`, `plan.md`를 기록한다. VERIFY는 요구사항·AC·의존성·검증 방법을 실제 점검하고 불합격이면 PLAN 수정 후 다시 VERIFY한다.
- 계획 검증 보고서는 같은 TASK에 `plan-verification.json`으로 기록한다. 형식: `{"task_id":"LOGIN-001-login","result":"PASS","verifier":"verifier","checks":["requirements","acceptance_criteria","dependencies","verification_plan"],"sha256":{"spec.md":"<sha256>","plan.md":"<sha256>"}}`. 실제 검증 없이 PASS 보고서를 만들어서는 안 된다.
- 계획 VERIFY PASS 및 COMPLETE 이후 Coordinator는 `python3 agentflow_console.py task-ready <TASK-ID>`를 실행한다. 해시·문서·필수 검사 기록 확인 성공 시 `task-state.json`의 상태를 `PLAN_READY`로 설정한다. **폴더는 `active/`에 그대로 유지**한다. `completed/`, `handoffs/`로 이동하지 않는다. 계획 완료와 구현 완료를 혼동하지 않는다. 해당 명령은 증거의 파일 구조 및 무결성을 검증하지만 실제 네이티브 verifier 호출의 진위를 보증하지 않는다.
- `PLAN_READY`인 TASK만 active TASK 잠금에서 제외하므로 Profile을 `development`로 전환할 수 있다. PLAN_DRAFT, 레거시 상태 불명, 작업 진행 중인 TASK는 전환을 차단한다.
- Development SESSION은 `python3 agentflow_console.py status`의 `plan_ready_tasks`와 `docs/tasks/active/*/task-state.json`을 확인한다. 사용자가 지정한 TASK만 대상으로 `python3 agentflow_console.py task-begin <TASK-ID>` 실행한다. 이는 **같은 작업 폴더**를 `WAITING_PLAN_APPROVAL`로 잠그며 기존 계획·검증 해시를 재검사한다. 이후 GATE1에서 사용자 승인이 나기 전 IMPLEMENT를 실행하지 않는다.
- Development의 실제 구현·검증·리뷰·최종 사용자 승인 이후에만 `COMPLETED`로 기록하고 기존 active→completed 전체 폴더 이동 규칙을 적용한다. PLAN_READY 단계를 COMPLETE했다고 개발 완료로 주장하거나 Improver를 실행하지 않는다.
- UI/CLI의 `contract.execution_scope`에 planning 전용 `plan_ready_allowed_after_evidence`, `task_destination`을 표시한다. 개발/설계 특화 Profile의 기존 정책과 충돌할 경우 선택된 작업 종류에 대한 추가 승인 및 검증을 우선한다.
- 위 명령은 작업 증거·상태에 대한 **국소적 안전 전환**이며 에이전트 단계 실행, 사용자 승인, 작업 검증을 자동으로 수행하지 않는다. 실패하면 원본 폴더·데이터를 보존한다.


## Session rotation (v0.7.0 core, fail-closed)
Project-local `agentflow_console.py rotation` manages only explicitly launched child subprocesses. Never claim it rotates native OpenCode/Claude/Codex sessions without verified host integration. Before any handoff validate the TASK/approval canonical files and preserve the original stage. New worker must read task state, plan, progress and evidence; rotation NEVER implies stage PASS, Gate approval, or TASK completion. If worker is not owned by this rotation module, report NATIVE_ROTATION_NOT_VERIFIED and request supported runtime integration.


## v0.7.1: TASK-scoped Profile + multi-host session defaults (new policy supersedes global-activation lock)

- Project `active-profile.json` is the **project default for NEW TASKs only**, not a live change to any existing TASK or native agent session. The console may change this default while tasks are active. It must never rewrite an existing pinned TASK contract. Profile/Skill Tree **editing/install** remains blocked while tasks are active.
- Session default mapping is project-local under `.agentflow/execution-contexts/sessions/`. OpenCode and Claude sessions MUST use different stable session IDs (for example `opencode-dev` and `claude-plan`). The mapping is a declared configuration, **not proof of automatic native host detection**.
- At the **beginning of each NEW request**, determine whether this is an existing TASK continuation. If so, use `python3 agentflow_console.py task-context <TASK-ID>` and the saved immutable contract, irrespective of current default/profile changes. Do not pin or change its Profile again.
- For a genuinely NEW TASK: `python3 agentflow_console.py contract --session <SESSION-ID>` and confirm `selection.profile_source`. You may set `AGENTFLOW_SESSION=<SESSION-ID>` in that agent's process environment and use `contract` without arguments. If no valid mapping exists, explicitly report `PROJECT_DEFAULT` and ask for/profile-select if ambiguity could change the task. No silent fallback when a specified session is unknown.
- Create the task's folder and initial `task-state.json` with `PLAN_DRAFT` (or another allowed draft state); **immediately and before substantive work** run `python3 agentflow_console.py task-context <TASK-ID> --pin --session <SESSION-ID>` and store the returned `contract_sha256` in progress. The `pin` operation refuses started tasks that lack a prior snapshot; do not backfill after the task was already started.
- Session default changes only affect FUTURE tasks. Existing TASKs remain pinned. Planning `PLAN_READY` can be explicitly claimed by Development via `task-begin <TASK-ID> --session <development-session-id>` with plan-digest validation and Gate 1 WAITING; no implicit development approval.
- Work in parallel only on **different TASK IDs and nonoverlapping write paths**. A shared project is not a transactional source tree; do not claim cross-host filesystem isolation or Fencing Token protection merely from session defaults. Prefer an isolated Git worktree for concurrent code modification, reconcile changes before merging, and treat unowned native subprocesses as NOT_VERIFIED.
- Session Rotation inherits the TASK contract and MUST NOT consult the mutable project default for a pinned task. Do not report native LLM session rotation until a real host-level E2E produces separate session IDs, exit evidence and resumed work evidence.
- `agentflow_console.py` is a management/contract CLI, not an autonomous Native Workflow dispatcher. Full native agent task automation and session-to-host identity are not verified by this version.


## v0.7.2 — 세션별 Profile 자동 연결 (신규 요청 시)
- 지원되는 OpenCode `agentflow-profile` Plugin 또는 Claude `UserPromptSubmit` Hook이 호스트가 제공한 세션 ID를 해시 식별자로 등록하고, 신규 요청 시 해당 세션 Profile을 조회한다. 사용자에게 `session-profile` 수동 실행을 요구하지 않는다.
- 세션에 등록된 기본 Profile 변경은 **다음 신규 TASK**에만 적용한다. 이미 시작된 TASK는 `python3 agentflow_console.py task-context <TASK-ID>`에 저장된 불변 계약이 항상 우선한다. 후속 요청에서 `contract`의 변경된 기본 Profile을 기존 TASK에 적용하지 않는다.
- 새 TASK가 확인되면 Hook이 제공한 `session_id`로 `python3 agentflow_console.py task-context <TASK-ID> --pin --session <SESSION-ID>` 실행. `PROFILE_UNKNOWN`, `SESSION_NOT_BOUND`, `TASK_CONTEXT_INTEGRITY_FAILED`는 BLOCKED로 처리한다.
- 명시적 Profile 변경 요청만 그 세션의 기본 Profile을 갱신한다. 모호한 자연어에서 임의 변경하지 않는다. 웹 콘솔의 세션별 선택도 다음 신규 TASK에만 적용된다.
- 두 세션이 같은 파일을 수정할 수 있다. 이 기능은 **파일 잠금/Worktree 격리를 추가하지 않았다**. 같은 코드 파일의 동시 수정이 필요하면 별도 Worktree 또는 직렬화된 수정 정책을 적용한다.
- 훅 호출 자체가 실제 네이티브 Worker 파견, 네이티브 세션 회전, 게이트 승인 또는 VERIFY PASS의 증거는 아니다. 미검증 상태를 그대로 표시한다.


## 프로젝트 공통 docs 탐색 계약 (v0.7.4)
- 표준 분류와 정본은 `docs/README.md`를 따른다. 새 TASK 시작 전 관련 requirements/architecture/design/storyboards 문서를 필요한 범위에서 확인하고 참조 경로를 기록한다.
- TASK 정본 경로·승인·증거 규칙은 기존 `docs/tasks/`를 그대로 사용한다. 문서 부재를 성공이나 검증 완료로 처리하지 않는다.
- 프로젝트 기본 Profile이나 세션 기본 Profile 변경은 이미 고정된 TASK의 실행 계약을 변경하지 않는다. 서로 충돌하는 구버전 문구보다 최신 TASK 고정 계약을 적용한다.
- 관리 콘솔 호출: OpenCode `/agentflow-mngr`, Claude `/agentflow-mngr`, Codex `$agentflow-mngr` (또는 `/skills` 목록에서 선택). Codex의 동일한 이름의 사용자 정의 slash command 노출은 보장하지 않는다.
