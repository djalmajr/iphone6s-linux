"""Isolated Git worktrees prove bundle scope, exact writes and preservation."""
import difflib
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('KERNEL_BUNDLE_SCRIPT', ROOT / 'scripts/build/kernel_bundle.py'))
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location('bundle_under_test', SCRIPT)
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


class KernelBundle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='n71-bundle-git-')
        self.root = Path(self.temporary.name).resolve()
        self.original = self.root / 'original'
        self.original.mkdir()
        self.checkout = self.root / 'candidate'
        self.saved = BUNDLE.BASE, BUNDLE.ROOT, BUNDLE.FILES, BUNDLE.PATCHES
        BUNDLE.ROOT = self.root
        BUNDLE.FILES, BUNDLE.PATCHES = {}, {}
        self.before, self.after = {}, {}
        patches = self.root / 'phone/kernel/patches'
        patches.mkdir(parents=True)
        # Same four paths and two-patch shape; fixture contents are independent.
        groups = [('0001.patch', list(self.saved[2])[:1]),
                  ('0002.patch', list(self.saved[2])[1:])]
        for patch_name, names in groups:
            raw = b'Subject: synthetic bundle\n\n'
            for name in names:
                before = ('/* preserved header */\n' + name + '_old\n/* preserved footer */\n').encode()
                after = before.replace(b'_old\n', b'_new\n')
                self.before[name], self.after[name] = before, after
                BUNDLE.FILES[name] = (hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest())
                path = self.original / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(before)
                raw += ''.join(difflib.unified_diff(before.decode().splitlines(True),
                              after.decode().splitlines(True), 'a/' + name, 'b/' + name)).encode()
            (patches / patch_name).write_bytes(raw)
            BUNDLE.PATCHES[patch_name] = hashlib.sha256(raw).hexdigest()
        (self.original / 'keep').write_text('UNRELATED\n')
        self.git(self.original, 'init', '-q')
        self.git(self.original, 'add', '.')
        self.git(self.original, '-c', 'user.name=Bundle Test', '-c',
                 'user.email=bundle@example.invalid', 'commit', '-qm', 'Synthetic fixture')
        BUNDLE.BASE = self.git(self.original, 'rev-parse', 'HEAD').decode().strip()
        self.git(self.original, 'worktree', 'add', '--detach', str(self.checkout), BUNDLE.BASE)

    def tearDown(self):
        BUNDLE.BASE, BUNDLE.ROOT, BUNDLE.FILES, BUNDLE.PATCHES = self.saved
        self.temporary.cleanup()

    def git(self, folder, *args):
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null',
                                       '-c', 'core.fsmonitor=false', '-C', str(folder), *args],
                                       stderr=subprocess.PIPE, timeout=20)

    def test_exact_apply_and_idempotence_preserve_baseline(self):
        # Kills missing patch application and invented image/physical proof.
        report = BUNDLE.apply(self.checkout)
        for name, expected in self.after.items():
            self.assertEqual((self.checkout / name).read_bytes(), expected)
            self.assertEqual((self.original / name).read_bytes(), self.before[name])
        self.assertEqual(self.git(self.original, 'status', '--porcelain'), b'')
        self.assertEqual((self.checkout / 'keep').read_text(), 'UNRELATED\n')
        self.assertEqual(report['stage'], 'patched')
        self.assertEqual(report['required_localversion'], '-iphone6s-dart-serdev1')
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse(report['kernel_image_linked'])
        self.assertEqual(BUNDLE.apply(self.checkout), report)
        self.assertEqual(BUNDLE.inspect(self.checkout)[1], report)

    def test_scope_base_patch_and_full_blob_refusals(self):
        # Kills baseline patching, base/patch integrity and alias guard removal.
        with self.assertRaises((ValueError, OSError)):
            BUNDLE.apply(self.original)
        with self.assertRaises(ValueError):
            BUNDLE.inspect(self.checkout)
        base = BUNDLE.BASE
        BUNDLE.BASE = '0' * 40
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        BUNDLE.BASE = base
        name = next(iter(BUNDLE.PATCHES))
        patch = self.root / 'phone/kernel/patches' / name
        raw = patch.read_bytes()
        patch.write_bytes(raw.replace(b'_new', b'_bad'))
        with self.assertRaises(ValueError):
            BUNDLE.patch_bytes()
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        patch.write_bytes(raw)
        alias = self.root / 'alias'
        alias.symlink_to(self.checkout, target_is_directory=True)
        with self.assertRaises(ValueError):
            BUNDLE.apply(alias)
        BUNDLE.apply(self.checkout)
        name = next(iter(BUNDLE.FILES))
        before, after = BUNDLE.FILES[name]
        BUNDLE.FILES[name] = ('0' * 64, after)
        with self.assertRaises(ValueError):
            BUNDLE.inspect(self.checkout)
        BUNDLE.FILES[name] = (before, after)
        for path, raw in self.before.items():
            (self.checkout / path).write_bytes(raw)
        target = self.checkout / name
        target.write_bytes(self.before[name] + b'OTHER_WORK\n')
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        self.assertTrue(target.read_bytes().endswith(b'OTHER_WORK\n'))

    def test_partial_external_staged_hidden_and_symlink_preservation(self):
        # Kills partial bundles, external status and hidden-index acceptance.
        name = next(iter(BUNDLE.FILES))
        target = self.checkout / name
        target.write_bytes(self.after[name])
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        target.write_bytes(self.before[name])
        keep = self.checkout / 'keep'
        keep.write_text('EXTERNAL\n')
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        self.assertEqual(keep.read_text(), 'EXTERNAL\n')
        keep.write_text('UNRELATED\n')
        extra = self.checkout / 'extra'
        extra.write_text('NEW_EXTERNAL\n')
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        self.assertEqual(extra.read_text(), 'NEW_EXTERNAL\n')
        extra.unlink()
        self.git(self.checkout, 'update-index', '--assume-unchanged', 'keep')
        keep.write_text('HIDDEN\n')
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout)
        self.assertEqual(keep.read_text(), 'HIDDEN\n')
        self.git(self.checkout, 'update-index', '--no-assume-unchanged', 'keep')
        keep.write_text('UNRELATED\n')
        external = self.root / 'external'
        external.write_bytes(self.before[name])
        target.unlink()
        target.symlink_to(external)
        with self.assertRaises((ValueError, OSError)):
            BUNDLE.apply(self.checkout)
        self.assertEqual(external.read_bytes(), self.before[name])
        target.unlink()
        target.write_bytes(self.before[name])
        BUNDLE.apply(self.checkout)
        self.git(self.checkout, 'add', name)
        with self.assertRaises(ValueError):
            BUNDLE.inspect(self.checkout)


if __name__ == '__main__':
    unittest.main()
