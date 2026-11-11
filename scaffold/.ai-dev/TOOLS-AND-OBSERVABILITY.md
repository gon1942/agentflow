# Project-only RTK / CRG / Browser + 관측 계약

주도 스킬 및 적용 단계의 정본: `docs/workflow/WORKFLOW.md`. 이 문서는 **도구 실행 세부 지침**이며 별도 워크플로 상태 머신이 아니다.

## RTK 1.1.0 (선택적 출력 축약)

프로젝트 내부의 `./.ai-dev/tools/rtk/bin/rtk` 경로만 사용한다. Hook이 없다고 전역 설치를 수행하지 말고 직접 호출한다. `RTK Hook NOT_VERIFIED`는 `RTK binary READY`와 다른 상태다.

```bash
# 리포지토리 탐색이나 개발 중 결과를 간단히 볼 때만 사용
./.ai-dev/tools/rtk/bin/rtk git status
./.ai-dev/tools/rtk/bin/rtk git diff
./.ai-dev/tools/rtk/bin/rtk grep 'symbol' .
```

**VERIFY/REVIEW 판정 증거**에는 RTK 출력으로 대체하거나 원본 `exit_code`를 가정하지 않는다. Verifier는 비압축 테스트 명령을 직접 실행하고 실제 자식 종료 코드, 타임스탬프, 비압축 원본 stdout/stderr(민감정보 점검 후), 테스트·AC 판단을 인계한다. `tee` 사용 시 `$?`가 `tee`의 종료 코드가 되지 않도록 `set -o pipefail` 또는 `PIPESTATUS`/별도 프로세스 종료코드를 정확히 사용한다. 별도 RTK 요약은 `summary_only=true`로 기록한다. 쉘에 비밀정보가 들어간 명령/출력은 그대로 기록하지 않는다.

## CRG 2.3.9 (조건부 코드 그래프 탐색)

프로젝트 내부의 `./.ai-dev/tools/crg-venv/bin/code-review-graph`만 사용한다. 설치 시 graph가 없어도 신규·빈 프로젝트에서 정상일 수 있다. 사용할 경우 프로젝트 소스가 있는지, 그래프의 실제 생성·최신성 근거가 있는지 먼저 평가한다.

```bash
./.ai-dev/tools/crg-venv/bin/code-review-graph --help
./.ai-dev/tools/crg-venv/bin/code-review-graph status
# 그래프가 필요하고 실제 소스가 있을 때에만 프로젝트 루트에서:
./.ai-dev/tools/crg-venv/bin/code-review-graph build
# 최신성을 확인할 때(지원되는 CLI 옵션·결과 확인):
./.ai-dev/tools/crg-venv/bin/code-review-graph detect-changes --brief
```

도구 사용 목적: ANALYZE 관련 호출자·의존성, PLAN 영향 파일·테스트 후보, REVIEW 변경 전파·의존자. 큰 단일 파일 변경처럼 그래프 이득이 없으면 `SKIP_NOT_NEEDED`, 신규 빈 프로젝트는 `SKIP_EMPTY`. CRG 실패/그래프 stale/partial은 별도 표시하고 원본 코드 탐색으로 보강한다. **CRG 결과만으로 테스트 범위를 축소하거나 검증 통과를 선언하지 않는다.** 그래프 최신성을 확인하지 못했으면 `GRAPH_FRESHNESS_NOT_VERIFIED`.

## Browser (웹 UI일 때)

`.ai-dev/tools/browser/node_modules` 아래 Playwright 1.65.0 / agent-browser 0.41.2, 시스템 Chrome만 전역 예외. 설치/Chrome smoke PASS와 실제 로그인 E2E는 다르다. Verifier가 웹 UI/인증 작업에서 실제 성공·실패 경로 및 필요시 접근성·콘솔 오류를 검증하고 실제 실행 근거를 남긴다. 브라우저 미실행은 `NOT_RUN`.

## 관측 / 시간 / 증거 / Improver

- 설치기는 `.ai-dev/tools/tools-lock.json`에 도구 버전·준비 상태를 기록한다. READY는 Hook/MCP/그래프/실제 실행 성공을 증명하지 않는다.
- OpenCode의 `.opencode/plugins/skill-observer.js`는 `skill` 도구 호출 메타데이터만 `.ai-dev/observations/skill-tool-events.jsonl`에 남긴다. 이름은 봤지만 실제 해결된 출처는 `NOT_VERIFIED`.
- OpenCode의 `.opencode/plugins/tool-usage-observer.js`는 **프로젝트 내부 RTK/CRG를 직접 호출하는 shell 명령**의 메타데이터만 기록한다. 명령·프롬프트·출력·비밀번호·토큰은 기록하지 않는다. 도구 호출 관측 ≠ 성공/결과 정확성/CRG graph freshness.
- 프로젝트 원본 검사 로그는 요약을 위해 삭제하지 않으며, 민감정보를 먼저 검토한다. `docs/tasks/active/<AREA-NNN-descriptive-slug>/tool-evidence.md` (or its completed archive)에는 단계, 사용 여부, 호출 ID, 실제 종료 코드·그래프 상태, 원본 증거 경로, RTK 요약 여부를 분리해 기록한다.
- `progress.md`에 실제 단계 시각과 재작업 round를 이벤트마다 기록한다. 기록이 없으면 `NOT_MEASURED`. 원시 로그 경로만 기록하고 비밀 본문을 채팅/관측 이벤트에 싣지 않는다.
- COMPLETE 후 **improver 1회 분석**: 실제 CLI 오류, 반복된 테스트, 단계별 시간·차단/재검증 횟수, 미확인 스킬 출처, CRG/RTK 사용 효율을 평가한다. 출처 없는 추정 절감률 금지. 개선 제안만 남기고 **자동 변경 금지**.
