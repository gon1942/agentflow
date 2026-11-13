---
name: agentflow-mngr
description: 프로젝트 AgentFlow 관리 콘솔 시작, 종료, 상태 확인. 사용자 지시에서 동작을 구분합니다.
---

AgentFlow 관리 콘솔을 시작하거나 종료합니다. 사용자의 명시적 동작: `$ARGUMENTS`
명령이 start/실행이면 시작하고, stop/종료이면 종료하고, status/상태이면 상태만 확인합니다. 입력이 비어 있거나 다른 문자열이면 선택을 질문하며 **어떠한 셸 명령도 실행하지 않습니다.**

- `/agentflow-mngr start` 또는 `/agentflow-mngr 실행`: `python3 agentflow_console.py start --browser`
- `/agentflow-mngr stop` 또는 `/agentflow-mngr 종료`: `python3 agentflow_console.py stop`
- `/agentflow-mngr status` 또는 `/agentflow-mngr 상태`: `python3 agentflow_console.py console-status`
- 인수가 없으면 시작/종료/상태 중 하나를 먼저 물어봅니다. **무조건 시작하지 않습니다.**
- start는 이미 실행 중인 관리 서버를 재사용합니다.
- stop은 현재 프로젝트에서 AgentFlow가 관리하는 서버만 종료해야 합니다. 다른 프로세스/포트는 건드리지 않습니다.
- 반드시 프로젝트 루트에서 명령 하나만 실행합니다. 토큰·전체 접속 URL은 출력하지 않습니다.
- TASK, Profile, Gate, Skill Tree는 변경하지 않습니다.
