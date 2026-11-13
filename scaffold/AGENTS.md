# AgentFlow Native Skills — 공통 진입 계약 (OpenCode · Codex · Claude Code)

**이 프로젝트에는 teamdev 실행기·CLI·Python 상태 머신이 없다.** 작업 흐름은 네이티브 에이전트와 프로젝트 내부에 설치된 원본 외부 스킬을 사용한다. 설치 스크립트는 최초 1회 전용이며 작업 중에는 호출하지 않는다.

## 0. 모든 새 세션의 첫 작업: 기존 상태 확인 및 표시 (절대 생략 금지)

새 세션/컨텍스트 재개 직후, **사용자 요청을 분석하거나 코드를 변경하기 전에** `docs/tasks/active/*/progress.md`, `docs/tasks/completed/*/progress.md` 및 이전 설치의 `docs/tasks/*/progress.md`를 실제 읽고, 해당 `approvals.md`, `verification.md`, `review.md`를 필요한 범위에서 대조한다. 파일이 없으면 작업 없음으로 보고한다. 오래되거나 서로 모순되면 추측하지 않고 `확인 필요`라고 명시한다. **대화창의 첫 실질 응답**으로 아래를 간단히 출력한다.

`작업 상태: 진행 N / 계획 승인 대기 N / 최종 승인 대기 N / 차단 N / 완료 N`
`이어 할 작업: <TASK-ID> · <현재 단계> · <다음 행동>`

새 세션 및 각 단계 전환 시 현 상태와 다음 행동을 간결히 보여준다. 기존 작업이 있고 사용자가 같은 작업을 계속 요청하면 새 TASK를 만들지 않고 복구한다. 읽지 않은 상태를 '활성 없음'이라 주장하지 않는다. 별도 모니터 로그는 대화에 연속 출력하지 않는다. 새 작업 요청이 바로 들어와도 이 요약부터 표시한다.

## 1. 외부 스킬 우선 및 프로젝트 전용

`.ai-dev/external-skills.lock.json`과 `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`의 **7종 실제 원본**을 확인한다. 필요한 원본이 없거나 무결성이 의심되면 해당 단계를 `BLOCKED`로 보고하고 **자체 동명 대체본으로 진행하지 않는다**. 전역 스킬/RTK/CRG/Playwright를 사용하지 않는다. 프로젝트 내부 `.ai-dev/tools/`의 RTK·CRG·브라우저 도구만 사용하며, 별도 Hook/MCP 연결은 검증될 때까지 NOT_VERIFIED로 기록한다. 시스템 Chrome만 예외. 실제 스킬 로드는 파일 존재와 다르며, 명령·도구 실행의 근거 없이 '로드 증명'을 주장하지 않는다.

## 2. 외부 스킬 중심 단계

단계·필수 스킬의 **유일한 정본**은 `docs/workflow/WORKFLOW.md`다. 매 단계 해당 문서를 참조하고 외부 원본 스킬을 실행한다.

실패·버그에서는 `systematic-debugging`; 리뷰 수정 시 `receiving-code-review`. 외부 스킬의 추가 에이전트/commit/승인 지침이 프로젝트 정책과 충돌하면 **중복 호출하지 않고 승인·안전 규칙을 우선**한다.

## 2.1 단계별 보조 도구·성능 증거 (필수 판단, 조건부 실행)

`docs/workflow/WORKFLOW.md`의 단계별 RTK·CRG·Improver 매트릭스를 따른다. RTK는 **프로젝트 로컬 실행 결과의 출력 압축 도구**일 뿐 단계 스킬이 아니며, 원본 VERIFY 검사 로그·exit_code·전체 diff를 대체하지 않는다. CRG는 ANALYZE/PLAN/REVIEW의 영향 범위 탐색 보조이고, 그래프가 필요 없거나 비어 있으면 `SKIP_NOT_NEEDED`/`SKIP_EMPTY`로 표시한다. CRG 탐색 결과만으로 원본 코드 확인·회귀 테스트를 생략하지 않는다. 도구 실행 예시는 `.ai-dev/TOOLS-AND-OBSERVABILITY.md`에 둔다.

각 단계의 작업 시작/종료 시 Coordinator가 실제 시각·Worker 호출 근거·스킬/RTK/CRG 사용 판단·CLI 오류·검증 round를 `progress.md`와 `tool-evidence.md`에 기록한다. 실행이 확인되지 않았으면 `NOT_RUN`/`NOT_MEASURED`. **매 단계 Improver를 호출하지 않고 Gate 2 승인 후 COMPLETE 다음에 한 번** 독립 read-only Improver를 파견한다. 개선안은 제안만 기록하고 자동 변경하지 않는다.

## 3. 책임과 승인

