"""Power2 integration contracts using synthetic nonbootable private inputs."""
import json
import stat
import unittest
import test_kernel_integration as legacy

PROFILE = 'n71-dart-serdev-power-v2'
VERSION = '-iphone6s-dart-serdev-power2'


class BindingIntegrationTests(unittest.TestCase):
    setUp = legacy.KernelIntegrationTests.setUp
    tearDown = legacy.KernelIntegrationTests.tearDown
    save = legacy.KernelIntegrationTests.save
    save_source = legacy.KernelIntegrationTests.save_source
    save_kernel_record = legacy.KernelIntegrationTests.save_kernel_record
    run_cli = legacy.KernelIntegrationTests.run_cli
    save_bundle_record = legacy.KernelIntegrationTests.save_bundle_record
    update_bundle_record = legacy.KernelIntegrationTests.update_bundle_record

    def binding_record(self):
        self.save_bundle_record(power=True)
        self.bundle_record_name = 'kernel-n71-binding-build.json'
        source = self.bundle_record['source']
        source.update(bundle=PROFILE, required_localversion=VERSION)
        source['patches']['0007-apple-pmgr-no-manual-bind.patch'] = (
            '3f5a3e4c97a6cf898eaf90d53fcdc45a9796707c4123a14b1d0e043b58934aaa')
        source['files']['drivers/pmdomain/apple/pmgr-pwrstate.c'][1] = (
            '0d84693ae4f5a24df9f8c9499ecd0f8f6725566223428dfe7af686cf7a21f5b2')
        self.bundle_record['build']['kernel_release'] = '7.2.0' + VERSION
        config = (self.kernel / 'config').read_bytes().replace(
            b'-iphone6s-dart-serdev-power1', VERSION.encode())
        for name in ('config', 'config-embedded'):
            self.save(self.kernel / name, config)
        self.update_bundle_record()

    def assert_refused(self):
        result = self.run_cli(PROFILE)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('KERNEL_INTEGRATION_VERIFIED', result.stdout)
        self.assertFalse(self.output.exists())

    def test_explicit_record_selection_preserves_legacy_identity_and_inputs(self):
        self.binding_record()
        records = [self.root / 'docs/evidence' / name for name in (
            'kernel-source-build.json', 'kernel-n71-bundle-build.json',
            'kernel-n71-power-bundle-build.json')]
        for record in records:
            record.write_bytes(b'LEGACY_MANIFEST_UNTOUCHED')
        before = {path: path.read_bytes() for path in self.source.iterdir()}
        implicit = self.run_cli()
        self.assertEqual(implicit.returncode, 1, implicit.stderr)
        self.assertFalse(self.output.exists())
        result = self.run_cli(PROFILE)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.output / 'provenance.json').read_text())
        self.assertEqual(report['kernel_patchset'], PROFILE)
        self.assertEqual(report['kernel_release'], '7.2.0' + VERSION)
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse(report['default_payload_changed'])
        self.assertTrue(report['identities_preserved'])
        self.assertIn((self.kernel / 'Image.gz').read_bytes(), (self.output / 'payload.bin').read_bytes())
        for record in records:
            self.assertEqual(record.read_bytes(), b'LEGACY_MANIFEST_UNTOUCHED')
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)
        for target, original in (('client_ed25519', 'client'), ('known_hosts', 'known_hosts')):
            self.assertEqual((self.output / target).read_bytes(), (self.source / original).read_bytes())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in self.output.iterdir()))

    def test_rejects_changed_identity_sources_and_link_metadata(self):
        self.binding_record()
        original = json.loads(json.dumps(self.bundle_record))
        changes = [('source', key, 'changed') for key in ('commit', 'bundle', 'required_localversion')]
        changes += [('source', 'patches', {}), ('source', 'files', {})]
        changes += [('build', key, False) for key in (
            'full_image_linked', 'vmlinux_modpost_verified', 'serdev_stop_bits_export_verified')]
        changes += [('build', 'kernel_release', '7.2.0-iphone6s-dart-serdev-power1')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                self.bundle_record = json.loads(json.dumps(original))
                self.bundle_record[section][key] = value
                self.update_bundle_record()
                self.assert_refused()
        self.bundle_record = json.loads(json.dumps(original))
        del self.bundle_record['source']['patches']['0007-apple-pmgr-no-manual-bind.patch']
        self.update_bundle_record()
        self.assert_refused()
        self.bundle_record = json.loads(json.dumps(original))
        self.bundle_record['source']['files']['drivers/pmdomain/apple/pmgr-pwrstate.c'][1] = (
            'ec4841316d8c3a8dad7ac44d93edac0209c581b4e4c0d2fb9dcfb89853754414')
        self.update_bundle_record()
        self.assert_refused()

    def test_requires_builtin_providers_even_with_consistent_artifact_hashes(self):
        self.binding_record()
        original = (self.kernel / 'config').read_bytes()
        for key in ('PINCTRL_APPLE_GPIO', 'APPLE_PMGR_PWRSTATE'):
            with self.subTest(key=key):
                changed = original.replace(('CONFIG_' + key + '=y').encode(),
                                           ('CONFIG_' + key + '=m').encode())
                for name in ('config', 'config-embedded'):
                    self.save(self.kernel / name, changed)
                self.update_bundle_record()
                self.assert_refused()

    def test_refuses_all_old_module_paths_before_creating_candidate(self):
        self.binding_record()
        original = list(self.members)
        for name in ('lib/modules/old.ko', 'run/stale.ko.gz', 'lib/modules/modules.dep',
                     'lib/modules/nested/old.ko.zst'):
            with self.subTest(name=name):
                self.members = original + [{'name': name, 'mode': stat.S_IFREG | 0o600,
                                             'body': b'OLD_ABI_SENTINEL'}]
                self.save_source()
                self.assert_refused()

    def test_artifact_digest_mismatch_refused_before_output(self):
        self.binding_record()
        raw = (self.kernel / 'Image.gz').read_bytes()
        self.save(self.kernel / 'Image.gz', raw + b'ALTERED')
        self.assert_refused()


if __name__ == '__main__':
    unittest.main()
