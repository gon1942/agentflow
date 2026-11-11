# AgentFlow Native Skills + Tools + Improver v0.4.0 RC — verification report

## What changed

- Meaningful task names: `AREA-NNN-english-kebab-slug`; read-only `suggestTaskName` checks active, completed and flat legacy folders for collisions.
- TASK storage: `docs/tasks/active/<task>/`; after actual Gate 2 user approval, the entire TASK directory is moved to `docs/tasks/completed/<task>/`. Plan, evidence, and approval are kept together; overwrite and archive-on-failure forbidden by coordinator instruction.
- New sessions: read-only `session-status.js` scans active/completed/flat legacy tasks, counts progress/approval/blocked/completed and displays next tasks. Folder/status mismatches, duplicate IDs, missing progress, missing Gate 2 approval or hashes, and stale hashes are classified BLOCKED.
- Gate 2 records must contain Spec, Plan, verification and review SHA-256 that match current files. This is file integrity validation, **not authenticated human approval**. Coordinator must also verify actual user reply, the authorized plan and fresh independent Worker execution.
- Existing seven pinned external skills, project-local RTK/CRG/browser, optional Improver, two human gates, and **no teamdev/custom workflow CLI** retained.

## Actual executed checks (this release environment)

| Test | Result | Boundary |
| --- | --- | --- |
| Python unittest full suite | 40/40 PASS | 28 prior tests + 12 new task lifecycle tests |
| Python syntax/compileall | PASS | installer, provisioning and tests |
| Node plugin syntax checks | PASS | three project-local plugins |
| New-project installer with pinned hash fixtures | PASS | offline fixture, no live upstream fetch |
| Real Node login functional tests | PASS | Node subprocess, login success/failure/404; Worker and user approvals are simulated |
| Simulated Gate 2 + real native filesystem archive | PASS | full TASK folder movement preserves plan/evidence, newly started session recognizes completed task |
| Negative cases: no approval, missing hash, tampered verification, bad folder, duplicated ID, unreadable progress | PASS | read-only scanner reports BLOCKED |
| Same-task defect → correction → re-verification | PASS | actual Node command; agents and approval events synthetic |
| ZIP unpack → full test suite | PASS | tested from final packaged copy |

## NOT VERIFIED (required before stable release)

- Actual OpenCode, Claude Code, or Codex native worker dispatch and external skill-load traces: **NOT_VERIFIED** (native agents unavailable in release environment).
- Live upstream Superpowers GitHub download, project-local RTK/CRG/browser installation from network: **NOT_VERIFIED** (test uses pinned, locally generated fixture).
- Genuine human Gate 1 and Gate 2 approval, host-enforced policy: **NOT_VERIFIED**.
- Live Chrome browser login E2E, entire real agent user request → completion, and performance comparison: **NOT_VERIFIED**.
- Multi-session concurrent write protection: **not provided**; single coordinator writer required. Markdown is not an authenticated approval database.

**Release quality: RC only, not production/stable signoff.** Do not infer an actual agent E2E PASS from fixture-based contract tests.
