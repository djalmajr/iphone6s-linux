"""Observe the automation's filesystem and CLI contract with an isolated peer."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
spec = importlib.util.spec_from_file_location('phone_herdr', ROOT / 'scripts/host/herdr.py')
herdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(herdr)

PEER = '''#!/bin/bash
set -eu
base=$(dirname "$0")
if [ "$1" = --version ]; then echo 'herdr 0.9.1'; exit; fi
test "$1" = --session && test "$2" = iphone-server
shift 2
if [ "$#" = 0 ]; then echo HERDR_TEST_ATTACHED; exit; fi
case "$1" in
  status)
    if [ -f "$base/status-failure" ]; then exit 29; fi
    if [ -f "$base/running" ]; then
      echo 'status: running'
      echo 'private_protocol_compatible: yes'
    else echo 'status: not running'; fi ;;
  server)
    echo start >> "$base/starts"
    test "$SHELL" = /bin/bash
    test "$HERDR_STARTUP_CWD" = "$base/data"
    touch "$base/running" ;;
  session)
    test "$2" = stop && test "$3" = iphone-server
    echo stop >> "$base/stops"
    rm -f "$base/running" ;;
  *) exit 19 ;;
esac
'''


class HerdrStartTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.peer = self.base / 'herdr'
        self.peer.write_text(PEER)
        self.peer.chmod(0o700)
        self.digest = hashlib.sha256(self.peer.read_bytes()).hexdigest()
        # The short-lived CLI peer has no daemon to detach; real detachment is a VM gate.
        detacher = self.base / 'setsid'
        detacher.write_text('#!/bin/sh\nexec "$@"\n')
        detacher.chmod(0o700)
        self.marker = self.base / 'data/herdr/autostart'
        self.state = self.base / 'run'

    def invoke(self, action):
        source = herdr.script(action)
        source = source.replace('/usr/local/bin/herdr', str(self.peer))
        source = source.replace('/run/iphone-herdr', str(self.state))
        source = source.replace('/srv/data', str(self.base / 'data'))
        source = source.replace('f4ccf4de745f2cb9a39a983e9ba3703dad50ec2a58dea83026ceab721bbd8d9e', self.digest)
        return subprocess.run(['/bin/bash', '-se'], input=source, text=True,
                              capture_output=True, timeout=15,
                              env=dict(os.environ, PATH=str(self.base) + os.pathsep + os.environ['PATH']))

    def started(self):
        return (self.base / 'starts').read_text().splitlines()

    def test_boot_disabled_then_enable_restores_only_opt_in(self):
        result = self.invoke('boot')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / 'starts').exists())
        result = self.invoke('enable')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text(), '1\n')
        self.assertEqual(self.marker.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.started(), ['start'])
        result = self.invoke('boot')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.started(), ['start'])
        self.assertFalse((self.base / 'data/herdr/config.toml').exists())

    def test_repeated_start_keeps_session_and_restart_targets_only_its_session(self):
        for _ in range(2):
            result = self.invoke('start')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.started(), ['start'])
        result = self.invoke('restart')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.started(), ['start', 'start'])
        self.assertEqual((self.base / 'stops').read_text(), 'stop\n')

    def test_disable_does_not_stop_running_work(self):
        self.assertEqual(self.invoke('enable').returncode, 0)
        result = self.invoke('disable')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertTrue((self.base / 'running').exists())
        self.assertFalse((self.base / 'stops').exists())

    def test_bad_marker_or_symlink_refused_without_changing_target(self):
        self.marker.parent.mkdir(parents=True)
        self.marker.write_text('execute anything\n')
        self.assertNotEqual(self.invoke('boot').returncode, 0)
        target = self.base / 'outside'
        target.write_text('1\n')
        self.marker.unlink()
        self.marker.symlink_to(target)
        for action in ('boot', 'enable', 'disable'):
            self.assertNotEqual(self.invoke(action).returncode, 0)
            self.assertEqual(target.read_text(), '1\n')
        self.assertFalse((self.base / 'starts').exists())

    def test_existing_operation_lock_refuses_duplicate_start(self):
        (self.state / 'operation.lock').mkdir(parents=True)
        result = self.invoke('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'starts').exists())
        self.assertTrue((self.state / 'operation.lock').is_dir())

    def test_attach_releases_operation_lock_before_the_client_exec(self):
        result = self.invoke('attach')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('HERDR_TEST_ATTACHED', result.stdout)
        self.assertFalse((self.state / 'operation.lock').exists())
        self.assertEqual(self.invoke('start').returncode, 0)
        self.assertEqual(self.started(), ['start'])

    def test_altered_binary_is_not_executed(self):
        self.peer.write_text(self.peer.read_text() + '\n# modified\n')
        result = self.invoke('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'starts').exists())
        self.assertFalse(self.state.exists())

    def test_status_failure_does_not_launch_another_server(self):
        (self.base / 'status-failure').touch()
        result = self.invoke('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'starts').exists())

    def test_hardlinked_marker_and_redirected_state_are_refused(self):
        self.marker.parent.mkdir(parents=True)
        target = self.base / 'outside'
        target.write_text('1\n')
        os.link(target, self.marker)
        self.assertNotEqual(self.invoke('enable').returncode, 0)
        self.assertEqual(target.read_text(), '1\n')
        self.marker.unlink()
        if self.state.exists():
            import shutil
            shutil.rmtree(self.state)
        self.state.symlink_to(self.marker.parent)
        self.assertNotEqual(self.invoke('start').returncode, 0)
        self.assertFalse((self.base / 'starts').exists())
        self.assertFalse((self.marker.parent / 'status.txt').exists())

    def test_cli_transports_script_with_strict_ssh_and_propagates_failure(self):
        peer = self.base / 'ssh'
        peer.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\n'
                        + 'assert "StrictHostKeyChecking=yes" in sys.argv\n'
                        + 'assert "ForwardAgent=no" in sys.argv\n'
                        + 'Path(' + repr(str(self.base / 'received')) + ').write_text(sys.stdin.read())\n'
                        + 'raise SystemExit(31)\n')
        peer.chmod(0o700)
        environment = dict(os.environ, PATH=str(self.base))
        environment.pop('IPHONE_LINUX_PROFILE', None)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/host/herdr.py'), 'status'],
                                env=environment, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn('status server --json', (self.base / 'received').read_text())
        self.assertIn('31', result.stderr)

    def test_restart_requires_explicit_stop_flag_before_any_ssh(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/host/herdr.py'), 'restart'],
                                capture_output=True, text=True, timeout=5,
                                env=dict(os.environ, PATH='/nonexistent'))
        self.assertEqual(result.returncode, 2)
        self.assertIn('--confirm-stop', result.stderr)


if __name__ == '__main__':
    unittest.main()
