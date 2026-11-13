import sys,json,urllib.request,urllib.error,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.server import make_handler
from scaffold.agentflow_console import ai, advisor
fixture=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active');fixture.setUp()
server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(fixture.manager,'e2e-token'))
threading.Thread(target=server.serve_forever,daemon=True).start()
errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1600,'height':950})
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('dialog',lambda d:d.accept())
  def bridge(source,path,data=None):
   payload=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
   headers={'X-AgentFlow-Token':'e2e-token','Host':f'127.0.0.1:{server.server_port}','Content-Type':'application/json'}
   req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',data=payload,headers=headers,method='POST' if payload else 'GET')
   try:
    with urllib.request.urlopen(req,timeout=20) as resp:return {'status':resp.status,'body':json.loads(resp.read())}
   except urllib.error.HTTPError as e:return {'status':e.code,'body':json.loads(e.read())}
  page.expose_binding('nativeBridge',bridge)
  page.goto('about:blank#token=e2e-token')
  content=(root/'scaffold/agentflow_console/ui.html').read_text().replace('<script>','''<script>window.fetch=async function(path,args){let data=args?.body?JSON.parse(args.body):null;const r=await window.nativeBridge(path,data);return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}})}</script><script>''',1)
  page.set_content(content,wait_until='domcontentloaded')
  page.wait_for_function("document.getElementById('topState').textContent==='READY'",timeout=15000)
  page.locator('#menu button[data-page="skills"]').click()
  page.locator('#aiQuestion').fill('구현을 위한 요구사항 분석과 작업 계획 스킬 추천')
  page.locator('#aiExternalSearch').uncheck()
  class Result:
   returncode=0;stderr=b''
   stdout=json.dumps({'summary':'추천 완료','recommendations':[{'name':'brainstorming','origin':'local','stages':['ANALYZE'],'reason':'test'},{'name':'requirements-analysis','origin':'external','stages':['ANALYZE'],'reason':'requirements analysis'}]},ensure_ascii=False).encode()
  with patch.object(ai.shutil,'which',return_value='/usr/bin/opencode'),patch.object(ai.subprocess,'run',return_value=Result()):
   page.get_by_role('button',name='AI에게 스킬 추천 요청').click()
   page.wait_for_function("document.getElementById('advisorRuns').options.length>0",timeout=15000)
  assert '실행 ID:' in page.locator('#advisorAssessment').inner_text()
  assert 'HOST_SUGGESTION' in page.locator('#advisorTraceView').inner_text()
  assert 'POLICY_ASSESSMENT' in page.locator('#advisorTraceView').inner_text()
  assert page.locator('#aiCandidateList').get_by_text('requirements-analysis').count()>0
  page.locator('.advisor-trace-panel').screenshot(path='/mnt/data/agentflow-v064-trace-ui.png')
  assert not errors,errors
  print('BROWSER PASS: live server AI suggestion -> trace persisted -> browser log UI, policy assessment, no JS errors')
  browser.close()
finally:
 server.shutdown();server.server_close();fixture.doCleanups()
