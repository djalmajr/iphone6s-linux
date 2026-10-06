"""Compose the typed PREF build through the CLI and preserve the prior payload."""
import contextlib
import hashlib
import io
import json
import os
import sys
import unittest
from unittest.mock import patch
import test_n71_diagnostic_io16_profile as io16

held = io16.held
ROOT, RELEASE = held.ROOT, held.RELEASE


class Pref64ProfileTests(unittest.TestCase):
    setUp = held.HeldProfileTests.setUp
    write = held.HeldProfileTests.write
    save_build = held.HeldProfileTests.save_build
    resource_build = held.HeldProfileTests.resource_build
    invoke = held.HeldProfileTests.invoke
    compose_ok = held.HeldProfileTests.compose_ok

    def test_pref64_composition_and_collector_require_all_four_reports(self):
        io16.IO16ProfileTests.test_io16_composition_and_collector_require_all_three_reports(self)
        old = self.runtime / 'io16-resource'
        evidence = json.loads((ROOT / 'docs/evidence/n71-pci-pref64-build.json').read_text())
        self.write(self.root / 'docs/evidence/n71-pci-pref64-policy.json',
                   (ROOT / 'docs/evidence/n71-pci-pref64-policy.json').read_bytes())
        for key, name in (('base_assignment_evidence_sha256', 'n71-pci-resource-assignment.json'),
                          ('base_readback_evidence_sha256', 'n71-pci-resource-readback.json'),
                          ('base_optional_evidence_sha256', 'n71-pci-optional-build.json'),
                          ('base_io16_evidence_sha256', 'n71-pci-io16-build.json'),
                          ('pref64_policy_evidence_sha256', 'n71-pci-pref64-policy.json')):
            evidence[key] = hashlib.sha256((self.root / 'docs/evidence' / name).read_bytes()).hexdigest()
        self.driver = held.elf('RESOURCE_PREF64_PCIE'); digest = hashlib.sha256(self.driver).hexdigest()
        evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko'] = {
            'bytes': len(self.driver), 'sha256': digest, 'vermagic': RELEASE + ' SMP preempt mod_unload aarch64'}
        evidence['real_module_build']['modules']['n71-wlan-power-diagnostic.ko'] = dict(
            self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'])
        self.write(self.root / 'docs/evidence/n71-pci-pref64-build.json', json.dumps(evidence).encode())
        self.write(self.runtime / 'modules/n71-pcie-diagnostic.ko', self.driver); self.args[-1] = digest
        new = self.compose_ok('pref64-resource', self.held + ['--pcie-resource-capable'])
        self.assertEqual({p.name for p in new.iterdir()}, held.PROFILE_FILES)
        for name in ('payload.bin', 'initramfs.gz', 'client_ed25519', 'known_hosts', 'deployment.json'):
            self.assertEqual((new / name).read_bytes(), (old / name).read_bytes(), name)
        self.assertEqual((new / 'n71-pcie-diagnostic.ko').read_bytes(), self.driver)
        self.assertEqual((new / 'n71-wlan-power-diagnostic.ko').read_bytes(), self.reg)
        metadata = json.loads((new / 'provenance.json').read_text())
        self.assertEqual(metadata['module_sha256'], digest); self.assertIs(metadata['module_automatic_load'], False)
        profile = dict(self.source, payload=new / 'payload.bin', initramfs=new / 'initramfs.gz',
                       client_key=new / 'client_ed25519', known_hosts=new / 'known_hosts',
                       sha256=hashlib.sha256((new / 'payload.bin').read_bytes()).hexdigest(),
                       initramfs_sha256=hashlib.sha256((new / 'initramfs.gz').read_bytes()).hexdigest())
        with patch.object(held.LINK, 'ROOT', self.root), patch.object(held.LINK.device_profile, 'verify', return_value=profile):
            records = held.LINK.selected_records(True, True, release=RELEASE, scan_link_target=True,
                                                scan_pme_disable=True, scan_hold=True, resource_capable=True,
                                                resource_module_sha256=digest)
            for key in ('assignment_readback', 'assignment_optional_windows', 'assignment_io16_upper', 'assignment_pref64_disable'):
                self.assertIs(records[0].get(key), True)
            argv = ['n71-link-session.py', '--profile', str(new / 'deployment.json'), '--host-scan',
                    '--scan-link-target', '--scan-pme-disable', '--scan-hold', '--resource-capable', '--check']
            with patch.object(sys, 'argv', argv), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()):
                try:
                    self.assertEqual(held.LINK.main(), 0)
                except ValueError as error:
                    self.fail('Valid PREF64 collector profile refused: ' + str(error))


if __name__ == '__main__':
    unittest.main()
