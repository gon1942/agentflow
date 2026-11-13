// Project-only read-only task discovery. No workflow CLI or automatic gate transitions.
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { createHash } from 'node:crypto';

export const STATUSES = new Set(['ANALYZE','PLAN','WAITING_PLAN_APPROVAL','IMPLEMENT','VERIFY','REVIEW','WAITING_FINAL_APPROVAL','BLOCKED','COMPLETED']);
const ACTIVE = 'active';
const COMPLETE = 'completed';
const HANDOFF = 'handoffs';
const LEGACY = 'legacy';
const NAME_RE = /^([A-Z][A-Z0-9]{1,19})-(\d{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)$/;
const UPSTREAM_SKILLS = ['brainstorming','writing-plans','test-driven-development','verification-before-completion','requesting-code-review','receiving-code-review','systematic-debugging'];

async function dirs(path) {
  try { return (await readdir(path, {withFileTypes:true})).filter(x=>x.isDirectory() && !x.isSymbolicLink()).map(x=>x.name); }
  catch (e) {if (e?.code === 'ENOENT') return null; throw e;}
}
async function taskItem(root, bucket, name) {
  const base = bucket === LEGACY ? join(root,'docs','tasks',name) : join(root,'docs','tasks',bucket,name);
  let data;
  try { data=await readFile(join(base,'progress.md'),'utf8'); }
  catch { return {bucket,name,status:'BLOCKED',reason:'progress.md 읽기 실패', valid:false}; }
  const fm = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(data)?.[1] ?? '';
  const state = /^status:\s*([A-Z_]+)\s*$/m.exec(fm)?.[1];
  if (!STATUSES.has(state)) return {bucket,name,status:'BLOCKED',reason:'상태 확인 필요',valid:false};
  const explicitId = /^task_id:\s*([^\r\n]+)\s*$/m.exec(fm)?.[1]?.trim();
  // Old flat TASK IDs are accepted as legacy, but cannot be declared archived.
  const idFromName = NAME_RE.exec(name);
  const expectedId = idFromName ? `${idFromName[1]}-${idFromName[2]}` : name;
  if (explicitId && explicitId !== 'TASK-ID' && explicitId !== expectedId && explicitId !== name) {
    return {bucket,name,status:'BLOCKED',reason:'TASK ID / 폴더명 불일치',valid:false};
  }
  if ((bucket === COMPLETE && state !== 'COMPLETED') || (bucket === ACTIVE && state === 'COMPLETED')) {
    return {bucket,name,status:'BLOCKED',reason:'폴더 / status 불일치',valid:false};
  }
  if (state === 'COMPLETED') {
    let approval;
    try { approval=await readFile(join(base,'approvals.md'),'utf8'); }
    catch {return {bucket,name,status:'BLOCKED',reason:'완료 승인 파일 읽기 실패',valid:false};}
    // Do not treat the presence of APPROVED in an arbitrary note as authenticated approval.
    // Coordinator must independently check the actual user message and evidence hashes.
    const gate2=(approval.split(/^##\s*Gate 2\b/m)[1] ?? '').split(/^##\s/m)[0];
    const approved = /^[-*]?\s*(?:상태|status):\s*APPROVED\s*$/mi.test(gate2);
    const skipped = /^[-*]?\s*(?:상태|status):\s*SKIPPED_BY_PROFILE_POLICY\s*$/mi.test(gate2);
    // Specialized planning artifact completion is NOT a development completion.
    // Permit it only with immutable profile snapshot, explicit verified-artifact
    // marker and integrity hashes of the produced files. Do not infer it merely
    // from the absence of a Gate 2 approval.
    const planningOnly = /^(?:completion_subject):\s*PROFILE_DELIVERABLE_ONLY\s*$/m.test(data) &&
      /^profile:\s*(task-planning|storyboard)\s*$/m.test(data) &&
      /^selected_stages:\s*ANALYZE,PLAN,VERIFY,COMPLETE\s*$/m.test(data) &&
      /^verification_status:\s*PASS\s*$/m.test(data) &&
      /^configuration_sha256:\s*[a-fA-F0-9]{64}\s*$/m.test(data);
    if (!approved && !skipped && !planningOnly) {
      return {bucket,name,status:'BLOCKED',reason:'Gate 2 승인 또는 검증된 문서 Profile 완료 근거 확인 필요',valid:false};
    }
    if (planningOnly && !approved && !skipped) {
      for (const [label,file] of [['Spec','spec.md'],['Plan','plan.md'],['verification','verification.md']]) {
        const declared=new RegExp(`^[-*]?\\s*완료 대상 ${label} SHA-256:\\s*([a-fA-F0-9]{64})\\s*$`,'mi').exec(data)?.[1];
        if (!declared || await sha(join(base,file)) !== declared.toLowerCase())
          return {bucket,name,status:'BLOCKED',reason:`문서 Profile ${label} SHA-256 누락/불일치`,valid:false};
      }
      return {bucket,name,status:'COMPLETED',valid:true,completion_scope:'PLANNING_DELIVERABLE_ONLY'};
    }
    if (skipped && !approved) {
      // Only user-defined profiles. Cross-check immutable TASK-start evidence; a
      // missing / inconsistent snapshot cannot turn a missing approval into success.
      const profile = /^[-*]?\s*Profile ID:\s*([a-z][a-z0-9-]*)\s*$/mi.exec(gate2)?.[1];
      const digest = /^[-*]?\s*configuration_sha256:\s*([a-fA-F0-9]{64})\s*$/mi.exec(gate2)?.[1]?.toLowerCase();
      if (!profile || profile === 'development' || profile === 'lifecycle-dev' || !digest ||
          !data.includes(`profile: ${profile}`) || !data.includes(`configuration_sha256: ${digest}`)) {
        return {bucket,name,status:'BLOCKED',reason:'Gate 2 생략 Profile Snapshot 불일치',valid:false};
      }
    }
    // Best-effort static integrity check only. Markdown cannot authenticate the human approver.
    for (const [label,file] of [['Spec','spec.md'],['Plan','plan.md'],['verification','verification.md'],['review','review.md']]) {
      const declared=new RegExp(`^[-*]?\\s*승인 대상 ${label} SHA-256:\\s*([a-fA-F0-9]{64})\\s*$`,'mi').exec(gate2)?.[1];
      if (!declared) return {bucket,name,status:'BLOCKED',reason:`Gate 2 ${label} 해시 누락`,valid:false};
      const actual=await sha(join(base,file));
      if (actual !== declared.toLowerCase()) return {bucket,name,status:'BLOCKED',reason:`Gate 2 ${label} 해시 불일치`,valid:false};
    }
  }
  return {bucket,name,status:state,valid:true};
}
export async function scanTasks(root) {
  const base=join(root,'docs','tasks');
  let rootNames; try {rootNames=await dirs(base);} catch {return {unreadable:true,items:[]};}
  if (!rootNames) return {unreadable:false,items:[]};
  const items=[];
  for (const bucket of [ACTIVE,COMPLETE]) {
    if (!rootNames.includes(bucket)) continue;
    let names; try {names=await dirs(join(base,bucket));} catch {return {unreadable:true,items};}
    for (const name of names ?? []) items.push(await taskItem(root,bucket,name));
  }
  for (const name of rootNames.filter(x=>x!==ACTIVE && x!==COMPLETE && x!==HANDOFF)) {
    if (name.startsWith('.')) continue;
    items.push(await taskItem(root,LEGACY,name));
  }
  // Reused names/IDs must block both copies, including active vs completed and legacy vs new.
  const seen=new Map();
  for (const item of items) {
    const m=NAME_RE.exec(item.name); const id=m?`${m[1]}-${m[2]}`:item.name;
    const previous=seen.get(id);
    if (previous) {
      previous.status='BLOCKED';previous.reason='중복 TASK ID';previous.valid=false;
      item.status='BLOCKED';item.reason='중복 TASK ID';item.valid=false;
    } else seen.set(id,item);
  }
  return {unreadable:false,items};
}
export async function readProjectStatus(root) {
  const {unreadable,items}=await scanTasks(root);
  if (unreadable) return {summary:'작업 상태 미확인',next:'docs/tasks 읽기 실패',items};
  const count={active:0,plan:0,final:0,blocked:0,done:0};
  const next=[];
  for (const item of items) {
    const {name,status,reason,bucket}=item;
    if (status==='COMPLETED') count.done++;
    else if (status==='WAITING_PLAN_APPROVAL') {count.plan++;next.push({priority:0,label:`${name}: 계획 승인 대기`});}
    else if (status==='WAITING_FINAL_APPROVAL') {count.final++;next.push({priority:1,label:`${name}: 최종 승인 대기`});}
    else if (status==='BLOCKED') {count.blocked++;next.push({priority:2,label:`${name}: ${reason ?? '차단'}`});}
    else {count.active++;next.push({priority:3,label:`${name}: ${status}${bucket===LEGACY?' (이전 구조)':''}`});}
  }
  return {summary:`진행 ${count.active} / 계획 승인 대기 ${count.plan} / 최종 승인 대기 ${count.final} / 차단 ${count.blocked} / 완료 ${count.done}`,
    next:next.sort((a,b)=>a.priority-b.priority||a.label.localeCompare(b.label)).slice(0,5).map(x=>x.label).join(' · ')||'현재 대기·진행 TASK 없음',items};
}

// Read-only naming suggestion. Coordinator creates the folder after checking both lists.
export async function suggestTaskName(root, area, description) {
  if (typeof area!=='string' || !/^[A-Z][A-Z0-9]{1,19}$/.test(area)) throw new Error('INVALID_AREA');
  const slug=String(description).trim().toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,64).replace(/-$/,'');
  if (!slug) throw new Error('INVALID_SLUG: provide an English functional description');
  const {unreadable,items}=await scanTasks(root);
  if (unreadable) throw new Error('TASK_SCAN_BLOCKED');
  let max=0;
  for (const item of items) {
    const m=new RegExp(`^${area}-(\\d+)(?:-|$)`).exec(item.name);
    if (m) max=Math.max(max,Number(m[1]));
  }
  const id=`${area}-${String(max+1).padStart(3,'0')}`;
  return {task_id:id,folder:`${id}-${slug}`,relative_path:`docs/tasks/active/${id}-${slug}`};
}

async function sha(path) {try{return createHash('sha256').update(await readFile(path)).digest('hex');}catch{return null;}}
export async function findGlobalSkillConflicts(root,home=homedir()) {
  const locations=[join(home,'.config/opencode/skills'),join(home,'.config/opencode/skill'),join(home,'.opencode/skills'),join(home,'.opencode/skill')];
  const risks=new Set();
  for(const name of UPSTREAM_SKILLS){
    const local=await sha(join(root,'.opencode/skills',name,'SKILL.md'));
    if(!local) continue;
    for(const base of locations){const foreign=await sha(join(base,name,'SKILL.md'));if(foreign&&foreign!==local)risks.add(name);}
  }
  return [...risks].sort();
}
