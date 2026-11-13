'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const read = rel => fs.readFileSync(path.join(root, rel), 'utf8');

test('v1.0.1 release metadata and minimal root documentation', () => {
  const pkg = JSON.parse(read('package.json'));
  assert.equal(pkg.version, '1.0.1');
  const dist = JSON.parse(read('scaffold/.ai-dev/distribution.json'));
  assert.equal(dist.version, pkg.version, 'installed distribution metadata must match npm version');
  const rootMarkdown = fs.readdirSync(root).filter(f => f.endsWith('.md')).sort();
  assert.deepEqual(rootMarkdown, ['README.md']);
  assert.match(read('README.md'), /v1\.0\.1/);
  assert.doesNotMatch(read('README.md'), /\]\((?:RELEASE-NOTES-0\.|VALIDATION-0\.|README-NPX\.md|MULTI-PROFILE-GUIDE\.md)/);
  for (const f of ['release/RELEASE-NOTES-1.0.1.md','release/CHANGELOG-1.0.1.md','release/VALIDATION-1.0.1.md']) {
    assert.ok(fs.existsSync(path.join(root,f)), `${f} missing`);
  }
  assert.ok(!fs.existsSync(path.join(root,'SHA256SUMS.txt')), 'stale historical digest list must not ship');
});

test('npm file allowlist includes only README as top-level Markdown', () => {
  const pkg = JSON.parse(read('package.json'));
  const topLevelMd = pkg.files.filter(f => !f.includes('/') && f.endsWith('.md'));
  assert.deepEqual(topLevelMd, ['README.md']);
  assert.ok(pkg.files.includes('scaffold/docs/workflow/WORKFLOW.md'));
  assert.ok(pkg.files.includes('scaffold/docs/workflow/APPROVALS.md'));
  assert.ok(pkg.files.includes('scaffold/docs/templates/task/plan.md'));
  assert.ok(pkg.files.includes('scaffold/.opencode/agents/coordinator.md'));
  assert.ok(pkg.files.includes('scaffold/.claude/agents/verifier.md'));
});

test('installed scaffold retains all operational Markdown files and profile configuration', () => {
  for (const f of ['scaffold/AGENTS.md','scaffold/CLAUDE.md',
    'scaffold/docs/workflow/WORKFLOW.md','scaffold/docs/workflow/APPROVALS.md',
    'scaffold/docs/workflow/PROFILE-CONTRACTS.md','scaffold/docs/templates/task/spec.md',
    'scaffold/.agents/skills/agentflow-mngr/SKILL.md',
    'scaffold/.agentflow/skill-trees/project-architect.json',
    'scaffold/.agentflow/skill-trees/development-worker.json']) {
    assert.ok(fs.existsSync(path.join(root,f)),`runtime file missing: ${f}`);
  }
});
