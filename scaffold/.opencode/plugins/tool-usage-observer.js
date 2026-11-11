// Minimal metadata-only observation of project-local auxiliary CLI invocations.
// NOT a tool execution verifier, not proof of result or graph freshness.
import { mkdir, appendFile } from 'node:fs/promises';
import { join } from 'node:path';

const RTK = /^(?:\.\/)?\.ai-dev\/tools\/rtk\/bin\/rtk(?:\s|$)/;
const CRG = /^(?:\.\/)?\.ai-dev\/tools\/crg-venv\/bin\/code-review-graph(?:\s|$)/;
function recognize(command, directory) {
  if (typeof command !== 'string') return null;
  // Only a project-local executable appearing at the start of a direct shell invocation.
  // If the command is wrapped by cd/tee/sh, emit no observation rather than guess.
  const trimmed = command.trimStart();
  const absolutePrefix = directory ? directory.replace(/\/$/, '') + '/' : '';
  const local = absolutePrefix && trimmed.startsWith(absolutePrefix)
    ? trimmed.slice(absolutePrefix.length) : trimmed;
  if (RTK.test(local)) return 'RTK_DIRECT_COMMAND_OBSERVED';
  if (CRG.test(local)) return 'CRG_DIRECT_COMMAND_OBSERVED';
  return null;
}

export const AgentFlowToolUsageObserver = async ({ directory }) => ({
  'tool.execute.after': async (input) => {
    if (input?.tool !== 'bash') return;
    const category = recognize(input?.args?.command, directory);
    if (!category) return;
    const event = {
      type: category,
      timestamp: new Date().toISOString(),
      session_id: typeof input.sessionID === 'string' ? input.sessionID : null,
      call_id: typeof input.callID === 'string' ? input.callID : null,
      scope: 'PROJECT_ONLY',
      outcome: 'NOT_VERIFIED',
      note: 'Direct command invocation matched; shell exit, program output and graph freshness not proven'
    };
    try {
      const base = join(directory, '.ai-dev', 'observations');
      await mkdir(base, { recursive: true });
      await appendFile(join(base, 'project-tool-events.jsonl'), JSON.stringify(event) + '\n', 'utf8');
    } catch { /* Fail silent: missing observation must never count as a PASS. */ }
  }
});
