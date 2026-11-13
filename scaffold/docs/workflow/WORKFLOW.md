# AgentFlow Native Skills — 외부 스킬 주도 워크플로 정본

**이 문서가 단계·스킬·도구 선택의 유일한 정본이다.** **유일한 진행 순서:** 사용자 요청 → ANALYZE → PLAN → Gate 1(사용자 계획 승인) → IMPLEMENT → VERIFY → REVIEW → Gate 2(사용자 최종 승인) → COMPLETE.

| 단계 | 책임 원본 외부 스킬 (프로젝트 내부) | RTK (출력 보조) | CRG (탐색 보조) | Improver 증거 수집 | 주체 |
| --- | --- | --- | --- | --- | --- |
| SESSION | 없음; 기존 상태 읽기 | 필요시 출력 축약 | 기존 그래프 최신성만 판단 | 미처리 개선 제안 확인 | Coordinator |
| ANALYZE | `brainstorming` | 긴 조사 출력 요약 | 관련 symbol/caller/dependency (필요 시) | 반복 오류·소요 시간 기록 | Coordinator |
| PLAN | `writing-plans` | 근거 검색 요약 | 영향 파일·테스트 후보 확인 (필요 시) | 병목 후보 별도 기록 | Coordinator |
| Gate 1 | 없음: **사용자 명시 승인** | 사용하지 않음 | 사용하지 않음 | 사용하지 않음 | 사용자 |
| IMPLEMENT | `test-driven-development` | 빌드·개발 출력 보조 | 다중 파일 영향 시만 | RED/GREEN/REFACTOR 실행 시각·오류 수집 | Implementer → Coordinator |
| BUG/FAIL | `systematic-debugging` (조건부) | 오류 원본을 보존한 뒤 가독성 향상 | 호출·의존성 경로 원인 추적 | 재현·원인·재발 패턴 기록 | 해당 단계 Worker |
| VERIFY | `verification-before-completion` | **원본 비압축 검사 로그를 절대 대체하지 않음** | 영향 테스트 후보 보조, 필수 테스트 생략 금지 | 실제 exit·AC·브라우저 결과·시간 수집 | 독립 Verifier |
| REVIEW | `requesting-code-review` + 원본 `code-reviewer.md` | 전체 원본 diff 유지, 탐색 출력만 축약 | blast radius/caller/dependent 확인 (필요 시) | 반복 Finding 및 미검증 수집 | 독립 Reviewer |
| REVIEW 수정 | `receiving-code-review` + 필요시 TDD/디버깅 | 오류 로그 축약 보조 | 수정 영향 범위 확인 | round·수정·재작업 시간 기록 | Implementer → 재VERIFY → 재REVIEW |
| Gate 2 | 없음: **사용자 명시 승인** | 사용하지 않음 | 사용하지 않음 | 사용하지 않음 | 사용자 |
| COMPLETE | 없음; 승인 후 결과 보존 | 사용하지 않음 | 사용하지 않음 | **완료 후 읽기 전용 Improver 1회 분석** | Coordinator + Improver |

## 책임 경계

- **판정 주체**: 실제 외부 원본 스킬은 작업 방법, Verifier는 실제 테스트 결과, Reviewer는 Finding을 판단한다. **Gate 1/2는 사용자만 승인**한다. CRG·RTK·Improver는 VERIFY PASS/REVIEW PASS/승인을 대신하지 않는다.
- **도구 위치**: `./.ai-dev/tools/rtk/bin/rtk`, `./.ai-dev/tools/crg-venv/bin/code-review-graph`, `./.ai-dev/tools/browser/`만 사용. 시스템 Chrome만 예외. 전역 바이너리·전역 Hook/MCP 초기화·전역 스킬 자동 대체 금지. `install.py`는 일회성 설치 전용이고 `teamdev`나 자체 워크플로 CLI가 아니다.
- **RTK 적용**: 큰 탐색·개발 출력을 읽을 때만 프로젝트 내 명령으로 명시적 호출. 원본 빌드·테스트 출력을 보존해야 하는 검증에는 RTK를 끼워 넣지 않고 원래 명령을 직접 실행한다. RTK 통계는 실측되지 않았으면 `NOT_MEASURED`.
- **CRG 적용**: 탐색할 소스가 있거나 교차 파일 영향이 클 때만 사용. graph가 없으면 `SKIP_EMPTY`, 단순 작업에 불필요하면 `SKIP_NOT_NEEDED`; 필요하다면 내부 CRG CLI의 지원 옵션을 먼저 확인하고 build 후 최신성을 점검한다. 실패하면 `CRG_BLOCKED`/native source search fallback을 명시하되 해당 단계 전체를 자동 PASS하지 않는다. 그래프만으로 테스트·소스 읽기를 생략하지 않는다.
- **Improver 적용**: 매 단계 별도 Worker를 호출하지 않는다. Coordinator가 이벤트 발생 시점에 가벼운 증거(시각, 실제 스킬/Worker, CRG 판단, RTK 사용, CLI 오류, 검증 round)를 기록한다. **Gate 2 승인 → COMPLETE 후** 실제 근거가 있는 경우 독립 improver 한 번 실행해 개선 후보를 `improvement.md`에 보존한다. 파견 실패는 `IMPROVER_NOT_RUN`으로 보고하며 이미 승인된 제품 완료를 취소하지 않는다. 개선안 구현은 사용자 승인받은 별도 TASK.

