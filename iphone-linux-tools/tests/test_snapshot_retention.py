import hashlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tarfile
import tempfile
import unittest


HOST = Path(__file__).resolve().parents[1] / 'scripts/host'
sys.path.insert(0, str(HOST))
import persist
import snapshot_lock
import snapshot_retention


class SnapshotRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name) / 'backups'
        self.previous_store = persist.STORE
        persist.STORE = self.store

    def tearDown(self):
        persist.STORE = self.previous_store
        self.temp.cleanup()

    def add_snapshot(self, snapshot_id, **options):
        kind = options.get('kind', 'automatic')
        created_at = options.get('created_at')
        valid = options.get('valid', True)
        extra = options.get('extra')
        directory = self.store / snapshot_id
        directory.mkdir(parents=True)
        archive = directory / 'files.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            member = tarfile.TarInfo('srv/data/state.txt')
            content = b'snapshot data\n'
            member.size = len(content)
            member.mode = 0o640
            output.addfile(member, io.BytesIO(content))
        manifest = {
            'format': 1,
            'id': snapshot_id,
            'kind': kind,
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'entries': 1,
        }
        if created_at is not None:
            manifest['created_at'] = created_at
        if not valid:
            manifest['sha256'] = '0' * 64
        (directory / 'manifest.json').write_text(json.dumps(manifest))
        if extra:
            for name, content in extra.items():
                (directory / name).write_text(content)
        return directory

    def test_prune_keeps_latest_pending_manual_invalid_and_extra(self):
        # Mutation captured: removing pending/latest protection must not delete their snapshots.
        ids = [
            '20260930T120000Z-00000001',
            '20260930T120001Z-00000002',
            '20260930T120002Z-00000003',
            '20260930T120003Z-00000004',
        ]
        for index, snapshot_id in enumerate(ids):
            self.add_snapshot(snapshot_id, created_at=f'2026-09-30T12:00:0{index}.000000Z')
        self.add_snapshot('20260930T120004Z-00000005', kind='manual')
        self.add_snapshot('20260930T120005Z-00000006', kind='pre-restore')
        self.add_snapshot('20260930T120006Z-00000007', valid=False)
        self.add_snapshot('20260930T120007Z-00000008', extra={'extra.txt': 'keep'})
        (self.store / '20260930T120008Z-00000009').symlink_to(self.store / ids[0], target_is_directory=True)
        journal = self.store / 'restore-journal'
        journal.mkdir()
        (journal / ('a' * 32 + '.json')).write_text(json.dumps({
            'format': 1, 'id': 'a' * 32, 'phase': 'applying',
            'source': ids[0], 'before': ids[1],
        }))

        removed = snapshot_retention.prune(
            self.store, {'keep': 1, 'latest': ids[1]}, persist.load_snapshot)

        self.assertEqual(removed, [ids[2]])
        self.assertTrue((self.store / ids[0]).exists())
        self.assertTrue((self.store / ids[1]).exists())
        self.assertFalse((self.store / ids[2]).exists())
        self.assertTrue((self.store / ids[3]).exists())
        for snapshot_id in ('20260930T120004Z-00000005', '20260930T120005Z-00000006',
                            '20260930T120006Z-00000007', '20260930T120007Z-00000008',
                            '20260930T120008Z-00000009'):
            self.assertTrue((self.store / snapshot_id).exists())

    def test_latest_survives_clock_regression(self):
        old = '20260930T120000Z-00000001'
        new = '20260930T120001Z-00000002'
        self.add_snapshot(old, created_at='2026-09-30T11:00:00.000001Z')
        self.add_snapshot(new, created_at='2026-09-30T12:00:00.000001Z')

        removed = snapshot_retention.prune(
            self.store, {'keep': 1, 'latest': old}, persist.load_snapshot)

        self.assertEqual(removed, [])
        self.assertTrue((self.store / old).exists())
        self.assertTrue((self.store / new).exists())

    def test_created_at_microseconds_order_same_second(self):
        # Mutation captured: ignoring created_at must not replace microsecond ordering with ID order.
        earlier_id = '20260930T120000Z-ffffffff'
        later_id = '20260930T120000Z-00000001'
        self.add_snapshot(earlier_id, created_at='2026-09-30T12:00:00.000001Z')
        self.add_snapshot(later_id, created_at='2026-09-30T12:00:00.000002Z')

        removed = snapshot_retention.prune(self.store, {'keep': 1}, persist.load_snapshot)

        self.assertEqual(removed, [earlier_id])
        self.assertTrue((self.store / later_id).exists())

    def test_historical_ids_are_fallback_order(self):
        older_id = '20260930T120000Z-ffffffff'
        newer_id = '20260930T120001Z-00000001'
        self.add_snapshot(older_id)
        self.add_snapshot(newer_id)
        dated_id = '20260930T115959Z-12345678'
        self.add_snapshot(dated_id, created_at='2026-09-30T11:59:59.000001Z')

        removed = snapshot_retention.prune(self.store, {'keep': 1}, persist.load_snapshot)

        self.assertEqual(removed, [dated_id, older_id])
        self.assertTrue((self.store / newer_id).exists())

    def test_invalid_journal_blocks_retention(self):
        # Mutation captured: unknown journal phases must block retention instead of being ignored.
        snapshot_id = '20260930T120000Z-00000001'
        self.add_snapshot(snapshot_id)
        journal = self.store / 'restore-journal'
        journal.mkdir()
        (journal / ('b' * 32 + '.json')).write_text(json.dumps({
            'format': 1, 'id': 'b' * 32, 'phase': 'unknown',
            'source': snapshot_id,
        }))

        with self.assertRaises(ValueError):
            snapshot_retention.prune(self.store, {'keep': 1}, persist.load_snapshot)
        self.assertTrue((self.store / snapshot_id).exists())

    def test_lock_is_nonblocking_and_releases_without_deleting_inode(self):
        child_code = (
            'import pathlib,sys\n'
            'sys.path.insert(0, sys.argv[2])\n'
            'import snapshot_lock\n'
            'with snapshot_lock.lock(pathlib.Path(sys.argv[1])):\n'
            '    print("LOCKED", flush=True)\n'
            '    input()\n'
        )
        process = subprocess.Popen(
            [sys.executable, '-c', child_code, str(self.store), str(HOST)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            lock_path = self.store / snapshot_lock.LOCK_NAME
            ready, _, _ = select.select([process.stdout], [], [], 5)
            self.assertTrue(ready, 'O processo filho não confirmou LOCKED a tempo.')
            self.assertEqual(process.stdout.readline().strip(), 'LOCKED')
            with self.assertRaises(BlockingIOError):
                with snapshot_lock.lock(self.store):
                    pass
            process.stdin.write('\n')
            process.stdin.flush()
            process.stdin.close()
            result = process.wait(timeout=5)
            error = process.stderr.read()
            process.stderr.close()
            process.stdout.close()
            self.assertEqual(result, 0, error)
            inode = lock_path.stat().st_ino
            with snapshot_lock.lock(self.store):
                pass
            self.assertEqual(lock_path.stat().st_ino, inode)
            self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.store.stat().st_mode & 0o777, 0o700)
            self.assertEqual(lock_path.stat().st_uid, os.getuid())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_lock_rejects_symlink_and_hardlink(self):
        # Mutation captured: accepting symlink or hardlink lock targets must fail closed.
        self.store.mkdir(parents=True)
        lock_path = self.store / snapshot_lock.LOCK_NAME
        target = self.store / 'target'
        target.write_text('x')
        lock_path.symlink_to(target)
        with self.assertRaises((OSError, ValueError)):
            with snapshot_lock.lock(self.store):
                pass
        lock_path.unlink()
        os.link(target, lock_path)
        with self.assertRaises(ValueError):
            with snapshot_lock.lock(self.store):
                pass

    def test_lock_rejects_fifo_without_blocking(self):
        # Mutation captured: dropping inode validation can change a rejected FIFO mode.
        self.store.mkdir(parents=True)
        lock_path = self.store / snapshot_lock.LOCK_NAME
        os.mkfifo(lock_path, 0o640)
        lock_path.chmod(0o640)
        child_code = (
            'import pathlib,sys\n'
            'sys.path.insert(0, sys.argv[2])\n'
            'import snapshot_lock\n'
            'try:\n'
            '    with snapshot_lock.lock(pathlib.Path(sys.argv[1])): pass\n'
            'except (OSError, ValueError):\n'
            '    print("rejected")\n'
        )
        result = subprocess.run(
            [sys.executable, '-c', child_code, str(self.store), str(HOST)],
            capture_output=True, text=True, timeout=2,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'rejected')
        self.assertEqual(lock_path.stat().st_mode & 0o777, 0o640)


if __name__ == '__main__':
    unittest.main()
