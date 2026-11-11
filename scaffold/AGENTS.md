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
