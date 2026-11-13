"""Headless actual Chromium UI + loopback server for profile switching while TASK active."""
import sys,threading,json,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.server import make_handler
fx=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active');fx.setUp()
srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(fx.manager,'e2e-token'))
threading.Thread(target=srv.serve_forever,daemon=True).start()
errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1440,'height':1000})
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('dialog',lambda d:d.accept())
  def bridge(source,path,data=None):
   url=f'http://127.0.0.1:{srv.server_port}{path}'
   hdr={'X-AgentFlow-Token':'e2e-token','Host':f'127.0.0.1:{srv.server_port}','Content-Type':'application/json'}
   if data is not None:hdr['Origin']=f'http://127.0.0.1:{srv.server_port}'
   req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers=hdr,method='POST' if data is not None else 'GET')
   try:
    with urllib.request.urlopen(req,timeout=10) as resp:return {'status':resp.status,'body':json.load(resp)}
   except urllib.error.HTTPError as e:return {'status':e.code,'body':json.load(e)}
  page.expose_binding('nativeBridge',bridge)
  page.goto('about:blank#token=e2e-token')
  html=(root/'scaffold/agentflow_console/ui.html').read_text().replace('<script>','''<script>window.fetch=async function(path,args){let d=args?.body?JSON.parse(args.body):null;const r=await window.nativeBridge(path,d);return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}})}</script><script>''',1)
  page.set_content(html,wait_until='domcontentloaded')
  page.wait_for_function("document.getElementById('topState').textContent==='READY'",timeout=15000)
  page.locator('#menu button[data-page="profiles"]').click()
  page.locator('#contextSessionId').fill('opencode-dev')
  page.locator('#contextHost').select_option('opencode')
  page.locator('#contextProfile').select_option('development')
  page.get_by_role('button',name='세션 기본 Profile 설정').click()
  page.wait_for_function("document.getElementById('contextSessions').innerText.includes('opencode-dev')",timeout=10000)
  page.locator('#contextSessionId').fill('claude-plan')
  page.locator('#contextHost').select_option('claude')
  page.locator('#contextProfile').select_option('task-planning')
  page.get_by_role('button',name='세션 기본 Profile 설정').click()
  page.wait_for_function("document.getElementById('contextSessions').innerText.includes('claude-plan')",timeout=10000)
  t=fx.root/'docs/tasks/active/DEV-001';t.mkdir();(t/'task-state.json').write_text(json.dumps({'task_id':'DEV-001','state':'PLAN_DRAFT'}))
  page.evaluate("() => api('/api/task-context/pin',{task_id:'DEV-001',session_id:'opencode-dev'})")
  page.evaluate('refresh()')
  page.wait_for_function("document.getElementById('contextTasks').innerText.includes('DEV-001')",timeout=10000)
  # Project default must switch even with an active TASK.
  page.evaluate("() => api('/api/profile/activate',{profile:'task-planning',generation:1})")
  page.evaluate('refresh()')
  page.wait_for_function("state.active_profile.profile==='task-planning'",timeout=10000)
  assert 'DEV-001 · PLAN_DRAFT · development' in page.locator('#contextTasks').inner_text()
  assert 'opencode-dev' in page.locator('#contextSessions').inner_text()
  assert 'claude-plan' in page.locator('#contextSessions').inner_text()
  page.screenshot(path='/mnt/data/agentflow-v071-multi-profile-browser.png',full_page=False)
  assert not errors,errors
  print('BROWSER PASS: session defaults, pinned task, active TASK project default change, no JS errors')
  browser.close()
finally:
 srv.shutdown();srv.server_close();fx.doCleanups()
