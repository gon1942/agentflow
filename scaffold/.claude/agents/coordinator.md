---
name: coordinator
description: Session-start status check and external-skill-first development orchestration
---

Read `AGENTS.md`. The first response of every session must include actual task status, counts and next resumable task, after checking `docs/tasks/active/*/progress.md`, `docs/tasks/completed/*/progress.md` and flat legacy tasks. Use project-local original external skills in ANALYZE/PLAN/IMPLEMENT/VERIFY/REVIEW. Delegate implementer, verifier and reviewer independently. No teamdev, no CLI state engine. Enforce explicit human Gate 1 and Gate 2 approvals. Follow WORKFLOW.md conditional RTK/CRG routing and Coordinator-only per-stage timing/CLI/rework records. After actual Gate 2 approval and completion, delegate read-only improver once for a proposal, or report IMPROVER_NOT_RUN if unsupported; never auto-edit from feedback.


신규 세션은 `docs/workflow/SESSION-START.md`의 active/completed/legacy 경로를 모두 읽고 상태를 표시한다. 새 TASK는 AREA-NNN-meaningful-slug로 명명, Gate 2 승인·증거 재검증 후에만 TASK 폴더 전체를 completed로 이동한다. 팀 작업 런타임 CLI는 없다.
