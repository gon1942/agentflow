# 프로젝트 전용 스킬 잠금

`external-skills.lock.json`은 최초 설치 시 생성되며, 7개 필수 외부 스킬의 Git blob sha1과 **모든 설치 보조 파일**의 SHA256을 기록한다. 다른 프로젝트의 글로벌 스킬을 참조하지 않는다. 외부 스킬의 설치만으로 실제 에이전트 사용을 보증하지 않는다. 이 프로젝트에는 `teamdev`, CLI 상태 머신, 프로세스 서버가 없다.

## Skill Studio 관리 콘솔

프로젝트에 포함된 `agentflow_console.py`는 Profile·Skill Tree·스킬 설치를 위한 **별도 로컬 관리 CLI**이다. 기존의 `teamdev`나 워크플로 실행 엔진을 추가하지 않는다. `python3 agentflow_console.py start --browser`로 127.0.0.1 전용 웹 콘솔을 실행할 수 있다. CLI: `status`, `contract`, `profiles`, `trees`, `skills`, `clone`, `activate`, `inspect`, `install`. 오프라인 로컬 폴더·ZIP 등록 지원, 자동 실행은 하지 않는다. AI/온라인 Git 소스 자동 검색은 별도 검증이 끝날 때까지 미지원. 스킬 저장소는 기존 `.ai-dev/external-skills.lock.json` 하나를 사용한다.
