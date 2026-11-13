# AgentFlow v1.0.1 — Documentation hygiene patch

Status: **release candidate / Gate 2 not approved**. This is a packaging/documentation patch on v1.0.0, not a functional architecture change. npm Registry publication was **NOT_RUN**.

## Scope

- Keep `README.md` as the **only Markdown at source/package root**. Consolidate npm, npx, Python and Project Architect usage; remove obsolete old-release references.
- Exclude 72 historical Markdown files from v1.0.1 source distribution. The unchanged v1.0.0 ZIP remains the archive of those historical notes.
- Move the **current** release notes, change log, and verification report to `release/` in source ZIP, while also providing them as standalone files. They are deliberately excluded from npm tarball to keep its runtime documentation minimal.
- Remove obsolete root `SHA256SUMS.txt`, `RC4-VALIDATION.txt`, `TEST-EVIDENCE-1.0.0.txt` and old RC browser preview. Rebuild v1.0.1 checksums in separate delivery artifact.
- Update `package.json` to `1.0.1`, the installed `scaffold/.ai-dev/distribution.json`, and version-specific tests. The npm package still exposes `@gon1942/agentflow`.
- Preserve **all 99 operational scaffold files**, with only the installed distribution version metadata updated. Project profiles, work steps, gates, templates, agents, plugins and runtime CLI are otherwise byte-for-byte unchanged from v1.0.0.

## Availability

A verified locally built `.tgz` is provided. This build environment did **not** publish it to npm. The public npx command needs the owner to publish the matching package version.

## Unchanged limitations

No claim of OpenCode / Claude Code / Codex native E2E, live GitHub upstream installation or independent reviewer approval. Refer to `VALIDATION-1.0.1.md` for executed tests.
