"""Real Git proves seven-patch selection, immutable earlier profiles and atomic preflight."""
import difflib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_kernel_power_bundle as power

BUNDLE = power.BUNDLE
ROOT, SCRIPT = power.ROOT, power.SCRIPT


class BindingBundle(power.PowerBundle):
    def setUp(self):
        super().setUp()
        self.saved_binding = BUNDLE.BINDING_FILES, BUNDLE.BINDING_PATCHES
        name = list(self.saved[4])[-1]
        before = self.after[name]
        after = before.replace(b'_new\n', b'_bound\n')
        raw = ''.join(difflib.unified_diff(before.decode().splitlines(True),
                      after.decode().splitlines(True), 'a/' + name, 'b/' + name)).encode()
        (self.root / 'phone/kernel/patches/0007.patch').write_bytes(raw)
        BUNDLE.BINDING_FILES = {name: (power.digest(self.before[name]), power.digest(after))}
        BUNDLE.BINDING_PATCHES = {'0007.patch': power.digest(raw)}
        self.binding_after = {**self.after, name: after}

    def tearDown(self):
        BUNDLE.BINDING_FILES, BUNDLE.BINDING_PATCHES = self.saved_binding
        super().tearDown()

    def apply_binding(self):
        try:
            return BUNDLE.apply(self.checkout, profile=BUNDLE.BINDING_BUNDLE)
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            self.fail('Valid binding profile refused: ' + str(error))

    def test_binding_exact_apply_report_and_idempotence_preserve_original(self):
        # Kills wrong identity, omitted late patch and reused earlier full-blob hash.
        report = self.apply_binding()
        self.assertEqual(report['bundle'], 'n71-dart-serdev-power-v2')
        self.assertEqual(report['required_localversion'], '-iphone6s-dart-serdev-power2')
        self.assertEqual(list(report['patches']), ['000' + str(i) + '.patch' for i in range(1, 8)])
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse(report['kernel_image_linked'])
        for name in self.before:
            self.assertEqual((self.checkout / name).read_bytes(), self.binding_after[name])
            self.assertEqual((self.original / name).read_bytes(), self.before[name])
        self.assertEqual((self.checkout / 'keep').read_text(), 'UNRELATED\n')
        self.assertEqual(self.git(self.original, 'status', '--porcelain'), b'')
        self.assertEqual(self.apply_binding(), report)
        self.assertEqual(BUNDLE.inspect(self.checkout, profile=BUNDLE.BINDING_BUNDLE)[1], report)
        for profile in (BUNDLE.BUNDLE, BUNDLE.POWER_BUNDLE):
            with self.assertRaises(ValueError):
                BUNDLE.inspect(self.checkout, profile=profile)

    def test_power1_source_cannot_be_completed_in_place(self):
        # Kills treating the protected power1 worktree as a partially applied new profile.
        report = self.apply_power()
        before = {name: (self.checkout / name).read_bytes() for name in self.before}
        with self.assertRaises(ValueError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.BINDING_BUNDLE)
        self.assertEqual({name: (self.checkout / name).read_bytes() for name in self.before}, before)
        self.assertEqual(BUNDLE.inspect(self.checkout, profile=BUNDLE.POWER_BUNDLE)[1], report)

    def test_binding_late_patch_integrity_and_preflight_preserve_candidate(self):
        # Kills missing hash verification and writes before the last patch preflight succeeds.
        patch = self.root / 'phone/kernel/patches/0007.patch'
        raw = patch.read_bytes()
        patch.write_bytes(raw + b'CHANGED\n')
        with self.assertRaises(ValueError):
            BUNDLE.patch_bytes(profile=BUNDLE.BINDING_BUNDLE)
        patch.write_bytes(raw.replace(b'_new\n', b'_wrong\n'))
        BUNDLE.BINDING_PATCHES['0007.patch'] = power.digest(patch.read_bytes())
        with self.assertRaises(subprocess.CalledProcessError):
            BUNDLE.apply(self.checkout, profile=BUNDLE.BINDING_BUNDLE)
        self.assertEqual({name: (self.checkout / name).read_bytes() for name in self.before}, self.before)
        self.assertEqual(self.git(self.checkout, 'status', '--porcelain'), b'')

    def test_cli_offers_explicit_binding_profile(self):
        # Kills a backend profile unavailable through the public CLI.
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('n71-dart-serdev-power-v2', result.stdout)


@unittest.skipIf(os.environ.get('KERNEL_BUNDLE_SCRIPT'), 'Mutation child already selects subject')
class BindingMutations(unittest.TestCase):
    def test_compiled_selection_mutations_are_assertion_killed(self):
        # Kills wrong ABI selection, missing last patch/blob, integrity and duplicate writes.
        source = SCRIPT.read_text()
        changes = (
            ('binding-identity', "BINDING_LOCALVERSION = '-iphone6s-dart-serdev-power2'",
             "BINDING_LOCALVERSION = '-iphone6s-dart-serdev-power1'"),
            ('binding-files', '{**FILES, **POWER_FILES, **BINDING_FILES}', '{**FILES, **POWER_FILES}'),
            ('binding-patches', '{**PATCHES, **POWER_PATCHES, **BINDING_PATCHES}', '{**PATCHES, **POWER_PATCHES}'),
            ('binding-cli', '(BUNDLE, POWER_BUNDLE, BINDING_BUNDLE)', '(BUNDLE, POWER_BUNDLE)'),
            ('binding-patch-integrity', 'kernel_patchset.digest(raw) != expected', 'False'),
            ('duplicate-apply', "subprocess.run(command + ['--check', '-'], input=raw, check=True,",
             "subprocess.run(command + ['-'], input=raw, check=True,"),
        )
        with tempfile.TemporaryDirectory(prefix='n71-binding-mutations-') as directory:
            for name, before, after in changes:
                self.assertEqual(source.count(before), 1, name)
                body = source.replace(before, after, 1)
                compile(body, name, 'exec')
                path = Path(directory) / (name + '.py')
                path.write_text(body)
                methods = {
                    'binding-cli': 'test_cli_offers_explicit_binding_profile',
                    'binding-patch-integrity': 'test_binding_late_patch_integrity_and_preflight_preserve_candidate',
                }
                method = methods.get(name, 'test_binding_exact_apply_report_and_idempotence_preserve_original')
                env = dict(os.environ, KERNEL_BUNDLE_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE='1',
                           PYTHONPATH=os.pathsep.join([str(ROOT / 'tests'), str(ROOT / 'scripts/build')]))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                                         'test_kernel_binding_bundle.BindingBundle.' + method],
                                        capture_output=True, text=True, timeout=60, env=env)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('FAIL:', result.stderr, name + result.stderr)
                self.assertIn('AssertionError', result.stderr, name)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('KERNEL_BINDING_ASSERTION_KILL ' + name, flush=True)
        print('KERNEL_BINDING_MUTATION_GATE_OK count=6', flush=True)


if __name__ == '__main__':
    unittest.main()
