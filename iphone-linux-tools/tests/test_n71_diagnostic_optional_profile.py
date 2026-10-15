"""Compose and check the optional-range build without touching phone identities."""
import contextlib
import hashlib
import io
import json
import os
import sys
import unittest
from unittest.mock import patch
import test_n71_diagnostic_held_profile as held

ROOT, RELEASE = held.ROOT, held.RELEASE


class OptionalProfileTests(unittest.TestCase):
    setUp = held.HeldProfileTests.setUp
    write = held.HeldProfileTests.write
    save_build = held.HeldProfileTests.save_build
    resource_build = held.HeldProfileTests.resource_build
    invoke = held.HeldProfileTests.invoke
    compose_ok = held.HeldProfileTests.compose_ok

    def test_optional_build_composes_and_checks_required_reports(self):
        base, _ = self.resource_build()
        old = self.compose_ok('old-resource', self.held + ['--pcie-resource-capable'])
        prior = json.loads((ROOT / 'docs/evidence/n71-pci-resource-readback.json').read_text())
        prior['base_assignment_evidence_sha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
        prior['real_module_build']['modules']['n71-wlan-power-diagnostic.ko'] = dict(
            self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'])
        prior_path = self.root / 'docs/evidence/n71-pci-resource-readback.json'
        self.write(prior_path, json.dumps(prior).encode())
        self.driver = held.elf('RESOURCE_OPTIONAL_PCIE'); digest = hashlib.sha256(self.driver).hexdigest()
        evidence = json.loads((ROOT / 'docs/evidence/n71-pci-optional-build.json').read_text())
        evidence['base_assignment_evidence_sha256'] = hashlib.sha256(base.read_bytes()).hexdigest()
        evidence['base_readback_evidence_sha256'] = hashlib.sha256(prior_path.read_bytes()).hexdigest()
        evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko'] = {
            'bytes': len(self.driver), 'sha256': digest, 'vermagic': RELEASE + ' SMP preempt mod_unload aarch64'}
        evidence['real_module_build']['modules']['n71-wlan-power-diagnostic.ko'] = dict(
            self.build['kernel_build']['modules']['n71-wlan-power-diagnostic.ko'])
        self.write(self.root / 'docs/evidence/n71-pci-optional-build.json', json.dumps(evidence).encode())
        self.write(self.runtime / 'modules/n71-pcie-diagnostic.ko', self.driver); self.args[-1] = digest
        new = self.compose_ok('optional-resource', self.held + ['--pcie-resource-capable'])
        self.assertEqual({p.name for p in new.iterdir()}, held.PROFILE_FILES)
        for name in ('payload.bin', 'initramfs.gz', 'client_ed25519', 'known_hosts', 'deployment.json'):
            self.assertEqual((new / name).read_bytes(), (old / name).read_bytes(), name)
        self.assertEqual((new / 'n71-pcie-diagnostic.ko').read_bytes(), self.driver)
        self.assertEqual((new / 'n71-wlan-power-diagnostic.ko').read_bytes(), self.reg)
        metadata = json.loads((new / 'provenance.json').read_text())
        self.assertEqual(metadata['module_sha256'], digest)
        self.assertIs(metadata['module_automatic_load'], False)
        profile = dict(self.source, payload=new / 'payload.bin', initramfs=new / 'initramfs.gz',
                       client_key=new / 'client_ed25519', known_hosts=new / 'known_hosts',
                       sha256=hashlib.sha256((new / 'payload.bin').read_bytes()).hexdigest(),
                       initramfs_sha256=hashlib.sha256((new / 'initramfs.gz').read_bytes()).hexdigest())
        with patch.object(held.LINK, 'ROOT', self.root), patch.object(held.LINK.device_profile, 'verify', return_value=profile):
            records = held.LINK.selected_records(True, True, release=RELEASE, scan_link_target=True,
                                                scan_pme_disable=True, scan_hold=True, resource_capable=True,
                                                resource_module_sha256=digest)
            self.assertIs(records[0].get('assignment_readback'), True)
            self.assertIs(records[0].get('assignment_optional_windows'), True)
            argv = ['n71-link-session.py', '--profile', str(new / 'deployment.json'), '--host-scan',
                    '--scan-link-target', '--scan-pme-disable', '--scan-hold', '--resource-capable', '--check']
            with patch.object(sys, 'argv', argv), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()):
                try:
                    self.assertEqual(held.LINK.main(), 0)
                except ValueError as error:
                    self.fail('Valid optional collector profile refused: ' + str(error))


if __name__ == '__main__':
    unittest.main()
