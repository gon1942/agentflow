# AgentFlow 문서 경로 · 정본 정책

이 문서는 프로젝트 내부 docs/ 디렉터리의 단일 경로 정책이다. 에이전트는 작업과 연관된 파일만 필요한 만큼 읽는다. 모든 문서를 무조건 컨텍스트에 로드하지 않는다.

| 경로 | 용도 | 주요 단계 |
| --- | --- | --- |
| `docs/requirements/` | 프로젝트 공통 요구사항·기능 명세·수용 기준 | ANALYZE |
| `docs/architecture/` | 시스템 구성·컴포넌트·API/데이터 설계·ADR (`decisions/`) | ANALYZE·PLAN·REVIEW |
| `docs/design/` | 기능·UI/UX·API 상세 설계 | ANALYZE·PLAN·VERIFY |
| `docs/storyboards/` | 화면·메뉴별 스토리보드 | ANALYZE·PLAN |
| `docs/tasks/` | TASK 명세·실행계획·승인·실행증거의 유일 정본 | 모든 단계 |
| `docs/templates/` | 문서 템플릿 (산출물 아님) | 작성시 |
| `docs/workflow/` | 프로세스·게이트·에이전트 규칙 | 모든 단계 |

## 탐색 및 작성
- SESSION에서 TASK 진행 상태와 고정 Profile·승인·검증을 우선 확인한다.
- ANALYZE/PLAN에서 요청과 관련된 요구사항 → 시스템 아키텍처 → 상세 설계 → 스토리보드를 탐색한다. 누락 문서는 `NOT_FOUND`로 기록하되 불필요한 문서를 생성하지 않는다.
- PLAN의 TASK 계획은 반드시 `docs/tasks/active/<TASK-ID>/`에 기록한다. 다른 분류 디렉터리에 복제 정본을 만들지 않는다.
- 구현자는 승인된 TASK Plan과 관련 문서를, 독립 검증·리뷰는 AC 및 설계 정본과 실행 증거를 확인한다.
- Storyboard Profile은 `docs/storyboards/<scope>/`에 산출물을 작성한다.
- 각 파일의 상대경로 및 변경 근거를 TASK에 기록한다. 승인된 실행 계약과 외부 문서가 충돌하면 임의 수정하지 않고 계획 변경·재승인을 따른다.
- 기존 프로젝트의 문서가 다른 경로에 있다면 우선 해당 경로를 찾아 참조할 수 있지만, 승인 없이 이동·덮어쓰기하지 않는다.
- `README.md`, `.gitkeep`은 문서 통계 산출물 수에 포함하지 않는다.


5개 Profile의 역할 및 ID 호환성: `docs/workflow/PROFILE-CONTRACTS.md` 참고.
