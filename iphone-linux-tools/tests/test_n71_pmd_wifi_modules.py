"""PMD build identity bound to compiled evidence and real filesystem probes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_n71_wifi_modules as legacy

MODULE = legacy.MODULE
PROFILE = 'n71-dart-serdev-pmd-v1'


class PmdWifi(unittest.TestCase):
    def test_identity_matches_completed_kernel_record(self):
        record = json.loads((legacy.ROOT / 'docs/evidence/kernel-n71-pmd-build.json').read_text())
        self.assertEqual(record['status'], 'compiled_verified')
        build = record['build']
        expected = {'.config': build['outputs']['config']['sha256'],
                    'arch/arm64/boot/Image': build['outputs']['Image']['sha256'],
                    'vmlinux.symvers': build['vmlinux_symvers_sha256']}
        try:
            identity = MODULE.build_identity(PROFILE)
        except ValueError as error:
            self.fail('Qualified PMD profile refused: ' + str(error))
        self.assertEqual(identity, (build['kernel_release'], expected))
        for previous in ('n71-dart-serdev-v1', 'n71-dart-serdev-power-v2'):
            self.assertNotEqual(identity, MODULE.build_identity(previous))

    def test_pmd_files_require_their_hashes_and_release_without_writing(self):
        with tempfile.TemporaryDirectory(prefix='n71-pmd-wifi-kernel-') as directory:
            output = Path(directory).resolve()
            data = {'.config': legacy.WifiModuleTests.config(self).encode(),
                    'arch/arm64/boot/Image': b'synthetic PMD image; never bootable',
                    'vmlinux.symvers': b'synthetic PMD exports'}
            for name, raw in data.items():
                p = output / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(raw)
            release = output / 'include/config/kernel.release'
            release.parent.mkdir(parents=True)
            release.write_text('7.2.0-iphone6s-dart-serdev-pmd1\n')
            before = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}
            with patch.object(MODULE, 'PMD_KERNEL_FILES', before):
                try:
                    self.assertEqual(MODULE.kernel_state(output, profile=PROFILE), MODULE.REQUIRED)
                except ValueError as error:
                    self.fail('Valid PMD filesystem fixture refused: ' + str(error))
                for previous in ('n71-dart-serdev-v1', 'n71-dart-serdev-power-v2'):
                    with self.assertRaises(ValueError):
                        MODULE.kernel_state(output, profile=previous)
                for name, raw in data.items():
                    (output / name).write_bytes(raw + b'changed')
                    with self.assertRaises(ValueError):
                        MODULE.kernel_state(output, profile=PROFILE)
                    (output / name).write_bytes(raw)
                release.write_text('7.2.0-iphone6s-dart-serdev-power2\n')
                with self.assertRaises(ValueError):
                    MODULE.kernel_state(output, profile=PROFILE)
            self.assertEqual({name: (output / name).read_bytes() for name in data}, data)
            self.assertFalse((output / 'provenance-private.json').exists())

    def test_real_help_contains_explicit_pmd_choice_without_building(self):
        environment = dict(os.environ, PYTHONPATH=str(legacy.ROOT / 'scripts/build'),
                           PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, str(legacy.SPEC.origin), '--help'],
                                capture_output=True, text=True, env=environment, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('n71-dart-serdev-pmd-v1', result.stdout)
        self.assertIn('n71-dart-serdev-power-v2', result.stdout)


    def test_real_git_audit_detects_features_outside_driver_package(self):
        with tempfile.TemporaryDirectory(prefix='n71-pmd-wifi-git-') as directory:
            checkout = Path(directory).resolve()
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            for name in MODULE.MACRO_FILES:
                path = checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('CONFIG_BRCMFMAC_PCIE\n')
            outside = checkout / 'include/outside.h'
            outside.parent.mkdir(parents=True)
            outside.write_text('CONFIG_BRCMFMAC_PROTO_MSGBUF\n')
            subprocess.run(['git', '-C', str(checkout), 'add', '--', '.'], check=True)
            paths = MODULE.feature_paths(checkout)
            self.assertEqual(set(paths), MODULE.MACRO_FILES | {'include/outside.h'})
            with self.assertRaises(ValueError):
                MODULE.macro_scope(paths)
            self.assertEqual(outside.read_text(), 'CONFIG_BRCMFMAC_PROTO_MSGBUF\n')
            subprocess.run(['git', '-C', str(checkout), 'rm', '-f', '-q', '--', 'include/outside.h'], check=True)
            MODULE.macro_scope(MODULE.feature_paths(checkout))


@unittest.skipIf(os.environ.get('N71_WIFI_MODULES_SCRIPT'), 'Mutation child selects subject')
class PmdWifiMutations(unittest.TestCase):
    def test_new_identity_and_cli_mutations_are_assertion_killed(self):
        source = Path(legacy.SPEC.origin).read_text()
        changes = (
            ('branch', 'if profile == kernel_bundle.PMD_BUNDLE:', 'if False:', 'identity'),
            ('release', 'return PMD_RELEASE, PMD_KERNEL_FILES', 'return BINDING_RELEASE, PMD_KERNEL_FILES', 'identity'),
            ('hashes', 'return PMD_RELEASE, PMD_KERNEL_FILES', 'return PMD_RELEASE, BINDING_KERNEL_FILES', 'identity'),
            ('cli', 'choices=(kernel_bundle.BUNDLE, kernel_bundle.BINDING_BUNDLE, kernel_bundle.PMD_BUNDLE)',
             'choices=(kernel_bundle.BUNDLE, kernel_bundle.BINDING_BUNDLE)', 'cli'),
            ('global-grep', "'CONFIG_BRCMFMAC_(PCIE|PROTO_MSGBUF)']",
             "'CONFIG_BRCMFMAC_(PCIE|PROTO_MSGBUF)', '--', BROADCOM]", 'global'),
        )
        methods = {'identity': 'test_identity_matches_completed_kernel_record',
                   'cli': 'test_real_help_contains_explicit_pmd_choice_without_building',
                   'global': 'test_real_git_audit_detects_features_outside_driver_package'}
        with tempfile.TemporaryDirectory(prefix='n71-pmd-wifi-mutations-') as directory:
            for name, before, after, method in changes:
                self.assertEqual(source.count(before), 1, name)
                changed = source.replace(before, after, 1)
                compile(changed, name, 'exec')
                path = Path(directory) / (name + '.py')
                path.write_text(changed)
                environment = dict(os.environ, N71_WIFI_MODULES_SCRIPT=str(path),
                                   PYTHONDONTWRITEBYTECODE='1',
                                   PYTHONPATH=str(legacy.ROOT / 'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                                         'test_n71_pmd_wifi_modules.PmdWifi.' + methods[method]],
                                        capture_output=True, text=True, env=environment, timeout=30)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('PMD_WIFI_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
