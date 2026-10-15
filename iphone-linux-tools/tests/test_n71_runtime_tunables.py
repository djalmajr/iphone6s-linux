"""Check selected tunable hierarchy, row framing, bounds and private paths."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/research/n71_runtime_tunables.py'
SPEC = importlib.util.spec_from_file_location('n71_runtime_tunables', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def node(depth, name, properties=()):
    prefix = ' ' * (depth * 4)
    result = prefix + f'{"name":32} {name}\n'
    for key, data in properties:
        for offset in range(0, len(data), 16):
            row = data[offset:offset + 16]
            result += prefix + f'{key if offset == 0 else "":32} ' + row.hex(' ') + '  |synthetic|\n'
    return result


def capture():
    record = struct.pack('<IIQQ', 0x100, 4, 0xff, 0x125)
    blocks = [node(0, 'device-tree'), node(1, 'arm-io'),
              node(2, 'apcie', [('apcie-common-tunables', record * 2),
                               ('apcie-phy-tunables', record)]),
              node(3, 'pci-bridge0', [('pcie-rc-tunables', record)]),
              node(3, 'pci-bridge1', [('apcie-config-tunables', record),
                                     ('pcie-rc-tunables', record)])]
    return ('\n' + ('-' * 128 + '\n').join(blocks) + 'pongoOS> ').encode()


class N71RuntimeTunables(unittest.TestCase):
    def test_selected_order_and_masked_value(self):
        tables = MODULE.parse_capture(capture())
        self.assertEqual(set(tables), {'common', 'phy', 'port1', 'config1'})
        self.assertEqual(tables['common']['records'], [{'offset': 0x100, 'mask': 0xff, 'value': 0x25}] * 2)
        self.assertEqual(tables['config1']['path'], '/device-tree/arm-io/apcie/pci-bridge1')

    def test_stride_width_alignment_aperture_and_high_bits(self):
        cases = [b'', b'\0' * 23, b'\0' * 25, b'\0' * (24 * 513)]
        for offset, width, mask, value in [(0, 8, 1, 1), (1, 4, 1, 1),
                                          (0x1000, 4, 1, 1), (0, 4, 1 << 32, 1),
                                          (0, 4, 1, 1 << 32)]:
            cases.append(struct.pack('<IIQQ', offset, width, mask, value))
        for raw in cases:
            with self.subTest(raw_bytes=len(raw)), self.assertRaises(ValueError):
                MODULE.decode_records(raw, 0x1000)
        self.assertEqual(MODULE.decode_records(struct.pack('<IIQQ', 0xffc, 4, 1, 1), 0x1000)[0]['offset'], 0xffc)

    def test_wrong_port_incomplete_prompt_and_hierarchy(self):
        for raw in [capture().replace(b'pci-bridge1', b'pci-bridge2'),
                    capture().replace(b'pongoOS>', b'incomplete'),
                    capture().replace(b'    name', b'     name', 1),
                    capture().replace(b'arm-io', b'wrong'),
                    b'x' * (MODULE.MAX_CAPTURE + 1)]:
            with self.subTest(bytes=len(raw)), self.assertRaises(ValueError):
                MODULE.parse_capture(raw)

    def test_bad_rows_and_duplicate_property(self):
        for raw in [capture().replace(b'00 01 00 00', b'gg 01 00 00', 1),
                    capture().replace(b'00 01 00 00', b'00 01 00', 1),
                    capture().replace(b'apcie-phy-tunables', b'apcie-common-tunables')]:
            with self.assertRaises(ValueError):
                MODULE.parse_capture(raw)

    def test_private_input_paths(self):
        old = MODULE.ROOT
        try:
            with tempfile.TemporaryDirectory() as temporary:
                MODULE.ROOT = Path(temporary).resolve()
                runtime = MODULE.ROOT / 'runtime'
                runtime.mkdir(mode=0o700)
                raw = runtime / 'capture.txt'
                raw.write_bytes(capture())
                raw.chmod(0o600)
                self.assertEqual(MODULE.private_path(raw), raw)
                for rejected in [MODULE.ROOT / 'outside', runtime / '..' / 'outside']:
                    with self.assertRaises(ValueError):
                        MODULE.private_path(rejected)
                link = runtime / 'link.txt'
                link.symlink_to(raw)
                with self.assertRaises(ValueError):
                    MODULE.private_path(link)
                raw.chmod(0o644)
                with self.assertRaises(ValueError):
                    MODULE.private_path(raw)
        finally:
            MODULE.ROOT = old


if __name__ == '__main__':
    unittest.main()
