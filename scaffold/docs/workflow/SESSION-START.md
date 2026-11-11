# 새 세션 작업 상태 복원 (v0.4.0)

Coordinator는 **매 새 세션의 첫 실질 답변 전에** 다음을 읽는다.

- `docs/tasks/active/*/progress.md`
- `docs/tasks/completed/*/progress.md`
- 이전 구조 `docs/tasks/*/progress.md` (호환성; active/completed 자체는 TASK가 아님)

정상 상태: `ANALYZE`, `PLAN`, `WAITING_PLAN_APPROVAL`, `IMPLEMENT`, `VERIFY`, `REVIEW`, `WAITING_FINAL_APPROVAL`, `BLOCKED`, `COMPLETED`.

1. 진행 / 계획 승인 대기 / 최종 승인 대기 / 차단 / 완료 수를 계산한다. TASK ID, 한글 제목, 현재 단계, 다음 행동을 간단히 표시한다. 상태가 불명확하면 `작업 상태 미확인`이다.
2. `active/`에 COMPLETED가 있거나 `completed/`에 COMPLETED가 아닌 작업이 있으면 경로·상태 불일치 → **BLOCKED**. 같은 TASK ID가 둘 이상 있거나 `progress.md`가 없으면 **BLOCKED**.
3. `COMPLETED`는 Gate 2 승인 원문, `approvals.md`의 `## Gate 2` 아래 `- 상태: APPROVED`, 현행 Spec/Plan 및 verification/review 해시의 일치 여부를 Coordinator가 확인해야 신뢰한다. 자동 플러그인은 문서의 정적 요약만 제공하며 사람 승인 신원을 증명하지 못한다.
4. 이전 평면 TASK는 읽기 전용 호환 상태로 요약한다. 수동 이행 없이 경로를 바꾸거나 기존 기록을 덮어쓰지 않는다.
5. 새 TASK는 AREA-NNN-meaningful-slug 규칙으로 명명한다. active/completed/평면 모든 작업에서 동일 영역 번호의 최대값 다음을 쓴다. 사용자 작업명을 짧은 영문 kebab-case로 표현하고 별도 한글 제목을 기록한다.
6. 기존 작업을 이어 달라는 요청이면 새 TASK를 만들지 않고 최신 Spec/Plan·승인·실행 증거를 확인하고 이어서 진행한다. 여러 후보가 있으면 진행 전에 사용자의 작업 지정을 확인한다.
7. 대화창 첫 응답: `작업 상태: 진행 N / 계획 승인 대기 N / 최종 승인 대기 N / 차단 N / 완료 N`; `이어 할 작업: <작업명> · <단계> · <다음 행동>` (없으면 활성 작업 없음). 실시간 로그는 별도 터미널에서만 본다.
8. `improvement.md`의 미반영 제안은 필요하면 요약하되 신규 TASK를 자동 생성·수정하지 않는다. 전역 스킬 충돌은 경고하고 프로젝트 내부 원본을 우선한다.

**원칙:** 이 절차는 `teamdev`/커스텀 워크플로 CLI가 없으며 새 세션 상태 요약은 저장된 자료를 바탕으로 한 관측이지 별도의 인증된 승인 엔진이 아니다.
