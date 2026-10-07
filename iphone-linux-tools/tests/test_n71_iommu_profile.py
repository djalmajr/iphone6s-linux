"""Exercise IOMMU selection, composer, CLI and real same-boot coordinator."""
import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_n71_diagnostic_pref64_profile as pref
import test_n71_iommu_result as association

held = pref.held
ROOT, RELEASE = held.ROOT, held.RELEASE
SPEC = importlib.util.spec_from_file_location('iommu_profile_resource_build',
    os.environ.get('N71_RESOURCE_BUILD_SCRIPT', ROOT / 'scripts/host/n71_resource_build.py'))
BUILD = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BUILD)
SPEC = importlib.util.spec_from_file_location('iommu_profile_resource_result',
    os.environ.get('N71_IOMMU_PROFILE_RESOURCE_SCRIPT', ROOT / 'scripts/host/n71_resource_result.py'))
RESOURCE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(RESOURCE)
RESOURCE.n71_resource_build = BUILD
held.MODULE.n71_resource_result = held.LINK.n71_resource_result = RESOURCE


class IommuProfileTests(unittest.TestCase):
    write = held.HeldProfileTests.write
    save_build = held.HeldProfileTests.save_build
    resource_build = held.HeldProfileTests.resource_build
    invoke = held.HeldProfileTests.invoke
    compose_ok = held.HeldProfileTests.compose_ok

    def setUp(self):
        held.HeldProfileTests.setUp(self)
        self.test_pref64_composition_and_collector_require_all_four_reports = lambda: pref.Pref64ProfileTests.test_pref64_composition_and_collector_require_all_four_reports(self)
        self.image = bytes(range(256)) * 4
        self.kernel['Image.gz'] = gzip.compress(self.image, mtime=0)
        baseline, _ = held.inputs()
        self.source['payload'].write_bytes(self.loader + held.MODULE.KERNEL.BOOTARGS + baseline
                                           + self.kernel['Image.gz'] + self.source['initramfs'].read_bytes())
        pref.Pref64ProfileTests.test_unsized_composition_preserves_payload_and_requires_four_reports(self)
        self.prior = self.runtime / 'pref64-unsized-resource'
        proof = json.loads((ROOT / 'docs/evidence/n71-dma-topology-qualification.json').read_text())
        self.driver = held.elf('IOMMU_PCIE'); self.args[-1] = hashlib.sha256(self.driver).hexdigest()
        proof['kernel_build'].update(module_bytes=len(self.driver), module_sha256=self.args[-1])
        proof['kernel_build']['baseline_sha256']['arch/arm64/boot/Image'] = hashlib.sha256(self.image).hexdigest()
        self.write(self.runtime / 'modules/n71-pcie-diagnostic.ko', self.driver)
        self.write(self.root / 'docs/evidence/n71-dma-topology-qualification.json', json.dumps(proof).encode())
        kernel = json.loads((ROOT / 'docs/evidence/kernel-n71-binding-build.json').read_text())
        kernel['build']['outputs']['Image'] = {'bytes': len(self.image), 'sha256': hashlib.sha256(self.image).hexdigest()}
        kernel['build']['outputs']['Image.gz'] = {'bytes': len(self.kernel['Image.gz']), 'sha256': hashlib.sha256(self.kernel['Image.gz']).hexdigest()}
        self.write(self.root / 'docs/evidence/kernel-n71-binding-build.json', json.dumps(kernel).encode())
        self.record['source']['commit'] = kernel['source']['commit']
        path = self.root / 'docs/evidence/n71-pci-pref64-unsized-build.json'
        base = json.loads(path.read_text()); base['real_module_build']['protected_outputs'] = proof['kernel_build']['baseline_sha256']
        self.write(path, json.dumps(base).encode())
        for name in BUILD.IOMMU_POLICIES:
            self.write(self.root / 'phone/kernel' / name, (ROOT / 'phone/kernel' / name).read_bytes())
        self.iommu_flags = self.held + ['--pcie-resource-capable', '--pcie-iommu-parent']
        self.phone = association.IommuPhone()

    def select(self, **changes):
        options = dict(release=RELEASE, pcie_sha256=self.args[-1], iommu_parent=True); options.update(changes)
        return RESOURCE.selected_records(self.root, **options)

    def accepted(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, KeyError, OSError) as error:
            self.fail('Valid IOMMU profile refused: ' + str(error))

    def cli(self, profile, *, check=True, source=None, name='session', remove=()):
        data = dict(self.source, payload=profile / 'payload.bin', initramfs=profile / 'initramfs.gz',
                    client_key=profile / 'client_ed25519', known_hosts=profile / 'known_hosts',
                    sha256=hashlib.sha256((profile / 'payload.bin').read_bytes()).hexdigest(),
                    initramfs_sha256=hashlib.sha256((profile / 'initramfs.gz').read_bytes()).hexdigest())
        flags = ['--host-scan', '--scan-link-target', '--scan-pme-disable', '--scan-hold', '--resource-capable', '--iommu-parent']
        argv = ['n71-link-session.py', '--profile', str(profile / 'deployment.json')] + [x for x in flags if x not in remove]
        if check: argv += ['--check']
        else: argv += ['--output-dir', str(self.runtime / name)]
        if source: argv += ['--release-held', str(source)]
        constructor = held.LINK.Session
        def session(*args, **kwargs):
            real = constructor(*args, **kwargs)
            real.capture = lambda *values, **options: self.phone.capture(real, *values, **options)
            return real
        with patch.object(held.LINK, 'ROOT', self.root), patch.object(held.LINK.device_profile, 'verify', return_value=data), \
                patch.object(held.LINK.device_profile, 'ssh_options', return_value=[]), \
                patch.object(held.LINK, 'Session', session), patch.object(sys, 'argv', argv), \
                patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()):
            return held.LINK.main()

    def test_new_profile_preserves_payload_reg_on_and_required_reports(self):
        # Mutations killed: lose new module/flags, alter REG_ON or skip composer kernel qualification.
        records = self.accepted(self.select)
        self.assertEqual(records[0]['bytes'], len(self.driver)); self.assertEqual(records[0]['sha256'], self.args[-1])
        for flag in ('assignment_readback', 'assignment_optional_windows', 'assignment_io16_upper', 'assignment_pref64_disable', 'iommu_parent'):
            self.assertIs(records[0].get(flag), True)
        self.assertEqual(records[1]['sha256'], hashlib.sha256(self.reg).hexdigest())
        output = self.compose_ok('iommu-profile', self.iommu_flags)
        self.assertEqual({p.name for p in output.iterdir()}, held.PROFILE_FILES)
        for name in ('payload.bin', 'deployment.json', 'initramfs.gz', 'client_ed25519', 'known_hosts', 'n71-wlan-power-diagnostic.ko'):
            self.assertEqual((output / name).read_bytes(), (self.prior / name).read_bytes(), name)
        self.assertEqual((output / 'n71-pcie-diagnostic.ko').read_bytes(), self.driver)
        metadata = json.loads((output / 'provenance.json').read_text())
        self.assertIs(metadata['pcie_iommu_parent'], True); self.assertIs(metadata['module_automatic_load'], False)
        self.assertEqual(self.accepted(self.cli, output), 0)
        self.assertFalse(self.phone.calls)

    def test_explicit_mode_hash_and_unchanged_assignment_policy_are_required(self):
        # Mutations killed: bypass exact bool/hash, baseline linkage or current/qualified policy hashes.
        for value in (1, None):
            with self.assertRaises(ValueError): self.select(iommu_parent=value)
            with self.assertRaises(ValueError):
                BUILD.select(self.root, self.select(), release=RELEASE, pcie_sha256=self.args[-1], iommu_parent=value)
        for digest in (None, 'f' * 64):
            with self.assertRaises(ValueError): self.select(pcie_sha256=digest)
        proof = self.root / 'docs/evidence/n71-dma-topology-qualification.json'
        original = proof.read_bytes(); value = json.loads(original)
        key = 'phone/kernel/' + BUILD.IOMMU_POLICIES[0]; value['inputs_sha256'][key] = 'f' * 64
        self.write(proof, json.dumps(value).encode())
        with self.assertRaises(ValueError): self.select()
        self.write(proof, original)
        path = self.root / key; original_policy = path.read_bytes(); self.write(path, b'foreign policy')
        with self.assertRaises(ValueError): self.select()
        self.write(path, original_policy)
        path = self.root / 'docs/evidence/n71-pci-pref64-unsized-build.json'; value = json.loads(path.read_text())
        value['real_module_build']['protected_outputs'] = {}
        self.write(path, json.dumps(value).encode())
        with self.assertRaises(ValueError): self.select()

    def test_composer_refuses_missing_scope_and_foreign_image_before_output(self):
        # Mutations killed: omit explicit resource scope or accept same-ABI foreign kernel bytes.
        with self.assertRaises(ValueError): self.invoke('no-scope', ['--pcie-iommu-parent'])
        self.assertFalse((self.runtime / 'no-scope').exists())
        baseline, _ = held.inputs(); self.kernel['Image.gz'] = gzip.compress(bytes(reversed(self.image)), mtime=0)
        self.source['payload'].write_bytes(self.loader + held.MODULE.KERNEL.BOOTARGS + baseline
                                           + self.kernel['Image.gz'] + self.source['initramfs'].read_bytes())
        with self.assertRaises(ValueError): self.invoke('foreign-image', self.iommu_flags)
        self.assertFalse((self.runtime / 'foreign-image').exists())

    def test_cli_refuses_mode_drift_and_a_changed_kernel_inside_payload(self):
        # Mutations killed: omit metadata/CLI match or bypass payload Image qualification.
        output = self.compose_ok('checked', self.iommu_flags)
        with self.assertRaises(ValueError): self.cli(output, remove=('--iommu-parent',))
        metadata = json.loads((output / 'provenance.json').read_text())
        for value in (False, 1):
            changed = dict(metadata, pcie_iommu_parent=value)
            self.write(output / 'provenance.json', json.dumps(changed).encode())
            with self.assertRaises(ValueError): self.cli(output)
        self.write(output / 'provenance.json', json.dumps(metadata).encode())
        raw = (output / 'payload.bin').read_bytes(); self.assertEqual(raw.count(self.kernel['Image.gz']), 1)
        altered = gzip.compress(bytes(reversed(self.image)), mtime=0)
        self.write(output / 'payload.bin', raw.replace(self.kernel['Image.gz'], altered))
        metadata['payload_sha256'] = hashlib.sha256((output / 'payload.bin').read_bytes()).hexdigest()
        self.write(output / 'provenance.json', json.dumps(metadata).encode())
        with self.assertRaises(ValueError): self.cli(output)

    def test_cli_mode_scope_precedes_identity_access(self):
        # Mutation killed: move invalid mode refusal after identity verification effects.
        marker = self.root / 'identity-accessed'
        output = self.compose_ok('scope-profile', self.iommu_flags)
        def access():
            marker.write_text('synthetic identity accessed')
            return dict(self.source, payload=output / 'payload.bin',
                        sha256=hashlib.sha256((output / 'payload.bin').read_bytes()).hexdigest())
        argv = ['n71-link-session.py', '--profile', str(self.source['payload'].parent / 'deployment.json'), '--iommu-parent', '--check']
        with patch.object(held.LINK, 'ROOT', self.root), patch.object(held.LINK.device_profile, 'verify', access), \
                patch.object(sys, 'argv', argv), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError): held.LINK.main()
        self.assertFalse(marker.exists())
        with patch.object(held.LINK, 'ROOT', self.root):
            with self.assertRaises(ValueError):
                held.LINK.selected_records(True, True, release=RELEASE, scan_link_target=True,
                    scan_pme_disable=True, scan_hold=True, resource_capable=True,
                    resource_module_sha256=self.args[-1], iommu_parent=1)

    def test_cli_acquires_checks_and_releases_actual_journal_without_second_scan(self):
        # Mutations killed: lose IOMMU Session selection in run/check/release or unload before proof.
        output = self.compose_ok('live-model', self.iommu_flags)
        self.assertEqual(self.accepted(self.cli, output, check=False, name='acquire'), 0)
        source = self.runtime / 'acquire'
        data = json.loads((source / 'held-state-private.json').read_text())
        self.assertIs(data['iommu_parent'], True)
        self.assertTrue(data['result'].get('iommu_association', {}).get('software_association_observed'))
        self.assertEqual(self.accepted(self.cli, output, source=source), 0)
        self.assertEqual(self.accepted(self.cli, output, check=False, source=source, name='release'), 0)
        final = json.loads((self.runtime / 'release/held-state-private.json').read_text())
        self.assertTrue(final['result'].get('iommu_cleanup', {}).get('software_ownership_released'))
        self.assertEqual(sum(stage == 'pcie' for stage, _ in self.phone.calls), 1)
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)


