"""Real Git checks the additive PMD bundle without changing earlier profiles."""
import difflib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_kernel_binding_bundle as binding

BUNDLE = binding.BUNDLE
ROOT, SCRIPT = binding.ROOT, binding.SCRIPT
digest = binding.power.digest


class PMDBundle(unittest.TestCase):
    def setUp(self):
        self.fixture = binding.BindingBundle('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.saved = BUNDLE.PMD_FILES, BUNDLE.PMD_PATCHES
        self.addCleanup(self.restore)
        self.folder = self.fixture.root
        self.original, self.checkout = self.fixture.original, self.fixture.checkout
        self.git = self.fixture.git
        self.before = dict(self.fixture.before)
        self.expected = dict(self.fixture.binding_after)
        names = ('drivers/iommu/apple-dart.c', 'drivers/iommu/io-pgtable-dart.c',
                 'include/linux/io-pgtable.h')
        raw = b'Subject: synthetic PMD fixture\n\n'
        BUNDLE.PMD_FILES = {}
        for name in names:
            if name not in self.before:
                before = ('/* GPL-2.0 fixture */\n' + name + '_old\n').encode()
                path = self.original / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(before)
                self.before[name] = before
                self.expected[name] = before
            start = self.expected[name]
            after = start.replace(b'_new\n', b'_pmd\n').replace(b'_old\n', b'_pmd\n')
            self.expected[name] = after
            BUNDLE.PMD_FILES[name] = (digest(self.before[name]), digest(after))
            raw += ''.join(difflib.unified_diff(start.decode().splitlines(True),
                           after.decode().splitlines(True), 'a/' + name, 'b/' + name)).encode()
        self.patch = self.folder / 'phone/kernel/patches/0009.patch'
        self.patch.write_bytes(raw)
        BUNDLE.PMD_PATCHES = {'0009.patch': digest(raw)}
        self.git(self.original, 'add', '.')
        self.git(self.original, '-c', 'user.name=PMD Test', '-c',
                 'user.email=pmd@example.invalid', 'commit', '-qm', 'Extend independent fixture')
        BUNDLE.BASE = self.git(self.original, 'rev-parse', 'HEAD').decode().strip()
        self.git(self.checkout, 'checkout', '--detach', '-q', BUNDLE.BASE)

    def restore(self):
        BUNDLE.PMD_FILES, BUNDLE.PMD_PATCHES = self.saved

    def apply_pmd(self):
        try:
            return BUNDLE.apply(self.checkout, profile=BUNDLE.PMD_BUNDLE)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            self.fail('Valid PMD bundle refused: ' + str(error))

    def test_exact_additive_bundle_and_idempotence(self):
        # Kills dropped PMD/base patches, wrong blob selection and an old kernel identity.
        report = self.apply_pmd()
        self.assertEqual(report['bundle'], 'n71-dart-serdev-pmd-v1')
        self.assertEqual(report['required_localversion'], '-iphone6s-dart-serdev-pmd1')
        self.assertEqual(set(report['files']), set(self.before))
        self.assertEqual(list(report['patches']),
                         ['000' + str(i) + '.patch' for i in range(1, 8)] + ['0009.patch'])
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse(report['kernel_image_linked'])
        for name, expected in self.expected.items():
            self.assertEqual((self.checkout / name).read_bytes(), expected)
            self.assertEqual((self.original / name).read_bytes(), self.before[name])
        self.assertEqual((self.checkout / 'keep').read_text(), 'UNRELATED\n')
        self.assertEqual(self.git(self.original, 'status', '--porcelain'), b'')
        self.assertEqual(self.apply_pmd(), report)
        self.assertEqual(BUNDLE.inspect(self.checkout, profile=BUNDLE.PMD_BUNDLE)[1], report)

    def test_old_profiles_are_preserved_and_cannot_be_upgraded_in_place(self):
        # Kills changing power2's patch selection or accepting a partial upgrade.
        version, files, patches = BUNDLE.bundle_spec(BUNDLE.BINDING_BUNDLE)
        self.assertEqual(version, '-iphone6s-dart-serdev-power2')
        self.assertEqual(len(files), 6)
        self.assertEqual(len(patches), 7)
        self.assertNotIn('0009.patch', patches)
        report = BUNDLE.apply(self.checkout, profile=BUNDLE.BINDING_BUNDLE)
        before = {name: (self.checkout / name).read_bytes() for name in self.before}
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.PMD_BUNDLE)
        self.assertEqual({name: (self.checkout / name).read_bytes() for name in self.before}, before)
        self.assertEqual(BUNDLE.inspect(self.checkout, profile=BUNDLE.BINDING_BUNDLE)[1], report)
        with self.assertRaises(ValueError):
            BUNDLE.bundle_spec('unknown-pmd-profile')

    def test_late_patch_integrity_and_atomic_preflight(self):
        # Kills ignored PMD patch hashes and writes before all patches validate.
        raw = self.patch.read_bytes()
        self.patch.write_bytes(raw + b'CHANGED\n')
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.PMD_BUNDLE)
        self.patch.write_bytes(raw.replace(b'_new\n', b'_wrong\n'))
        BUNDLE.PMD_PATCHES['0009.patch'] = digest(self.patch.read_bytes())
        with self.assertRaises(subprocess.CalledProcessError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.PMD_BUNDLE)
        self.assertEqual(self.git(self.checkout, 'status', '--porcelain'), b'')
        for name, before in self.before.items():
            self.assertEqual((self.checkout / name).read_bytes(), before)

    def test_cli_exposes_explicit_new_bundle(self):
        # Kills a profile implemented in Python but inaccessible through the CLI.
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('n71-dart-serdev-pmd-v1', result.stdout)


