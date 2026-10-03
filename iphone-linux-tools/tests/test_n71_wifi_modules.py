"""Preserved-kernel and package boundaries for the module-only build recipe."""
import importlib.util
import hashlib
import os
from pathlib import Path
import struct
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


if __name__ == '__main__':
    unittest.main()
