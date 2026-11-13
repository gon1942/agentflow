"""Chromium dashboard top-row and document counts backed by real local fixture API."""
import json,sys,threading,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from test_default_three_profiles import ThreeDefaultProfiles
from scaffold.agentflow_console.server import make_handler
fx=ThreeDefaultProfiles('test_all_profiles_installed_first_boot_development_active');fx.setUp()
for sub in ('requirements','architecture','design','storyboards'):
    d=fx.root/'docs'/sub
    d.mkdir(parents=True,exist_ok=True)
    (d/'example.md').write_text('# Demo\n')
server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(fx.manager,'e2e-token'))
threading.Thread(target=server.serve_forever,daemon=True).start()
errors=[]
try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1600,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def bridge(source,path,data=None):
            hdr={'X-AgentFlow-Token':'e2e-token','Host':f'127.0.0.1:{server.server_port}','Content-Type':'application/json'}
            if data is not None:hdr['Origin']=f'http://127.0.0.1:{server.server_port}'
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}',data=json.dumps(data).encode() if data is not None else None,headers=hdr,method='POST' if data is not None else 'GET')
            with urllib.request.urlopen(req,timeout=10) as r:return {'status':r.status,'body':json.load(r)}
        page.expose_binding('nativeBridge',bridge)
        page.goto('about:blank#token=e2e-token')
        html=(root/'scaffold/agentflow_console/ui.html').read_text().replace('<script>','''<script>window.fetch=async function(path,args){const r=await window.nativeBridge(path,args?.body?JSON.parse(args.body):null);return new Response(JSON.stringify(r.body),{status:r.status,headers:{'Content-Type':'application/json'}})}</script><script>''',1)
        page.set_content(html,wait_until='domcontentloaded')
        page.wait_for_function("document.getElementById('topState').textContent==='READY'",timeout=15000)
        assert page.locator('.dashboard-document-tile').count()==4
        assert page.locator('.dashboard-document-amount').all_inner_texts()==['1건']*4
        assert page.locator('#dashboard .dashboard-kpis').count()==0
        heads=page.locator('#dashboard .dashboard-bottom-row-v061 h2').all_inner_texts()
        assert heads==['작업 상태 현황','최근 작업 활동','프로필 구성 현황','빠른 작업'],heads
        assert page.locator('.dashboard-bottom-row-v061').bounding_box()['y']<page.locator('.dashboard-documents-panel').bounding_box()['y']<page.locator('.dashboard-main-row').bounding_box()['y']
        page.screenshot(path='/mnt/data/agentflow-v075-dashboard-browser.png',full_page=True)
        assert not errors,errors
        print('BROWSER PASS: 4 operational panels first, 4 real document counts, redundant KPIs removed, no JS errors')
        browser.close()
finally:
    server.shutdown();server.server_close();fx.doCleanups()
