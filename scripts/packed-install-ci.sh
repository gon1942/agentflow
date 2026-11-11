#!/usr/bin/env bash
# CI integration test: actual npm pack -> npx install, original upstream pinned bytes, project-only paths.
# Explicit TEST-ONLY_SKIP_TOOLS: CI still checks Node/Python packaging, skills and session plugin.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$ROOT"
TAR="$(npm pack --pack-destination "$TMP" --silent)"
COMMIT=22f0b463e7a5e579904dd6211a520321035526f7
curl --fail --location --silent --show-error --max-time 100 \
 "https://codeload.github.com/obra/superpowers/zip/$COMMIT" -o "$TMP/upstream.zip"
AGENTFLOW_TEST_ONLY_SKIP_TOOLS=1 \
  npm exec --yes --package "$TMP/$TAR" -- agentflow init "$TMP/project" \
  --upstream-zip "$TMP/upstream.zip" --skip-tools
[[ -f "$TMP/project/.agents/skills/requesting-code-review/code-reviewer.md" ]]
[[ -f "$TMP/project/.opencode/plugins/package.json" ]]
[[ -d "$TMP/project/docs/tasks/active" ]]
[[ -d "$TMP/project/docs/tasks/completed" ]]
[[ ! -e "$TMP/project/teamdev" ]]
AGENTFLOW_TEST_ONLY_SKIP_TOOLS=1 \
  npm exec --yes --package "$TMP/$TAR" -- agentflow init "$TMP/project" \
  --upstream-zip "$TMP/upstream.zip" --skip-tools | grep -q '"written_files": 0'
printf 'PACKED_INSTALL_PASS (tool provisioning deliberately skipped; native E2E NOT_VERIFIED)\n'
