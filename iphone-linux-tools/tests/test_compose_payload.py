"""Filesystem and CLI regressions for the output redirect bug in #25."""
import hashlib
import importlib.util
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
spec = importlib.util.spec_from_file_location('compose_payload', ROOT / 'scripts/build/compose-payload.py')
composer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(composer)


class ComposePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='compose-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.project = self.base / 'project'
        self.script = self.project / 'scripts/build/compose-payload.py'
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/build/compose-payload.py', self.script)
        self.artifacts = self.project / 'artifacts'
        self.artifacts.mkdir()
        for name in ('m1n1.bin', 's8000-n71.dtb', 'vmlinuz-apple-16k'):
            (self.artifacts / name).write_bytes(name.encode())
        self.initramfs = self.base / 'initramfs'
        self.initramfs.write_bytes(b'SYNTHETIC_RAMFS')
        self.expected = (b'm1n1.bin' + composer.BOOTARGS + b's8000-n71.dtb'
                         + b'vmlinuz-apple-16k' + b'SYNTHETIC_RAMFS')
        self.output = self.project / 'candidate.bin'
        self.external = self.base / 'outside'

    def compose(self):
        return composer.compose(self.initramfs, self.output, self.artifacts)

    def policy_refused(self):
        try:
            self.compose()
        except (OSError, ValueError) as error:
            self.assertIsInstance(error, ValueError, 'Policy must reject before output filesystem IO.')
            return str(error)
        self.fail('Composer accepted an invalid output.')

    def cli(self):
        try:
            return subprocess.run([sys.executable, str(self.script), str(self.initramfs), str(self.output)],
                                  capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            self.fail('Composer blocked on a special output instead of refusing it.')

    def test_cli_publishes_exact_private_payload(self):
        # Mutation: direct write instead of private temporary publishes mode 644.
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), self.expected)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        self.assertIn(hashlib.sha256(self.expected).hexdigest(), result.stdout)
        self.assertEqual(list(self.output.parent.glob('.compose-*')), [])

    def test_identical_recompose_keeps_inode_and_mtime(self):
        # Mutation: replacing identical output recreates its inode or timestamp.
        self.compose()
        self.output.chmod(0o755)
        before = self.output.stat()
        self.compose()
        after = self.output.stat()
        self.assertEqual((after.st_ino, after.st_mtime_ns), (before.st_ino, before.st_mtime_ns))
        self.assertEqual(after.st_mode & 0o777, 0o600)
        self.assertEqual(self.output.read_bytes(), self.expected)

    def test_different_existing_output_remains_unchanged(self):
        # Mutation: ignoring differing bytes overwrites a preserved output.
        self.output.write_bytes(b'KEEP_EXISTING')
        self.output.chmod(0o640)
        with self.assertRaises(ValueError):
            self.compose()
        self.assertEqual(self.output.read_bytes(), b'KEEP_EXISTING')
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.output.parent.glob('.compose-*')), [])

    def test_existing_and_dangling_links_preserve_external_target(self):
        # Mutation: following output metadata allows redirects past the guard.
        self.external.write_bytes(self.expected)
        self.external.chmod(0o755)
        self.output.symlink_to(self.external)
        self.policy_refused()
        self.assertEqual(self.external.read_bytes(), self.expected)
        self.assertEqual(self.external.stat().st_mode & 0o777, 0o755)
        self.external.unlink()
        self.policy_refused()
        self.assertFalse(self.external.exists())
        self.assertTrue(self.output.is_symlink())

    def test_hardlink_and_special_mode_are_refused(self):
        # Mutation: dropping link count or mode checks permits chmod on shared output.
        self.external.write_bytes(self.expected)
        self.external.chmod(0o755)
        os.link(self.external, self.output)
        with self.assertRaises(ValueError):
            self.compose()
        self.assertEqual(self.external.stat().st_mode & 0o777, 0o755)
        self.output.unlink()
        self.output.write_bytes(self.expected)
        self.output.chmod(0o1600)
        with self.assertRaises(ValueError):
            self.compose()
        self.assertEqual(self.output.stat().st_mode & 0o7777, 0o1600)

    def test_fifo_is_refused_before_open_without_blocking(self):
        # Mutation: accepting special output types blocks at the FIFO open.
        os.mkfifo(self.output)
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Destino deve ser arquivo regular', result.stderr)
        self.assertTrue(stat.S_ISFIFO(self.output.lstat().st_mode))

    def test_linked_parent_does_not_publish_outside_chosen_tree(self):
        # Mutation: following parent stat instead of lstat permits directory redirects.
        self.external.mkdir()
        linked = self.project / 'linked'
        linked.symlink_to(self.external, target_is_directory=True)
        self.output = linked / 'candidate.bin'
        with self.assertRaises(ValueError):
            self.compose()
        self.assertEqual(list(self.external.iterdir()), [])

    def test_unowned_or_writable_parent_is_refused(self):
        # Mutation: ignoring directory ownership/permissions permits unsafe publication.
        with mock.patch.object(composer.os, 'geteuid', return_value=os.geteuid() + 1):
            with self.assertRaises(ValueError):
                self.compose()
        self.project.chmod(0o777)
        with self.assertRaises(ValueError):
            self.compose()
        self.assertFalse(self.output.exists())

    def test_failed_rename_removes_only_its_temporary(self):
        # Mutation: omitting temporary cleanup leaves a private archive after failure.
        self.external.write_bytes(b'KEEP_OUTSIDE')
        with mock.patch.object(composer.os, 'replace', side_effect=OSError('synthetic rename failure')):
            with self.assertRaises(OSError):
                self.compose()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob('.compose-*')), [])
        self.assertEqual(self.external.read_bytes(), b'KEEP_OUTSIDE')

    def test_dotdot_destination_is_refused_before_reading_inputs(self):
        # Mutation: dropping literal-path validation moves failure past the output guard.
        self.output = self.project / 'absent/../candidate.bin'
        self.initramfs.unlink()
        self.assertIn('componentes ..', self.policy_refused())
        self.assertFalse((self.project / 'candidate.bin').exists())


if __name__ == '__main__':
    unittest.main()
