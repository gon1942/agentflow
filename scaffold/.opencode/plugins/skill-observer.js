// Optional OpenCode native skill-call observer. Project-only, no teamdev or global hooks.
// This sees the skill tool call; it cannot prove which duplicate-name global source was resolved.
import { readFile, mkdir, appendFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';

const NAMES = new Set([
  'brainstorming', 'writing-plans', 'test-driven-development',
  'verification-before-completion', 'requesting-code-review',
  'receiving-code-review', 'systematic-debugging'
]);

export const AgentFlowSkillObserver = async ({ directory }) => ({
  'tool.execute.after': async (input, output) => {
    if (input?.tool !== 'skill') return;
    const name = input?.args?.name ?? input?.args?.skill ?? null;
    const valid = typeof name === 'string' && NAMES.has(name);
    let sha256 = null;
    if (valid) {
      try {
        const bytes = await readFile(join(directory,'.opencode','skills',name,'SKILL.md'));
        sha256 = createHash('sha256').update(bytes).digest('hex');
      } catch { /* Missing project-local copy: no silent global fallback. */ }
    }
    // Include NO output, prompt, shell commands or other tool args; they may contain secrets.
    const event = {
      type: 'NATIVE_SKILL_TOOL_CALL_OBSERVED',
      timestamp: new Date().toISOString(),
      session_id: typeof input.sessionID === 'string' ? input.sessionID : null,
      call_id: typeof input.callID === 'string' ? input.callID : null,
      skill: valid ? name : 'UNKNOWN',
      project_local_sha256: sha256,
      source_resolution: 'NOT_VERIFIED',
      note: 'Tool call observed, resolved source and actual instruction adherence not proven'
    };
    try {
      const base = join(directory,'.ai-dev','observations');
      await mkdir(base,{recursive:true});
      await appendFile(join(base,'skill-tool-events.jsonl'),JSON.stringify(event)+'\n','utf8');
    } catch { /* Observation failure must not cause a false workflow PASS. */ }
  }
});
