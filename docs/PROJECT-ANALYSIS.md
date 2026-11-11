# AgentFlow 프로젝트 분석 보고

- **분석 대상**: `@gon1942/agentflow` 0.5.0-rc.1 (npm 배포 RC)
- **분석일**: 2026-11-11
- **분석 범위**: 전체 저장소 구조, 설치기 동작, scaffold 구성, 보안 설계, 테스트/CI/릴리스 상태

## 1. 프로젝트 개요

**npm 배포용 AI 에이전트 워크플로 설치기**입니다. `npx @gon1942/agentflow init ./my-project` 한 번으로, OpenCode / Claude Code / Codex 세 에이전트 런타임에서 즉시 사용 가능한 **skills-first 개발 워크플로 환경**을 대상 프로젝트에 구축합니다.

핵심 철학 (v0.4.0에서 계승):

- **"No teamdev, no workflow CLI, no 중앙 상태머신"** — 런타임 엔진을 만들지 않고, 검증된 외부 스킬(obra/superpowers 7종) + 네이티브 에이전트 + Markdown 문서 계약으로 워크플로를 구성
- **PROJECT_ONLY** — 전역 쓰기 금지, 모든 도구는 대상 프로젝트 `.ai-dev/tools/` 안에만 설치
- **증거 기반** — "해시 일치 ≠ 스킬 로드 증명", "파일 존재 ≠ READY" 등 과장 주장을 시스템적으로 차단

## 2. 구조

```
source/
├── bin/agentflow.cjs (54줄)   # npx 진입점: 인자 검증 → Python 3.10+ 탐지 → install.py 위임
├── install.py (228줄)          # 1회성 설치기: 업스트림 검증 → scaffold 복사
├── tool_provision.py (210줄)   # RTK/CRG/브라우저 프로젝트 로컬 프로비저닝
├── scaffold/                   # 설치될 프로젝트 템플릿 (전부 대상에 복사됨)
│   ├── AGENTS.md / CLAUDE.md   # 3개 런타임 공통 진입 계약
│   ├── .opencode/agents/       # coordinator, implementer, verifier, reviewer, improver
│   ├── .claude/agents/ · .codex/agents/  # 동일 5역할의 런타임별 정의
│   ├── .opencode/plugins/      # session-status, skill-observer, tool-usage-observer
│   ├── docs/workflow/          # WORKFLOW.md(정본), APPROVALS.md, SESSION-START.md
│   └── docs/templates/task/    # spec/plan/progress/approvals/verification/review 등 8종
├── tests/ (5개 Python, 777줄)  # 설치/보안/스테이지/E2E/작업 라이프사이클
├── npm-tests/installer.test.cjs
├── scripts/packed-install-ci.sh # npm pack → 실제 npx 설치 통합 테스트
└── .github/workflows/           # test.yml, publish.yml(OIDC 수동 게이트)
```

## 3. 설치 흐름 (실제 동작)

1. **`bin/agentflow.cjs`**: `init <path>` + `--upstream-zip`, `--no-browser`만 허용. `--skip-tools`는 `AGENTFLOW_TEST_ONLY_SKIP_TOOLS=1` 환경변수가 있을 때만 통과(테스트 전용 탈출구). Python 3.10+ 찾아 `install.py` 실행
2. **`install.py`**:
   - obra/superpowers를 **Git 커밋 `22f0b46`으로 고정**해 다운로드 (또는 오프라인 ZIP)
   - zip 경로 조작(`..`, 절대경로, `\`, symlink 항목) 거부, 크기 상한(50MB/12MB/2MB) 적용
   - 7개 SKILL.md + 14개 동반 파일을 **Git blob SHA-1로 전수 검증** → 불일치 시 설치 차단
   - scaffold 전체 + 스킬 3식(`.opencode/skills`, `.claude/skills`, `.agents/skills`) + `external-skills.lock.json` 매니페스트 생성
   - 기존 파일 충돌/대상 경로 symlink 시 **절대 덮어쓰지 않음**. 원자적 임시파일 쓰기(`open('xb')` + fsync + replace)
3. **`tool_provision.py`**: RTK v1.1.0(GitHub 릴리스 checksums.txt SHA-256 검증 후 설치), CRG v2.3.9(프로젝트 로컬 venv + pip), Playwright 1.65.0/agent-browser 0.41.2(npm `--ignore-scripts`, 시스템 Chrome 실기기 smoke). 전부 BLOCKED/READY 이진 판정, 전역 폴백 없음

## 4. 설치 후 워크플로 (scaffold가 부여하는 것)

`요청 → ANALYZE(brainstorming) → PLAN(writing-plans) → Gate 1 사용자 승인 → IMPLEMENT(TDD) → VERIFY → REVIEW → Gate 2 사용자 승인 → COMPLETE(+읽기전용 Improver 1회)`

- Coordinator 혼자만 상태 기록 갱신, TASK는 `AREA-NNN-kebab-slug`로 명명, `docs/tasks/active/` → Gate 2 후 `completed/`로 폴더 전체 이동
- 검증 로그 원본 보존(RTK 요약으로 대체 금지), 승인 원문·SHA-256 해시 보존, 근거 없는 PASS 금지
- 세션 플러그인 3종이 새 세션 시작 시 작업 상태(`진행 N / 승인대기 N / 차단 N / 완료 N`)를 자동 스캔·표시

## 5. 품질·보안 평가

### 잘 된 점

- 공급망 보안이 상당히 성숙함: 핀된 커밋 + 이중 해시(SHA-1 blob + SHA-256), zip 경로 조작 방어, symlink 회피, 원자적 쓰기, MIT 라이선스 보존 검증
- npm 게시: OIDC Trusted Publishing + `environment: npm-release` 수동 승인 + 태그=`v{version}` 일치 강제 + `next` 전용
- `VALIDATION.md`가 "무엇이 NOT_VERIFIED인지" 정직하게 명시 (네이티브 E2E, 실사람 승인, 라이브 네트워크 설치 등 — RC 품질 경계 명시)

### 리스크 / 주의점

- 설치 시 Python 3.10+ 필수 → npx 사용자 중 Python 없는 환경에서 `PYTHON_REQUIRED`로 실패 (Node-only 설치기는 "not yet implemented")
- 검증 다수가 **픽스처 기반** — 실제 네트워크 설치·네이티브 worker 파견·Chrome E2E는 미검증 상태 (RC인 이유)
- `repository` URL이 "proposed, not verified" — 게시 전 소유권 확인 필요
- Git 상태가 `Initial` 커밋 1개뿐인 로컬 저장소 (아직 공개 push 전 단계)

## 분석 방법 및 한계

- 확인 방법: 전체 파일 트리 조사 + 핵심 파일 원문 읽기 (package.json, README.md, CHANGELOG.md, VALIDATION.md, bin/agentflow.cjs, install.py, tool_provision.py, scaffold/AGENTS.md, scaffold/docs/workflow/WORKFLOW.md, .github/workflows/*.yml, scripts/packed-install-ci.sh)
- 읽지 않은 부분: tests/ 5개 파일 내부 로직, scaffold 에이전트 정의 5종·플러그인 JS 본문, E2E-ACCEPTANCE.md (구조 파악에는 불필요)
- 본 문서는 특정 시점(2026-11-11, 커밋 `ccb5baa`)의 스냅샷 분석임
