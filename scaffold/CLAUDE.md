# Claude Code — AgentFlow Native Skills

공통 지침은 프로젝트 루트의 `AGENTS.md`가 정본이다. 매 신규 세션 첫 응답 전에 `docs/tasks/active/*/progress.md` + `docs/tasks/completed/*/progress.md` + 레거시 `docs/tasks/*/progress.md`를 확인하여 진행·승인 대기·차단·완료 작업 수와 다음 작업을 사용자에게 보여준다. 실시간 로깅 금지. `teamdev` 및 자체 워크플로 CLI는 없다. 프로젝트 내부 `.claude/skills`의 원본 외부 스킬을 실제로 사용한다. PLAN 승인 전 구현 금지, REVIEW PASS 후 Gate 2 승인 전 완료 금지. 네이티브 implementer/verifier/reviewer를 분리 사용하고 불가능하면 BLOCKED 표시.
