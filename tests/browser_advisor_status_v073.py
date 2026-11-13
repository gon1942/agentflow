"""Browser E2E of loading, double-click prevention, success and retry after failure."""
import sys,json,threading,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.server import make_handler
fixture=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active');fixture.setUp()
server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(fixture.manager,'e2e-token'))
threading.Thread(target=server.serve_forever,daemon=True).start()
errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1500,'height':980})
  page.on('pageerror',lambda e:errors.append(str(e)))
  def bridge(source,path,data=None):
   payload=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
   headers={'X-AgentFlow-Token':'e2e-token','Host':f'127.0.0.1:{server.server_port}','Content-Type':'application/json'}
   req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',data=payload,headers=headers,method='POST' if payload else 'GET')
   try:
    with urllib.request.urlopen(req,timeout=20) as resp:return {'status':resp.status,'body':json.loads(resp.read())}
   except urllib.error.HTTPError as e:return {'status':e.code,'body':json.loads(e.read())}
  page.expose_binding('nativeBridge',bridge)
  page.goto('about:blank#token=e2e-token')
  hook='''<script>window.__aiCallCount=0;window.__settleAI=null;
window.fetch=async function(path,args){
  if(path==='/api/ai/suggest'){
    window.__aiCallCount++;
    return new Promise((resolve,reject)=>{window.__settleAI=(ok)=>{
      if(ok) resolve(new Response(JSON.stringify({profile:'development',stage:'ANALYZE',summary:'완료',suggestion:'example',recommendations:[],run_id:'test-run'}),{status:200,headers:{'Content-Type':'application/json'}}));
      else reject(new Error('synthetic network error'));
    }});
  }
  let d=args?.body?JSON.parse(args.body):null;
  const r=await window.nativeBridge(path,d);
  return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}});
};</script><script>'''
  content=(root/'scaffold/agentflow_console/ui.html').read_text().replace('<script>',hook,1)
  page.set_content(content,wait_until='domcontentloaded')
  page.wait_for_function("document.getElementById('topState').textContent==='READY'",timeout=15000)
  page.locator('#menu button[data-page="skills"]').click()
  page.locator('#aiQuestion').fill('요구사항 분석 스킬을 추천해줘')
  page.locator('#aiSuggestButton').click()
  page.wait_for_function('window.__aiCallCount===1')
  assert page.locator('#aiSuggestButton').is_disabled()
  assert '진행 중' in page.locator('#aiSuggestStatus').inner_text()
  page.evaluate('suggestSkills()')
  assert page.evaluate('window.__aiCallCount')==1
  page.screenshot(path='/mnt/data/agentflow-v073-advisor-progress.png')
  page.evaluate('window.__settleAI(true)')
  page.wait_for_function("document.getElementById('aiSuggestStatus').textContent.includes('완료')")
  assert page.locator('#aiSuggestButton').is_enabled()
  page.locator('#aiSuggestButton').click()
  page.wait_for_function('window.__aiCallCount===2')
  assert page.locator('#aiSuggestButton').is_disabled()
  page.evaluate('window.__settleAI(false)')
  page.wait_for_function("document.getElementById('aiSuggestStatus').textContent.includes('실패')")
  assert page.locator('#aiSuggestButton').is_enabled()
  assert '추천 실행 실패:' in page.locator('#aiResult').inner_text()
  assert not errors,errors
  print('BROWSER PASS: loading visible, no duplicate, success, failure, retry enabled')
  browser.close()
finally:
 server.shutdown();server.server_close();fixture.doCleanups()
