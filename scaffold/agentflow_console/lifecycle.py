"""Project-scoped console daemon management; independent of an AI agent shell.

Linux/POSIX only. No global files, no workflow changes and no persistent token in logs.
"""
from __future__ import annotations
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser

class ConsoleError(ValueError):
    pass


def paths(project):
    root = Path(project).resolve()
    launcher = root / 'agentflow_console.py'
    if not launcher.is_file():
        raise ConsoleError('CONSOLE_LAUNCHER_NOT_FOUND')
    run = root / '.agentflow' / 'run'
    if run.is_symlink():
        raise ConsoleError('UNSAFE_RUN_DIRECTORY')
    run.mkdir(parents=True, exist_ok=True)
    os.chmod(run, 0o700)
    return root, launcher, run


@contextlib.contextmanager
def lock(run):
    path = run / 'console.lock'
    if path.is_symlink():
        raise ConsoleError('UNSAFE_LOCK_PATH')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w') as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            yield
    finally:
        pass


def _state_path(run):
    path = run / 'console.json'
    if path.is_symlink():
        raise ConsoleError('UNSAFE_STATE_FILE')
    return path


def _read(run):
    path = _state_path(run)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return None
        return data
    except (ValueError, OSError):
        return None


def _matches(state, launcher):
    """Reject reused PIDs and unrelated processes. Linux /proc is expected on Ubuntu."""
    try:
        pid = int(state['pid'])
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        args = [v.decode('utf8', errors='replace') for v in cmd if v]
        return ('_serve-managed' in args and str(launcher) in args
                and str(state.get('project')) == str(launcher.parent))
    except (OSError, KeyError, ValueError, TypeError):
        return False


def _probe(state):
    try:
        address = f"http://127.0.0.1:{int(state['port'])}/api/health"
        request = urllib.request.Request(address, headers={'X-AgentFlow-Token': state['token']})
        with urllib.request.urlopen(request, timeout=0.7) as response:
            return response.status == 200
    except (OSError, KeyError, ValueError, TypeError):
        return False


def _current(run, launcher):
    state = _read(run)
    return state if state and _matches(state, launcher) and _probe(state) else None


def info(project):
    root, launcher, run = paths(project)
    state = _current(run, launcher)
    return {'project': str(root), 'running': bool(state),
            'pid': state['pid'] if state else None,
            'port': state['port'] if state else None,
            'url': f"http://127.0.0.1:{state['port']}/" if state else None,
            'note': 'Access token intentionally omitted; use console-open to open browser.'}


def start(project, browser=False):
    root, launcher, run = paths(project)
    with lock(run):
        state = _current(run, launcher)
        if state is None:
            # Don't overwrite state when a managed process still exists but is unresponsive.
            stale = _read(run)
            if stale and _matches(stale, launcher):
                raise ConsoleError('CONSOLE_UNHEALTHY: use stop before restarting')
            _state_path(run).unlink(missing_ok=True)
            logfile = run / 'console.log'
            if logfile.is_symlink():
                raise ConsoleError('UNSAFE_LOG_PATH')
            with open(logfile, 'ab') as log:
                child = subprocess.Popen([sys.executable, str(launcher), '--project', str(root),
                                          '_serve-managed'], cwd=root, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True, close_fds=True)
            for _ in range(60):
                state = _current(run, launcher)
                if state and int(state['pid']) == child.pid:
                    break
                if child.poll() is not None:
                    raise ConsoleError(f'CONSOLE_START_FAILED: exit={child.returncode}; inspect .agentflow/run/console.log')
                time.sleep(0.1)
            else:
                raise ConsoleError('CONSOLE_START_TIMEOUT: inspect .agentflow/run/console.log')
        result = {'running': True, 'pid': state['pid'], 'port': state['port'],
                  'already_running': 'child' not in locals()}
    if browser:
        webbrowser.open(_url(state))
    return result


def _url(state):
    return f"http://127.0.0.1:{state['port']}/#token={state['token']}"


def open_existing(project):
    root, launcher, run = paths(project)
    with lock(run):
        state = _current(run, launcher)
        if not state:
            raise ConsoleError('CONSOLE_NOT_RUNNING: run start first')
        url = _url(state)
    opened = webbrowser.open(url)
    # This command is commonly run inside headless agent environments.
    # No secret URL printed to logs; user can invoke console-open from desktop.
    return {'running': True, 'pid': state['pid'], 'port': state['port'], 'browser_open_requested': bool(opened)}


def stop(project):
    root, launcher, run = paths(project)
    with lock(run):
        state = _read(run)
        if not state:
            return {'running': False, 'stopped': False}
        if not _matches(state, launcher):
            _state_path(run).unlink(missing_ok=True)
            return {'running': False, 'stopped': False, 'stale_state_cleaned': True}
        pid = int(state['pid'])
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not _matches(state, launcher):
                break
            time.sleep(0.1)
        else:
            raise ConsoleError('CONSOLE_STOP_TIMEOUT: process still alive')
        _state_path(run).unlink(missing_ok=True)
        return {'running': False, 'stopped': True, 'pid': pid}


def doctor(project):
    root, launcher, run = paths(project)
    hosts = {name: {'installed': bool(shutil.which(name)), 'executable': shutil.which(name)}
             for name in ('opencode', 'claude', 'codex')}
    return {'project': str(root), 'server': info(project), 'python': sys.executable,
            'hosts': hosts, 'runtime': {'home_present': bool(os.environ.get('HOME')),
                                       'path_present': bool(os.environ.get('PATH')),
                                       'opencode_parent_context': any(k.startswith('OPENCODE_') for k in os.environ)},
            'note': 'Host installed != authenticated or native skill loaded. No secrets are shown.'}


def managed_serve(project):
    from .server import make_handler
    from .core import Manager
    from http.server import ThreadingHTTPServer
    import secrets
    root, launcher, run = paths(project)
    token = secrets.token_urlsafe(32)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Manager(root), token))
    httpd.daemon_threads = True
    state = {'project': str(root), 'pid': os.getpid(), 'port': httpd.server_port, 'token': token}
    tmp = run / f'.console-{os.getpid()}.tmp'
    old_umask = os.umask(0o077)
    try:
        tmp.write_text(json.dumps(state))
        os.chmod(tmp, 0o600)
        os.replace(tmp, _state_path(run))
    finally:
        os.umask(old_umask)
        tmp.unlink(missing_ok=True)
    def shutdown(_signum, _frame):
        # No serve_forever shutdown() from signal handler (can deadlock).
        raise KeyboardInterrupt()
    previous = signal.signal(signal.SIGTERM, shutdown)
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        signal.signal(signal.SIGTERM, previous)
        current = _read(run)
        if current and current.get('pid') == os.getpid() and current.get('token') == token:
            _state_path(run).unlink(missing_ok=True)