@unittest.skipIf(os.environ.get('KERNEL_BUNDLE_SCRIPT'), 'Mutation child selects subject')
class PMDMutations(unittest.TestCase):
    def test_selection_mutations_fail_by_assertion(self):
        # Kills invalid selection, scope, integrity, atomicity and identity changes.
        source = SCRIPT.read_text()
        mutations = (
            ('identity', "PMD_LOCALVERSION = '-iphone6s-dart-serdev-pmd1'",
             "PMD_LOCALVERSION = '-iphone6s-dart-serdev-power2'", 'exact'),
            ('files', '{**files, **PMD_FILES}', 'files', 'exact'),
            ('patches', '{**patches, **PMD_PATCHES}', 'patches', 'exact'),
            ('base', '_, files, patches = bundle_spec(BINDING_BUNDLE)',
             '_, files, patches = bundle_spec(POWER_BUNDLE)', 'exact'),
            ('cli', ' + (PMD_BUNDLE,)', '', 'cli'),
            ('hash', 'kernel_patchset.digest(raw) != expected', 'False', 'integrity'),
            ('duplicate-apply', "subprocess.run(command + ['--check', '-'], input=raw, check=True,",
             "subprocess.run(command + ['-'], input=raw, check=True,", 'exact'),
        )
        methods = {'exact': 'test_exact_additive_bundle_and_idempotence',
                   'cli': 'test_cli_exposes_explicit_new_bundle',
                   'integrity': 'test_late_patch_integrity_and_atomic_preflight'}
        with tempfile.TemporaryDirectory(prefix='n71-pmd-bundle-mutations-') as directory:
            for name, before, after, method in mutations:
                self.assertEqual(source.count(before), 1, name)
                body = source.replace(before, after, 1)
                compile(body, name, 'exec')
                path = Path(directory) / (name + '.py')
                path.write_text(body)
                env = dict(os.environ, KERNEL_BUNDLE_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE='1',
                           PYTHONPATH=os.pathsep.join([str(ROOT / 'tests'), str(ROOT / 'scripts/build')]))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                                         'test_kernel_pmd_bundle.PMDBundle.' + methods[method]],
                                        capture_output=True, text=True, timeout=60, env=env)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('FAIL:', result.stderr, name + result.stderr)
                self.assertIn('AssertionError', result.stderr, name)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('KERNEL_PMD_ASSERTION_KILL ' + name, flush=True)
        print('KERNEL_PMD_MUTATION_GATE_OK count=7', flush=True)


if __name__ == '__main__':
    unittest.main()
