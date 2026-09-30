import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('persist', Path(__file__).resolve().parents[1] / 'scripts/host/persist.py')
persist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(persist)


class SnapshotBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.root = Path(self.work.name)
        self.previous_store = persist.STORE
        persist.STORE = self.root

    def tearDown(self):
        persist.STORE = self.previous_store
        self.work.cleanup()

    def archive(self, entries):
        path = self.root / 'fixture.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, kind in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.mode = 0o640
                member.linkname = '/etc/passwd' if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ''
                if kind == tarfile.REGTYPE:
                    content = b'example data\n'
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
                else:
                    archive.addfile(member)
        return path

    def test_regular_work_files_are_accepted(self):
        path = self.archive([('root/notes.txt', tarfile.REGTYPE), ('srv/data/state.txt', tarfile.REGTYPE)])
        self.assertEqual(persist.validate_archive(path), [('root/notes.txt', False), ('srv/data/state.txt', False)])

    def test_outside_scope_and_ssh_identity_are_rejected(self):
        for name in ('/etc/passwd', 'root/../etc/passwd', 'root/.ssh/authorized_keys', 'root/.config/herdr/sessions/live.json', 'srv/iphone/config', 'root//double', 'root/new\nline'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    persist.validate_archive(self.archive([(name, tarfile.REGTYPE)]))

    def test_links_and_special_files_cannot_be_restored(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    persist.validate_archive(self.archive([('root/danger', kind)]))

    def test_duplicate_and_file_as_parent_are_rejected(self):
        for entries in ([('root/file', tarfile.REGTYPE)] * 2,
                        [('root/file', tarfile.REGTYPE), ('root/file/child', tarfile.REGTYPE)]):
            with self.assertRaises(ValueError):
                persist.validate_archive(self.archive(entries))

    def test_changed_archive_fails_integrity_check(self):
        snapshot_id = '20260929T000000Z-12345678'
        directory = self.root / snapshot_id
        directory.mkdir()
        archive = self.archive([('srv/data/state', tarfile.REGTYPE)])
        archive.rename(directory / 'files.tar.gz')
        archive = directory / 'files.tar.gz'
        manifest = {'format': 1, 'id': snapshot_id, 'entries': 1, 'sha256': persist.digest(archive)}
        (directory / 'manifest.json').write_text(json.dumps(manifest))
        self.assertEqual(len(persist.load_snapshot(snapshot_id)[1]), 1)
        with archive.open('ab') as file:
            file.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'Integridade'):
            persist.load_snapshot(snapshot_id)

    def test_snapshot_id_cannot_escape_store(self):
        with self.assertRaises(ValueError):
            persist.load_snapshot('../../private')


if __name__ == '__main__':
    unittest.main()
