"""Reject accidental local path redirection before snapshot/journal I/O."""
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import persist
import restore_journal
import snapshot_lock

ID = '20261001T000000Z-11223344'
BEFORE = '20261001T000001Z-55667788'


class LocalSnapshotPathTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='snapshot-paths-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.store = self.root / 'store'
        self.store.mkdir(mode=0o700)
        previous = persist.STORE
        persist.STORE = self.store
        self.addCleanup(setattr, persist, 'STORE', previous)
        self.outside = self.root / 'outside'
        self.outside.mkdir()
        self.outside.chmod(0o755)
        self.sentinel = self.outside / 'sentinel'
        self.sentinel.write_bytes(b'UNRELATED_SYNTHETIC_DATA')
        self.original_mode = stat.S_IMODE(self.outside.stat().st_mode)

    def archive(self, directory):
        directory.mkdir(exist_ok=True)
        path = directory / 'files.tar.gz'
        with tarfile.open(path, 'w:gz') as tar:
            member = tarfile.TarInfo('srv/data/synthetic.txt')
            member.size, member.mode = 9, 0o640
            tar.addfile(member, io.BytesIO(b'SYNTHETIC'))
        data = {'format': 1, 'id': ID, 'entries': 1, 'sha256': persist.digest(path),
                'kind': 'manual'}
        (directory / 'manifest.json').write_text(json.dumps(data))

    def unchanged(self):
        self.assertEqual(stat.S_IMODE(self.outside.stat().st_mode), self.original_mode)
        self.assertEqual(self.sentinel.read_bytes(), b'UNRELATED_SYNTHETIC_DATA')
        self.assertFalse(list(self.outside.glob('*.json')))

    def test_regular_snapshot_and_journal_remain_compatible(self):
        self.archive(self.store / ID)
        path, members = persist.load_snapshot(ID)
        self.assertEqual(path, self.store / ID / 'files.tar.gz')
        self.assertEqual(members, [('srv/data/synthetic.txt', False)])
        self.assertEqual(persist.load_snapshot(None), (path, members))
        record = restore_journal.prepare(self.store, ID, BEFORE)
        restore_journal.transition(self.store, record, 'applying')
        self.assertEqual(restore_journal.records(self.store)[0]['phase'], 'applying')
        self.assertEqual(stat.S_IMODE((self.store / 'restore-journal').stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(next((self.store / 'restore-journal').glob('*.json')).stat().st_mode), 0o600)

    def test_journal_directory_link_never_writes_or_chmods_external_directory(self):
        # Mutation captured: omitting journal-directory check writes/chmods a symlink target.
        (self.store / 'restore-journal').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            restore_journal.prepare(self.store, ID, BEFORE)
        with self.assertRaises(ValueError):
            restore_journal.records(self.store)
        self.unchanged()

    def test_dangling_journal_link_is_not_an_empty_journal(self):
        # Mutation captured: checking exists() silently drops unknown pending references.
        (self.store / 'restore-journal').symlink_to(self.root / 'absent', target_is_directory=True)
        with self.assertRaises(ValueError):
            restore_journal.records(self.store)
        self.unchanged()

    def test_snapshot_directory_link_is_rejected_for_explicit_and_default_selection(self):
        # Mutation captured: loading a valid-ID directory link escapes the local store.
        source = self.outside / 'source'
        self.archive(source)
        (self.store / ID).symlink_to(source, target_is_directory=True)
        for identifier in (ID, None):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    persist.load_snapshot(identifier)
        with self.assertRaises(ValueError):
            persist.snapshots()
        self.unchanged()

    def test_snapshot_archive_and_manifest_links_are_rejected(self):
        # Mutation captured: checking the directory alone still reads linked child files.
        directory = self.store / ID
        for name in ('manifest.json', 'files.tar.gz'):
            for hard in (False, True):
                with self.subTest(name=name, hard=hard):
                    self.archive(directory)
                    child = directory / name
                    target = self.outside / ('target-' + name)
                    target.write_bytes(child.read_bytes())
                    child.unlink()
                    if hard:
                        os.link(target, child)
                    else:
                        child.symlink_to(target)
                    with self.assertRaises(ValueError):
                        persist.load_snapshot(ID)
                    child.unlink()
                    target.unlink()
        self.unchanged()

    def test_journal_record_links_are_rejected_before_read(self):
        # Mutation captured: accepting record links reads foreign recovery state.
        record = restore_journal.prepare(self.store, ID, BEFORE)
        path = self.store / 'restore-journal' / (record['id'] + '.json')
        content = path.read_bytes()
        target = self.outside / 'journal-copy'
        target.write_bytes(content)
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind):
                path.unlink()
                if kind == 'symlink':
                    path.symlink_to(target)
                else:
                    os.link(target, path)
                with self.assertRaises(ValueError):
                    restore_journal.records(self.store)
                self.assertEqual(target.read_bytes(), content)
        self.unchanged()

    def test_journal_fifo_is_rejected_before_read(self):
        # Mutation captured: reading a special record file would block instead of failing.
        record = restore_journal.prepare(self.store, ID, BEFORE)
        path = self.store / 'restore-journal' / (record['id'] + '.json')
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(ValueError):
            restore_journal.records(self.store)
        self.unchanged()

    def test_foreign_owned_regular_file_is_rejected_by_shared_boundary(self):
        # Mutation captured: ignoring inode ownership admits files outside this operator's store.
        if os.geteuid() == 0:
            target = self.root / 'foreign-owner-synthetic'
            target.write_bytes(b'SYNTHETIC')
            os.chown(target, 1, -1)
        else:
            target = Path('/usr/bin/env')
        info = target.lstat()
        self.assertTrue(stat.S_ISREG(info.st_mode))
        self.assertEqual(info.st_nlink, 1)
        self.assertNotEqual(info.st_uid, os.geteuid())
        self.assertEqual(info.st_mode & 0o7000, 0)
        with self.assertRaises(ValueError):
            snapshot_lock.check_local_path(target)
        if os.geteuid() == 0:
            with self.assertRaises(ValueError):
                snapshot_lock._open_lock(target)
        self.unchanged()

    def test_store_link_is_rejected_by_lock_and_journal_before_external_changes(self):
        # Mutation captured: following a store alias changes an unrelated directory's mode.
        alias = self.root / 'store-alias'
        alias.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            with snapshot_lock.lock(alias):
                self.fail('Redirected store lock acquired')
        with self.assertRaises(ValueError):
            restore_journal.prepare(alias, ID, BEFORE)
        self.unchanged()


if __name__ == '__main__':
    unittest.main()
