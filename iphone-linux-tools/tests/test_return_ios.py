"""Reboot contract with real snapshots and synthetic USB/SSH executables."""
import base64
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReturnIOSTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='return-ios-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.host = self.root / 'scripts/host'
        self.host.mkdir(parents=True)
        for name in ('return_ios.py', 'autosnap.py', 'persist.py', 'device_profile.py',
                     'restore_journal.py', 'snapshot_lock.py', 'snapshot_retention.py'):
            shutil.copy(ROOT / 'scripts/host' / name, self.host / name)
        tools = self.root / 'bin'
        tools.mkdir()
        for name in ('ssh', 'idevice_id', 'ideviceinfo', 'ioreg'):
            path = tools / name
            shutil.copy(ROOT / 'tests/fixtures/return-ios-stub.sh', path)
            path.chmod(0o700)
        self.environment = dict(os.environ, PATH=os.pathsep.join(
            (str(tools), os.environ['PATH'])))
        self.environment.pop('IPHONE_LINUX_PROFILE', None)
        self.archive()

    def archive(self, name='srv/data/state.txt'):
        with tarfile.open(self.root / 'incoming.tar.gz', 'w:gz') as archive:
            member = tarfile.TarInfo(name)
            member.size, member.mode = 11, 0o640
            archive.addfile(member, io.BytesIO(b'saved state'))

    def run_cli(self, mode='success', *arguments):
        (self.root / 'mode').write_text(mode)
        (self.root / 'phase').unlink(missing_ok=True)
        (self.root / 'events').unlink(missing_ok=True)
        wait = '10'
        return subprocess.run([sys.executable, str(self.host / 'return_ios.py'),
                               '--wait', wait, *arguments], env=self.environment,
                              capture_output=True, text=True, timeout=30)

    def events(self):
        path = self.root / 'events'
        return path.read_text().splitlines() if path.exists() else []

    def test_success_requires_real_verified_snapshot_and_usb_observation(self):
        for mode in ('success', 'ssh-disconnect'):
            with self.subTest(mode=mode):
                result = self.run_cli(mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('BACKUP_VERIFIED', result.stdout)
                self.assertIn('RETURN_IOS_VERIFIED', result.stdout)
                self.assertNotIn('SYNTHETIC-USB-ID', result.stdout + result.stderr)
                events = self.events()
                self.assertGreater(events.index('REBOOT'), events.index('ssh'))
                self.assertIn('ideviceinfo', events[events.index('REBOOT'):])
        archives = list((self.root / 'backups').glob('*/files.tar.gz'))
        self.assertEqual(len(archives), 2)
        for path in archives:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with tarfile.open(path) as archive:
                self.assertEqual(archive.extractfile('srv/data/state.txt').read(), b'saved state')

    def test_ssh_usb_or_backup_failure_blocks_reboot(self):
        for mode in ('pin-error', 'already-ios', 'usb-error'):
            result = self.run_cli(mode)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn('REBOOT', self.events())
            self.assertFalse((self.root / 'backups').exists())
        self.archive('outside/state.txt')
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('REBOOT', self.events())
        self.assertEqual(list((self.root / 'backups').glob('*/files.tar.gz')), [])

    def assert_return_refused(self, mode):
        result = self.run_cli(mode)
        phase_proof = (f'mode={mode}; events={self.events()!r}\n'
                       f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('RETURN_IOS_VERIFIED', result.stdout)
        self.assertIn('RETURN_IOS_FAILED', result.stderr)
        self.assertNotIn('SYNTHETIC-USB-ID', result.stdout + result.stderr)
        self.assertIn('BACKUP_VERIFIED', result.stdout, phase_proof)
        self.assertEqual(len(list((self.root / 'backups').glob('*/files.tar.gz'))), 1, phase_proof)

    def test_sync_failure_never_reports_success(self):
        self.assert_return_refused('sync-error')
        self.assertNotIn('REBOOT', self.events())

    def test_missing_sync_confirmation_never_reports_success(self):
        self.assert_return_refused('missing-sync')
        self.assertNotIn('REBOOT', self.events())

    def test_disconnected_sync_blocks_reboot(self):
        self.assert_return_refused('sync-disconnect')
        self.assertNotIn('REBOOT', self.events())

    def test_fast_reboot_after_separate_confirmed_sync(self):
        result = self.run_cli('fast-reboot')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RETURN_IOS_VERIFIED', result.stdout)
        events = self.events()
        self.assertLess(events.index('SYNC'), events.index('REBOOT'))
        self.assertIn('ideviceinfo', events[events.index('REBOOT'):])

    def test_reboot_error_never_reports_success(self):
        self.assert_return_refused('request-error')

    def test_linux_still_present_never_reports_success(self):
        self.assert_return_refused('linux-stays')

    def test_linux_reappears_after_model_query_never_reports_success(self):
        self.assert_return_refused('linux-returns')

    def test_wrong_ios_model_never_reports_success(self):
        self.assert_return_refused('wrong-model')

    def test_multiple_usb_devices_never_report_success(self):
        self.assert_return_refused('multiple')

    def test_ios_model_query_failure_never_reports_success(self):
        self.assert_return_refused('info-error')

    def test_malformed_gadget_plist_never_reports_success(self):
        self.assert_return_refused('bad-plist')

    def test_explicit_invalid_profile_and_wait_refused_before_dependencies(self):
        self.environment['IPHONE_LINUX_PROFILE'] = ''
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.events(), [])
        self.environment.pop('IPHONE_LINUX_PROFILE')
        for value in ('0', '301', 'bad'):
            result = self.run_cli('success', '--wait', value)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.events(), [])

    def test_selected_profile_is_used_by_backup_and_reboot(self):
        base = self.root / 'candidate'
        base.mkdir(mode=0o700)
        wire = b'\0\0\0\x0bssh-ed25519\0\0\0\x20' + b's' * 32
        contents = {'payload.bin': 'nonexecutable fixture', 'initramfs.gz': 'fixture',
                    'client': 'synthetic identity fixture',
                    'known_hosts': 'candidate-test ssh-ed25519 ' + base64.b64encode(wire).decode() + '\n'}
        profile = dict(format=1, payload='payload.bin', sha256='a' * 64,
                       initramfs='initramfs.gz', initramfs_sha256='b' * 64,
                       client_key='client', known_hosts='known_hosts', host_key_alias='candidate-test')
        contents['profile.json'] = json.dumps(profile)
        for name, value in contents.items():
            path = base / name
            path.write_text(value)
            path.chmod(0o600)
        self.environment['IPHONE_LINUX_PROFILE'] = str(base / 'profile.json')
        (self.root / 'expect-alias').touch()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_snapshot_tampered_after_publication_blocks_reboot(self):
        path = self.host / 'persist.py'
        source = path.read_text()
        # The real backup still runs; the synthetic producer corrupts its output afterwards.
        original = '        backup()\n'
        self.assertIn(original, source)
        path.write_text(source.replace(original,
            "        snapshot_id = backup()\n"
            "        (STORE / snapshot_id / 'files.tar.gz').write_bytes(b'corrupted fixture')\n", 1))
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('REBOOT', self.events())
        self.assertNotIn('RETURN_IOS_VERIFIED', result.stdout)

    def test_backup_exit_failure_even_with_valid_archive_blocks_reboot(self):
        path = self.host / 'persist.py'
        source = path.read_text()
        self.assertIn('        backup()\n', source)
        path.write_text(source.replace('        backup()\n',
            '        backup()\n        raise SystemExit(1)\n', 1))
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('REBOOT', self.events())
        self.assertEqual(len(list((self.root / 'backups').glob('*/files.tar.gz'))), 1)

    def test_timeout_stops_owned_process(self):
        path = self.root / 'timeout.pid'
        program = "import os,pathlib,time; pathlib.Path(" + repr(str(path)) + ").write_text(str(os.getpid())); time.sleep(60)"
        script = "import sys;sys.path.insert(0,sys.argv[1]);import return_ios;r=return_ios.run_owned([sys.executable,'-c',sys.argv[2]],2);print(r[2]);print(r[0])"
        child = None
        try:
            result = subprocess.run([sys.executable, '-c', script, str(self.host), program],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(path.exists())
            child = int(path.read_text())
            self.assertEqual(result.stdout.splitlines()[0], 'True')
            self.assertNotEqual(result.stdout.splitlines()[1], '0')
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
        finally:
            if child is not None:
                try:
                    os.kill(child, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_owned_pid_is_published_only_after_complete_write(self):
        (self.root / 'mode').write_text('slow-backup')
        (self.root / 'hold-pid-publication').touch()
        job = subprocess.Popen([str(self.root / 'bin/ssh'), '-o', 'StrictHostKeyChecking=yes',
                                '-o', 'IdentitiesOnly=yes', 'tar -czf synthetic-archive'],
                               env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            marker = self.root / 'pid-opened'
            while not marker.exists() and time.monotonic() < deadline and job.poll() is None:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), 'Synthetic PID producer never reached the write barrier')
            path = self.root / 'owned.pid'
            self.assertFalse(path.exists(), 'An unfinished PID was visible to the cancellation reader')
            self.assertEqual((self.root / 'owned.pid.tmp').read_text(), '')
            (self.root / 'release-pid-publication').touch()
            deadline = time.monotonic() + 10
            while not path.exists() and time.monotonic() < deadline and job.poll() is None:
                time.sleep(0.01)
            self.assertTrue(path.exists(), 'Synthetic PID was not published')
            self.assertEqual(path.read_text(), str(job.pid))
            self.assertFalse((self.root / 'owned.pid.tmp').exists())
        finally:
            if job.poll() is None:
                job.terminate()
            try:
                job.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                job.kill()
                job.communicate()

    def test_cancellation_stops_owned_backup_ssh_without_reboot(self):
        (self.root / 'mode').write_text('slow-backup')
        job = subprocess.Popen([sys.executable, str(self.host / 'return_ios.py')],
                               env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
        child = None
        try:
            deadline = time.monotonic() + 10
            path = self.root / 'owned.pid'
            while not path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(path.exists(), 'Synthetic backup never reached owned SSH')
            child = int(path.read_text())
            job.send_signal(signal.SIGTERM)
            output, error = job.communicate(timeout=8)
            self.assertEqual(job.returncode, 1, output + error)
            self.assertIn('cancelado', error)
            self.assertNotIn('REBOOT', self.events())
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    os.kill(child, 0)
                except ProcessLookupError:
                    break
                if sys.platform == 'linux':
                    state = Path('/proc') / str(child) / 'stat'
                    if state.exists() and state.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                        break
                time.sleep(0.02)
            else:
                self.fail('Owned backup SSH survived cancellation')
        finally:
            if job.poll() is None:
                job.kill()
                job.communicate()
            if child is not None:
                try:
                    os.kill(child, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == '__main__':
    unittest.main()
