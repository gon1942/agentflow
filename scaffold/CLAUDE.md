# Claude Code — AgentFlow Native Skills

공통 지침은 프로젝트 루트의 `AGENTS.md`가 정본이다. 매 신규 세션 첫 응답 전에 `docs/tasks/active/*/progress.md` + `docs/tasks/completed/*/progress.md` + 레거시 `docs/tasks/*/progress.md`를 확인하여 진행·승인 대기·차단·완료 작업 수와 다음 작업을 사용자에게 보여준다. 실시간 로깅 금지. `teamdev` 및 자체 워크플로 CLI는 없다. 프로젝트 내부 `.claude/skills`의 원본 외부 스킬을 실제로 사용한다. PLAN 승인 전 구현 금지, REVIEW PASS 후 Gate 2 승인 전 완료 금지. 네이티브 implementer/verifier/reviewer를 분리 사용하고 불가능하면 BLOCKED 표시.

사용자 정의 Profile은 `agentflow_console.py contract` 승인 설정에 따라 Gate 1·2 선택 가능(기본 lifecycle-dev 필수). 생략 근거를 SKIPPED_BY_PROFILE_POLICY로 기록하고 독립 VERIFY/REVIEW·별도 배포/commit 승인은 유지한다.


## Profile별 단계 실행 범위 (v0.5.4)

- 새 TASK 시작 시 반드시 `python3 agentflow_console.py contract`의 `execution_scope`를 읽고 Profile ID, `configuration_sha256`, `stop_after_stage`, 활성 단계를 TASK 기록에 고정한다. 과거 TASK에는 소급 적용하지 않는다.
- 기본 `lifecycle-dev`는 `COMPLETE` 종료를 필수로 하며, 필수 Gate·독립 VERIFY·REVIEW·리뷰 수정 루프를 우회하지 않는다. 문서형/사용자 정의 Profile만 마지막 실행 단계(`ANALYZE`, `PLAN`, `IMPLEMENT`, `VERIFY`, `REVIEW`, `COMPLETE`)를 선택할 수 있다. 중간 단계만 독립적으로 건너뛰는 것은 지원하지 않는다. `SESSION`은 항상 실행한다.
- `stop_after_stage=PLAN`이면 `SESSION → ANALYZE → PLAN`까지만 실행하고 정확히 멈춘다. PLAN 문서 및 TASK 증거를 남기고 `STOPPED_AFTER_PLAN`으로 기록한다. IMPLEMENT·VERIFY·REVIEW·Gate 2·COMPLETE를 실행하거나 실행했다고 표시하지 않는다. Gate 1은 아직 도달하지 않았으므로 승인 생략(`SKIPPED_BY_PROFILE_POLICY`)과 구분하여 `NOT_REACHED_BY_STAGE_SCOPE`로 기록한다.
- 부분 범위 종료 상태는 `COMPLETED`가 아니며, `docs/tasks/completed/` 아카이브, 품질 통과 주장, 승인 기록 가장, 완료 후 Improver 호출을 금지한다. 개발·배포·Git commit/push/merge는 별도 승인·검증을 따른다. 종료 지점 이후 검증·리뷰를 수행하지 않은 산출물은 **검증 전 초안**이다.
- 비활성 단계의 Skill Tree 정의는 보존하되 실행하지 않으며, 비활성 단계의 스킬 설치 여부로 새 TASK 시작을 차단하지 않는다. 범위를 `COMPLETE`로 다시 확대할 때 해당 단계 필수 스킬·역할·Gate 검증을 다시 시행한다. 진행 중 TASK가 있으면 범위 변경 차단한다.
- 이 예외는 Profile별 문서 초안 작성 범위에만 해당한다. 전체 개발 완료로 주장되는 작업에는 모든 필수 승인·독립 검증·리뷰가 필요하다. 관리 웹 콘솔/CLI 자체는 TASK 상태 엔진이 아니므로 실제 수행 증거는 Coordinator가 보존해야 한다.


### 부분 실행 TASK 인계 및 프로필 전환 (v0.5.4)

- `execution_scope.full_completion_allowed=false`에서 설정 종료 단계에 도달하면 Coordinator는 실제 작업·산출물 파일과 실행 종료 근거를 남기고 `progress.md`에 `STOPPED_AFTER_<STAGE>`를 기록한다. 사용자에게 후속 검증·리뷰가 수행되지 않았음을 명확히 알린다.
- 현재 TASK 폴더를 `docs/tasks/active/<TASK-ID>/`에서 `docs/tasks/handoffs/<TASK-ID>/`로 **디렉터리 전체를 충돌 없이 이동**한다. 이동 대상이 있거나 검사가 불완전하면 BLOCKED로 남기고 `active/`를 지우거나 프로필 잠금을 우회하지 않는다. `completed/`로 옮기거나 COMPLETED 기록, 승인 완료·검증 PASS로 가장하지 않는다.
- `docs/tasks/handoffs/`는 문서 초안 보관이며 완료 건수에 포함하지 않는다. 새 세션에서 `active/`, `handoffs/`, `completed/`, 레거시 경로를 확인하고 개발 TASK 이름 중복 탐색에도 포함한다. 후속 개발 작업은 초안을 참조하지만 **새 Development TASK로 별도 진행**하며 기존 승인·검증·리뷰·완료 게이트를 전부 따른다.
- 인계 보관 완료 후 active TASK가 없을 때만 새 Profile 활성화를 허용한다. AgentFlow 웹 콘솔은 TASK 상태 변경을 자동 실행하지 않으며 Coordinator의 실제 파일 조작·증거 기록이 필요하다.