## 실제 스킬 원본·호출 근거

필수 스킬의 `SKILL.md`는 프로젝트 내부 `.opencode/skills`, `.claude/skills`, `.agents/skills`에서 읽는다. `.ai-dev/external-skills.lock.json`의 SHA-256과 대조한다. 파일 존재/해시 일치 = `INSTALL_READY`, Worker 자기 신고 = `SELF_REPORTED`, 네이티브 스킬 도구 호출 관측 = `TOOL_CALL_OBSERVED`; 이것만으로 출처가 확정되거나 모델 지침을 따랐다는 뜻은 아니다. 전역 동명 스킬과 출처가 충돌하면 `SKILL_SOURCE_NOT_VERIFIED`로 보고하고 조용히 대체하지 않는다.

Worker 반환에는 TASK/role, 프로젝트 내 스킬 경로, SHA-256, 네이티브 호출 ID(있을 때), 명령·실제 **자식 프로세스** 종료 코드, 로그·AC·소요 시간 출처가 있어야 한다. 미확인 항목은 `NOT_VERIFIED`/`NOT_RUN`/`NOT_MEASURED`로 기록한다. 인증·승인 정책과 충돌하는 외부 스킬의 자동 commit/추가 Worker 지시는 적용하지 않는다.

## 독립 Worker / 상태와 승인

OpenCode/Claude/Codex 네이티브 implementer/verifier/reviewer를 분리 파견한다. Reviewer는 이미 파견된 본인이 원본 `requesting-code-review`의 `code-reviewer.md` 평가 지침을 사용하며 추가 Reviewer를 중복 파견하지 않는다. 호스트에서 독립 Worker를 실제 파견할 수 없으면 `BLOCKED`를 표시하며 자체 리뷰를 독립 PASS라고 보고하지 않는다.

TASK 정본은 `docs/tasks/active/<AREA-NNN-descriptive-slug>/{spec.md,plan.md,progress.md,approvals.md,verification.md,review.md,tool-evidence.md,improvement.md}`이고 원본 증거는 `evidence/round-NN/`에 보관한다. **Coordinator 한 명만** progress/approval 및 보존된 보고서를 갱신한다. Worker는 결과를 반환하고, 필요시 `.ai-dev/run-evidence/<TASK-ID>/`에 임시 검사 로그를 둘 수 있다. Coordinator는 민감정보를 확인·제거한 뒤 원본 명령 출력이 축약되지 않은 증거를 보관한다. 기록이 없는 성공 주장은 금지한다.

Gate 1에서 사용자 승인 원문 및 승인된 Spec/Plan/AC/검증 명령 해시를 보존한다. 승인 범위가 변하면 동일 TASK의 Amend 제안 후 **재승인 전 구현 정지**. Verifier와 Reviewer는 최신 코드 변경분을 각각 실제로 검사하고, REQUEST_CHANGES이면 동일 TASK에서 수정 → **새 VERIFY → 새 REVIEW**. Gate 2 직전 승인 범위와 검증/리뷰 파일 해시 및 최신성, 실제 독립 Worker 근거를 재점검한 뒤 사용자에게 요청한다. Gate 2 승인 전 `COMPLETED` 기록 금지.

