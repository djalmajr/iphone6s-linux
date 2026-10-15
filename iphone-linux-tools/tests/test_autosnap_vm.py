"""Scheduler to real BusyBox archive/restore in the dedicated disposable VM."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import test_restore_failure_vm as vm_fixture

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0
                     and os.environ.get('IPHONE_RESTORE_VM_TESTS') == '1',
                     'requires explicit disposable Linux VM/root opt-in')
class AutoSnapshotVmTests(unittest.TestCase):
    def test_scheduled_busybox_snapshots_survive_disconnect_and_restore(self):
        fixture = vm_fixture.RestoreFailureTests('test_full_tmpfs_allows_explicit_recovery')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.seed()
        project = fixture.base / 'project'
        host = project / 'scripts/host'
        host.mkdir(parents=True)
        for name in ('autosnap.py', 'persist.py', 'device_profile.py', 'restore_journal.py', 'snapshot_lock.py', 'snapshot_retention.py'):
            shutil.copy(ROOT / 'scripts/host' / name, host / name)
        fixture.store = project / 'backups'
        vm_fixture.persist.STORE = fixture.store
        commands = fixture.base / 'commands'
        commands.mkdir()
        script = commands / 'ssh'
        script.write_text('#!' + sys.executable + '\nimport pathlib,subprocess,sys\n'
                          'fault=pathlib.Path(' + repr(str(fixture.fault / 'offline')) + ')\n'
                          'if fault.exists(): sys.exit(255)\n'
                          'raise SystemExit(subprocess.call(' + repr([sys.executable, str(fixture.transport), str(fixture.root), str(fixture.store), str(fixture.fault)]) + '+[sys.argv[-1]]))\n')
        script.chmod(0o700)
        environment = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ['PATH'])
        result = subprocess.run([sys.executable, str(host / 'autosnap.py'), 'watch', '--interval', '1', '--keep', '1', '--cycles', '2'],
                                env=environment, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('Snapshot:'), 2)
        archives = list(fixture.store.glob('*/files.tar.gz'))
        self.assertEqual(len(archives), 1)
        snapshot = archives[0].parent.name
        original = archives[0].read_bytes()
        (fixture.fault / 'offline').touch()
        result = subprocess.run([sys.executable, str(host / 'autosnap.py'), 'once', '--keep', '1'],
                                env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(archives[0].read_bytes(), original)
        state = json.loads((project / 'logs/autosnap-last.json').read_text())
        self.assertEqual(state['outcome'], 'failed')
        self.assertEqual(state['last_success'], snapshot)
        (fixture.fault / 'offline').unlink()
        vm_fixture.persist.SSH = [sys.executable, str(fixture.transport), str(fixture.root), str(fixture.store), str(fixture.fault)]
        (fixture.root / 'srv/data/a.txt').write_bytes(b'changed after snapshot\n')
        with contextlib.redirect_stdout(io.StringIO()):
            vm_fixture.persist.restore(snapshot)
        self.assertEqual((fixture.root / 'srv/data/a.txt').read_bytes(), b'old\n')
        self.assertEqual((fixture.root / 'srv/data/b.bin').read_bytes(), b'B' * 8192)
        self.assertEqual((fixture.root / 'srv/data/a.txt').stat().st_mode & 0o777, 0o640)
        self.assertEqual(fixture.identity.read_bytes(), b'synthetic identity only\n')
        self.assertEqual(list(fixture.store.glob('.partial-*')), [])


if __name__ == '__main__':
    unittest.main()