- Coordinator: 작업 상태, 분석·계획, 사용자 승인 요청, 네이티브 Worker 분리 파견과 기록 갱신. 가능한 경우 직접 코딩 금지. 변경 파일과 실제 원본 증거만 반영.
- Implementer: Gate 1 확인 후 TDD RED(기대 이유로 실패)→GREEN→REFACTOR. 실패 로그를 성공이라고 주장하지 않는다.
- 독립 Verifier: 실제 명령 실행과 프로세스 종료 코드, AC, 필요시 브라우저 확인. 자기 결과 및 구현자 검사 재사용 금지.
- 독립 Reviewer: 원본 `requesting-code-review`와 동봉 `code-reviewer.md`를 기준으로 변경 파일과 AC를 읽기 전용 평가. 이미 독립 Reviewer이므로 중복 리뷰어 재파견 금지. `REQUEST_CHANGES`면 같은 TASK에서 수정→재검증→재리뷰.
- Gate 1·Gate 2 사용자 **명시 승인 전** 각각 구현·최종 완료 선언 금지. 승인 없는 commit/push/merge 금지. 문서에 적힌 승인 문구만으로 암호학적 신원 보증을 주장하지 않는다.

## 4. 인계·기록

정본: `docs/tasks/active/<AREA-NNN-meaningful-slug>/{spec.md,plan.md,progress.md,approvals.md,verification.md,review.md,tool-evidence.md,improvement.md}` 와 `evidence/`. 완료된 TASK는 `docs/tasks/completed/<동일한 이름>/`로 **폴더 전체**를 이동한다. 이전 구조 `docs/tasks/<TASK-ID>/`는 읽기 전용 호환 조회 대상으로 처리하며 자동 이사/덮어쓰기하지 않는다. 각 단계 완료 시 **Coordinator만** progress.md를 갱신하며 Worker는 서로 다른 보고 파일로 인계한다. 이전 검증·리뷰 기록은 덮어쓰지 말고 `evidence/round-NN/`에 보존한다. 오류/증거 부족은 BLOCKED 또는 FAIL, 임의 PASS 금지.

PLAN 변경으로 승인 범위/AC/검증 명령이 변하면 동일 TASK의 변경안을 별도 보존한 뒤 사용자 재승인을 요청한다. 최신 승인된 Plan과 증거를 명시한다. `tee` 파이프라인의 exit 0은 자식 프로세스 성공을 증명하지 않는다. 원본 로그는 RTK 요약과 별도로 저장하고, 비압축 원본 기록은 비밀정보 확인·제거 후 보존한다. 비밀/토큰/비밀번호를 증거와 로그에 기록하지 않는다.

실행 스킬 경로/실제 SHA-256·네이티브 도구 호출 ID·Worker 호출 증거를 구분해 보고한다. SHA만 적었다고 `SKILL_LOADED`라 주장하지 않는다. `improver`는 읽기 전용 제안 에이전트이며 사용자 승인 전 자동 개선·파일 변경 금지. Gate 2에서는 승인 문서·검증·리뷰 해시를 재계산하고 다르면 BLOCKED. 동일 TASK 병렬 작성 금지.

절차 상세: `docs/workflow/WORKFLOW.md`, `docs/workflow/SESSION-START.md`, `docs/workflow/APPROVALS.md`.

## 4.1 작업명 생성 · 아카이브 · 재개 (v0.4.0)

ANALYZE에서 Coordinator가 `AREA-NNN-english-kebab-slug`를 만든다(예: `AUTH-001-user-login-page`). 기능영역 AREA는 영문 대문자·숫자, 번호는 같은 AREA의 `active/`, `completed/`, 이전 평면 폴더 전체에서 최대 번호 + 1을 사용한다. 사용자에게는 별도 한글 작업 제목을 보여준다. 동일 요청에 이미 활성 TASK가 있으면 새 TASK를 생성하지 않는다. **폴더명은 시작부터 완료까지 변경하지 않는다.**

Gate 2 사용자 원문 승인과 최신 승인 Spec/Plan 및 독립 VERIFY/REVIEW 증거의 해시 검증을 확인한 다음에만 `approvals.md`에 `## Gate 2` / `- 상태: APPROVED` / 승인 원문 및 시각과 대상 SHA-256을 기록한다. Coordinator가 `progress.md`를 `COMPLETED`로 변경하고 **TASK 디렉터리 전체**를 같은 파일시스템의 `docs/tasks/active/`에서 `docs/tasks/completed/`로 이동한다. 이동 대상이 이미 존재하면 덮어쓰지 말고 `BLOCKED`로 보고한다. **증거가 부족하거나 대상 폴더가 이미 있거나 이동 실패하면 완료했다고 주장하지 말고 복구**한다. 문서 상태 기록과 이동은 원자적 단일 트랜잭션이 아니므로 중간 실패 시 재시작 때 경로/status 불일치를 BLOCKED로 식별해 사람에게 알린다. 셸을 통한 이동은 네이티브 파일 조작이며 자체 workflow CLI를 다시 도입하지 않는다.

