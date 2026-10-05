"""Diagnostic payload may change DT only; ABI and identity bindings stay exact."""
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from test_n71_pcie_diagnostic import fixture, pin, MODULE as DT
from test_n71_topology import encode

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'n71_diagnostic_payload', os.environ.get('N71_DIAGNOSTIC_COMPOSER_SCRIPT', ROOT / 'scripts/build/compose-n71-diagnostic.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def inputs():
    raw = fixture()
    with pin(raw):
        candidate = DT.prepare(*raw)
    return raw[0], candidate


class N71DiagnosticPayload(unittest.TestCase):
    def test_exact_payload_delta_preserves_kernel_userspace_and_loader(self):
        baseline, candidate = inputs()
        prefix, kernel, initramfs = b'LOADER', b'KERNEL', b'PRIVATE_USERS'
        source = prefix + MODULE.KERNEL.BOOTARGS + baseline + kernel + initramfs
        result = MODULE.compose(source, prefix, baseline, candidate, kernel, initramfs)
        self.assertEqual(result, prefix + MODULE.KERNEL.BOOTARGS + candidate + kernel + initramfs)
        for altered in (source + b'extra', source.replace(b'KERNEL', b'OTHER!'),
                        source.replace(b'PRIVATE_USERS', b'CHANGED_USERS')):
            with self.assertRaises(ValueError):
                MODULE.compose(altered, prefix, baseline, candidate, kernel, initramfs)

    def test_device_tree_cannot_change_usb_gauge_or_perst(self):
        baseline, candidate = inputs()
        original = MODULE.TOPOLOGY.parse_dtb(candidate)
        for path, key, value in (
                ('/soc/usb', 'status', b'disabled\0'),
                (MODULE.TOPOLOGY.UART, 'status', b'okay\0'),
                (MODULE.TOPOLOGY.PCIE, 'perst-gpios', struct.pack('>III', 31, 2, 1)),
                (MODULE.TOPOLOGY.PCIE, 'n71,extra', b'bad')):
            nodes = {path: dict(props) for path, props in original.items()}
            nodes[path][key] = value
            with self.subTest(path=path, key=key), self.assertRaises(ValueError):
                MODULE.validate_dtb(baseline, encode(nodes))

    def test_tunable_alignment_and_mask_refused(self):
        baseline, candidate = inputs()
        for value in (b'', b'x', struct.pack('>III', 1, 1, 1),
                      struct.pack('>III', 0x4000, 1, 1), struct.pack('>III', 0, 1, 2)):
            nodes = MODULE.TOPOLOGY.parse_dtb(candidate)
            nodes[MODULE.TOPOLOGY.PCIE]['n71,phy-tunables'] = value
            with self.subTest(value_bytes=len(value)), self.assertRaises(ValueError):
                MODULE.validate_dtb(baseline, encode(nodes))

    def test_module_architecture_type_and_exact_vermagic(self):
        # Synthetic ELF header, not a loadable module or proof of symbols/linking.
        header = bytearray(64)
        header[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', header, 16, 1, 183)
        marker = b'vermagic=7.2.0-iphone6s-source SMP preempt mod_unload aarch64\0'
        valid = bytes(header) + marker
        MODULE.validate_module(valid)
        for wrong in (valid[:63], valid.replace(b'\x7fELF', b'BAD!'),
                      valid.replace(b'7.2.0-iphone6s-source ', b'7.2.0-iphone6s-source+ '),
                      valid + marker, valid[:18] + struct.pack('<H', 62) + valid[20:]):
            with self.assertRaises(ValueError):
                MODULE.validate_module(wrong)

    def test_bundle_module_requires_selected_release_and_rejects_unknown_abi(self):
        header = bytearray(64)
        header[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', header, 16, 1, 183)
        baseline = '7.2.0-iphone6s-source'
        bundle = '7.2.0-iphone6s-dart-serdev1'
        power = '7.2.0-iphone6s-dart-serdev-power1'
        binding = '7.2.0-iphone6s-dart-serdev-power2'

        def image(release):
            return bytes(header) + ('vermagic=' + release + ' SMP preempt mod_unload aarch64\0').encode()

        # Kills omission of a selected known ABI and mixing modules across all four releases.
        for selected in (baseline, bundle, power, binding):
            try:
                MODULE.validate_module(image(selected), kernel_release=selected)
            except ValueError as error:
                self.fail('Known selected ABI refused: ' + str(error))
        crossed = [(actual, selected) for actual in (baseline, bundle, power, binding)
                   for selected in (baseline, bundle, power, binding) if actual != selected]
        for actual, selected in crossed + [(bundle + '+', bundle), (power + '+', power), (binding + '+', binding),
                                            (baseline + '+', baseline + '+'), ('7.0.12', '7.0.12')]:
            with self.subTest(actual=actual, selected=selected), self.assertRaises(ValueError):
                MODULE.validate_module(image(actual), kernel_release=selected)


    def test_cli_exposes_explicit_power2_without_implicit_selection(self):
        result = subprocess.run([sys.executable, MODULE.__file__, '--help'],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('n71-dart-serdev-power-v2', result.stdout)
        self.assertIn('--kernel-patchset', result.stdout)


if __name__ == '__main__':
    unittest.main()
