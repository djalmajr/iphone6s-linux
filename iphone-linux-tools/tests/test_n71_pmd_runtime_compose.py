"""Real PMD compositor with synthetic kernel/identity I/O; no boot or network."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_pmd_runtime_profile as runtime_fixture
import test_n71_diagnostic_held_profile as held_fixture

ROOT = runtime_fixture.ROOT
SOURCE = ROOT / 'scripts/build/compose-n71-diagnostic.py'
COMPOSER = ModuleType('pmd_compositor'); COMPOSER.__file__ = str(SOURCE)
exec(compile(Path(os.environ.get('N71_PMD_COMPOSER_SCRIPT', SOURCE)).read_text(), str(SOURCE), 'exec'), COMPOSER.__dict__)
RELEASE = runtime_fixture.RELEASE
BUNDLE = 'n71-dart-serdev-pmd-v1'


class PmdRuntimeCompose(unittest.TestCase):
    def setUp(self):
        data = runtime_fixture.PmdRuntimeProfile('test_real_compiled_selection_binds_caller_reg_on_wcc_and_kernel')
        data.setUp(); self.addCleanup(data.doCleanups); self.data = data; self.root = data.root
        held = held_fixture.HeldProfileTests('test_complete_pair_provenance_payload_and_private_modes')
        held.setUp(); self.addCleanup(held.doCleanups); self.held = held
        for name in ('runtime/source', 'runtime/diagnostic', 'runtime/kernel', 'artifacts'):
            shutil.copytree(held.root / name, self.root / name, dirs_exist_ok=True)
        shutil.copyfile(held.root / 'docs/evidence/m1n1-rebuild.json', self.root / 'docs/evidence/m1n1-rebuild.json')
        self.source = {key: self.root / value.relative_to(held.root) if isinstance(value, Path) else value
                       for key, value in held.source.items()}
        self.modules = self.root / 'runtime/modules'; self.modules.mkdir(mode=0o700)
        for record, raw in data.modules + data.drivers:
            path = self.modules / record['module']; path.write_bytes(raw); path.chmod(0o600)
        self.record = {'source': {'commit': '958481f87fee0949ff6a9a4af77f7eb6dac8a149'}, 'build': {'kernel_release': RELEASE}}
        self.args = [str(SOURCE), '--source-profile', str(self.root / 'runtime/source/deployment.json'),
            '--kernel-dir', str(self.root / 'runtime/kernel'), '--kernel-patchset', BUNDLE,
            '--diagnostic-dir', str(self.root / 'runtime/diagnostic'), '--module', str(self.modules / 'n71-pcie-diagnostic.ko'),
            '--module-sha256', data.selected['diagnostics'][0]['sha256']]
        self.flags = ['--pcie-aspm-off', '--pcie-scan-hold', '--pcie-resource-capable', '--pcie-iommu-parent',
            '--pcie-driver-runtime', '--wcc-dir', str(self.modules), '--reg-on-module', str(self.modules / 'n71-wlan-power-diagnostic.ko')]
        for hook in (patch.object(COMPOSER, 'ROOT', self.root),
                     patch.object(COMPOSER.DIAGNOSTIC.TUNABLES, 'ROOT', self.root)):
            hook.start(); self.addCleanup(hook.stop)

    def invoke(self, name, flags=None, identity=None):
        output = self.root / 'runtime' / name
        argv = self.args + (self.flags if flags is None else flags) + ['--output-dir', str(output)]
        with (patch.object(COMPOSER.device_profile, 'verify', identity or (lambda: self.source)),
              patch.object(COMPOSER.KERNEL, 'kernel_inputs', return_value=(self.held.kernel, self.record)),
              patch.object(COMPOSER.n71_iommu_build, 'kernel_image', return_value=None),
              patch.object(sys, 'argv', argv), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO())):
            COMPOSER.main()
        return output

    def accepted(self, function, *args, **kwargs):
        try: return function(*args, **kwargs)
        except (ValueError, KeyError, OSError, SystemExit) as error: self.fail('Qualified PMD composition refused: ' + str(error))

    def test_complete_pmd_profile_preserves_inputs_keys_and_seven_selected_modules(self):
        # Mutations killed: remove PMD parser/held support while retaining legacy choices.
        before = {key: value.read_bytes() for key, value in self.source.items() if isinstance(value, Path)}
        environment = dict(os.environ)
        output = self.accepted(self.invoke, 'complete')
        expected = held_fixture.PROFILE_FILES | {record['module'] for record, _ in self.data.drivers}
        self.assertEqual({p.name for p in output.iterdir()}, expected)
        for record, raw in self.data.modules + self.data.drivers:
            self.assertEqual((output / record['module']).read_bytes(), raw)
        metadata = json.loads((output / 'provenance.json').read_text())
        self.assertEqual(metadata['kernel_release'], RELEASE); self.assertEqual(metadata['kernel_patchset'], BUNDLE)
        self.assertIs(metadata['pcie_driver_runtime'], True); self.assertEqual(metadata['driver_modules'], self.data.selected['drivers'])
        self.assertIs(metadata['module_automatic_load'], False); self.assertIs(metadata['default_profile_changed'], False)
        self.assertIs(metadata['physical_boot_tested'], False); self.assertIs(metadata['wifi_verified'], False)
        for target, source in [('initramfs.gz', 'initramfs'), ('client_ed25519', 'client_key'), ('known_hosts', 'known_hosts')]:
            self.assertEqual((output / target).read_bytes(), before[source])
        self.assertEqual({key: value.read_bytes() for key, value in self.source.items() if isinstance(value, Path)}, before)
        self.assertEqual(dict(os.environ), environment)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir()))

    def test_pmd_requires_complete_runtime_scope_before_identity_or_output(self):
        # Mutation killed: allow a PMD held profile without explicit runtime/WCC selection.
        def identity(): self.fail('Identity accessed before PMD scope validation')
        no_runtime = [flag for flag in self.flags if flag not in ('--pcie-driver-runtime', '--wcc-dir', str(self.modules))]
        cases = [no_runtime]
        for flag in ('--pcie-aspm-off', '--pcie-resource-capable', '--pcie-iommu-parent'):
            flags = list(self.flags); flags.remove(flag); cases.append(flags)
        for flags in cases:
            with self.subTest(flags=flags), self.assertRaises(ValueError): self.invoke('refused', flags, identity)
        self.assertFalse((self.root / 'runtime/refused').exists())

    def test_recorded_pmd_elf_is_accepted_and_crossed_or_unknown_abi_is_refused(self):
        # Mutation killed: omit PMD from the supported exact module ABI list.
        raw = self.data.modules[0][1]
        self.accepted(COMPOSER.validate_module, raw, kernel_release=RELEASE)
        for version in ('unrecorded', '7.2.0-iphone6s-dart-serdev-power2'):
            with self.subTest(version=version), self.assertRaises(ValueError): COMPOSER.validate_module(raw, kernel_release=version)
        with self.assertRaises(ValueError): COMPOSER.validate_module(b'broken' + raw[6:], kernel_release=RELEASE)


@unittest.skipIf(os.environ.get('N71_PMD_COMPOSER_SCRIPT'), 'Mutation child selects subject')
class PmdComposerMutations(unittest.TestCase):
    def test_removed_pmd_abi_parser_or_scope_fail_by_assertion(self):
        variants = [
            ('abi', "'7.2.0' + KERNEL.kernel_bundle.PMD_LOCALVERSION", "'7.2.0' + KERNEL.kernel_bundle.BINDING_LOCALVERSION", 'recorded_pmd_elf_is_accepted_and_crossed_or_unknown_abi_is_refused'),
            ('parser', '                                                     KERNEL.kernel_bundle.PMD_BUNDLE))', '                                                     KERNEL.kernel_bundle.BINDING_BUNDLE))', 'complete_pmd_profile_preserves_inputs_keys_and_seven_selected_modules'),
            ('held', '(KERNEL.kernel_bundle.BINDING_BUNDLE, KERNEL.kernel_bundle.PMD_BUNDLE)', '(KERNEL.kernel_bundle.BINDING_BUNDLE,)', 'complete_pmd_profile_preserves_inputs_keys_and_seven_selected_modules'),
            ('scope', 'options.kernel_patchset == KERNEL.kernel_bundle.PMD_BUNDLE and not options.pcie_driver_runtime', 'False', 'pmd_requires_complete_runtime_scope_before_identity_or_output'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-compose-mutations-') as directory:
            for name, before, after, method in variants:
                text = SOURCE.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, N71_PMD_COMPOSER_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_n71_pmd_runtime_compose.PmdRuntimeCompose.test_'+method],
                                        env=environment, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_COMPOSE_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
