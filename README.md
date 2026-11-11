# AgentFlow Native Skills — npm distribution RC

Project-local external Superpowers 7 pinned skills + native OpenCode / Claude Code / Codex agents, project-local RTK/CRG and browser tools. **No `teamdev`, no workflow CLI, and no central workflow state machine.** This release wraps the validated v0.4.0 installer and does not redesign its development workflow.

## Prerequisites

- Node.js 20+ for npx
- **Python 3.10+ required for installation** (current hardened installer is Python-based)
- Network for pinned upstream Superpowers skills, RTK/CRG and browser packages
- System Chrome for browser smoke (optional `--no-browser`)

## Install

After publication to npm (not yet published):

```sh
npx --yes @gon1942/agentflow@0.5.0-rc.1 init ./my-project
```

For a locally packed artifact (testing before publication):

```sh
npm pack
npx --yes --package ./gon1942-agentflow-0.5.0-rc.1.tgz agentflow init ./my-project
```

Existing project files are never overwritten by default. You may use `--upstream-zip path/to/official-pinned.zip` to supply an authenticated upstream archive without network for skills, but tool installation still requires dependencies unless already cached. No global fallback is permitted. Installer scripts are **not copied into installed projects**.

## Runtime workflow

Request → ANALYZE (`brainstorming`) → PLAN (`writing-plans`) → Gate 1 user approval → IMPLEMENT (`test-driven-development`) → VERIFY (`verification-before-completion`) → REVIEW (`requesting-code-review`) → Gate 2 user approval → COMPLETE. `receiving-code-review` and `systematic-debugging` are conditional. Read `docs/workflow/WORKFLOW.md` in an installed project for the full policy.

Task archives: `docs/tasks/active/` → `docs/tasks/completed/`. New sessions inspect both. Improver is read-only and proposes improvements, never automatically edits code.

## Security / release

- The npm package deliberately does **not** contain globally installed binaries or local secrets. OpenCode plugins use their own `type: module` package boundary even inside CommonJS projects.
- Upstream files are checked against pinned Git blob SHA-1 and helper file hashes; MIT attribution is preserved.
- GitHub Actions PR CI runs unit and packed-package checks. Publishing is a separate manually gated workflow; first release belongs on `next`, not `latest`.
- Do not claim `SKILL_LOADED`, native-worker E2E, Chrome E2E, human approval, or npm publication PASS without actual evidence.

## Test

```sh
npm ci
npm test
npm run test:python
npm pack --dry-run
```

Maintainers: Before public push/publish, confirm repository owner/name and npm scope ownership. The repository URLs in package.json are **proposed**, not verified.

## Release procedure (maintainers)

1. Confirm GitHub owner/repository and npm scope ownership; create a **public** repository, then push only after checking the source for credentials.
2. Configure GitHub branch protection/required CI and an `npm-release` environment requiring manual approval.
3. Create the matching npm package and configure npm Trusted Publishing for the GitHub Actions workflow `publish.yml` (OIDC).
4. Run the packed-install CI and a real local native-worker workflow from request through Gate 2/COMPLETE.
5. Trigger the `Publish approved npm prerelease` workflow to publish `0.5.0-rc.1` to the `next` dist-tag; do not use `latest` until full E2E has passed.
6. From a new folder, verify the published package with `npx --yes @gon1942/agentflow@0.5.0-rc.1 init ./smoke-project`.

The CI packed-install check uses a TEST-ONLY flag to omit tool provisioning so it **does not** establish RTK/CRG/Chrome readiness. Production `init` always attempts those tools.
