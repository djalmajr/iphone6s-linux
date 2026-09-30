"""Scheduler contract tests with a synthetic SSH dependency and real snapshots."""
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

SSH_STUB = r'''#!/usr/bin/env python3
from pathlib import Path
import os,sys,time
base=Path(__file__).resolve().parents[1]
mode=(base/'fault').read_text() if (base/'fault').exists() else ''
if mode=='offline': sys.exit(255)
if mode=='slow':
    (base/'ssh.pid').write_text(str(os.getpid()))
    time.sleep(30)
data=(base/'incoming.tar.gz').read_bytes()
sys.stdout.buffer.write(data[:64] if mode=='truncated' else data)
'''


class AutoSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='iphone-autosnap-test-')
        self.addCleanup(self.work.cleanup)
        self.addCleanup(self.cleanup_job)
        self.root = Path(self.work.name)
        self.host = self.root / 'scripts/host'
        self.host.mkdir(parents=True)
        for name in ('autosnap.py', 'persist.py', 'device_profile.py', 'restore_journal.py', 'snapshot_lock.py', 'snapshot_retention.py', 'iphone-linux.sh'):
            shutil.copy(ROOT / 'scripts/host' / name, self.host / name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'ssh').write_text(SSH_STUB)
        (self.bin / 'ssh').chmod(0o700)
        (self.bin / 'ioreg').write_text('#!/bin/sh\necho "iPhone 6s Linux probe"\n')
        (self.bin / 'ioreg').chmod(0o700)
        self.environment = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        with tarfile.open(self.root / 'incoming.tar.gz', 'w:gz') as archive:
            for name, data in (('srv/data/state.txt', b'synthetic saved data\n'), ('root/.ssh/authorized_keys', b'synthetic excluded key\n')):
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o640
                archive.addfile(member, io.BytesIO(data))

    def cleanup_job(self):
        path = self.root / 'ssh.pid'
        if not path.exists():
            return
        try:
            pid = int(path.read_text())
            group = os.getpgid(pid)
            if group != os.getpgrp():
                os.killpg(group, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def assert_job_stopped(self):
        pid = int((self.root / 'ssh.pid').read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                (self.root / 'ssh.pid').unlink(missing_ok=True)
                return
            if sys.platform == 'linux':
                state = Path('/proc') / str(pid) / 'stat'
                if state.exists() and state.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                    (self.root / 'ssh.pid').unlink(missing_ok=True)
                    return
            time.sleep(0.01)
        self.fail('Owned SSH job survived cancellation/timeout')

    def run_scheduler(self, *arguments):
        return subprocess.run([sys.executable, str(self.host / 'autosnap.py'), *arguments],
                              env=self.environment, capture_output=True, text=True, timeout=15)

    def snapshots(self):
        return sorted((self.root / 'backups').glob('*/files.tar.gz'))

    def test_recurrence_publishes_valid_private_snapshot_and_retains_latest(self):
        # Mutation captured: ignoring --keep leaves old automatic snapshots.
        started = time.monotonic()
        result = self.run_scheduler('watch', '--cycles', '2', '--interval', '1', '--keep', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(time.monotonic() - started, 1)
        self.assertEqual(result.stdout.count('Snapshot:'), 2)
        snapshots = self.snapshots()
        self.assertEqual(len(snapshots), 1)
        with tarfile.open(snapshots[0], 'r:gz') as archive:
            self.assertEqual(archive.getnames(), ['srv/data/state.txt'])
            self.assertEqual(archive.extractfile('srv/data/state.txt').read(), b'synthetic saved data\n')
        state = json.loads((self.root / 'logs/autosnap-last.json').read_text())
        self.assertEqual(state['outcome'], 'success')
        self.assertEqual(state['last_success'], snapshots[0].parent.name)
        self.assertEqual((self.root / 'logs').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / 'logs/autosnap-last.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(snapshots[0].stat().st_mode & 0o777, 0o600)
        self.assertFalse(list((self.root / 'backups').glob('.partial-*')))

    def test_offline_and_truncated_transfer_preserve_all_previous_snapshots(self):
        # Mutation captured: reporting failed transfer as success hides unavailable backups.
        for _ in range(2):
            self.assertEqual(self.run_scheduler('once', '--keep', '2').returncode, 0)
        originals = {p.parent.name: p.read_bytes() for p in self.snapshots()}
        self.assertEqual(len(originals), 2)
        success = json.loads((self.root / 'logs/autosnap-last.json').read_text())['last_success']
        for fault in ('offline', 'truncated'):
            with self.subTest(fault=fault):
                (self.root / 'fault').write_text(fault)
                result = self.run_scheduler('once', '--keep', '1')
                self.assertEqual(result.returncode, 1)
                self.assertEqual({p.parent.name: p.read_bytes() for p in self.snapshots()}, originals)
                state = json.loads((self.root / 'logs/autosnap-last.json').read_text())
                self.assertEqual(state['outcome'], 'failed')
                self.assertEqual(state['last_success'], success)
                self.assertFalse(list((self.root / 'backups').glob('.partial-*')))

    def test_timeout_preserves_backup_and_next_attempt_can_run(self):
        # Mutation captured: misclassifying timeout hides stalled jobs.
        self.assertEqual(self.run_scheduler('once').returncode, 0)
        original = self.snapshots()[0].read_bytes()
        (self.root / 'fault').write_text('slow')
        result = self.run_scheduler('once', '--timeout', '1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.snapshots()[0].read_bytes(), original)
        self.assertEqual(json.loads((self.root / 'logs/autosnap-last.json').read_text())['outcome'], 'timeout')
        self.assert_job_stopped()
        (self.root / 'fault').unlink()
        self.assertEqual(self.run_scheduler('once', '--keep', '1').returncode, 0)
        self.assertEqual(len(self.snapshots()), 1)

    def test_finite_watch_reports_failed_job(self):
        # Mutation captured: returning zero hides a failed finite schedule.
        self.assertEqual(self.run_scheduler('once').returncode, 0)
        previous = self.snapshots()[0].read_bytes()
        (self.root / 'fault').write_text('offline')
        result = self.run_scheduler('watch', '--cycles', '1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.snapshots()[0].read_bytes(), previous)
        self.assertEqual(json.loads((self.root / 'logs/autosnap-last.json').read_text())['outcome'], 'failed')

    def test_sigterm_cancels_owned_job_without_publishing(self):
        # Mutation captured: dropping SIGTERM forwarding leaves an orphan job.
        (self.root / 'fault').write_text('slow')
        process = subprocess.Popen([sys.executable, str(self.host / 'autosnap.py'), 'watch', '--cycles', '1'],
                                   env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / 'ssh.pid').exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.root / 'ssh.pid').exists())
            process.terminate()
            output, error = process.communicate(timeout=6)
            self.assertEqual(process.returncode, 130, error)
            self.assertIn('Agendador encerrado', output)
            self.assert_job_stopped()
            self.assertEqual(self.snapshots(), [])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_auto_restore_refuses_active_linux_and_invalid_snapshot_before_boot(self):
        # Mutation captured: removing the active-session guard permits overwrite.
        self.assertEqual(self.run_scheduler('once').returncode, 0)
        archive = self.snapshots()[0]
        command = ['bash', str(self.host / 'iphone-linux.sh'), 'boot', '--restore', archive.parent.name]
        result = subprocess.run(command, env=self.environment, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Linux já está ativo', result.stderr)
        before = archive.read_bytes()
        self.assertEqual(len(self.snapshots()), 1)
        self.assertEqual(archive.read_bytes(), before)
        with archive.open('ab') as file:
            file.write(b'corrupted')
        result = subprocess.run(command, env=self.environment, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Integridade', result.stderr)
        self.assertNotIn('Linux já está ativo', result.stderr)


if __name__ == '__main__':
    unittest.main()
