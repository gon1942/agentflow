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
threading.Thread(target=server.serve_forever,daemon=True).start()
errors=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1600,'height':1000})
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('dialog',lambda d:d.accept())
  def bridge(source,path,data=None):
   payload=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
   headers={'X-AgentFlow-Token':'e2e-token','Host':f'127.0.0.1:{server.server_port}','Content-Type':'application/json'}
   req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',data=payload,headers=headers,method='POST' if payload else 'GET')
   try:
    with urllib.request.urlopen(req,timeout=10) as resp:return {'status':resp.status,'body':json.loads(resp.read())}
   except urllib.error.HTTPError as e:return {'status':e.code,'body':json.loads(e.read())}
  page.expose_binding('nativeBridge',bridge)
  page.goto('about:blank#token=e2e-token')
  content=(root/'scaffold/agentflow_console/ui.html').read_text().replace('<script>','''<script>window.fetch=async function(path,args){let data=args?.body?JSON.parse(args.body):null;const r=await window.nativeBridge(path,data);return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}})}</script><script>''',1)
  page.set_content(content,wait_until='domcontentloaded')
  page.wait_for_function("document.getElementById('topState').textContent==='READY'",timeout=15000)
  A='a'*40;B='b'*40
  page.evaluate("""([A,B])=>{renderAiCandidates({recommendations:[{name:'skill-a',origin:'external',stage:'ANALYZE',url:'https://github.com/example/repo-a.git',commit:A,subdir:'skills/a'},{name:'skill-b',origin:'external',stage:'ANALYZE',url:'https://github.com/example/repo-b.git',commit:B,subdir:'skills/b'}]});show('skills')}""",[A,B])
  buttons=page.get_by_role('button',name='Git 소스 검사 화면으로 이동')
  assert buttons.count()==2
  buttons.nth(0).click()
  assert page.locator('#gitCommit').input_value()==A
  # Simulate completed SHA lookup and Git review for A.
  page.evaluate("""()=>{inspectedGit={url:document.getElementById('gitUrl').value,commit:document.getElementById('gitCommit').value,subdir:document.getElementById('gitSubdir').value};document.getElementById('installGitBtn').disabled=false;document.getElementById('gitPreview').textContent='PREVIOUS INSPECTION PASSED'}""")
  assert page.locator('#installGitBtn').is_enabled()
  buttons.nth(1).click()
  assert page.locator('#gitCommit').input_value()==B
  assert page.locator('#gitSubdir').input_value()=='skills/b'
  assert page.locator('#installGitBtn').is_disabled()
  assert 'PREVIOUS INSPECTION PASSED' not in page.locator('#gitPreview').inner_text()
  assert page.evaluate('inspectedGit===null')
  # Re-selecting the same recommendation also discards prior review.
  page.evaluate("""()=>{inspectedGit={url:'old',commit:'old',subdir:'old'};document.getElementById('installGitBtn').disabled=false;document.getElementById('gitPreview').textContent='OLD'}""")
  buttons.nth(1).click()
  assert page.locator('#installGitBtn').is_disabled()
  assert 'OLD' not in page.locator('#gitPreview').inner_text()
  # Manual edits invalidate approval.
  page.evaluate("""()=>{inspectedGit={url:'old',commit:'old',subdir:'old'};document.getElementById('installGitBtn').disabled=false;}""")
  page.locator('#gitSubdir').fill('skills/other')
  assert page.locator('#installGitBtn').is_disabled()
  assert page.evaluate('inspectedGit===null')
  # Late async SHA resolution cannot overwrite a newly selected candidate.
  page.evaluate("""()=>{window.pendingResolve=new Promise(resolve=>{window.releaseResolve=resolve});const original=window.api;window.api=async (path,payload)=>path==='/api/skill/git/resolve'?window.pendingResolve:original(path,payload)}""")
  buttons.nth(0).click()
  page.get_by_role('button',name='GitHub 최신 Commit SHA 조회').click()
  page.wait_for_function('typeof window.releaseResolve==="function"')
  buttons.nth(1).click()
  page.evaluate("""()=>window.releaseResolve({commit:'cccccccccccccccccccccccccccccccccccccccc',repository:'fake',branch:'main'})""")
  page.wait_for_timeout(100)
  assert page.locator('#gitCommit').input_value()==B
  assert page.locator('#installGitBtn').is_disabled()
  assert not errors,errors
  print('BROWSER PASS: recommendation switch, same-candidate reselection, manual edit, delayed GitHub SHA response all invalidate stale inspection; zero JS errors')
  browser.close()
finally:
 server.shutdown();server.server_close();fixture.doCleanups()
