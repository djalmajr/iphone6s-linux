"""PMD selection through the real CLI with nonbootable filesystem fixtures."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import test_kernel_binding_integration as binding
import test_kernel_integration as legacy

PROFILE = 'n71-dart-serdev-pmd-v1'
VERSION = '-iphone6s-dart-serdev-pmd1'


class PmdIntegration(unittest.TestCase):
    setUp = legacy.KernelIntegrationTests.setUp
    tearDown = legacy.KernelIntegrationTests.tearDown
    save = legacy.KernelIntegrationTests.save
    save_source = legacy.KernelIntegrationTests.save_source
    save_kernel_record = legacy.KernelIntegrationTests.save_kernel_record
    run_cli = legacy.KernelIntegrationTests.run_cli
    save_bundle_record = legacy.KernelIntegrationTests.save_bundle_record
    update_bundle_record = legacy.KernelIntegrationTests.update_bundle_record
    binding_record = binding.BindingIntegrationTests.binding_record

    def pmd_record(self):
        self.binding_record()
        self.bundle_record_name = 'kernel-n71-pmd-build.json'
        source = self.bundle_record['source']
        source.update(bundle=PROFILE, required_localversion=VERSION)
        source['patches']['0009-s5l8960x-dart-pmd.patch'] = (
            'cddfa9cfb894b80236eee0df0a1c199fc2c14b0ebb5570e3a3d502ddc5666e3f')
        source['files'].update({
            'drivers/iommu/apple-dart.c': [
                'f19d3c2a7ada7451956f2a87fea09c174584bfd68ba7a1f6e8793db653047f85',
                '8581e8cc3b19817a5d29db6255c6162de4068f2cfea2c4404c06dfe894282e9b'],
            'drivers/iommu/io-pgtable-dart.c': [
                'ba8b9e53edb1bbf3ebd2e1881c10a40d3b93284e9f074231f07e0443874be493',
                '9afb247569da7bd025a098e77af49af771545d3d90e52b42f11c0c980fdc1038'],
            'include/linux/io-pgtable.h': [
                '360318641218b27728313dfa1beadf5e9ce8671f6e3223104113e16db6aef0ec',
                'c9dfc3d06047e92782ceb35e28792a5346b7272dc0bfdd02eef754b3831b576c'],
        })
        self.bundle_record['build']['kernel_release'] = '7.2.0' + VERSION
        config = (self.kernel / 'config').read_bytes().replace(
            b'-iphone6s-dart-serdev-power2', VERSION.encode())
        for name in ('config', 'config-embedded'):
            self.save(self.kernel / name, config)
        self.update_bundle_record()

    def assert_refused(self):
        result = self.run_cli(PROFILE)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('KERNEL_INTEGRATION_VERIFIED', result.stdout)
        self.assertFalse(self.output.exists())

    def test_explicit_selection_preserves_identities_and_prior_records(self):
        self.pmd_record()
        self.assertEqual(len(self.bundle_record['source']['patches']), 8)
        self.assertEqual(len(self.bundle_record['source']['files']), 8)
        records = [self.root / 'docs/evidence' / name for name in (
            'kernel-source-build.json', 'kernel-n71-bundle-build.json',
            'kernel-n71-power-bundle-build.json', 'kernel-n71-binding-build.json')]
        for record in records:
            record.write_bytes(b'PRIOR_RECORD_PRESERVED')
        before = {path: path.read_bytes() for path in self.source.iterdir()}
        implicit = self.run_cli()
        self.assertEqual(implicit.returncode, 1, implicit.stderr)
        self.assertFalse(self.output.exists())
        result = self.run_cli(PROFILE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((self.output / 'provenance.json').read_text())
        self.assertEqual(report['kernel_patchset'], PROFILE)
        self.assertEqual(report['kernel_release'], '7.2.0' + VERSION)
        self.assertTrue(report['identities_preserved'])
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse(report['default_payload_changed'])
        self.assertIn((self.kernel / 'Image.gz').read_bytes(), (self.output / 'payload.bin').read_bytes())
        for record in records:
            self.assertEqual(record.read_bytes(), b'PRIOR_RECORD_PRESERVED')
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)
        for target, original in (('client_ed25519', 'client'), ('known_hosts', 'known_hosts')):
            self.assertEqual((self.output / target).read_bytes(), (self.source / original).read_bytes())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in self.output.iterdir()))

    def test_missing_and_crossed_power2_record_refused_without_output(self):
        self.pmd_record()
        path = self.root / 'docs/evidence' / self.bundle_record_name
        path.unlink()
        self.assert_refused()
        crossed = self.bundle_record['source']
        crossed.update(bundle='n71-dart-serdev-power-v2',
                       required_localversion='-iphone6s-dart-serdev-power2')
        self.bundle_record['build']['kernel_release'] = '7.2.0-iphone6s-dart-serdev-power2'
        self.update_bundle_record()
        self.assert_refused()

    def test_full_link_export_release_and_all_source_pins_required(self):
        self.pmd_record()
        original = json.loads(json.dumps(self.bundle_record))
        changes = [('source', key, 'changed') for key in ('commit', 'bundle', 'required_localversion')]
        changes += [('build', key, False) for key in (
            'full_image_linked', 'vmlinux_modpost_verified', 'serdev_stop_bits_export_verified')]
        changes += [('build', 'kernel_release', '7.2.0-iphone6s-dart-serdev-power2')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                self.bundle_record = json.loads(json.dumps(original))
                self.bundle_record[section][key] = value
                self.update_bundle_record()
                self.assert_refused()
        for section in ('patches', 'files'):
            for name in original['source'][section]:
                with self.subTest(section=section, name=name):
                    self.bundle_record = json.loads(json.dumps(original))
                    del self.bundle_record['source'][section][name]
                    self.update_bundle_record()
                    self.assert_refused()

    def test_builtin_providers_and_distinct_embedded_configuration_required(self):
        self.pmd_record()
        original = (self.kernel / 'config').read_bytes()
        for before, after in (
                (b'CONFIG_PINCTRL_APPLE_GPIO=y', b'CONFIG_PINCTRL_APPLE_GPIO=m'),
                (b'CONFIG_APPLE_PMGR_PWRSTATE=y', b'CONFIG_APPLE_PMGR_PWRSTATE=m'),
                (VERSION.encode(), b'-iphone6s-dart-serdev-power2'),
                (b'# CONFIG_LOCALVERSION_AUTO is not set', b'CONFIG_LOCALVERSION_AUTO=y')):
            with self.subTest(before=before):
                for name in ('config', 'config-embedded'):
                    self.save(self.kernel / name, original.replace(before, after))
                self.update_bundle_record()
                self.assert_refused()

    def test_old_module_paths_refused_before_creating_candidate(self):
        self.pmd_record()
        original = list(self.members)
        for name in ('lib/modules/stale.ko', 'run/stale.ko.gz',
                     'lib/modules/modules.dep', 'lib/modules/nested/old.ko.zst'):
            with self.subTest(name=name):
                self.members = original + [{'name': name, 'mode': stat.S_IFREG | 0o600,
                                            'body': b'OLD_ABI_SENTINEL'}]
                self.save_source()
                self.assert_refused()


@unittest.skipIf(os.environ.get('KERNEL_INTEGRATION_SCRIPT'), 'Mutation child selects subject')
class PmdIntegrationMutations(unittest.TestCase):
    def test_new_selection_guards_fail_by_assertion(self):
        source = legacy.SCRIPT.read_text()
        bundle = '(kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE)'
        choices = '(kernel_patchset.PATCHSET, kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE)'
        changes = (
            ('record', "'kernel-n71-pmd-build.json' if patchset == kernel_bundle.PMD_BUNDLE",
             "'kernel-n71-binding-build.json' if patchset == kernel_bundle.PMD_BUNDLE", 'explicit'),
            ('bundle', 'bundle = patchset in ' + bundle + ' + PMD_BUNDLES',
             'bundle = patchset in ' + bundle, 'explicit'),
            ('providers', 'if patchset in (kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE) + PMD_BUNDLES and any(',
             'if patchset in (kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE) and any(', 'builtin'),
            ('old-module', 'forbid_extra_modules=options.kernel_patchset in ' + bundle + ' + PMD_BUNDLES',
             'forbid_extra_modules=options.kernel_patchset in ' + bundle, 'old_module'),
            ('cli', 'choices=' + choices + ' + PMD_BUNDLES', 'choices=' + choices, 'explicit'),
        )
        methods = {'explicit': 'test_explicit_selection_preserves_identities_and_prior_records',
                   'builtin': 'test_builtin_providers_and_distinct_embedded_configuration_required',
                   'old_module': 'test_old_module_paths_refused_before_creating_candidate'}
        with tempfile.TemporaryDirectory(prefix='n71-pmd-integration-mutations-') as directory:
            for name, before, after, method in changes:
                self.assertEqual(source.count(before), 1, name)
                changed = source.replace(before, after, 1)
                compile(changed, name, 'exec')
                path = Path(directory) / (name + '.py')
                path.write_text(changed)
                environment = dict(os.environ, KERNEL_INTEGRATION_SCRIPT=str(path),
                                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(legacy.ROOT / 'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                                         'test_kernel_pmd_integration.PmdIntegration.' + methods[method]],
                                        capture_output=True, text=True, env=environment, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('PMD_INTEGRATION_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
