"""Real isolated Git worktrees: exact patch and preservation boundaries."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('KERNEL_PATCHSET_SCRIPT', ROOT / 'scripts/build/kernel_patchset.py'))
SPEC = importlib.util.spec_from_file_location('patchset_under_test', SCRIPT)
PATCHSET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHSET)


class KernelPatchset(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='n71-patchset-git-')
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.candidate = self.root / 'candidate'
        self.saved_base, self.saved_patch = PATCHSET.BASE, PATCHSET.PATCH
        self.patch = self.root / 'patch'
        shutil.copyfile(self.saved_patch, self.patch)
        PATCHSET.PATCH = self.patch
        old, _ = PATCHSET.patch_method()
        self.original = b'/* synthetic source context */\n' + old
        target = self.source / PATCHSET.TARGET
        target.parent.mkdir(parents=True)
        target.write_bytes(self.original)
        (self.source / 'keep').write_bytes(b'KEEP_UNRELATED_SOURCE')
        self.git(self.source, 'init', '-q')
        self.git(self.source, 'add', '.')
        self.git(self.source, '-c', 'user.name=Patch Test', '-c', 'user.email=patch-test@example.invalid',
                 'commit', '-qm', 'Synthetic source fixture')
        PATCHSET.BASE = self.git(self.source, 'rev-parse', 'HEAD').decode().strip()
        self.git(self.source, 'worktree', 'add', '--detach', str(self.candidate), PATCHSET.BASE)

    def tearDown(self):
        PATCHSET.BASE, PATCHSET.PATCH = self.saved_base, self.saved_patch
        self.temporary.cleanup()

    def git(self, root, *args):
        return subprocess.check_output(
            ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
             '-C', str(root), *args], stderr=subprocess.PIPE, timeout=20)

    def test_apply_is_exact_idempotent_and_preserves_main_checkout(self):
        # Mutation captured: metadata claiming physical boot invents hardware proof.
        report = PATCHSET.apply(self.candidate)
        _, after = PATCHSET.patch_method()
        expected = b'/* synthetic source context */\n' + after
        self.assertEqual((self.candidate / PATCHSET.TARGET).read_bytes(), expected)
        self.assertEqual((self.source / PATCHSET.TARGET).read_bytes(), self.original)
        self.assertEqual((self.candidate / 'keep').read_bytes(), b'KEEP_UNRELATED_SOURCE')
        self.assertEqual(report['stage'], 'patched')
        self.assertFalse(report['physical_boot_tested'])
        self.assertEqual(PATCHSET.apply(self.candidate), report)
        self.assertEqual(PATCHSET.inspect(self.candidate)[2], report)
        self.assertEqual(self.git(self.source, 'status', '--porcelain'), b'')

    def test_preserved_checkout_and_original_check_are_refused(self):
        # Mutation captured: dropping the .git worktree guard patches the baseline.
        with self.assertRaises((ValueError, OSError)):
            PATCHSET.apply(self.source)
        with self.assertRaises(ValueError):
            PATCHSET.inspect(self.candidate)
        self.assertEqual((self.source / PATCHSET.TARGET).read_bytes(), self.original)

    def test_other_tracked_untracked_staged_and_target_mutations_preserved(self):
        # Mutation captured: dropping status scope accepts unrelated source changes.
        for name in ('keep', 'untracked'):
            path = self.candidate / name
            path.write_bytes(b'EXTERNAL_WORK')
            with self.assertRaises(ValueError):
                PATCHSET.apply(self.candidate)
            self.assertEqual(path.read_bytes(), b'EXTERNAL_WORK')
            if name == 'keep':
                path.write_bytes(b'KEEP_UNRELATED_SOURCE')
            else:
                path.unlink()
        target = self.candidate / PATCHSET.TARGET
        target.write_bytes(self.original + b'EXTERNAL_SOURCE_CHANGE')
        with self.assertRaises(ValueError):
            PATCHSET.apply(self.candidate)
        self.assertTrue(target.read_bytes().endswith(b'EXTERNAL_SOURCE_CHANGE'))
        target.write_bytes(self.original)
        PATCHSET.apply(self.candidate)
        self.git(self.candidate, 'add', PATCHSET.TARGET)
        with self.assertRaises(ValueError):
            PATCHSET.inspect(self.candidate)

    def test_patch_hash_commit_and_hidden_index_flags_are_refused(self):
        # Mutations captured: dropping patch/base/index checks accepts changed inputs.
        # Valid framing/original hunk with an altered plus-line must fail integrity.
        self.patch.write_bytes(self.patch.read_bytes().replace(b'val > 0xff', b'val > 0xfe'))
        with self.assertRaises(ValueError):
            PATCHSET.apply(self.candidate)
        shutil.copyfile(self.saved_patch, self.patch)
        PATCHSET.BASE = '0' * 40
        with self.assertRaises(ValueError):
            PATCHSET.apply(self.candidate)
        PATCHSET.BASE = self.git(self.source, 'rev-parse', 'HEAD').decode().strip()
        self.git(self.candidate, 'update-index', '--assume-unchanged', 'keep')
        (self.candidate / 'keep').write_bytes(b'HIDDEN_SOURCE_CHANGE')
        with self.assertRaises(ValueError):
            PATCHSET.apply(self.candidate)
        self.assertEqual((self.candidate / 'keep').read_bytes(), b'HIDDEN_SOURCE_CHANGE')

    def test_target_symlink_and_checkout_alias_are_refused(self):
        # Mutation captured: resolving the checkout argument silently accepts an alias.
        target = self.candidate / PATCHSET.TARGET
        external = self.root / 'untouched'
        external.write_bytes(self.original)
        target.unlink()
        target.symlink_to(external)
        with self.assertRaises(ValueError):
            PATCHSET.apply(self.candidate)
        self.assertEqual(external.read_bytes(), self.original)
        target.unlink()
        target.write_bytes(self.original)
        alias = self.root / 'alias'
        alias.symlink_to(self.candidate, target_is_directory=True)
        with self.assertRaises(ValueError):
            PATCHSET.apply(alias)


if __name__ == '__main__':
    unittest.main()
