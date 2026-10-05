"""Preserved-kernel and package boundaries for the module-only build recipe."""
import importlib.util
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/build'))
SPEC = importlib.util.spec_from_file_location('wifi_modules', os.environ.get(
    'N71_WIFI_MODULES_SCRIPT', ROOT / 'scripts/build/build-n71-wifi-modules.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WifiModuleTests(unittest.TestCase):
    def config(self):
        return '\n'.join(name + '=' + value if value != 'n' else '# ' + name + ' is not set'
                         for name, value in MODULE.REQUIRED.items())

    def test_every_core_configuration_dependency_is_required(self):
        text = self.config()
        self.assertEqual(MODULE.configuration(text), MODULE.REQUIRED)
        for name, value in MODULE.REQUIRED.items():
            with self.subTest(name=name):
                before = name + '=' + value if value != 'n' else '# ' + name + ' is not set'
                after = name + '=y' if value == 'n' else '# ' + name + ' is not set'
                with self.assertRaises(ValueError):
                    MODULE.configuration(text.replace(before, after))

    def test_driver_features_cannot_escape_the_audited_package(self):
        MODULE.macro_scope(MODULE.MACRO_FILES)
        for extra in ('include/linux/pci.h', MODULE.BROADCOM + '/brcmfmac-other/bus.h',
                      MODULE.BROADCOM + '/brcmfmac/../include/shared.h'):
            with self.assertRaises(ValueError):
                MODULE.macro_scope(MODULE.MACRO_FILES | {extra})
        for missing in MODULE.MACRO_FILES:
            with self.assertRaises(ValueError):
                MODULE.macro_scope(MODULE.MACRO_FILES - {missing})

    def test_external_commands_use_exact_exports_without_install_targets(self):
        exports = [Path('/build/vmlinux.symvers'), Path('/new/rfkill/Module.symvers')]
        plain = MODULE.make_command(Path('/build'), Path('/new/cfg80211'), exports)
        pcie = MODULE.make_command(Path('/build'), Path('/new/brcm80211'), exports, pcie=True)
        self.assertIn('modules', plain)
        self.assertIn('KCFLAGS=-Werror', plain)
        self.assertIn('LOCALVERSION=', plain)
        self.assertIn('KBUILD_EXTRA_SYMBOLS=/build/vmlinux.symvers /new/rfkill/Module.symvers', plain)
        self.assertNotIn('CONFIG_BRCMFMAC_PCIE=y', plain)
        self.assertEqual(pcie[-2:], ['CONFIG_BRCMFMAC_PCIE=y', 'CONFIG_BRCMFMAC_PROTO_MSGBUF=y'])
        self.assertNotIn('modules_install', pcie)
        self.assertFalse(any('WARN=' in argument or 'olddefconfig' == argument for argument in pcie))

    def test_elf_requires_machine_type_release_and_unique_vermagic(self):
        raw = bytearray(64)
        raw[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', raw, 16, 1, 183)
        magic = ('vermagic=' + MODULE.RELEASE + ' SMP preempt mod_unload aarch64\0').encode()
        valid = bytes(raw) + magic
        MODULE.verify_elf(valid)
        wrong_machine = bytearray(valid)
        struct.pack_into('<H', wrong_machine, 18, 62)
        for altered in (valid[:6], bytes(wrong_machine), valid.replace(b'7.2.0', b'7.0.0'),
                        valid + magic, valid[:16] + b'\x02\x00' + valid[18:]):
            with self.assertRaises(ValueError):
                MODULE.verify_elf(altered)

    def test_alias_retains_the_upstream_device_and_class_match(self):
        MODULE.verify_alias(['sdio:c*v02D0d4356*', 'pci:v000014E4d000043A3sv*sd*bc02sc80i*'])
        for aliases in ([], [MODULE.ALIAS.replace('43A3', '43A4')],
                        [MODULE.ALIAS.replace('bc02sc80', 'bc*sc*')]):
            with self.assertRaises(ValueError):
                MODULE.verify_alias(aliases)

    def test_existing_output_and_aliases_are_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            source, output = parent / 'source', parent / 'kernel-output'
            source.mkdir(mode=0o700)
            output.mkdir(mode=0o700)
            existing = parent / 'existing'
            existing.mkdir(mode=0o700)
            dangling = parent / 'dangling'
            dangling.symlink_to(parent / 'absent')
            for candidate in (existing, dangling, source / 'new', output / 'new'):
                with self.assertRaises(ValueError):
                    MODULE.destination(candidate, source, output)
                self.assertFalse((candidate / 'provenance-private.json').exists())

    def test_preserved_artifacts_are_hashed_before_accepting_the_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            data = {'.config': self.config().encode(), 'arch/arm64/boot/Image': b'preserved image',
                    'vmlinux.symvers': b'preserved exports'}
            for name, raw in data.items():
                file = output / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(raw)
            release = output / 'include/config/kernel.release'
            release.parent.mkdir(parents=True)
            release.write_text(MODULE.RELEASE + '\n')
            hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}
            with patch.object(MODULE, 'KERNEL_FILES', hashes):
                self.assertEqual(MODULE.kernel_state(output), MODULE.REQUIRED)
                for name, raw in data.items():
                    (output / name).write_bytes(raw + b'changed')
                    with self.assertRaises(ValueError):
                        MODULE.kernel_state(output)
                    (output / name).write_bytes(raw)
                release.write_text('7.2.0-iphone6s-source\n')
                with self.assertRaises(ValueError):
                    MODULE.kernel_state(output)

    def test_module_build_space_budget_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            target = parent / 'new'
            source, output = parent / 'source', parent / 'kernel'
            with patch.object(MODULE.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**3 - 1)):
                with self.assertRaises(ValueError):
                    MODULE.destination(target, source, output)
            with patch.object(MODULE.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024**3)):
                MODULE.destination(target, source, output)
            self.assertFalse(target.exists())

    def test_selected_binding_identity_is_pinned_and_unknown_profiles_refused(self):
        self.assertEqual(MODULE.build_identity('n71-dart-serdev-power-v2'), (
            '7.2.0-iphone6s-dart-serdev-power2', {
                '.config': 'c4e421b28d9ff2f3c372fa0d13431742a69a922a47bde23d62e9036483ae36b8',
                'arch/arm64/boot/Image': 'f36963f9f2abcce8e93b8c912112deb4b2563b36c5cc781c46e1bc8e9b819eed',
                'vmlinux.symvers': '03b00b50ef19d434d3f4ea13b21f68f9e52bb163642421010edf76a0ddb6ce61',
            }))
        self.assertEqual(MODULE.build_identity('n71-dart-serdev-v1'), (MODULE.RELEASE, MODULE.KERNEL_FILES))
        for profile in ('unknown', 'n71-dart-serdev-power-v1'):
            with self.assertRaises(ValueError):
                MODULE.build_identity(profile)

    def test_selected_elf_rejects_crossed_kernel_release(self):
        releases = {'n71-dart-serdev-v1': '7.2.0-iphone6s-dart-serdev1',
                    'n71-dart-serdev-power-v2': '7.2.0-iphone6s-dart-serdev-power2'}
        for profile, release in releases.items():
            raw = bytearray(64)
            raw[:7] = b'\x7fELF\x02\x01\x01'
            struct.pack_into('<HH', raw, 16, 1, 183)
            valid = bytes(raw) + ('vermagic=' + release + ' SMP preempt mod_unload aarch64\0').encode()
            try:
                MODULE.verify_elf(valid, profile=profile)
            except ValueError as error:
                self.fail('Correct selected ABI refused: ' + str(error))
            for other in releases:
                if other != profile:
                    with self.assertRaises(ValueError):
                        MODULE.verify_elf(valid, profile=other)

    def test_binding_output_requires_its_own_hashes_and_release(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            data = {'.config': self.config().encode(), 'arch/arm64/boot/Image': b'synthetic binding image',
                    'vmlinux.symvers': b'synthetic binding exports'}
            for name, raw in data.items():
                path = output / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            path = output / 'include/config/kernel.release'
            path.parent.mkdir(parents=True)
            path.write_text('7.2.0-iphone6s-dart-serdev-power2\n')
            hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}
            with patch.object(MODULE, 'BINDING_KERNEL_FILES', hashes):
                try:
                    self.assertEqual(MODULE.kernel_state(output, profile='n71-dart-serdev-power-v2'), MODULE.REQUIRED)
                except ValueError as error:
                    self.fail('Correct binding artifacts refused: ' + str(error))
                for name, raw in data.items():
                    (output / name).write_bytes(raw + b'changed')
                    with self.assertRaises(ValueError):
                        MODULE.kernel_state(output, profile='n71-dart-serdev-power-v2')
                    (output / name).write_bytes(raw)
                path.write_text('7.2.0-iphone6s-dart-serdev1\n')
                with self.assertRaises(ValueError):
                    MODULE.kernel_state(output, profile='n71-dart-serdev-power-v2')

    def test_cli_offers_explicit_binding_selection_without_building(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts/build'), PYTHONDONTWRITEBYTECODE='1')
        call = subprocess.run([sys.executable, str(SPEC.origin), '--help'], capture_output=True,
                              text=True, env=environment, timeout=10)
        self.assertEqual(call.returncode, 0, call.stderr)
        self.assertIn('--profile {n71-dart-serdev-v1,n71-dart-serdev-power-v2}', call.stdout)


if __name__ == '__main__':
    unittest.main()
