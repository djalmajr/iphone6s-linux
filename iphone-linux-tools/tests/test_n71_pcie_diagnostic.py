"""Prove private DT composition preserves devices and validates pinned inputs."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from test_n71_topology import encode, model, word
from test_n71_runtime_tunables import capture

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'n71_diagnostic', ROOT / 'scripts/build/prepare-n71-pcie-diagnostic.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    before, staged = model()
    gpio = {'reg': word(2, 0x0f100000, 0, 0x100000), '#gpio-cells': word(2),
            'apple,npins': word(208), 'phandle': word(31), 'gpio-controller': b''}
    before[MODULE.GPIO] = gpio
    staged[MODULE.GPIO] = copy.deepcopy(gpio)
    return encode(before), encode(staged), capture()


def pin(inputs):
    return patch.multiple(MODULE, **dict(zip(
        ('BASE_SHA', 'STAGED_SHA', 'CAPTURE_SHA'),
        (hashlib.sha256(value).hexdigest() for value in inputs))))


class N71PrivateDiagnostic(unittest.TestCase):
    def test_single_node_delta_private_cells_and_disabled_other_devices(self):
        inputs = fixture()
        with pin(inputs):
            result = MODULE.prepare(*inputs)
        original = MODULE.TOPOLOGY.parse_dtb(inputs[1])
        after = MODULE.TOPOLOGY.parse_dtb(result)
        self.assertEqual(set(after), set(original))
        for path, properties in original.items():
            if path != MODULE.TOPOLOGY.PCIE:
                self.assertEqual(after[path], properties)
        pcie = after[MODULE.TOPOLOGY.PCIE]
        self.assertEqual(pcie['compatible'], b'apple,n71-pcie-diagnostic\0')
        self.assertEqual(pcie['perst-gpios'], word(31, 161, 1))
        self.assertEqual(pcie['n71,phy-tunables'], word(0x100, 0xff, 0x25))
        self.assertEqual(pcie['n71,common-tunables'], word(0x100, 0xff, 0x25) * 2)
        self.assertEqual(after[MODULE.TOPOLOGY.DART]['status'], b'disabled\0')
        self.assertEqual(after[MODULE.TOPOLOGY.UART]['status'], b'disabled\0')

    def test_reservation_entries_and_boot_cpu_preserved(self):
        template = bytearray(fixture()[0])
        header = list(struct.unpack_from('>10I', template))
        entry = struct.pack('>QQ', 0x800000000, 0x10000)
        template[40:40] = entry
        header[1] += 16
        header[2] += 16
        header[3] += 16
        header[7] = 3
        struct.pack_into('>10I', template, 0, *header)
        nodes = MODULE.TOPOLOGY.parse_dtb(bytes(template))
        result = MODULE.serialize_dtb(bytes(template), nodes)
        self.assertEqual(result[40:72], entry + b'\0' * 16)
        self.assertEqual(struct.unpack_from('>I', result, 28)[0], 3)
        self.assertEqual(MODULE.TOPOLOGY.parse_dtb(result), nodes)

    def test_each_input_hash_mismatch_refused(self):
        inputs = fixture()
        with pin(inputs):
            for index in range(3):
                wrong = list(inputs)
                wrong[index] += b'changed'
                with self.subTest(index=index), self.assertRaises(ValueError):
                    MODULE.prepare(*wrong)

    def test_gpio_provider_bounds_and_changed_usb_refused(self):
        inputs = fixture()
        before = MODULE.TOPOLOGY.parse_dtb(inputs[0])
        staged = MODULE.TOPOLOGY.parse_dtb(inputs[1])
        before[MODULE.GPIO]['apple,npins'] = staged[MODULE.GPIO]['apple,npins'] = word(42)
        wrong = (encode(before), encode(staged), inputs[2])
        with pin(wrong), self.assertRaises(ValueError):
            MODULE.prepare(*wrong)
        staged = MODULE.TOPOLOGY.parse_dtb(inputs[1])
        staged['/soc/usb']['status'] = b'disabled\0'
        wrong = (inputs[0], encode(staged), inputs[2])
        with pin(wrong), self.assertRaises(ValueError):
            MODULE.prepare(*wrong)

    def test_unterminated_reservations_and_orphan_nodes_refused(self):
        template = bytearray(fixture()[0])
        template[40:56] = struct.pack('>QQ', 1, 1)
        nodes = MODULE.TOPOLOGY.parse_dtb(bytes(template))
        with self.assertRaises(ValueError):
            MODULE.serialize_dtb(bytes(template), nodes)
        nodes['/missing/child'] = {}
        with self.assertRaises(ValueError):
            MODULE.serialize_dtb(fixture()[0], nodes)


if __name__ == '__main__':
    unittest.main()
