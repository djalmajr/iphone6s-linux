"""Real Git proves the selected six-patch bundle and preserved legacy profile."""
import difflib
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_kernel_bundle import BUNDLE, ROOT, SCRIPT


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class PowerBundle(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='n71-power-git-')
        self.root = Path(self.temporary.name).resolve()
        self.original, self.checkout = self.root / 'original', self.root / 'candidate'
        self.original.mkdir()
        self.saved = tuple(getattr(BUNDLE, key) for key in
                           ('BASE', 'ROOT', 'FILES', 'PATCHES', 'POWER_FILES', 'POWER_PATCHES'))
        BUNDLE.ROOT = self.root
        BUNDLE.FILES, BUNDLE.PATCHES, BUNDLE.POWER_FILES, BUNDLE.POWER_PATCHES = {}, {}, {}, {}
        paths = list(self.saved[2]) + list(self.saved[4])
        self.before = {name: ('/* header */\n' + name + '_old\n/* footer */\n').encode()
                       for name in paths}
        self.after = {name: raw.replace(b'_old\n', b'_new\n') for name, raw in self.before.items()}
        patches = self.root / 'phone/kernel/patches'
        patches.mkdir(parents=True)
        groups = (('0001.patch', [paths[0]], b'_old\n', b'_new\n'),
                  ('0002.patch', paths[1:4], b'_old\n', b'_new\n'),
                  ('0003.patch', [paths[4]], b'_old\n', b'_new\n'),
                  ('0004.patch', [paths[5]], b'_old\n', b'_step4\n'),
                  ('0005.patch', [paths[5]], b'_step4\n', b'_step5\n'),
                  ('0006.patch', [paths[5]], b'_step5\n', b'_new\n'))
        for number, (patch_name, names, before, after) in enumerate(groups):
            raw = b'Subject: independent synthetic bundle\n\n'
            for name in names:
                start = self.before[name].replace(b'_old\n', before)
                end = start.replace(before, after)
                raw += ''.join(difflib.unified_diff(start.decode().splitlines(True),
                               end.decode().splitlines(True), 'a/' + name, 'b/' + name)).encode()
            (patches / patch_name).write_bytes(raw)
            selected = BUNDLE.PATCHES if number < 2 else BUNDLE.POWER_PATCHES
            selected[patch_name] = digest(raw)
        for number, (name, raw) in enumerate(self.before.items()):
            path = self.original / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            selected = BUNDLE.FILES if number < 4 else BUNDLE.POWER_FILES
            selected[name] = (digest(raw), digest(self.after[name]))
        (self.original / 'keep').write_text('UNRELATED\n')
        self.git(self.original, 'init', '-q')
        self.git(self.original, 'add', '.')
        self.git(self.original, '-c', 'user.name=Bundle Test', '-c',
                 'user.email=bundle@example.invalid', 'commit', '-qm', 'Independent fixture')
        BUNDLE.BASE = self.git(self.original, 'rev-parse', 'HEAD').decode().strip()
        self.git(self.original, 'worktree', 'add', '--detach', str(self.checkout), BUNDLE.BASE)

    def tearDown(self):
        for key, value in zip(('BASE', 'ROOT', 'FILES', 'PATCHES', 'POWER_FILES', 'POWER_PATCHES'),
                              self.saved):
            setattr(BUNDLE, key, value)
        self.temporary.cleanup()

    def git(self, folder, *args):
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null',
                                       '-c', 'core.fsmonitor=false', '-C', str(folder), *args],
                                       stderr=subprocess.PIPE, timeout=20)

    def apply_power(self):
        try:
            return BUNDLE.apply(self.checkout, profile=BUNDLE.POWER_BUNDLE)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            self.fail('Valid selected bundle refused: ' + str(error))

    def test_exact_layered_apply_identity_and_idempotence(self):
        # Kills omitted GPIO/PMGR patches, missing full blobs and a reused ABI identity.
        report = self.apply_power()
        self.assertEqual(report['bundle'], 'n71-dart-serdev-power-v1')
        self.assertEqual(report['required_localversion'], '-iphone6s-dart-serdev-power1')
        self.assertEqual(set(report['files']), set(self.before))
        self.assertEqual(list(report['patches']), ['000' + str(i) + '.patch' for i in range(1, 7)])
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse(report['kernel_image_linked'])
        for name in self.before:
            self.assertEqual((self.checkout / name).read_bytes(), self.after[name])
            self.assertEqual((self.original / name).read_bytes(), self.before[name])
        self.assertEqual(self.git(self.original, 'status', '--porcelain'), b'')
        self.assertEqual((self.checkout / 'keep').read_text(), 'UNRELATED\n')
        self.assertEqual(self.apply_power(), report)
        self.assertEqual(BUNDLE.inspect(self.checkout, profile=BUNDLE.POWER_BUNDLE)[1], report)
        with self.assertRaises(ValueError):
            BUNDLE.inspect(self.checkout)

    def test_legacy_default_and_unknown_or_mixed_profile_preserve_files(self):
        # Kills silent fallback for unknown profiles and accepting a partial power bundle.
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout, profile='unknown')
        self.assertEqual({n: (self.checkout / n).read_bytes() for n in self.before}, self.before)
        legacy = BUNDLE.apply(self.checkout)
        self.assertEqual(legacy['required_localversion'], '-iphone6s-dart-serdev1')
        self.assertEqual(legacy['bundle'], 'n71-dart-serdev-v1')
        selected = {n: (self.checkout / n).read_bytes() for n in self.before}
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.POWER_BUNDLE)
        self.assertEqual({n: (self.checkout / n).read_bytes() for n in self.before}, selected)
        for name in BUNDLE.POWER_FILES:
            self.assertEqual((self.checkout / name).read_bytes(), self.before[name])

    def test_late_patch_integrity_and_preflight_leave_candidate_intact(self):
        # Kills integrity checks limited to legacy patches; proves late failure has no writes.
        name = list(BUNDLE.POWER_PATCHES)[-1]
        patch = self.root / 'phone/kernel/patches' / name
        original = patch.read_bytes()
        patch.write_bytes(original + b'CHANGED\n')
        with self.assertRaises(ValueError):
            BUNDLE.patch_bytes(profile=BUNDLE.POWER_BUNDLE)
        patch.write_bytes(original.replace(b'_step5', b'_wrong'))
        BUNDLE.POWER_PATCHES[name] = digest(patch.read_bytes())
        with self.assertRaises(subprocess.CalledProcessError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.POWER_BUNDLE)
        self.assertEqual({n: (self.checkout / n).read_bytes() for n in self.before}, self.before)
        self.assertEqual(self.git(self.checkout, 'status', '--porcelain'), b'')
        self.assertEqual(self.git(self.original, 'status', '--porcelain'), b'')


