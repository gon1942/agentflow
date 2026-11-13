# Partial stage handoff drafts

부분 실행 Profile에서 종료한 TASK를 완료 처리하지 않고 보존하는 위치입니다.
Coordinator는 PLAN 등 설정된 종료 단계에서 `progress.md`에 `STOPPED_AFTER_PLAN` 또는 `STOPPED_AFTER_<STAGE>`를 기록하고, 해당 TASK의 디렉터리를 `docs/tasks/active/<TASK-ID>/`에서 `docs/tasks/handoffs/<TASK-ID>/`로 전체 이동합니다.
이동 전 증거·범위·시점 확인, 동일 ID 목적지 충돌 차단, 덮어쓰기 금지. 이동 실패 시 `BLOCKED`로 표시하고 active 상태를 무시하지 마세요.
이 폴더의 문서는 승인·독립 검증·리뷰 완료를 뜻하지 않습니다. Development에서는 이 초안을 **참고 입력**으로 사용하고 새 개발 TASK를 만들어 정상 Gate1/IMPLEMENT/VERIFY/REVIEW/Gate2 절차를 따릅니다.
새 세션에서는 handoffs를 열거하되 미완료 작업을 COMPLETED로 세지 않습니다.
