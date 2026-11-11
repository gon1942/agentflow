---
task_id: AREA-001
status: ANALYZE
updated_at: NOT_SET
owner: coordinator
---

# 작업 상태 (Coordinator만 갱신)

- 폴더명: AREA-001-meaningful-english-slug
- 한글 제목: NOT_SET
- 저장 위치: docs/tasks/active/AREA-001-meaningful-english-slug
- 완료 이동: Gate 2 승인 + 최신 검증·리뷰 근거 확인 후 active → completed 전체 이동

- 현재 단계: ANALYZE
- 다음 행동: 외부 `brainstorming`으로 요청·제약 분석
- 실제 독립 Worker 호출: NOT_VERIFIED
- 마지막 사용자 승인: 없음
- 블로커: 없음
- 완료 후 Improver: NOT_RUN

## 단계 이력 (실제 이벤트 기반)

실제 시작/종료 시각(ISO 8601)을 기록하고, 차이로 elapsed seconds를 계산한다. 승인 대기 시간은 Worker 실행 시간과 분리한다. 미관측 단계는 `NOT_MEASURED`이며, 임의 추정은 금지한다. 동일 TASK 재작업은 round-01, round-02 등으로 표기해 이전 증거를 지우지 않는다.

| 시작 시각 | 종료 시각 | 단계/round | Worker·네이티브 ID | 실제 스킬·도구 사용/증거 | 결과·오류 | 소요 초 |
| --- | --- | --- | --- | --- | --- | --- |

## 품질·성능 관측

- 실제 테스트 실행 횟수/마지막 명령 exit: NOT_MEASURED
- REVIEW 수정 루프 횟수: NOT_MEASURED
- 실패 또는 잘못된 CLI 호출 횟수: NOT_MEASURED
- RTK 출력 축약 실측 효과: NOT_MEASURED
- CRG 그래프 탐색 여부/효용: NOT_VERIFIED
- Browser 실제 E2E: NOT_RUN
- 사용자 승인 대기 시간: NOT_MEASURED
- 기록 경로: `tool-evidence.md`, `verification.md`, `review.md`, `evidence/round-NN/`
