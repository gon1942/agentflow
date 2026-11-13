"""Loopback-only AgentFlow management console HTTP server."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import base64
import binascii
from pathlib import Path
import secrets
import urllib.parse
from .core import Manager, ManagementError

STATIC = Path(__file__).with_name('ui.html')


def make_handler(manager: Manager, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'AgentFlowConsole/0.1'
        def log_message(self, fmt, *args):
            # No URL query/body/token logging.
            pass

        def _reply(self, status, data):
            blob = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(blob)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(blob)

        def _page(self):
            blob = STATIC.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(blob)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(blob)

        def _auth(self):
            # All requests including reads require unpredictable per-process token.
            return secrets.compare_digest(self.headers.get('X-AgentFlow-Token', ''), token)

        def _write_protection(self):
            if not self._auth():
                return False
            origin = self.headers.get('Origin')
            host = self.headers.get('Host', '').lower()
            if not host.startswith(('127.0.0.1:', 'localhost:')):
                return False
            if origin and origin not in ('http://' + host,):
                return False
            return True

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path == '/':
                # Token comes from console-open URL fragment; browser does not send it to server.
                self._page()
                return
            if not self._auth():
                self._reply(403, {'error': 'AUTH_REQUIRED'})
                return
            try:
                if url.path == '/api/health':
                    value = {'status': 'ok'}
                elif url.path == '/api/status':
                    value = manager.status()
                elif url.path == '/api/profiles':
                    value = manager.list_profiles()
                elif url.path == '/api/templates':
                    value = manager.list_templates()
                elif url.path == '/api/trees':
                    value = manager.list_trees()
                elif url.path == '/api/skills':
                    value = manager.list_skills()
                elif url.path == '/api/ai/runs':
                    from .advisor import list_traces
                    value = list_traces(manager.root)
                elif url.path == '/api/ai/run':
                    from .advisor import read_trace
                    value = read_trace(manager.root, urllib.parse.parse_qs(url.query).get('id',[''])[0])
                elif url.path == '/api/rotation/status':
                    from .rotation import RotationManager
                    tid=urllib.parse.parse_qs(url.query).get('task_id',[''])[0]
                    value=RotationManager(manager).status(tid)
                elif url.path == '/api/rotation/history':
                    from .rotation import RotationManager
                    tid=urllib.parse.parse_qs(url.query).get('task_id',[''])[0]
                    value=RotationManager(manager).history(tid)
                elif url.path == '/api/session-profiles':
                    from .contexts import ContextRegistry
                    value = ContextRegistry(manager).list_sessions()
                elif url.path == '/api/task-contexts':
                    from .contexts import ContextRegistry
                    value = ContextRegistry(manager).task_views()
                elif url.path == '/api/contract':
                    from .contexts import ContextRegistry
                    qs=urllib.parse.parse_qs(url.query)
                    value=ContextRegistry(manager).contract(qs.get('session',[None])[0],qs.get('profile',[None])[0])
                elif url.path == '/api/tasks':
                    value = manager.active_tasks()
                else:
                    return self._reply(404, {'error': 'NOT_FOUND'})
                self._reply(200, value)
            except (ManagementError, OSError) as exc:
                self._reply(409, {'error': str(exc)})

        def do_POST(self):
            if not self._write_protection():
                return self._reply(403, {'error': 'AUTH_OR_ORIGIN_REJECTED'})
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                return self._reply(415, {'error': 'JSON_ONLY'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                path = urllib.parse.urlparse(self.path).path
                max_length = 42_000_000 if path in ('/api/skill/upload/inspect','/api/skill/upload/install') else 1_000_000
                if length < 1 or length > max_length:
                    return self._reply(413, {'error': 'REQUEST_TOO_LARGE'})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ManagementError('INVALID_REQUEST')
                if path == '/api/session-profile/bind':
                    from .contexts import ContextRegistry
                    result = ContextRegistry(manager).bind_session(payload.get('session_id'),payload.get('host'),payload.get('profile'),payload.get('generation'))
                elif path == '/api/task-context/pin':
                    from .contexts import ContextRegistry
                    result = ContextRegistry(manager).pin_task(payload.get('task_id'),payload.get('session_id'),payload.get('profile'))
                elif path == '/api/profile/activate':
                    result = manager.activate(payload.get('profile'), payload.get('generation'))
                elif path == '/api/profile/template':
                    result = manager.add_template(payload.get('template'))
                elif path == '/api/profile/create':
                    result = manager.create_profile(payload.get('id'), payload.get('name'))
                elif path == '/api/profile/clone':
                    result = manager.clone_profile(payload.get('source'), payload.get('id'), payload.get('name'))
                elif path == '/api/profile/save':
                    result = manager.save_profile(payload)
                elif path == '/api/tree/save':
                    result = manager.save_tree(payload)
                elif path in ('/api/skill/upload/inspect', '/api/skill/upload/install'):
                    encoded = payload.get('archive_base64')
                    if not isinstance(encoded,str) or len(encoded) > 40_000_000:
                        raise ManagementError('ZIP_TOO_LARGE_OR_INVALID')
                    try:
                        archive = base64.b64decode(encoded,validate=True)
                    except (ValueError,binascii.Error):
                        raise ManagementError('ZIP_BASE64_INVALID')
                    if path.endswith('inspect'):
                        result = manager.inspect_uploaded_zip(archive)
                    else:
                        result = manager.install_uploaded_zip(archive, payload.get('archive_sha256'), payload.get('approved') is True)
                elif path == '/api/skill/create/inspect':
                    result = manager.inspect_created_skill(payload.get('name'), payload.get('description'), payload.get('instructions'))
                elif path == '/api/skill/create/install':
                    result = manager.install_created_skill(payload.get('name'), payload.get('description'), payload.get('instructions'), payload.get('approved') is True)
                elif path == '/api/skill/inspect':
                    result = manager.inspect_local(payload.get('source'), payload.get('kind'))
                elif path == '/api/skill/install':
                    result = manager.install_skill(payload.get('kind'), payload.get('source'), payload.get('approved') is True)
                elif path == '/api/skill/remove':
                    result = manager.remove_skill(payload.get('name'), payload.get('approved') is True)
                elif path == '/api/ai/apply-local':
                    result = manager.apply_local_recommendations(payload.get('profile'), payload.get('assignments'), payload.get('approved') is True)
                elif path == '/api/ai/suggest':
                    from .ai import suggest
                    result = suggest(manager, payload.get('host'), payload.get('question'), payload.get('profile'), payload.get('stage'), payload.get('search_external') is True)
                elif path == '/api/skill/git/resolve':
                    from .external import resolve_github_commit
                    result = resolve_github_commit(payload.get('url'))
                elif path == '/api/skill/git/inspect':
                    result = manager.inspect_git(payload.get('url'), payload.get('commit'), payload.get('subdir'))
                elif path == '/api/skill/git/install':
                    result = manager.install_git(payload.get('url'), payload.get('commit'), payload.get('subdir'), payload.get('approved') is True)
                else:
                    return self._reply(404, {'error': 'NOT_FOUND'})
                self._reply(200, result)
            except (ManagementError, ValueError, TypeError, OSError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
                self._reply(409, {'error': str(exc)[:500]})
    return Handler


def serve(project, port=0, open_browser=False):
    manager = Manager(project)
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(manager, token))
    url = f'http://127.0.0.1:{server.server_port}/#token={token}'
    print('AgentFlow Console — loopback only', flush=True)
    print('Open locally (URL contains a temporary secret; do not share):', url, flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('AgentFlow Console stopped.', flush=True)
    finally:
        server.server_close()
