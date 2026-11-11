# 승인·재승인 안전 계약 (teamdev 미사용)

Gate 1: Coordinator가 Spec/Plan/AC/검증 명령·위험을 표시하고 **실제 사용자 답변**에서 명시 승인을 확인할 때만 IMPLEMENT 시작. `approvals.md`에 승인 시각, 인용 가능한 원문, 승인 대상 파일 경로 및 SHA-256을 기록한다. 메시지 내용이 불명확하면 승인으로 간주하지 않는다.

Gate 2: Coordinator는 검증/리뷰가 작성된 시점의 승인된 Spec/Plan SHA-256 및 verification/review 파일의 SHA-256을 현재 파일에서 **다시 계산해 기록과 비교**한다. 차이가 있거나 최신 수정 이후 재검증이 없으면 `BLOCKED`로 표시하고 사용자 승인 요청을 중단한다. 독립 검증과 리뷰 결과가 실제 호출 증거를 포함하는지도 확인한다.

Gate 2: 최신 코드 변경 이후 실제 Verifier의 비압축 원본 테스트·정확한 자식 종료 코드와 Reviewer의 전체 원본 diff 검토를 확인한다. RTK 요약/CRG 그래프만으로 승인 근거를 대체할 수 없다.

Gate 2: Reviewer PASS 후라도 독립 VERIFY PASS 및 불완전한 검증 항목을 다시 확인하고, 사용자에게 보고 후 **명시적 최종 승인**을 받아야 COMPLETED를 기록한다. Gate 2 승인 대상에 verification/review 파일의 SHA-256을 기록해 변조·변경을 식별한다.

Plan Amend: 이미 승인된 범위, AC, 기술 결정, 검증 명령이 바뀌면 해당 시점의 승인 문서를 남기고 새 계획을 사용자에게 제시한다. 재승인 전 변경된 구현을 진행하지 않는다.

**한계:** 로컬 Markdown 승인 파일은 암호학적 사용자 신원 인증이나 동시 실행 잠금을 제공하지 않는다. 호스트가 승인 이벤트를 제공하면 이를 우선하며, 없으면 대화 속 직접 사용자 승인 확인에 의존한다. 다중 머신에서 동시에 같은 TASK를 갱신하면 안 된다. 코디네이터는 문서에 임의 'user APPROVED'를 작성해 승인으로 사용해서는 안 된다.

## v0.4.0 완료 아카이브 기준

Gate 2 승인 원문을 `approvals.md`의 `## Gate 2` 아래에 `- 상태: APPROVED`로 기록하는 시점은 반드시 검증·리뷰 및 승인된 Plan 최신성 확인 후이다. Coordinator는 `progress.md` 완료 기록 후 기존 이름 그대로 `docs/tasks/active/`의 **전체 디렉터리**를 `docs/tasks/completed/`로 이동한다. 대상이 있거나 이동 실패 시 완료 선언 금지; 새 세션이 불일치를 BLOCKED로 찾는다. 문서만으로 실제 인간 인증을 보장하지 않는다.

Gate 2 기록 양식의 해시 필드명은 `- 승인 대상 Spec SHA-256: <64자리 해시>`, `- 승인 대상 Plan SHA-256: ...`, `- 승인 대상 verification SHA-256: ...`, `- 승인 대상 review SHA-256: ...` 이다. 해시가 없거나 현행 파일 내용과 다르면 `COMPLETED`로 간주하지 않는다. OpenCode 세션 플러그인에서도 정적 검사하며 Coordinator는 실제 사용자 승인 원문과 독립 Worker 결과를 별도로 확인한다.