## 새 세션 / 시간 기록 / 실행 경계

새 세션 첫 응답과 단계 전환에서는 실제 `docs/tasks/active/*/progress.md`, `docs/tasks/completed/*/progress.md` 및 이전 구조 `docs/tasks/*/progress.md`를 확인해 진행·계획 승인 대기·최종 승인 대기·차단·완료 및 이어 할 TASK를 짧게 보여준다. Worker 시간은 모의·추정이 아니라 실제 시작/종료 이벤트로 기록하고, 검증 원본 명령·종료 코드는 RTK 압축 결과와 구별한다. 실패·테스트 누락·Browser NOT_RUN도 그대로 남긴다. 네이티브 호스트가 실질 승인/격리를 제공하지 않으면 문서 게이트만으로 보안을 보장할 수 없음을 공개한다.

프로젝트에는 `teamdev`·커스텀 워크플로 CLI·중앙 상태 머신이 없다. 테스트/빌드/RTK/CRG 등 프로젝트 도구 명령은 사용 가능하다. 세부 RTK/CRG 예시 및 관측 이벤트는 `.ai-dev/TOOLS-AND-OBSERVABILITY.md`, 세션 요약은 `docs/workflow/SESSION-START.md`, 승인 규칙은 `docs/workflow/APPROVALS.md`를 참고한다.

## v0.4.0: 의미 있는 작업 ID / 완료 보존

- 시작 시 `docs/workflow/SESSION-START.md`에 따라 active/completed/legacy 모두 검사하고 진행·계획 승인 대기·최종 승인 대기·차단·완료 및 다음 행동을 보여준다.
- Coordinator는 ANALYZE에서 `AREA-NNN-english-kebab-slug`로 최초 명명하고 두 폴더와 이전 TASK에서 동일 AREA 최대 순번을 확인한다. 기존 ACTIVE 작업이 동일 요청에 대응하면 새 작업을 만들지 않는다.
- PLAN은 `active/<작업명>/spec.md`, `plan.md`, `progress.md` 등에 보관한다. 모든 상태 변경은 Coordinator만 하며 단계 전환 요약은 대화창에 간단히 출력한다.
- Gate 2 이후 **승인 원문/대상 SHA-256 재계산 및 독립 검증·리뷰 확인 → 승인 기록 → progress=COMPLETED → 전체 TASK 폴더 active→completed 이동** 순서로 처리한다. 동일 경로 존재/불완전 상태/이동 실패 시 멈추고 BLOCKED로 알린다. 데이터 덮어쓰기 및 분실 금지.
- 완료된 TASK는 기존 이름 그대로 `completed/`에 보존하며 그 안의 Spec·Plan·기존 round별 증거를 모두 유지한다. Improver는 완료 폴더 기록을 읽어 제안만 기록하며 제품을 변경하지 않는다.
- 이전 `docs/tasks/<TASK-ID>` 구조는 새 세션에서 계속 읽지만 자동으로 이동하지 않는다. 과거 완료 기록에 원문 Gate 2 근거가 없으면 `BLOCKED`로 표시하여 수동 확인 후만 정리한다.
- 독립 Worker의 네이티브 E2E와 사람 승인 강제력은 프로젝트별 호스트에서 확인해야 하며, 문서만으로 보안을 보장하지 않는다.

## Profile / Skill Tree 관리 계약 (Skill Studio 확장)

신규 프로젝트는 `lifecycle-dev`, `development-worker`, `project-architect`, `storyboard`, `task-planning`의 기본 Profile 5개와 각 Skill Tree를 설치한다. 설치 직후 활성 Profile은 `lifecycle-dev`이다. 기존 `development` ID는 레거시 실행 계약 조회를 위해서만 유지한다. 기본 5개 Profile 모두 단계·스킬 설정에 동일한 UI와 서버 검증 규칙을 적용한다. 각 단계 ON/OFF 선택은 사용자 지정대로 저장하며 연관 단계를 자동으로 바꾸지 않는다. 실행 조건이 충족되지 않으면 원인·필요 증거를 상세히 안내한다. 이 파일은 **동적으로 배정할 스킬의 선언**이고 이 WORKFLOW.md와 APPROVALS.md의 필수 게이트/역할/순서를 교체하거나 삭제하지 않는다. 기존 필수 스킬 7종과 Gate1/2, 독립 VERIFY/REVIEW, REVIEW 수정 루프, 완료 후 Improver는 동일하게 유지한다.

