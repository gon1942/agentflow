# AgentFlow v1.0.1 — Change log

## Added
- Documentation hygiene contract tests (`tests/npm/docs_hygiene.test.cjs`).
- Release-scoped reports under `release/` in the source bundle.

## Changed
- `package.json`: `1.0.0` → `1.0.1`; restrict root npm Markdown to `README.md`.
- `README.md`: consolidate npx/Python installer, safeguards and external-skill guidance.
- `scaffold/.ai-dev/distribution.json`: reflect installed distribution version `1.0.1`.
- `tests/npm/{cli,tarball_e2e,package}.test.cjs`: version and minimal docs assertions.

## Excluded from v1.0.1 source root
- 72 obsolete/historical Markdown files (RC notes, older release notes, older validation reports and duplicate README guides).
- Stale historical root checksums, RC validation text, v1.0.0 test summary and old UI preview image.

## Explicitly preserved
- 99/99 scaffold files; no deleted runtime docs, stage templates, skill descriptions, AGENTS.md, CLAUDE.md, profiles or agent scripts.
- npm CLI command contract (`init`, `upgrade`, `doctor`); Python installation logic and pinned upstream-skill verification remain unchanged.
- Original v1.0.0 package as a recovery source for historical materials.
