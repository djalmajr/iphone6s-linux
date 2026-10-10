"""Synthetic filesystem/CLI regressions for scheduler redirects in #26."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
spec = importlib.util.spec_from_file_location('autosnap_paths', ROOT / 'scripts/host/autosnap.py')
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)
STATE = {'format': 1, 'last_success': None}


class AutoSnapshotPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='autosnap-paths-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / 'project'
        host = self.root / 'scripts/host'
        host.mkdir(parents=True)
        for name in ('autosnap.py', 'snapshot_lock.py'):
            shutil.copyfile(ROOT / 'scripts/host' / name, host / name)
        (host / 'persist.py').write_text(
            'from pathlib import Path\n'
            'root = Path(__file__).resolve().parents[2]\n'
            '(root / "job-started").write_text("started")\n'
            'print("Snapshot: 20261001T010000Z-abcdef01")\n')
        self.addCleanup(setattr, scheduler, 'ROOT', scheduler.ROOT)
        scheduler.ROOT = self.root
        self.logs = self.root / 'logs'
        self.path = self.logs / 'autosnap-last.json'
        self.external = self.base / 'outside'

    def cli(self, mode='once'):
        try:
            return subprocess.run([sys.executable, str(self.root / 'scripts/host/autosnap.py'), mode],
                                  capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            self.fail('Scheduler blocked on an invalid path.')

    def assert_refused(self):
        result = self.cli()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('Caminho local', result.stderr)
        self.assertFalse((self.root / 'job-started').exists())

    def test_missing_status_has_no_filesystem_side_effects(self):
        # Mutation: creating logs on read changes the read-only status contract.
        self.assertEqual(scheduler.read_status(), STATE)
        self.assertFalse(self.logs.exists())

    def test_linked_root_is_refused_without_creating_external_logs(self):
        # Mutation: dropping root validation permits publishing under a root alias.
        alias = self.base / 'root-alias'
        alias.symlink_to(self.root, target_is_directory=True)
        scheduler.ROOT = alias
        with self.assertRaises(ValueError):
            scheduler.read_status()
        with self.assertRaises(ValueError):
            scheduler.write_status(STATE)
        self.assertFalse(self.logs.exists())

    def test_regular_cli_state_is_private_and_readable(self):
        # Mutation: publishing without the private temporary leaves mode 644.
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.path.read_text())
        self.assertEqual(data['outcome'], 'success')
        self.assertEqual(data['last_success'], '20261001T010000Z-abcdef01')
        self.assertEqual(self.logs.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(scheduler.read_status(), data)
        self.assertEqual(list(self.logs.glob('.autosnap-*')), [])

    def test_logs_redirect_refused_before_read_write_or_job(self):
        # Mutation: omitting directory validation follows logs and starts a job.
        self.external.mkdir()
        self.external.chmod(0o755)
        self.logs.symlink_to(self.external, target_is_directory=True)
        self.assert_refused()
        with self.assertRaises(ValueError):
            scheduler.write_status(STATE)
        self.assertEqual(list(self.external.iterdir()), [])
        self.assertEqual(self.external.stat().st_mode & 0o777, 0o755)
        self.external.rmdir()
        with self.assertRaises(ValueError):
            scheduler.read_status()
        self.assertFalse(self.external.exists())

    def test_state_links_refused_and_external_bytes_preserved(self):
        # Mutation: omitting state validation reads redirected JSON or starts a job.
        self.logs.mkdir()
        self.external.write_text(json.dumps(STATE))
        self.external.chmod(0o640)
        original = self.external.read_bytes()
        self.path.symlink_to(self.external)
        self.assert_refused()
        with self.assertRaises(ValueError):
            scheduler.write_status(STATE)
        self.assertEqual(self.external.read_bytes(), original)
        self.assertEqual(self.external.stat().st_mode & 0o777, 0o640)
        self.external.unlink()
        self.assert_refused()
        with self.assertRaises(ValueError):
            scheduler.write_status(STATE)
        self.assertFalse(self.external.exists())

    def test_hardlink_state_refused_before_job(self):
        # Mutation: dropping shared link count permits reading aliased state.
        self.logs.mkdir()
        self.external.write_text(json.dumps(STATE))
        os.link(self.external, self.path)
        self.assert_refused()
        self.assertEqual(json.loads(self.external.read_text()), STATE)

    def test_fifo_state_refused_without_open_or_job(self):
        # Mutation: dropping nonregular metadata check blocks on FIFO read.
        self.logs.mkdir()
        os.mkfifo(self.path)
        self.assert_refused()
        self.assertTrue(stat.S_ISFIFO(self.path.lstat().st_mode))

    def test_incompatible_owner_and_special_modes_refused(self):
        # Mutation: dropping metadata owner/special-mode checks accepts invalid state.
        self.logs.mkdir()
        self.path.write_text(json.dumps(STATE))
        self.path.chmod(0o1600)
        self.assertEqual(self.path.stat().st_mode & 0o7777, 0o1600)
        self.assert_refused()
        self.path.chmod(0o600)
        with mock.patch.object(scheduler.os, 'geteuid', return_value=os.geteuid() + 1):
            with self.assertRaises(ValueError):
                scheduler.read_status()

    def test_failed_publication_preserves_previous_state_and_cleans_temporary(self):
        # Mutation: omitting cleanup leaves a private temporary after failed rename.
        scheduler.write_status(STATE)
        original = self.path.read_bytes()
        with mock.patch.object(Path, 'replace', side_effect=OSError('synthetic rename failure')):
            with self.assertRaises(OSError):
                scheduler.write_status({'format': 1, 'last_success': 'new'})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.logs.glob('.autosnap-*')), [])

    def test_changed_destination_is_refused_before_publication(self):
        # Mutation: omitting second validation overwrites a newly redirected state.
        self.external.write_text(json.dumps(STATE))
        original = self.external.read_bytes()
        real_dump = scheduler.json.dump

        def redirect(state, output, **options):
            real_dump(state, output, **options)
            self.path.symlink_to(self.external)

        with mock.patch.object(scheduler.json, 'dump', side_effect=redirect):
            with self.assertRaises(ValueError):
                scheduler.write_status(STATE)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(self.external.read_bytes(), original)
        self.assertEqual(list(self.logs.glob('.autosnap-*')), [])


if __name__ == '__main__':
    unittest.main()
