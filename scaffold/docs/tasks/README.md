# AgentFlow TASK 저장 구조 (v0.4.0)

```text
docs/tasks/
├── active/
│   └── AUTH-001-user-login-page/
│       ├── spec.md
│       ├── plan.md
│       ├── progress.md
│       ├── approvals.md
│       ├── verification.md
│       ├── review.md
│       ├── tool-evidence.md
│       ├── skill-evidence.md
│       ├── improvement.md
│       └── evidence/round-01/
└── completed/
    └── AUTH-002-user-signup/
        └── ... (원본 자료 전체)
```

- 사용자가 요청하면 Coordinator가 AREA-NNN-english-kebab-slug 형식으로 의미 있는 이름을 생성하며, `docs/tasks/active`에 생성한다. 실수로 기존 active/completed/평면 작업의 같은 ID를 재사용하지 않는다.
- PLAN만 이동하지 않는다. Gate 2 승인 후 검증·리뷰·승인·증거가 들어 있는 TASK 디렉터리 전체를 `completed/`로 이동한다.
- **완료 조건**: 실제 사용자 Gate 2 승인 원문, 최신 증거 해시 일치, Coordinator `COMPLETED` 표시, 폴더 이동 성공. 실패했다면 BLOCKED/복구 대상이며 완료 선언 금지.
- 새 세션은 두 디렉터리뿐 아니라 이전 `docs/tasks/<TASK-ID>/`도 호환 조회한다. 이름만 보고 완료로 판단하지 않고 progress/approvals와 대조한다.
- 프로젝트 내부 외부 스킬을 사용한다. `teamdev`·전용 워크플로 CLI·자동 Gate 승인은 없다.
