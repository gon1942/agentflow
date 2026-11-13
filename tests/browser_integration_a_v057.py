import sys,json,urllib.request,urllib.error,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.server import make_handler
fixture=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active');fixture.setUp()
server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(fixture.manager,'e2e-token'))
th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1680,'height':1000}, device_scale_factor=1)
  page.on('pageerror',lambda e:errors.append(str(e)))
  def bridge(source,path,data=None):
   data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
   headers={'X-AgentFlow-Token':'e2e-token','Host':f'127.0.0.1:{server.server_port}','Content-Type':'application/json'}
   req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',data=data,headers=headers,method='POST' if data else 'GET')
   try:
    with urllib.request.urlopen(req,timeout=10) as resp:return {'status':resp.status,'body':json.loads(resp.read())}
   except urllib.error.HTTPError as e:return {'status':e.code,'body':json.loads(e.read())}
  page.expose_binding('nativeBridge',bridge)
  page.on('dialog',lambda d:d.accept())
  page.goto('about:blank#token=e2e-token')
  content=(root/'scaffold/agentflow_console/ui.html').read_text()
  content=content.replace('<script>','''<script>
   window.fetch=async function(path,args){let data=args?.body?JSON.parse(args.body):null;const result=await window.nativeBridge(path,data);return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}})};
  </script><script>''',1)
  page.set_content(content,wait_until='domcontentloaded')
  page.wait_for_function("document.getElementById('topState').textContent==='READY'",timeout=15000)
  page.click('button[data-page="trees"]')
  page.select_option('#treeSelect','task-planning')
  assert page.locator('.studio-flow-item').count()==9
  assert page.locator('.studio-stage-row').count()==8
  assert page.locator('.studio-branch').count()==2
  assert 'writing-plans' in page.locator('#treeStageOverview').inner_text()
  assert page.locator('input[aria-label="IMPLEMENT 단계 사용"]').is_checked()==False
  page.locator('input[aria-label="IMPLEMENT 단계 사용"]').check()
  page.wait_for_function("document.querySelector('input[aria-label=\"IMPLEMENT 단계 사용\"]')?.checked===true",timeout=5000)
  assert fixture.manager.profile('task-planning')['enabled_stages']==['ANALYZE','PLAN','IMPLEMENT','VERIFY','COMPLETE']
  page.locator('input[aria-label="IMPLEMENT 단계 사용"]').uncheck()
  page.wait_for_function("document.querySelector('input[aria-label=\"IMPLEMENT 단계 사용\"]')?.checked===false",timeout=5000)
  assert fixture.manager.profile('task-planning')['enabled_stages']==['ANALYZE','PLAN','VERIFY','COMPLETE']
  page.locator('.studio-stage-row').filter(has_text='ANALYZE').click()
  assert 'brainstorming' in page.locator('#stageSkillList').inner_text()
  # Add installed skill to PLAN from library and save via real API.
  page.locator('.studio-stage-row').nth(1).click()
  page.locator('#studioSkillSearch').fill('brainstorming')
  page.locator('.studio-library-item button').first.click()
  assert '스킬 변경 미저장' in page.locator('#studioDirty').inner_text()
  page.locator('#trees .studio-head-actions button.primary').click()
  page.wait_for_function("document.getElementById('studioDirty').textContent.includes('저장됨')",timeout=5000)
  assert 'brainstorming' in [x['name'] for x in next(s for s in fixture.manager.tree('task-planning')['stages'] if s['id']=='PLAN')['skills']]
  # Change it to optional and remove it; save again.
  page.locator('#stageSkillList .studio-linked-item').filter(has_text='brainstorming').get_by_role('button',name='연결 해제').click()
  page.locator('#trees .studio-head-actions button.primary').click()
  page.wait_for_timeout(100)
  assert 'brainstorming' not in [x['name'] for x in next(s for s in fixture.manager.tree('task-planning')['stages'] if s['id']=='PLAN')['skills']]
  page.screenshot(path=str(root/'integration-a-browser-preview.png'),full_page=True)
  assert not errors,errors
  print('BROWSER PASS: eight stage cards, nine flow items, conditional toggles, persisted stage on/off, linked skills and library add/remove persisted via real API, no JS errors')
  browser.close()
finally:
 server.shutdown();server.server_close();fixture.doCleanups()
