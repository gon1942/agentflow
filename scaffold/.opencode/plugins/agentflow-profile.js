// Project-local profile bridge. V2 prompt hook where supported; V1 session discovery fallback.
// Does not change TASK approval or dispatch workers.
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { existsSync } from 'node:fs';

function resolveLocal(root, sessionID, prompt = null) {
  if (!root || !sessionID || !existsSync(join(root, 'agentflow_console.py'))) return null;
  const args = ['agentflow_console.py', 'agent-event', '--host', 'opencode', '--session-id', String(sessionID), '--stdin-json'];
  const done=spawnSync('python3',args,{cwd:root,encoding:'utf8',input:JSON.stringify({prompt}),timeout:5000,maxBuffer:65536});
  if (done.error || done.status !== 0) throw new Error('AgentFlow profile bridge blocked: ' + (done.stderr || done.error?.message || done.status));
  return JSON.parse(done.stdout);
}
export const AgentFlowProfile = async (ctx) => {
  const root=ctx.directory;
  // OpenCode V2: native prompt-admission hook, which can add stable routing context.
  if (ctx.session?.hook) {
    await ctx.session.hook('prompt',async event=>{
      const prompt = event.prompt?.text || '';
      const x=resolveLocal(root,event.sessionID,prompt);
      if (!x) return;
      event.prompt.text += '\n\n[AgentFlow session contract — runtime generated]\n' +
        'Profile: '+(x.profile||'UNKNOWN')+'; session: '+x.session_id+'; configuration_sha256: '+(x.configuration_sha256||'')+'\n'+x.instruction;
    });
  }
  return {
    // Earlier OpenCode SDK: refresh context at each system-prompt transform when the hook exists.
    'experimental.chat.system.transform': async (input, output) => {
      const id=input?.sessionID;
      if (!id || !Array.isArray(output?.system)) return;
      const x=resolveLocal(root,id);
      if (x) {
        const instruction = 'AgentFlow session='+x.session_id+' profile='+x.profile+' contract='+x.configuration_sha256+'\n'+x.instruction;
        // Some OpenAI-compatible model providers accept only one leading system block.
        // Do not append a second system message. Keep original system first.
        if (output.system.length > 0 && typeof output.system[0] === 'string') {
          if (!output.system[0].includes(instruction)) output.system[0] += '\n\n' + instruction;
        } else if (output.system.length === 0) {
          output.system.push(instruction);
        } else {
          // Fail closed on an unexpected system message shape: no mutation.
          throw new Error('AgentFlow: unsupported system message representation');
        }
      }
    },
    // Earlier OpenCode plugin API exposes session events; discover on session create.
    event: async ({event})=>{
      if(event?.type!=='session.created') return;
      const id=event.properties?.info?.id || event.properties?.id;
      if(id) resolveLocal(root,id);
    },
  };
};
