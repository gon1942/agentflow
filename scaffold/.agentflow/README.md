# AgentFlow Skill Studio — Project configuration

`active-profile.json` selects the current profile and has an optimistic `generation` counter. `profiles/*.json` map Coordinator → workflow → skill tree; `skill-trees/*.json` assign stage skills. The `development` template mirrors the protected original `docs/workflow/WORKFLOW.md`; data must never supersede Gate 1/2 or independent VERIFY/REVIEW.

## Usage

From the installed project root:

```bash
python3 agentflow_console.py status
python3 agentflow_console.py contract
python3 agentflow_console.py start --browser
python3 agentflow_console.py add-template storyboard
python3 agentflow_console.py clone development custom 'Custom'
python3 agentflow_console.py inspect local /path/to/skill
python3 agentflow_console.py install local /path/to/skill --approve
python3 agentflow_console.py activate storyboard --generation 1
```

Skill sources are inspected; `--approve` authorizes copying reviewed code into the PROJECT ONLY, not executing it. Native LLM/agent loading is NOT_VERIFIED by install/hash checks. Active tasks block management writes; the Coordinator still owns task status, Gate 1/2 and native worker dispatch. The console is a distinct local management interface, not a workflow CLI. When starting a task freeze the result of `contract` in the task record.

## Scope

Initial local console provides Profile/Tree CRUD, installed skill listing, local folder and ZIP installation, activation guard, and native dispatch configuration readout. `AI Skill Assistant`, Git online retrieval, direct website skill search, and real native agent tracing require additional adapter validation and are **not claimed as complete**.

**Policy boundary:** All profiles retain the `protected-development` workflow policy. Specialized Analysis/Storyboard stages are routing overlays or subphases, not a replacement for required human gates or independent verification and review. Non-standard workflow engines are not part of this release.

## Optional approval gates (non-built-in Profile)

The `development` profile always requires GATE1/GATE2. Non-built-in profiles may use `"approval_gates":{"GATE1":false,"GATE2":true}` in profile JSON, managed by the web Profile cards. Gates stay in the stage list but contain no skills. A false gate is recorded as `SKIPPED_BY_PROFILE_POLICY`, never as `APPROVED`, and independent VERIFY/REVIEW remains required. The coordinator must read the runtime contract at new task start and preserve the immutable snapshot. An in-progress task cannot have its gate settings changed. Separate release and repository-write approvals are unaffected.

## 기본 제공 Profile 3종 (v0.5.3)

- `development`: 기존 기능 구현/TDD, 독립 검증과 리뷰, Gate 1·2 필수. 최초 활성 Profile.
- `storyboard`: 화면·기능·UI/UX 설계 문서 작성. `docs/storyboards/<scope>/`를 기본 산출물로 권장.
- `task-planning`: 요구사항/스토리보드를 개발 TASK의 `spec.md`, `plan.md`, `progress.md`와 AC·의존성·검증 계획으로 변환. 기존 `docs/tasks/active/<TASK-ID>/` 정본 유지.

세 Profile의 전문 Skill Tree는 설치된 7개 스킬만 참조한다. 문서 작성용 별도 외부 전문 Skill은 자동 설치하거나 실제 로딩했다고 표시하지 않는다. 스토리보드·계획 Profile에서 IMPLEMENT는 **문서 생성**이고, 코드를 작성할 때만 개발 Profile의 TDD 계약을 적용한다. VERIFY 및 REVIEW 독립 Worker는 계속 필요하다. 문서 리뷰를 코드 리뷰 스킬이 대신했다고 주장하지 않는다.

Profile 전환은 웹 관리 콘솔 또는 `agentflow_console.py` 관리 명령에서 TASK가 없을 때만 가능하다.

New in v0.7.1: `.agentflow/execution-contexts/sessions/` contains per-agent-session new-TASK defaults; `tasks/` contains pinned execution contracts. Both are project-local; do not treat them as native session-process identities.


5개 Profile의 역할 및 ID 호환성: `docs/workflow/PROFILE-CONTRACTS.md` 참고.
