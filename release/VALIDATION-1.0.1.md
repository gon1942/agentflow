# AgentFlow v1.0.1 — Actual verification report

Status: **partial verified release candidate**, Gate 2 pending. Executed locally on Node v22.16.0, npm 10.9.2, Python 3.13.5. This report only reflects commands actually run in the build environment.

## Red / Green TDD

- A new doc-hygiene test was executed against the unmodified v1.0.0 metadata and historical Markdown layout. Test run **FAIL** as expected: root had 72 extra Markdown files; npm packaging included obsolete root docs.
- After changes, the test passed: **3/3 PASS**.
- A second failing test caught the stale installed distribution version `1.0.0`; updating `scaffold/.ai-dev/distribution.json` made it pass.

## Verified

1. `npm run test:cli`: **11/11 PASS** (includes package dry-run and an actual local `.tgz` npx install through a synthetic offline Python fixture). This fixture simulates external upstream and does **not** prove real source installation.
2. Python focused regression, run as `python3 -m unittest discover -s tests -p '<module>.py' -q` individually for ten modules: **78/78 PASS**. Modules: test_install (9), test_architect_sources_v082 (10), test_project_architect_external_v081 (3), test_stage_choice_v080 (8), test_five_profiles_v076 (10), test_default_three_profiles (4), test_security_and_tools (11), test_independent_stage_v056 (12), test_unified_stages_v078 (10), test_upgrade_v080 (1).
3. Scaffold comparison against v1.0.0: **99 same-path files**; 98 hash-identical; only `.ai-dev/distribution.json` version field changed. No runtime scaffold files deleted or added.
4. `npm pack --dry-run --json`: root Markdown contains **only README.md**; operational Markdown files are included in `scaffold/`.

## Not verified / constraints

- Full legacy Python test discovery: **NOT_RUN** for v1.0.1. The 78 focused PASS cases do not establish whole-suite regression PASS.
- Real GitHub upstream acquisition and native AgentFlow install: **NOT_RUN**. Only offline synthetic fixture integration passed.
- Native OpenCode / Claude Code / Codex skill invocation: **NOT_RUN**.
- Actual browser E2E: **NOT_RUN**.
- Independent verifier/reviewer agent review: **NOT_RUN**.
- npm Registry publication, public `npx @gon1942/agentflow@1.0.1` invocation: **NOT_RUN**. No authenticated publishing action was performed.
- User Gate 2 approval: **PENDING**.

The source ZIP and npm tarball checksums are recorded in the separately shipped SHA256SUMS file. The npm package intentionally excludes archived release reports and obsolete version documents.
