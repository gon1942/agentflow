# AgentFlow Native Skills — npm 배포 RC

프로젝트 로컬 외부 Superpowers 7종 고정 스킬 + 네이티브 OpenCode / Claude Code / Codex 에이전트, 프로젝트 로컬 RTK/CRG 및 브라우저 도구. **`teamdev` 없음, 워크플로 CLI 없음, 중앙 워크플로 상태머신 없음.** 이 릴리스는 검증 완료된 v0.4.0 설치기를 래핑하며, 개발 워크플로를 재설계하지 않는다.

## 사전 요구 사항

- npx 실행을 위한 Node.js 20+
- **설치 시 Python 3.10+ 필수** (현재 강화된 설치기는 Python 기반)
- 고정된 업스트림 Superpowers 스킬, RTK/CRG 및 브라우저 패키지 다운로드용 네트워크
- 브라우저 스모크 테스트용 시스템 Chrome (선택 사항, `--no-browser`로 생략 가능)

## 설치

npm 게시 후 (아직 게시되지 않음):

```sh
npx --yes @gon1942/agentflow@0.5.0-rc.1 init ./my-project
```

로컬 패키지로 테스트하는 경우 (게시 전 검증):

```sh
npm pack
npx --yes --package ./gon1942-agentflow-0.5.0-rc.1.tgz agentflow init ./my-project
```

기존 프로젝트 파일은 기본적으로 절대 덮어쓰지 않는다. 네트워크 없이 스킬 설치를 위해 인증된 업스트림 아카이브를 제공하려면 `--upstream-zip path/to/official-pinned.zip` 옵션을 사용할 수 있으나, 도구 설치는 캐시되어 있지 않는 한 여전히 의존성 다운로드가 필요하다. 전역 폴백은 허용되지 않는다. 설치 스크립트는 설치된 프로젝트에 **복사되지 않는다**.

## 런타임 워크플로

요청 → ANALYZE (`brainstorming`) → PLAN (`writing-plans`) → Gate 1 사용자 승인 → IMPLEMENT (`test-driven-development`) → VERIFY (`verification-before-completion`) → REVIEW (`requesting-code-review`) → Gate 2 사용자 승인 → COMPLETE. `receiving-code-review`와 `systematic-debugging`은 조건부로 실행한다. 전체 정책은 설치된 프로젝트의 `docs/workflow/WORKFLOW.md`를 참고한다.

작업 아카이브: `docs/tasks/active/` → `docs/tasks/completed/`. 새 세션은 둘 다 검사한다. Improver는 읽기 전용으로 개선안만 제안하며 코드를 자동으로 수정하지 않는다.

## 보안 / 릴리스

- npm 패키지에는 전역 설치 바이너리나 로컬 비밀값이 의도적으로 포함되어 있지 않다. OpenCode 플러그인은 CommonJS 프로젝트 내부에서도 자체 `type: module` 패키지 경계를 사용한다.
- 업스트림 파일은 고정된 Git blob SHA-1 및 헬퍼 파일 해시와 대조 검증되며, MIT 저작자 표기가 보존된다.
- GitHub Actions PR CI가 유닛 테스트와 패키지 검사를 실행한다. 게시는 별도의 수동 승인 워크플로이며, 첫 릴리스는 `latest`가 아닌 `next`에 배포한다.
- 실제 근거 없이 `SKILL_LOADED`, 네이티브 worker E2E, Chrome E2E, 사람 승인, npm 게시 PASS를 주장하지 않는다.

## 테스트

```sh
npm ci
npm test
npm run test:python
npm pack --dry-run
```

관리자 참고: 공개 push/publish 전에 저장소 소유자/이름과 npm 스코프 소유권을 확인할 것. package.json의 저장소 URL은 **제안된 값**이며 검증되지 않았다.

## 릴리스 절차 (관리자)

1. GitHub 소유자/저장소와 npm 스코프 소유권을 확인하고 **공개** 저장소를 생성한 뒤, 소스에 자격증명이 없는지 확인하고 나서만 push한다.
2. GitHub 브랜치 보호/필수 CI와 수동 승인이 필요한 `npm-release` 환경을 구성한다.
3. 해당 npm 패키지를 생성하고 GitHub Actions 워크플로 `publish.yml`에 npm Trusted Publishing(OIDC)을 구성한다.
4. 패키지 설치 CI와 실제 로컬 네이티브 worker 워크플로(요청부터 Gate 2/COMPLETE까지)를 실행한다.
5. `Publish approved npm prerelease` 워크플로를 트리거하여 `0.5.0-rc.1`을 `next` dist-tag로 게시한다. 전체 E2E가 통과하기 전까지는 `latest`를 사용하지 않는다.
6. 새 폴더에서 게시된 패키지를 `npx --yes @gon1942/agentflow@0.5.0-rc.1 init ./smoke-project`로 검증한다.

CI 패키지 설치 검사는 TEST 전용 플래그를 사용해 도구 프로비저닝을 생략하므로 RTK/CRG/Chrome 준비 상태를 **확립하지 않는다**. 프로덕션 `init`은 항상 해당 도구 설치를 시도한다.
