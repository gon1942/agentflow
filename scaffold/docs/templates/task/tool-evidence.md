# TASK-ID — 프로젝트 내부 도구 사용 및 판단 근거

| 단계/round | RTK 여부·용도 | 원본 비축약 로그 경로 / 실제 자식 exit | RTK 요약 경로 (선택) | CRG 판단·그래프 최신성 | Browser 실제 실행 | 네이티브 호출 ID/근거 |
| --- | --- | --- | --- | --- | --- | --- |
| ANALYZE/01 | NOT_USED | NOT_APPLICABLE | NOT_RUN | SKIP_EMPTY / GRAPH_FRESHNESS_NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED |

- RTK의 요약은 증거 원본의 대체가 아니다. `rtk gain` 추정치와 전체 토큰·비용 절감률을 혼동하지 않는다.
- CRG는 그래프가 없거나 불필요할 때 SKIP_EMPTY/SKIP_NOT_NEEDED로 기록하며, 설치 READY는 그래프 최신성 증거가 아니다.
- 실제 네이티브 도구 관측은 호출을 봤다는 뜻이며, 종료 코드·실제 출력·AC 판정까지 검증한 뜻이 아니다.
- Verifier의 실제 자식 exit_code와 명령 실행 시각/경로를 VERIFY의 근거로 보존한다. 불명확하면 NOT_VERIFIED.
