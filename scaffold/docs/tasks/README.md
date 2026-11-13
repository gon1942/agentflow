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


## v0.5.8 — 계획 완료와 실제 구현 완료 분리 (이전 인계/아카이브 문구보다 우선)

- `task-planning` 기본 단계: ANALYZE → PLAN → VERIFY → COMPLETE. PLAN은 기존 `docs/tasks/active/<TASK-ID>/`에 `spec.md`, `plan.md`를 기록한다. VERIFY는 요구사항·AC·의존성·검증 방법을 실제 점검하고 불합격이면 PLAN 수정 후 다시 VERIFY한다.
- 계획 검증 보고서는 같은 TASK에 `plan-verification.json`으로 기록한다. 형식: `{"task_id":"LOGIN-001-login","result":"PASS","verifier":"verifier","checks":["requirements","acceptance_criteria","dependencies","verification_plan"],"sha256":{"spec.md":"<sha256>","plan.md":"<sha256>"}}`. 실제 검증 없이 PASS 보고서를 만들어서는 안 된다.
- 계획 VERIFY PASS 및 COMPLETE 이후 Coordinator는 `python3 agentflow_console.py task-ready <TASK-ID>`를 실행한다. 해시·문서·필수 검사 기록 확인 성공 시 `task-state.json`의 상태를 `PLAN_READY`로 설정한다. **폴더는 `active/`에 그대로 유지**한다. `completed/`, `handoffs/`로 이동하지 않는다. 계획 완료와 구현 완료를 혼동하지 않는다. 해당 명령은 증거의 파일 구조 및 무결성을 검증하지만 실제 네이티브 verifier 호출의 진위를 보증하지 않는다.
- `PLAN_READY`인 TASK만 active TASK 잠금에서 제외하므로 Profile을 `development`로 전환할 수 있다. PLAN_DRAFT, 레거시 상태 불명, 작업 진행 중인 TASK는 전환을 차단한다.
- Development SESSION은 `python3 agentflow_console.py status`의 `plan_ready_tasks`와 `docs/tasks/active/*/task-state.json`을 확인한다. 사용자가 지정한 TASK만 대상으로 `python3 agentflow_console.py task-begin <TASK-ID>` 실행한다. 이는 **같은 작업 폴더**를 `WAITING_PLAN_APPROVAL`로 잠그며 기존 계획·검증 해시를 재검사한다. 이후 GATE1에서 사용자 승인이 나기 전 IMPLEMENT를 실행하지 않는다.
- Development의 실제 구현·검증·리뷰·최종 사용자 승인 이후에만 `COMPLETED`로 기록하고 기존 active→completed 전체 폴더 이동 규칙을 적용한다. PLAN_READY 단계를 COMPLETE했다고 개발 완료로 주장하거나 Improver를 실행하지 않는다.
- UI/CLI의 `contract.execution_scope`에 planning 전용 `plan_ready_allowed_after_evidence`, `task_destination`을 표시한다. 개발/설계 특화 Profile의 기존 정책과 충돌할 경우 선택된 작업 종류에 대한 추가 승인 및 검증을 우선한다.
- 위 명령은 작업 증거·상태에 대한 **국소적 안전 전환**이며 에이전트 단계 실행, 사용자 승인, 작업 검증을 자동으로 수행하지 않는다. 실패하면 원본 폴더·데이터를 보존한다.
