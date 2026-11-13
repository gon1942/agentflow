# AgentFlow 5-Profile contract (v0.7.7)

| ID (immutable) | UI name | Stage selection | Document output |
|---|---|---|---|
| `lifecycle-dev` | Full Lifecycle | ANALYZE → PLAN → GATE1 → IMPLEMENT → VERIFY → REVIEW → GATE2 → COMPLETE | task/code/evidence; **legacy ID retained** |
| `project-architect` | Project Architect | ANALYZE → PLAN → GATE1 → DESIGN (internal IMPLEMENT) → VERIFY → REVIEW → GATE2 → COMPLETE | `docs/requirements`, `docs/architecture` |
| `storyboard` | Storyboard | Existing scope unchanged | `docs/design`, `docs/storyboards` |
| `task-planning` | Task Planning | Existing scope unchanged | `docs/tasks/active/<TASK-ID>` |
| `development-worker` | Development | IMPLEMENT → VERIFY → REVIEW | source/test/review evidence; task remains awaiting Gate2 |

## Security and handoff

- Active selectable Profiles: `lifecycle-dev`, `development-worker`, `project-architect`, `storyboard`, `task-planning`. Legacy `development` stays hidden but readable for old TASK contracts.

- The `development` ID stays available only for historical immutable contract lookup. New TASKs select `lifecycle-dev`, while `development-worker` is the approved implementation/verification/review worker.
- New `development-worker` must only operate on a **Gate1-approved** TASK with an existing verified plan. A `PLAN_READY` handoff is `WAITING_PLAN_APPROVAL`, **not** approval. Coordinator/state machine manages approval and final archive; the worker has no authorization to approve or complete.
- Profile change never changes the profile pinned to a running TASK. Session Rotation must carry the existing profile ID, digest, approval state and task identity unchanged.
- Architect DESIGN is a **UI label** for IMPLEMENT stage; no new state enum. Deliverables are documents; no implementation claim.
- OpenCode, Claude, Codex share docs/README.md, AGENTS.md and this contract. CLI syntax can differ across hosts.
- External skills are optional until verified installed locally; never report an unused skill as executed.
