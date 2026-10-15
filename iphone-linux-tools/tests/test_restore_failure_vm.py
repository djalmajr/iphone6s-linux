"""Real BusyBox failure/recovery tests; run only in the disposable Linux VM."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HOST = Path(__file__).resolve().parents[1] / 'scripts/host'
sys.path.insert(0, str(HOST))
spec = importlib.util.spec_from_file_location('persist', HOST / 'persist.py')
persist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(persist)

TRANSPORT = r'''
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
root, store, fault = map(Path, sys.argv[1:4])
command = sys.argv[4]
script = sys.stdin.buffer.read() if command == '/bin/bash -se' else None
applying = script is not None and b'tar -xzf ' in script
uploading = command.startswith('umask 077; set -C; cat > ')
if applying or uploading:
    journals = [json.loads(p.read_text()) for p in (store / 'restore-journal').glob('*.json')]
    phase = 'applying' if applying else 'prepared'
    protected = [r for r in journals if r['phase'] == phase and (store / r['before'] / 'manifest.json').is_file()]
    if not protected:
        print('Recovery reference missing before extraction', file=sys.stderr)
        sys.exit(88)
    if uploading:
        extra = root / 'srv/data/extra.txt'
        if not extra.exists():
            extra.write_bytes(b'extra preserved\n')
if command.startswith('rm -f ') and (fault / 'cleanup').exists():
    sys.exit(77)
if applying and (fault / 'interrupt').exists():
    (fault / 'interrupt').unlink()
    process = subprocess.Popen(['chroot', str(root), '/bin/bash', '-c', command], stdin=subprocess.PIPE, start_new_session=True)
    process.stdin.write(script)
    process.stdin.close()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and process.poll() is None:
        if (root / 'srv/data/a.txt').read_bytes() == b'new\n':
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            sys.exit(255)
        time.sleep(0.001)
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()
    print('Could not interrupt actual extraction at checkpoint', file=sys.stderr)
    sys.exit(89)
result = subprocess.run(['chroot', str(root), '/bin/bash', '-c', command], input=script) if script is not None else subprocess.run(['chroot', str(root), '/bin/bash', '-c', command])
sys.exit(result.returncode)
'''


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0
                     and os.environ.get('IPHONE_RESTORE_VM_TESTS') == '1',
                     'requires explicit disposable Linux VM/root opt-in')
class RestoreFailureTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='iphone-restore-test-')
        self.addCleanup(self.work.cleanup)
        self.base = Path(self.work.name)
        self.root = self.base / 'phone'
        self.store = self.base / 'backups'
        self.fault = self.base / 'fault'
        self.fault.mkdir()
        self.store.mkdir(mode=0o700)
        for directory in ('bin', 'root/.ssh', 'srv/data', 'run', 'dev'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        shutil.copyfile('/usr/bin/busybox', self.root / 'bin/busybox')
        (self.root / 'bin/busybox').chmod(0o755)
        shutil.copyfile('/bin/bash', self.root / 'bin/bash')
        (self.root / 'bin/bash').chmod(0o755)
        libraries = subprocess.check_output(['ldd', '/bin/bash'], text=True)
        for name in set(re.findall(r'/[^\s()]+', libraries)):
            destination = self.root / name.lstrip('/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(name, destination)
        for applet in ('tar', 'gzip', 'sha256sum', 'stat', 'mkdir', 'rm', 'cat'):
            (self.root / 'bin' / applet).symlink_to('busybox')
        os.mknod(self.root / 'dev/null', 0o20666, os.makedev(1, 3))
        self.identity = self.root / 'root/.ssh/authorized_keys'
        self.identity.write_bytes(b'synthetic identity only\n')
        self.transport = self.base / 'transport.py'
        self.transport.write_text(TRANSPORT)
        self.old_store, self.old_ssh = persist.STORE, persist.SSH
        persist.STORE = self.store
        persist.SSH = [sys.executable, str(self.transport), str(self.root), str(self.store), str(self.fault)]
        self.addCleanup(self.restore_globals)

    def restore_globals(self):
        persist.STORE, persist.SSH = self.old_store, self.old_ssh

    def seed(self):
        for name, content, mode in (('a.txt', b'old\n', 0o640), ('b.bin', b'B' * 8192, 0o600)):
            path = self.root / 'srv/data' / name
            path.write_bytes(content)
            path.chmod(mode)

    def source_snapshot(self, size):
        snapshot = '20260930T000000Z-12345678'
        directory = self.store / snapshot
        directory.mkdir(mode=0o700)
        archive = directory / 'files.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            for name, content in (('a.txt', b'new\n'), ('b.bin', b'N' * size)):
                member = tarfile.TarInfo('srv/data/' + name)
                member.size, member.mode = len(content), 0o644
                output.addfile(member, io.BytesIO(content))
        manifest = {'format': 1, 'id': snapshot, 'kind': 'manual', 'entries': 2,
                    'sha256': persist.digest(archive)}
        (directory / 'manifest.json').write_text(json.dumps(manifest))
        return snapshot

    def assert_recovery(self, output):
        records = persist.restore_journal.records(self.store)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['phase'], 'recovery-needed')
        command = persist.restore_journal.recovery_command(record['before'])
        self.assertIn(command, output)
        self.assertEqual((self.store / 'restore-journal').stat().st_mode & 0o777, 0o700)
        self.assertEqual(next((self.store / 'restore-journal').glob('*.json')).stat().st_mode & 0o777, 0o600)
        pending = io.StringIO()
        with contextlib.redirect_stdout(pending):
            persist.restore_journal.show_pending(self.store)
        self.assertIn(command, pending.getvalue())
        self.assertEqual((self.root / 'srv/data/a.txt').read_bytes(), b'new\n')
        with contextlib.redirect_stdout(io.StringIO()):
            persist.restore(record['before'])
        for name, content, mode in (('a.txt', b'old\n', 0o640), ('b.bin', b'B' * 8192, 0o600)):
            path = self.root / 'srv/data' / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mode & 0o777, mode)
        self.assertEqual(self.identity.read_bytes(), b'synthetic identity only\n')
        self.assertEqual((self.root / 'srv/data/extra.txt').read_bytes(), b'extra preserved\n')
        pending = io.StringIO()
        with contextlib.redirect_stdout(pending):
            persist.restore_journal.show_pending(self.store)
        self.assertEqual(pending.getvalue(), '')
        self.assertEqual([r['phase'] for r in persist.restore_journal.records(self.store) if r['id'] == record['id']], ['recovered'])

    def test_interrupted_extraction_and_cleanup_error_allow_explicit_recovery(self):
        # Mutation captured: omitting the pre-apply journal prevents safe recovery.
        self.seed()
        source = self.source_snapshot(64 * 1024 * 1024)
        (self.fault / 'interrupt').touch()
        (self.fault / 'cleanup').touch()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError) as error:
            persist.restore(source)
        self.assertEqual(error.exception.returncode, 255)
        self.assertIn('limpeza', output.getvalue())
        self.assertLess((self.root / 'srv/data/b.bin').stat().st_size, 64 * 1024 * 1024)
        (self.fault / 'cleanup').unlink()
        self.assert_recovery(output.getvalue())

    def test_full_tmpfs_allows_explicit_recovery(self):
        # Mutation captured: suppressing the extraction error falsely reports success.
        target = self.root / 'srv/data'
        subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=64k,nosuid,nodev,noexec', 'tmpfs', str(target)], check=True)
        self.addCleanup(subprocess.run, ['umount', str(target)], check=True)
        self.seed()
        source = self.source_snapshot(1024 * 1024)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError) as error:
            persist.restore(source)
        self.assertNotEqual(error.exception.returncode, 0)
        self.assertLess((target / 'b.bin').stat().st_size, 1024 * 1024)
        self.assert_recovery(output.getvalue())


if __name__ == '__main__':
    unittest.main()
