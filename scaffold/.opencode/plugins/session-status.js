// Load-safe entrypoint: only plugin factory is exported. Utilities live outside auto-loaded plugins.
import {readProjectStatus,findGlobalSkillConflicts} from '../lib/session-status.js';
export const AgentFlowSessionStatus=async ({client,directory})=>({
  event:async ({event})=>{
    if(event?.type!=='session.created')return;
    try{
      const status=await readProjectStatus(directory);const conflicts=await findGlobalSkillConflicts(directory);
      const warning=conflicts.length?`\n전역 동명 스킬 충돌 위험: ${conflicts.join(', ')}`:'';
      await client.tui.showToast({body:{message:`AgentFlow 작업 상태: ${status.summary}\n${status.next}${warning}`.slice(0,900),variant:conflicts.length?'warning':'info',duration:12000}});
    }catch{/* Unsupported TUI/headless: Coordinator must show chat status. */}
  }
});