class IommuProfileMutations(unittest.TestCase):
    @unittest.skipIf(os.environ.get('N71_IOMMU_PROFILE_MUTATION_CHILD'), 'Parent mutation gate only')
    def test_compiled_variants_fail_by_assertion(self):
        variants = {
            'builder-mode-type': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                                  'type(iommu_parent) is bool', 'True'),
            'builder-requested-sha': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                                      "pcie_sha256 == build['module_sha256']", 'True'),
            'builder-base': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                             "base['protected_outputs'] == build['baseline_sha256']", 'True'),
            'qualified-policy': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                                  "proof['inputs_sha256'].get(path) == digest", 'True'),
            'current-policy': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                                "hashlib.sha256((root / path).read_bytes()).hexdigest() == digest", 'True'),
            'new-module-size': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                                 "bytes=build['module_bytes']", "bytes=previous[0]['bytes']"),
            'new-module-marker': ('scripts/host/n71_resource_build.py', 'N71_RESOURCE_BUILD_SCRIPT',
                                   "vermagic=build['vermagic'], iommu_parent=True",
                                   "vermagic=build['vermagic'], iommu_parent=False"),
            'resource-mode-type': ('scripts/host/n71_resource_result.py', 'N71_IOMMU_PROFILE_RESOURCE_SCRIPT',
                                    'type(iommu_parent) is bool', 'True'),
            'link-mode-type': ('scripts/host/n71-link-session.py', 'N71_HELD_READBACK_SESSION_SCRIPT',
                                'type(iommu_parent) is bool', 'True'),
            'composer-scope': ('scripts/build/compose-n71-diagnostic.py', 'N71_DIAGNOSTIC_COMPOSER_SCRIPT',
                                'if options.pcie_iommu_parent and not options.pcie_resource_capable:', 'if False:'),
            'composer-image': ('scripts/build/compose-n71-diagnostic.py', 'N71_DIAGNOSTIC_COMPOSER_SCRIPT',
                                "n71_iommu_build.kernel_image(ROOT, kernel['Image.gz'], release=record['build']['kernel_release'])", 'None'),
            'composer-mode': ('scripts/build/compose-n71-diagnostic.py', 'N71_DIAGNOSTIC_COMPOSER_SCRIPT',
                               "'pcie_iommu_parent': options.pcie_iommu_parent", "'pcie_iommu_parent': False"),
            'link-scope-before-identities': ('scripts/host/n71-link-session.py', 'N71_HELD_READBACK_SESSION_SCRIPT',
                                             'require(not options.iommu_parent or options.resource_capable,', 'require(True,'),
            'link-profile-mode': ('scripts/host/n71-link-session.py', 'N71_HELD_READBACK_SESSION_SCRIPT',
                                   "metadata.get('pcie_iommu_parent', False) is options.iommu_parent", 'True'),
            'link-payload-image': ('scripts/host/n71-link-session.py', 'N71_HELD_READBACK_SESSION_SCRIPT',
                                    'n71_iommu_build.payload_image(ROOT, profile, metadata, prefix_bytes=prefix_bytes, release=release)', 'None'),
            'session-run-mode': ('scripts/host/n71-link-session.py', 'N71_HELD_READBACK_SESSION_SCRIPT',
                                  'history=history,\n                          resource_capable=options.resource_capable, iommu_parent=options.iommu_parent)',
                                  'history=history,\n                          resource_capable=options.resource_capable, iommu_parent=False)'),
            'session-check-mode': ('scripts/host/n71-link-session.py', 'N71_HELD_READBACK_SESSION_SCRIPT',
                                    'scan_pme_disable=True, scan_hold=True, release=release,\n                              resource_capable=options.resource_capable, iommu_parent=options.iommu_parent)',
                                    'scan_pme_disable=True, scan_hold=True, release=release,\n                              resource_capable=options.resource_capable, iommu_parent=False)'),
        }
        import tempfile
        with tempfile.TemporaryDirectory(prefix='n71-iommu-profile-mutations-') as directory:
            for name, (filename, variable, before, after) in variants.items():
                source = (ROOT / filename).read_text(); self.assertEqual(source.count(before), 1, name)
                # A temporary copy must retain the production package root for imports.
                root_line = 'ROOT = Path(__file__).resolve().parents[2]'
                if root_line in source:
                    source = source.replace(root_line, 'ROOT = Path(' + repr(str(ROOT)) + ')', 1)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, N71_IOMMU_PROFILE_MUTATION_CHILD='1', PYTHONDONTWRITEBYTECODE='1')
                env[variable] = str(path)
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                         '-p', 'test_n71_iommu_profile.py', '-k', 'IommuProfileTests'],
                                        env=env, capture_output=True, text=True, timeout=40)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_IOMMU_PROFILE_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