- `stop_after_stage=GATE1`은 PLAN 작성 후 사용자 계획 승인을 수행하고 `STOPPED_AFTER_GATE1`로 인계 종료한다. IMPLEMENT·VERIFY·REVIEW·GATE2·COMPLETE는 수행하지 않는다. `GATE1` 비활성화 시 PLAN 종료로 축소한다.
- `stop_after_stage=GATE2`는 REVIEW 이후 Gate 2까지 수행하고 `STOPPED_AFTER_GATE2`로 인계 종료한다. COMPLETE 단계는 수행하지 않으며 전체 COMPLETED로 표시하지 않는다.


## v0.5.8 — 계획 완료와 실제 구현 완료 분리 (이전 인계/아카이브 문구보다 우선)

- `task-planning` 기본 단계: ANALYZE → PLAN → VERIFY → COMPLETE. PLAN은 기존 `docs/tasks/active/<TASK-ID>/`에 `spec.md`, `plan.md`를 기록한다. VERIFY는 요구사항·AC·의존성·검증 방법을 실제 점검하고 불합격이면 PLAN 수정 후 다시 VERIFY한다.
- 계획 검증 보고서는 같은 TASK에 `plan-verification.json`으로 기록한다. 형식: `{"task_id":"LOGIN-001-login","result":"PASS","verifier":"verifier","checks":["requirements","acceptance_criteria","dependencies","verification_plan"],"sha256":{"spec.md":"<sha256>","plan.md":"<sha256>"}}`. 실제 검증 없이 PASS 보고서를 만들어서는 안 된다.
- 계획 VERIFY PASS 및 COMPLETE 이후 Coordinator는 `python3 agentflow_console.py task-ready <TASK-ID>`를 실행한다. 해시·문서·필수 검사 기록 확인 성공 시 `task-state.json`의 상태를 `PLAN_READY`로 설정한다. **폴더는 `active/`에 그대로 유지**한다. `completed/`, `handoffs/`로 이동하지 않는다. 계획 완료와 구현 완료를 혼동하지 않는다. 해당 명령은 증거의 파일 구조 및 무결성을 검증하지만 실제 네이티브 verifier 호출의 진위를 보증하지 않는다.
- `PLAN_READY`인 TASK만 active TASK 잠금에서 제외하므로 Profile을 `development`로 전환할 수 있다. PLAN_DRAFT, 레거시 상태 불명, 작업 진행 중인 TASK는 전환을 차단한다.
- Development SESSION은 `python3 agentflow_console.py status`의 `plan_ready_tasks`와 `docs/tasks/active/*/task-state.json`을 확인한다. 사용자가 지정한 TASK만 대상으로 `python3 agentflow_console.py task-begin <TASK-ID>` 실행한다. 이는 **같은 작업 폴더**를 `WAITING_PLAN_APPROVAL`로 잠그며 기존 계획·검증 해시를 재검사한다. 이후 GATE1에서 사용자 승인이 나기 전 IMPLEMENT를 실행하지 않는다.
- Development의 실제 구현·검증·리뷰·최종 사용자 승인 이후에만 `COMPLETED`로 기록하고 기존 active→completed 전체 폴더 이동 규칙을 적용한다. PLAN_READY 단계를 COMPLETE했다고 개발 완료로 주장하거나 Improver를 실행하지 않는다.
- UI/CLI의 `contract.execution_scope`에 planning 전용 `plan_ready_allowed_after_evidence`, `task_destination`을 표시한다. 개발/설계 특화 Profile의 기존 정책과 충돌할 경우 선택된 작업 종류에 대한 추가 승인 및 검증을 우선한다.
- 위 명령은 작업 증거·상태에 대한 **국소적 안전 전환**이며 에이전트 단계 실행, 사용자 승인, 작업 검증을 자동으로 수행하지 않는다. 실패하면 원본 폴더·데이터를 보존한다.

## v0.7.1 session/TASK Profile contract
Refer to the v0.7.1 section in the native Coordinator instructions. New TASKs resolve `contract --session <SESSION-ID>` (or `AGENTFLOW_SESSION`) and immediately run `task-context <TASK-ID> --pin --session <SESSION-ID>` before implementation or planning. Continuing TASKs use `task-context <TASK-ID>`, not `contract`. Web console project-default changes never change running TASKs. Missing session identity MUST NOT be described as verified automatic native session binding.


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


Profile ID 호환성 및 5개 역할은 `docs/workflow/PROFILE-CONTRACTS.md`를 따른다.