**새 TASK 시작 전** Coordinator는 `python3 agentflow_console.py contract` (프로젝트 루트에서)를 실행하여 활성 Profile, 단계별 Worker와 스킬, 구성 해시를 확인하고 `docs/tasks/active/<TASK>/`의 계획/진행 기록에 구성 해시·Profile ID·Skill Tree ID를 고정한다. 이미 시작된 TASK의 Profile을 소급 변경하지 않는다. 단순 구성 확인은 네이티브 worker/skill 실제 실행 증거가 아니다. 각 단계의 Worker에게 현재 TASK에 고정된 단계별 `skills` 목록(필수/조건부)과 로컬 skill 경로를 명시적으로 인계하고 해당 SKILL.md를 네이티브 스킬 툴로 사용하도록 요청한다. `python3 agentflow_console.py`는 관리 인터페이스이며 **작업 상태 전환 CLI가 아니다.** `console open`이라고 하면 `python3 agentflow_console.py start --browser`를 사용한다. 검증되지 않은 동적 스킬 발견 시 BLOCKED 또는 NOT_VERIFIED로 보고한다.

Profile 활성화는 active TASK가 없을 때만 허용된다. 관리 CLI/웹에서 active TASK가 확인되면 변경하지 않는다. CLI나 웹에서 표시한 `HASH_VERIFIED`를 네이티브 스킬 로딩 또는 지침 준수 PASS로 사용하지 않는다. `lifecycle-dev`에서도 단계별 스킬 구성을 수정할 수 있지만 Gate 사용자 승인 주체 및 독립 VERIFY/REVIEW 담당 Agent는 변경할 수 없다. 다른 Profile은 작업 목적에 따른 추가 스킬 구성일 뿐, 구현 TASK의 기본 승인/검증 정책 우회 수단이 아니다.

## 선택형 사용자 승인 Gate (프로필별 확장)

기본 5개 Profile과 사용자 정의 Profile 모두 동일한 단계 선택 규칙으로 Gate를 설정한다. Profile은 `approval_gates: {"GATE1": boolean, "GATE2": boolean}` 설정을 사용할 수 있다. 미설정된 기존 프로필은 두 Gate를 모두 사용하는 것으로 간주한다. 반드시 새 TASK 시작 때 `agentflow_console.py contract`의 `approval_gates` 및 `protected_workflow.skipped_gates`를 확인하고 TASK 증거에 Profile ID·세대·구성 해시·Gate 설정을 고정한다.

Gate 단계는 모든 Skill Tree에서 유지되지만 외부 Skill을 지정하지 않는다. 비활성화된 Gate는 실제 사용자 승인을 요청하지 않고 `SKIPPED_BY_PROFILE_POLICY`(해당 Gate, Profile ID, 구성 SHA-256, 이유)를 `approvals.md` 및 `progress.md`에 기록하고 다음 단계로 진행한다. 이 기록을 `APPROVED`로 가장하지 않는다. Gate 1이 생략돼도 분석·계획·Spec/AC·작업 범위 기록은 유지한다. Gate 2가 생략돼도 독립 VERIFY/REVIEW·결과 해시 대조·완료 증거·아카이브 충돌 방지·Improver 읽기 전용 원칙은 유지한다. 별도의 배포/commit/push/merge/정책 변경 승인은 생략되지 않는다. 기존 TASK에는 시작 시 고정된 Gate 설정을 소급 변경하지 않는다.

Gate 기본값은 Profile별로 다르며, 사용자가 활성화한 단계들의 조합이 승인 안전 정책을 위반하는 경우 저장을 거부한다. 수정 범위를 Profile로 국한하며 승인 무력화가 공통 정책 삭제로 간주되지 않도록 한다.


## Profile별 단계 실행 범위 (v0.5.4)

