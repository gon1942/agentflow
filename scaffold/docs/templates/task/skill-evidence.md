# TASK-ID — 외부 스킬 사용 증거

| 단계 | Worker/호출 ID | SKILL.md 프로젝트 내 경로 | SHA-256 | 네이티브 도구 관측 | 실행 근거 | 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| ANALYZE | NOT_VERIFIED | .opencode/skills/brainstorming/SKILL.md | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED |

- 파일 원본 설치/해시 확인 `INSTALL_READY`는 로드/사용 증거가 아님
- 실제 도구 관측은 `TOOL_CALL_OBSERVED`; 파일 출처는 별도 `SOURCE_VERIFIED`
- RTK/CRG 실행 관측은 `tool-evidence.md` 및 `.ai-dev/observations/project-tool-events.jsonl`로 구분한다. 단순 호출 관측은 완료 증거가 아니다.
- Worker 자기 신고만 있으면 `SELF_REPORTED`이며 독립 검증 PASS로 승격 불가
