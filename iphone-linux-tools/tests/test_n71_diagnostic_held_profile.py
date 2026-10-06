"""The held composer emits a complete private pair only after all local gates."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_n71_diagnostic_payload import inputs

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('n71_held_profile_composer',
                                            os.environ.get('N71_DIAGNOSTIC_COMPOSER_SCRIPT', ROOT / 'scripts/build/compose-n71-diagnostic.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RELEASE = '7.2.0-iphone6s-dart-serdev-power2'
PATCHSET = 'n71-dart-serdev-power-v2'
PROFILE_FILES = {'payload.bin', 'initramfs.gz', 'client_ed25519', 'known_hosts',
                 'n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko', 'deployment.json', 'provenance.json'}


def elf(name):
    raw = bytearray(64)
    raw[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HH', raw, 16, 1, 183)
    return bytes(raw) + ('vermagic=' + RELEASE + ' SMP preempt mod_unload aarch64\0').encode() + name.encode()


class HeldProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir(mode=0o700)
        for name in ('source', 'diagnostic', 'modules', 'kernel'):
            (self.runtime / name).mkdir(mode=0o700)
        baseline, diagnostic = inputs()
        loader = b'FIXTURE_LOADER'.ljust(64, b'_')
        kernel = b'FIXTURE_KERNEL'
        initramfs = b'FIXTURE_USERSPACE_AND_IDENTITIES'
        source = self.runtime / 'source'
        data = {'payload.bin': loader + MODULE.KERNEL.BOOTARGS + baseline + kernel + initramfs,
                'initramfs.gz': initramfs, 'client_ed25519': b'FIXTURE_IDENTITY_NOT_A_REAL_KEY',
                'known_hosts': b'FIXTURE_HOST_NOT_A_REAL_PIN', 'deployment.json': b'{}\n'}
        self.source = {'payload': source / 'payload.bin', 'initramfs': source / 'initramfs.gz',
                       'client_key': source / 'client_ed25519', 'known_hosts': source / 'known_hosts',
                       'host_key_alias': 'fixture.invalid'}
        self.kernel = {'s8000-n71.dtb': baseline, 'Image.gz': kernel}
        self.record = {'source': {'commit': 'a' * 40}, 'build': {'kernel_release': RELEASE}}
        self.driver = elf('PCIE')
        self.reg = elf('REG_ON')
        self.build = copy.deepcopy(json.loads((ROOT / 'docs/evidence/n71-pci-held-caller.json').read_text()))
        for name, raw in (('n71-pcie-diagnostic.ko', self.driver), ('n71-wlan-power-diagnostic.ko', self.reg)):
            self.build['kernel_build']['modules'][name] = {
                'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'vermagic': RELEASE + ' SMP preempt mod_unload aarch64'}
            self.write(self.runtime / 'modules' / name, raw)
        for name, raw in data.items():
            self.write(source / name, raw)
        self.write(self.runtime / 'diagnostic/diagnostic-private.dtb', diagnostic)
        self.write(self.runtime / 'diagnostic/provenance-private.json',
                   json.dumps({'sha256': hashlib.sha256(diagnostic).hexdigest()}).encode())
        self.write(self.root / 'artifacts/m1n1.bin', loader)
        self.write(self.root / 'docs/evidence/m1n1-rebuild.json',
                   json.dumps({'shallow_clone': {'sha256': hashlib.sha256(loader).hexdigest(),
                                               'matches_original': True, 'bytes': len(loader)}}).encode())
        self.build_path = self.root / 'docs/evidence/n71-pci-held-caller.json'
        self.save_build()
        self.args = ['compose-n71-diagnostic.py', '--source-profile', str(source / 'deployment.json'),
                     '--kernel-dir', str(self.runtime / 'kernel'), '--kernel-patchset', PATCHSET,
                     '--diagnostic-dir', str(self.runtime / 'diagnostic'),
                     '--module', str(self.runtime / 'modules/n71-pcie-diagnostic.ko'),
                     '--module-sha256', hashlib.sha256(self.driver).hexdigest()]
        self.held = ['--pcie-aspm-off', '--pcie-scan-hold', '--reg-on-module',
                     str(self.runtime / 'modules/n71-wlan-power-diagnostic.ko')]
        original_umask = os.umask(0o077)
        self.addCleanup(os.umask, original_umask)
        self.diagnostic = diagnostic
        self.loader = loader
        self.resource_build(update_module=False)

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(data)
        path.chmod(0o600)

    def save_build(self):
        self.write(self.build_path, (json.dumps(self.build) + '\n').encode())

    def resource_build(self, *, update_module=True):
        evidence = json.loads((ROOT / 'docs/evidence/n71-pci-resource-assignment.json').read_text())
        driver = elf('RESOURCE_PCIE')
        evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko'] = {
            'bytes': len(driver), 'sha256': hashlib.sha256(driver).hexdigest(),
            'vermagic': RELEASE + ' SMP preempt mod_unload aarch64'}
        evidence['real_module_build']['modules']['n71-wlan-power-diagnostic.ko'] = dict(
            self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'])
        path = self.root / 'docs/evidence/n71-pci-resource-assignment.json'
        self.write(path, json.dumps(evidence).encode())
        if update_module:
            self.driver = driver
            self.write(self.runtime / 'modules/n71-pcie-diagnostic.ko', self.driver)
            self.args[-1] = hashlib.sha256(self.driver).hexdigest()
        return path, evidence

    def invoke(self, name, arguments=None):
        output = self.runtime / name
        argv = self.args + (self.held if arguments is None else arguments) + ['--output-dir', str(output)]
        with patch.object(MODULE, 'ROOT', self.root), patch.dict(os.environ), \
                patch.object(MODULE.DIAGNOSTIC.TUNABLES, 'ROOT', self.root), \
                patch.object(MODULE.device_profile, 'verify', return_value=self.source), \
                patch.object(MODULE.KERNEL, 'kernel_inputs', return_value=(self.kernel, self.record)), \
                patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            try:
                MODULE.main()
            except SystemExit as error:
                self.fail('Supported composer invocation exited: ' + str(error.code))
        return output

    def compose_ok(self, name, arguments=None):
        try:
            return self.invoke(name, arguments)
        except ValueError as error:
            self.fail('Valid profile refused: ' + str(error))

    def test_complete_pair_provenance_payload_and_private_modes(self):
        # Mutations killed: omit REG_ON, change held booleans or select an incomplete/default candidate.
        output = self.compose_ok('held')
        self.assertEqual({path.name for path in output.iterdir()}, PROFILE_FILES)
        self.assertEqual((output / 'n71-pcie-diagnostic.ko').read_bytes(), self.driver)
        self.assertEqual((output / 'n71-wlan-power-diagnostic.ko').read_bytes(), self.reg)
        for name in ('client_ed25519', 'known_hosts', 'initramfs.gz'):
            self.assertEqual((output / name).read_bytes(), (self.runtime / 'source' / name).read_bytes())
        self.assertEqual((output / 'payload.bin').read_bytes(),
                         self.loader + MODULE.bootargs(True) + self.diagnostic + self.kernel['Image.gz']
                         + self.source['initramfs'].read_bytes())
        metadata = json.loads((output / 'provenance.json').read_text())
        expected = {'pcie_scan_link_target': True, 'pcie_scan_pme_noop': False,
                    'pcie_scan_pme_disable': True, 'pcie_scan_hold': True, 'pcie_aspm_off': True,
                    'pcie_resource_capable': False, 'module_automatic_load': False, 'physical_boot_tested': False}
        for key, value in expected.items():
            self.assertIs(metadata[key], value, key)
        self.assertEqual(metadata['reg_on_module_sha256'], hashlib.sha256(self.reg).hexdigest())
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir()))

    def test_default_has_no_hold_reg_on_or_extra_aspm_selection(self):
        # Mutation killed: make hold or REG_ON implicit for legacy diagnostic profiles.
        output = self.compose_ok('default', [])
        self.assertNotIn('n71-wlan-power-diagnostic.ko', {path.name for path in output.iterdir()})
        metadata = json.loads((output / 'provenance.json').read_text())
        self.assertIs(metadata['pcie_scan_hold'], False)
        self.assertIs(metadata['pcie_resource_capable'], False)
        self.assertIs(metadata['pcie_aspm_off'], False)
        self.assertNotIn('reg_on_module_sha256', metadata)
        self.assertEqual((output / 'payload.bin').read_bytes(),
                         self.loader + MODULE.KERNEL.BOOTARGS + self.diagnostic + self.kernel['Image.gz']
                         + self.source['initramfs'].read_bytes())

    def test_hold_requires_explicit_aspm_power2_and_reg_on_before_output(self):
        # Mutations killed: omit any explicit candidate prerequisite.
        cases = (self.held[1:], self.held[:1] + self.held[2:])
        for index, arguments in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.invoke('invalid-' + str(index), arguments)
            self.assertFalse((self.runtime / ('invalid-' + str(index))).exists())
        original = self.args[:]
        for index, selected in enumerate(('n71-dart-serdev-v1', 'n71-dart-serdev-power-v1')):
            self.args[self.args.index(PATCHSET)] = selected
            with self.assertRaises(ValueError):
                self.invoke('wrong-abi-' + str(index))
            self.assertFalse((self.runtime / ('wrong-abi-' + str(index))).exists())
            self.args = original[:]
        output = self.runtime / 'missing-reg'
        argv = [sys.executable, MODULE.__file__, *self.args[1:], *self.held[:-2], '--output-dir', str(output)]
        process = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        self.assertEqual(process.returncode, 1)
        self.assertIn('Held profile requires explicit ASPM off, power2 and REG_ON module', process.stderr)
        self.assertFalse(output.exists())

    def test_pcie_size_and_hash_are_bound_to_the_qualified_pair(self):
        # Mutations killed: trust caller-provided module hash instead of the qualified build.
        row = self.build['kernel_build']['modules']['n71-pcie-diagnostic.ko']
        original = row.copy()
        for index, changed in enumerate((dict(row, bytes=row['bytes'] + 1), dict(row, sha256='0' * 64))):
            self.build['kernel_build']['modules']['n71-pcie-diagnostic.ko'] = changed
            self.save_build()
            with self.assertRaises(ValueError):
                self.invoke('wrong-pcie-' + str(index))
            self.assertFalse((self.runtime / ('wrong-pcie-' + str(index))).exists())
        self.build['kernel_build']['modules']['n71-pcie-diagnostic.ko'] = original

    def test_reg_on_size_hash_architecture_and_links_are_refused_before_output(self):
        # Mutations killed: skip REG_ON size/hash/ELF or accept private links.
        row = self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko']
        for index, changed in enumerate((dict(row, bytes=row['bytes'] + 1), dict(row, sha256='0' * 64))):
            self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'] = changed
            self.save_build()
            with self.assertRaises(ValueError):
                self.invoke('wrong-reg-' + str(index))
            self.assertFalse((self.runtime / ('wrong-reg-' + str(index))).exists())
        altered = self.reg[:18] + struct.pack('<H', 62) + self.reg[20:]
        path = self.runtime / 'modules/n71-wlan-power-diagnostic.ko'
        self.write(path, altered)
        self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'] = dict(row, sha256=hashlib.sha256(altered).hexdigest())
        self.save_build()
        with self.assertRaises(ValueError):
            self.invoke('wrong-reg-machine')
        self.write(path, self.reg)
        self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'] = row
        self.save_build()
        moved = path.with_name('reg-original-private.ko')
        path.rename(moved)
        path.symlink_to(moved)
        with self.assertRaises(ValueError):
            self.invoke('linked-reg')
        self.assertFalse((self.runtime / 'linked-reg').exists())

    def test_unqualified_build_and_output_reuse_cannot_create_a_profile(self):
        # Mutation killed: bypass selected build qualification or replace existing output.
        self.build['kernel_build']['modpost_passed'] = False
        self.save_build()
        with self.assertRaises(ValueError):
            self.invoke('unqualified')
        self.assertFalse((self.runtime / 'unqualified').exists())
        self.build['kernel_build']['modpost_passed'] = True
        self.save_build()
        output = self.compose_ok('once')
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        with self.assertRaises(ValueError):
            self.invoke('once')
        self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)

    def test_resource_selection_preserves_payload_and_identities_with_a_distinct_pair(self):
        # Mutations killed: use the old module, omit the explicit capability or enable automatic loading.
        baseline = self.compose_ok('old-held')
        old_driver = self.driver
        self.resource_build()
        output = self.compose_ok('resource-held', self.held + ['--pcie-resource-capable'])
        self.assertEqual({path.name for path in output.iterdir()}, PROFILE_FILES)
        self.assertNotEqual(self.driver, old_driver)
        self.assertEqual((output / 'n71-pcie-diagnostic.ko').read_bytes(), self.driver)
        self.assertEqual((output / 'n71-wlan-power-diagnostic.ko').read_bytes(), self.reg)
        for name in ('payload.bin', 'initramfs.gz', 'client_ed25519', 'known_hosts', 'deployment.json'):
            self.assertEqual((output / name).read_bytes(), (baseline / name).read_bytes(), name)
        metadata = json.loads((output / 'provenance.json').read_text())
        for name, value in (('pcie_resource_capable', True), ('pcie_scan_hold', True),
                            ('module_automatic_load', False), ('requires_explicit_run', True),
                            ('physical_boot_tested', False), ('wifi_verified', False)):
            self.assertIs(metadata[name], value, name)
        self.assertEqual(metadata['module_sha256'], hashlib.sha256(self.driver).hexdigest())
        self.assertEqual(metadata['reg_on_module_sha256'], hashlib.sha256(self.reg).hexdigest())
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir()))

    def test_resource_candidate_requires_hold_and_refuses_cross_selected_modules(self):
        # Mutations killed: bypass held scope or select the new module for an unflagged profile.
        for index, arguments in enumerate((['--pcie-resource-capable'],
                                            ['--pcie-resource-capable'] + self.held[:1] + self.held[2:])):
            with self.assertRaisesRegex(ValueError, 'Resource-capable profile requires explicit held selection'):
                self.invoke('resource-no-hold-' + str(index), arguments)
            self.assertFalse((self.runtime / ('resource-no-hold-' + str(index))).exists())
        old_driver = self.driver
        self.resource_build()
        with self.assertRaises(ValueError):
            self.invoke('resource-without-flag')
        self.assertFalse((self.runtime / 'resource-without-flag').exists())
        self.write(self.runtime / 'modules/n71-pcie-diagnostic.ko', old_driver)
        self.args[-1] = hashlib.sha256(old_driver).hexdigest()
        with self.assertRaises(ValueError):
            self.invoke('old-with-resource-flag', self.held + ['--pcie-resource-capable'])
        self.assertFalse((self.runtime / 'old-with-resource-flag').exists())

    def test_resource_build_metadata_and_reg_on_pair_must_be_qualified(self):
        # Mutation killed: bypass build qualification when the caller supplies a matching module SHA.
        path, evidence = self.resource_build()
        original = copy.deepcopy(evidence)
        for index, change in enumerate(('modpost', 'pcie-size', 'reg-pair')):
            evidence = copy.deepcopy(original)
            if change == 'modpost':
                evidence['real_module_build']['modpost_passed'] = False
            elif change == 'pcie-size':
                evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['bytes'] += 1
            else:
                evidence['real_module_build']['modules']['n71-wlan-power-diagnostic.ko']['sha256'] = '0' * 64
            self.write(path, json.dumps(evidence).encode())
            with self.assertRaises(ValueError):
                self.invoke('resource-invalid-' + str(index), self.held + ['--pcie-resource-capable'])
            self.assertFalse((self.runtime / ('resource-invalid-' + str(index))).exists())


if __name__ == '__main__':
    unittest.main()