- 새 TASK 시작 시 반드시 `python3 agentflow_console.py contract`의 `execution_scope`를 읽고 Profile ID, `configuration_sha256`, `stop_after_stage`, 활성 단계를 TASK 기록에 고정한다. 과거 TASK에는 소급 적용하지 않는다.
- 모든 Profile의 기본 단계는 다르며, 유효한 단계 구성 변경은 신규 TASK에만 적용한다. 마지막 실행 단계(`ANALYZE`, `PLAN`, `IMPLEMENT`, `VERIFY`, `REVIEW`, `COMPLETE`)를 선택할 수 있다. 중간 단계만 독립적으로 건너뛰는 것은 지원하지 않는다. `SESSION`은 항상 실행한다.
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
- `development` ID는 과거 계약 조회만 허용하고, `lifecycle-dev`는 기본값으로 전체 단계를 제공하되 동일한 편집·검증 규칙을 적용한다. git commit/push/merge/릴리스 승인은 별도로 요청한다.
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


## 프로젝트 공통 docs 탐색 계약 (v0.7.4)
- 표준 분류와 정본은 `docs/README.md`를 따른다. 새 TASK 시작 전 관련 requirements/architecture/design/storyboards 문서를 필요한 범위에서 확인하고 참조 경로를 기록한다.
- TASK 정본 경로·승인·증거 규칙은 기존 `docs/tasks/`를 그대로 사용한다. 문서 부재를 성공이나 검증 완료로 처리하지 않는다.
- 프로젝트 기본 Profile이나 세션 기본 Profile 변경은 이미 고정된 TASK의 실행 계약을 변경하지 않는다. 서로 충돌하는 구버전 문구보다 최신 TASK 고정 계약을 적용한다.
- 관리 콘솔 호출: OpenCode `/agentflow-mngr`, Claude `/agentflow-mngr`, Codex `$agentflow-mngr` (또는 `/skills` 목록에서 선택). Codex의 동일한 이름의 사용자 정의 slash command 노출은 보장하지 않는다.


## v0.7.6 Profile 구분 — 최신 정책
`docs/workflow/PROFILE-CONTRACTS.md`를 정본으로 참조한다. 기존 `development` ID는 레거시 TASK 계약 조회용이며 신규 Full Lifecycle은 `lifecycle-dev`, 신규 개발 Worker는 `development-worker` ID를 사용한다. 프로젝트 설계는 `project-architect`가 담당한다. 진행 중인 TASK의 Profile은 회전·기본 Profile 변경으로 변경되지 않는다. PLAN_READY는 Gate1 승인이 아니다.

## v0.7.8 — 5개 기본 Profile 단계·스킬 관리 통일 (최신 우선 정책)

- `lifecycle-dev`, `development-worker`, `project-architect`, `storyboard`, `task-planning`은 동일한 단계 ON/OFF, 조건부 단계, 스킬 필수/선택·연결 해제·추가 편집 UI와 서버 API를 사용한다. 기본 설정은 Profile마다 다르다.
- `SESSION`은 공통 자동 초기화로 비활성화할 수 없다. 단계/스킬 변경은 활성 TASK가 없을 때만 허용하며 과거 TASK의 구성 해시·승인·Session Rotation 계약은 변경하지 않는다.
- 단계 의존성 검증: `GATE1`은 PLAN 필요, REVIEW는 VERIFY 필요, GATE2는 REVIEW 필요, VERIFY 및 COMPLETE는 선행 산출물 단계 필요. PLAN+IMPLEMENT를 모두 사용하는 비-worker Profile은 GATE1을 생략할 수 없다.
- `development-worker`는 개별 Gate 사용자 승인 권한을 가지지 않으며 검증된 계획 인계 및 기존 Gate1 승인 계약 없이 구현을 시작할 수 없다. 검증/리뷰 단계를 비활성화하면 이를 완료했다고 간주하지 않고 완료/아카이브 자격을 부여하지 않는다.
- 모든 Profile의 Skill Tree에서 단계 순서와 `GATE1/GATE2=user`, `VERIFY=verifier`, `REVIEW=reviewer` 역할을 보존한다. Gate/SESSION/COMPLETE 단계에는 스킬을 연결하지 않는다. 실제 스킬 누락·무결성 불일치 시 해당 활성 단계의 작업 시작을 차단한다.
- 기존 `development` Profile은 레거시 TASK 계약 조회 전용으로 보존하고 변경·신규 활성화를 금지한다.
- 본 절은 이전 버전의 기본 Profile 잠금/단계 편집 예외 문구보다 우선한다. 단, 시스템의 명시 승인 및 완료 증거 요구를 대체하지 않는다.
