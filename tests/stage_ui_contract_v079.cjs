const fs=require('fs'), vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(require('path').resolve(__dirname,'../scaffold/agentflow_console/ui.html'),'utf8');
const js=html.split('<script>')[1].split('</script>')[0];
function take(start,end){const i=js.indexOf(start),j=js.indexOf(end,i);assert(i>=0&&j>i,start);return js.slice(i,j)}
const code=[take('const stageSequence=','async function updateStageEnabled('),take('async function updateStageEnabled(','async function setStageScope(')].join('\n');
let saved=null, dialogs=[], feedback=[],confirmed=true;
const base={
 profiles:[
 {id:'lifecycle-dev',name:'Lifecycle Dev',enabled_stages:['ANALYZE','PLAN','GATE1','IMPLEMENT','VERIFY','REVIEW','GATE2','COMPLETE'],skill_tree:'lifecycle-dev'},
 {id:'development-worker',name:'Development Worker',enabled_stages:['IMPLEMENT','VERIFY','REVIEW'],skill_tree:'development-worker'}
 ],trees:[],state:{tasks:[]},
 uiConfirm:async t=>{dialogs.push(t);return confirmed},msg:t=>feedback.push(t),
 api:async (endpoint,payload)=>{if(endpoint==='/api/profile/save')saved=payload},refresh:async()=>{},
 drawTreeOverview:()=>{},studioTree:()=>{},treeParsed:()=>({})
};
vm.createContext(base);vm.runInContext(code,base);
(async()=>{
 await base.updateStageEnabled('development-worker','GATE1',true);
 assert(saved.enabled_stages.includes('GATE1'));
 assert.strictEqual(saved.approval_gates.GATE1,true);
 saved=null;
 await base.updateStageEnabled('lifecycle-dev','VERIFY',false);
 assert(saved&&!saved.enabled_stages.includes('VERIFY'));
 assert(saved.enabled_stages.includes('REVIEW'));
 assert(saved.enabled_stages.includes('GATE2'));
 assert(dialogs.at(-1).includes('다른 단계의 사용 설정은 변경하지 않습니다'));
 saved=null;
 await base.updateStageEnabled('lifecycle-dev','GATE1',false);
 assert(saved&&!saved.enabled_stages.includes('GATE1'));
 assert(saved.enabled_stages.includes('PLAN'));
 assert(saved.enabled_stages.includes('IMPLEMENT'));
 saved=null;
 await base.updateStageEnabled('lifecycle-dev','REVIEW',true);
 assert(saved.enabled_stages.includes('VERIFY'));
 saved=null;confirmed=false;
 await base.updateStageEnabled('lifecycle-dev','VERIFY',false);
 assert.strictEqual(saved,null);
 console.log('STAGE UI USER CHOICE PASS 5 cases: worker gate, independent disable, planned gate, independent enable, cancel');
})().catch(e=>{console.error(e);process.exit(1)});
