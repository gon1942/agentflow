# Native E2E 검증 수락 기준 (운영 안정판 전환용)

## 원칙

이 릴리스의 로컬 자동화 테스트는 네이티브 OpenCode / Claude Code / Codex Worker 또는 실제 사용자 승인을 대체하지 않는다. **실제 설치부터 COMPLETE까지 테스트가 끝나기 전 stable 판정 금지.** 이 문서는 CLI 작업 엔진이 아니다.

## 실제 새 프로젝트 체크리스트

1. 배포 ZIP을 신규 디렉터리에 해제하고 `python3 install.py /new/project` 실행. `INSTALL_READY` 및 프로젝트 내부 Superpowers 원본 7종/3런타임 해시 검증, 로컬 RTK/CRG/Playwright/agent-browser 설치 상태 기록. 전역 대체 없음.
2. Orca/OpenCode에 프로젝트 열고 **새 Coordinator 세션** 시작. `docs/tasks` 실제 상태에서 진행·계획 승인 대기·최종 승인 대기·차단·완료가 표시되는지 확인. 다른 세션에서 TASK 하나 생성 후 재접속해서 연속성도 확인.
3. `ANALYZE`: 프로젝트 내부 `brainstorming` 사용 호출 근거(원본 경로·해시·호출ID) 확인. CRG는 소스/영향이 없으면 SKIP_EMPTY/SKIP_NOT_NEEDED, 있으면 실제 명령·그래프 최신성 검증. RTK는 탐색에만 보조적으로 사용.
4. `PLAN`: 원본 `writing-plans` 기반 Spec/Plan/AC/검증 명령 작성. 코디네이터가 실제 영향을 받는 파일, 테스팅 방법을 Gate 1 요청에 포함. **사용자 승인 전 구현이 없음**을 검증.
5. 사용자 Gate 1 명시 승인. 승인된 문서 해시/승인 메시지의 실제 근거 기록. 권한 없는 모의 승인/문서 조작으로는 구현 시작 금지.
6. `IMPLEMENT`: 독립 Implementer 파견 실제 ID, `test-driven-development` 실제 사용, RED→GREEN→REFACTOR 명령·실패의 정상 이유 확인. 빌드/탐색 RTK 선택적; CRG 변경 영향 필요 시만.
7. `VERIFY`: 독립 Verifier가 `verification-before-completion` 원본을 호출하고 **실제 원본 검사 명령과 자식 exit**로 승인된 전 범위 AC를 직접 검사. `tee` exit 0 오판 차단. RTK로 원본 로그 대체 금지. 웹 로그인은 로컬 Chrome 실제 정상/비정상 계정/폼 테스트 확인. 브라우저 미실행은 NOT_RUN.
8. `REVIEW`: 독립 Reviewer 실제 파견 증거와 원본 `requesting-code-review`/`code-reviewer.md` 사용 근거. 원본 변경 소스(미커밋/미추적 포함)·보안·영향 범위를 검토하고, 필요시 CRG(그래프 최신성 확인) 사용. 별도 Reviewer 재파견 금지.
9. 의도적인 결함 시나리오 하나를 같은 TASK에서 `REQUEST_CHANGES → receiving-code-review → 수정 → 신규 VERIFY → 신규 REVIEW`로 반복. 과거 증거 round-NN 별 보존. 승인 범위가 바뀌면 사용자 Plan Amend 재승인 테스트.
10. Gate 2 이전: Spec/Plan/AC/verification/review 최신성·해시 재검증. 명시 사용자 최종 승인 전 완료 금지. 승인 후 COMPLETE와 세션 상태 보존.
11. COMPLETE 이후 **improver 1회 실제 독립 호출**: stage별 실측 소요 시간, 오류, 검증 round, 스킬 경로, RTK/CRG 사용 빈도, 성능 병목 P0/P1/P2를 검토해 사용자에게 개선 후보만 제시. 자동 수정·승인 금지.
12. 완전히 새 세션으로 다시 시작해 COMPLETE 및 개선안 보존 확인. 실제 오류/단계별 시간, 승인 대기 시간, 실제 네이티브 스킬 호출, RTK/CRG 명령 메타데이터를 대조.

## 실패 시 보고 규칙

- `INSTALL_READY` != `SKILL_LOADED` != `SOURCE_VERIFIED`.
- `TOOL_CALL_OBSERVED` != RTK/CRG/스킬 성공. 그래프 최신성은 별도 확인.
- 실제 네이티브 Worker 없이 synthetic test를 돌린 결과는 `SIMULATED`, 별도 Worker 보장 실패는 `BLOCKED`.
- 테스트 미실행은 `NOT_RUN`, 실행 출처 미확인은 `NOT_VERIFIED`, 처리 시간 미실측은 `NOT_MEASURED`.
- Gate 1·Gate 2는 실제 사용자 승인만 인정; `approvals.md` 텍스트 단독으로 본인 인증이 되지는 않음.
- 이 릴리스는 tool/helper/정책/fixture 테스트만 통과했으며 위 단계 전체 **실제 네이티브 E2E는 아직 NOT_VERIFIED**.