@unittest.skipIf(os.environ.get('KERNEL_BUNDLE_SCRIPT'), 'Mutation child already selects subject')
class PowerBundleMutations(unittest.TestCase):
    def test_compiled_source_mutations_fail_by_assertion(self):
        # Kills wrong selection, missing source/patch provenance and unpinned late inputs.
        source = SCRIPT.read_text()
        changes = (
            ('power-identity', "POWER_LOCALVERSION = '-iphone6s-dart-serdev-power1'",
             "POWER_LOCALVERSION = '-iphone6s-dart-serdev1'"),
            ('power-files', '{**FILES, **POWER_FILES}', 'FILES'),
            ('power-patches', '{**PATCHES, **POWER_PATCHES}', 'PATCHES'),
            ('reported-profile', "'bundle': profile", "'bundle': BUNDLE"),
            ('reported-files', "'files': files", "'files': FILES"),
            ('reported-patches', "'patches': patches", "'patches': PATCHES"),
            ('unknown-profile', "raise ValueError('Unknown bundle profile.')",
             'return LOCALVERSION, FILES, PATCHES'),
            ('late-patch-hash', 'kernel_patchset.digest(raw) != expected', 'False'),
        )
        with tempfile.TemporaryDirectory(prefix='n71-power-mutations-') as directory:
            for name, before, after in changes:
                self.assertEqual(source.count(before), 1, name)
                body = source.replace(before, after, 1)
                compile(body, name, 'exec')
                path = Path(directory) / (name + '.py')
                path.write_text(body)
                environment = dict(os.environ, KERNEL_BUNDLE_SCRIPT=str(path),
                                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'scripts/build'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                                         '-s', str(ROOT / 'tests'), '-p', 'test_kernel_power_bundle.py'],
                                        capture_output=True, text=True, timeout=40, env=environment)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('FAIL:', result.stderr, name + result.stderr)
                self.assertIn('AssertionError', result.stderr, name)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('KERNEL_POWER_BUNDLE_ASSERTION_KILL ' + name, flush=True)
        print('KERNEL_POWER_BUNDLE_MUTATION_GATE_OK count=8', flush=True)


if __name__ == '__main__':
    unittest.main()