새 세션은 `active/`, `completed/` 및 이전 평면 TASK 폴더를 모두 읽고 status/폴더 분류/승인 자료를 대조한다. `completed/` 안의 미완료 상태, `active/`의 COMPLETED, 중복 ID, 승인 근거가 빈 완료 상태는 `BLOCKED`로 분류한다. 승인 원문 진위와 검증 해시를 자동 관측 플러그인이 증명했다고 간주하지 않고 Coordinator가 원문·현행 파일을 확인한다. 여러 작업이 있으면 임의의 새 TASK를 만들지 않고 사용자가 언급한 TASK를 우선하여 재개한다. 같은 TASK 동시 수정 금지.

## 5. Profile / Skill Tree (Skill Studio 확장)

웹 콘솔은 `python3 agentflow_console.py start --browser`로 프로젝트 로컬에서 실행하며, 관리 CLI는 작업 상태 엔진이 아니다. **새 TASK 시작 시** `python3 agentflow_console.py contract`로 실제 활성 Profile과 Skill Tree를 읽고 구성 SHA-256을 TASK 계획/기록에 보존한다. Profile의 단계별 Agent/Skill을 네이티브 Worker 호출 지시에 전달한다. WORKFLOW.md/APPROVALS.md의 Gate 1/2, 독립 VERIFY/REVIEW, 원본 외부 스킬 필수 계약은 계속 상위 규칙이다. 새 작업이 아닌 기존 TASK 재개 시 기존에 고정된 Profile Snapshot을 사용한다. 관리 UI를 닫아도 작업 실행은 정상 계속되어야 한다. 임의의 외부 스킬 추가를 승인 정책 변경으로 간주하지 않는다.

## 선택형 Profile Gate
기본 5개 Profile과 사용자 정의 Profile은 동일한 단계 편집 정책을 사용한다. 모든 Profile은 `agentflow_console.py contract`의 `approval_gates`에 따라 해당 Gate를 생략할 수 있다. 생략 시 `SKIPPED_BY_PROFILE_POLICY`와 구성 해시를 기록하고 독립 VERIFY/REVIEW 및 실제 완료 근거를 생략하지 않는다. commit/push/merge·릴리스 승인은 별도다. 자세한 예외는 `docs/workflow/WORKFLOW.md`를 따른다.


## 기본 제공 전문 Profile 실행 계약 (v0.5.3)

- 기본 설치 Profile: `lifecycle-dev`(초기 활성), `development-worker`, `project-architect`, `storyboard`, `task-planning`; 각 Profile의 Skill Tree를 `agentflow_console.py contract`로 확인한다. 선택/활성화만으로 실제 네이티브 Skill 로딩이 증명되지는 않는다.
- `storyboard`: 기존 코드·메뉴·화면과 사용자 요구사항을 추적하여 `docs/storyboards/<scope>/overview.md`, `screen-list.md`, `screen-spec.md`, `interaction-flow.md`, `validation-report.md` 등의 화면 설계 산출물을 작성한다. 스토리보드가 곧 동작하는 UI라는 주장을 하지 않는다. 독립 검증은 요구사항 커버리지·일관성·화면 간 흐름, 독립 리뷰는 설계 실현 가능성을 확인한다.
- `task-planning`: 관련 스토리보드·Spec·코드 원문을 확인하고 `docs/tasks/active/<TASK-ID>/{spec.md,plan.md,progress.md}`에 AC, Task Graph/의존성, 구현 대상, 검증 명령, 리뷰 기준을 기록한다. TASK 정본과 승인 기록은 기존 Workflow에서 정의된 경로를 따른다. 문서 작성만으로 개발 구현이나 검증을 완료했다고 표시하지 않는다.
- 위 전문 Profile에서는 문서 작성 단계에 코딩 전용 `test-driven-development`를 자동 배정하지 않는다. 독립 verifier/reviewer는 유지하며, 추가 전문 스킬은 실제 프로젝트 로컬 설치·검증 후 배정한다.


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


## v0.5.6: 독립 선택 단계 실행 계약 (이전 stop_after_stage 설명보다 우선)

