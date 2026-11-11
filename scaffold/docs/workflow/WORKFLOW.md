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
