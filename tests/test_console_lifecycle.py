"""Executable process-management tests, independent of installed upstream skills."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCAFFOLD = Path(__file__).resolve().parents[1] / 'scaffold'

class ConsoleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        shutil.copytree(SCAFFOLD, self.root, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.launcher = self.root / 'agentflow_console.py'

    def command(self, *args, code=0):
        out = subprocess.run([sys.executable, str(self.launcher), *args], cwd=self.root,
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(out.returncode, code, (out.stdout, out.stderr))
        return json.loads(out.stdout) if code == 0 else out.stderr

    def tearDown(self):
        self.command('stop')

    def test_lifecycle_reuse_and_stop(self):
        self.assertFalse(self.command('console-status')['running'])
        a = self.command('start')
        self.assertTrue(a['running'])
        self.assertFalse(a['already_running'])
        b = self.command('start')
        self.assertTrue(b['already_running'])
        self.assertEqual((a['pid'], a['port']), (b['pid'], b['port']))
        status = self.command('console-status')
        self.assertEqual(status['pid'], a['pid'])
        self.assertNotIn('token', status)
        self.assertEqual(self.command('stop')['pid'], a['pid'])
        self.assertFalse(self.command('console-status')['running'])

    def test_health_and_doctor(self):
        self.command('start')
        result = self.command('doctor')
        self.assertTrue(result['server']['running'])
        self.assertIn('opencode', result['hosts'])
        self.assertNotIn('token', result['server'])

    def test_health_endpoint_requires_token(self):
        import urllib.error
        import urllib.request
        self.command('start')
        path = self.root/'.agentflow/run/console.json'
        secret = json.loads(path.read_text())
        uri = f"http://127.0.0.1:{secret['port']}/api/health"
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(uri, timeout=2)
        self.assertEqual(context.exception.code, 403)
        request = urllib.request.Request(uri, headers={'X-AgentFlow-Token': secret['token']})
        with urllib.request.urlopen(request, timeout=2) as response:
            self.assertEqual(json.load(response)['status'], 'ok')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_parallel_start_one_instance(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            states = list(pool.map(lambda _: self.command('start'), range(4)))
        self.assertEqual(len({x['pid'] for x in states}), 1)
        self.assertEqual(len({x['port'] for x in states}), 1)

    def test_stale_state_cleanup_does_not_kill_other_process(self):
        run = self.root / '.agentflow/run'
        run.mkdir(parents=True, exist_ok=True)
        (run/'console.json').write_text(json.dumps({'pid': os.getpid(), 'port': 1, 'token': 'wrong', 'project': str(self.root)}))
        self.assertFalse(self.command('console-status')['running'])
        stopped = self.command('stop')
        self.assertTrue(stopped['stale_state_cleaned'])

    def test_no_running_console_open(self):
        message = self.command('console-open', code=2)
        self.assertIn('CONSOLE_NOT_RUNNING', message)

if __name__ == '__main__':
    unittest.main()