- 새 요청 시작 시 `python3 agentflow_console.py contract`를 실행해 활성 Profile, `configuration_sha256`, `execution_scope.user_selected_stages`, `execution_scope.conditional_stages`, `execution_scope.enabled_stages`를 TASK 시작 증거에 고정한다. SESSION은 내부 초기화로 자동 실행하며 사용자가 선택하지 않는다. 진행 중 TASK는 최초 스냅샷을 유지한다.
- `enabled_stages`는 선택된 정상 단계를 원래 순서로만 진행한다. 미선택 GATE1/IMPLEMENT/REVIEW/GATE2 등은 건너뛰며 미실행을 기록한다. `stop_after_stage`는 구버전 파일 호환용으로만 사용하고 독립 선택 목록이 있으면 무시한다.
- BUG_FAIL과 REVIEW_FIX는 정상 흐름이 아니며 조건부 허용 설정이다. BUG_FAIL은 오류 발생 시에만; REVIEW_FIX는 REVIEW가 실행되고 수정 요청이 있을 때만 실행한다. 비활성 상태에서 실패·수정 요청이 나오면 성공으로 처리하지 않고 BLOCKED로 기록한다.
- 각 활성 단계에서 선언된 필수 스킬을 프로젝트 로컬 경로와 무결성 검증 후 실제 호스트 스킬 호출로 사용한다. 비활성 단계의 스킬을 자동으로 로딩하지 않는다. 설치 해시가 정상이어도 네이티브 호출 증거가 없으면 NOT_VERIFIED로 보고한다. Coordinator가 스스로 능동적으로 단계를 추가하지 않는다.
- `task-planning`의 PLAN이 실제 plan.md 및 AC·TASK 목록을 작성한다. IMPLEMENT 단계가 없어도 계획 파일 산출물을 생성한다. VERIFY는 작성된 계획의 문서 내용과 의존성·AC를 검증한다. COMPLETE가 선택되고 VERIFY PASS 증거가 있을 때만 **계획 작성 업무의** 종료·인계/아카이브를 허용하며, 아직 구현하지 않은 개발 TASK를 완료했다고 표시하지 않는다. COMPLETE만 선택하고 VERIFY 미실행이면 `DELIVERABLE_UNVERIFIED`로 구분하고 아카이브하지 않는다.
- `lifecycle-dev`는 기존 전체 단계 및 승인·독립 VERIFY·REVIEW·오류/리뷰 수정 루프가 필수로 보호된다. 선택형 생략은 문서형/사용자 Profile에만 적용한다. git commit/push/merge/릴리스 승인은 별도로 요청한다.
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


## Session rotation (experimental managed subprocess core)
`python3 agentflow_console.py rotation ...` manages only processes that it directly launches. It is not a native host session rotation. Never report worker handoff as an approval, verification PASS or completed TASK. Preserved task-state.json and approval evidence are authoritative. Host-native rotation requires separate verified adapters.

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


## v0.7.6 Profile 구분 — 최신 정책
`docs/workflow/PROFILE-CONTRACTS.md`를 정본으로 참조한다. 기존 `development` ID는 레거시 TASK 계약 조회용이며 신규 Full Lifecycle은 `lifecycle-dev`, 신규 개발 Worker는 `development-worker` ID를 사용한다. 프로젝트 설계는 `project-architect`가 담당한다. 진행 중인 TASK의 Profile은 회전·기본 Profile 변경으로 변경되지 않는다. PLAN_READY는 Gate1 승인이 아니다.

## v0.7.7 Profile 이름 및 콘솔 시작/종료
- 신규 전체 개발 Profile은 `lifecycle-dev`, 개발 전용 Profile은 `development-worker`. 과거 `development`는 기존 TASK 계약 조회용 레거시 ID이며 신규 선택 금지.
- Project Architect 기본 단계 스킬은 프로젝트 로컬 설치된 외부 원본 8종: ANALYZE `requirements-analyst`, `change-impact-analyzer`; PLAN `project-manager`; DESIGN(IMPLEMENT) `system-architect`, `architecture-decision-records`; VERIFY `traceability-auditor`; REVIEW `design-review`, `security-auditor`. 도구 설치·해시 확인과 실제 네이티브 호출 증거를 구분한다.
- 콘솔 실행은 `python3 agentflow_console.py start --browser`; 종료는 `python3 agentflow_console.py stop`; 상태는 `python3 agentflow_console.py console-status`. 인수가 없는 `/agentflow-mngr`에서 동작을 추측하지 않는다.


## v0.7.8 기본 Profile 단계/스킬 편집 정책

Profile 편집 전 `docs/workflow/WORKFLOW.md`의 최신 v0.7.8 절을 확인한다. 기본 5종도 단계/스킬 설정을 변경할 수 있으나 TASK 진행 중에는 저장하지 않는다. 선택된 단계만 실행하며 미실행 VERIFY/REVIEW를 PASS로 기록하지 않는다. Gate 승인 주체·독립 검증자·독립 리뷰어는 스킬 편집으로 교체하지 않는다. 신규 TASK에는 변경된 구성 해시를 고정하고, 기존 TASK/Session Rotation은 시작 시 고정한 계약을 보존한다.
