"""Disabled resource staging cannot change the working N71 device tree."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('N71_TOPOLOGY_SCRIPT', ROOT / 'scripts/build/prepare-n71-topology.py'))
spec = importlib.util.spec_from_file_location('n71_topology', SCRIPT)
topology = importlib.util.module_from_spec(spec)
spec.loader.exec_module(topology)
SOURCE = os.environ.get('IPHONE_N71_VM_SOURCE')


def word(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def model():
    before = {'/': {'compatible': b'apple,n71\0apple,s8000\0'}, '/soc': {},
              '/soc/usb': {'status': b'okay\0', 'reg': word(2, 0x0c100000, 0, 0x10000)},
              '/soc/serial0': {'status': b'okay\0'},
              topology.CLOCK_REF: {'phandle': word(1), '#clock-cells': word(0)},
              topology.UART_PD: {'#power-domain-cells': word(0)},
              topology.PCIE_PD: {'phandle': word(3), '#power-domain-cells': word(0)},
              topology.AUX: {'#power-domain-cells': word(0)},
              topology.REF: {'#power-domain-cells': word(0)},
              topology.LINK1: {'#power-domain-cells': word(0)}}
    for path in tuple(before):
        parent = path.rsplit('/', 1)[0]
        while parent:
            before.setdefault(parent, {})
            parent = parent.rsplit('/', 1)[0]
    after = copy.deepcopy(before)
    for path, handle in ((topology.UART_PD, 2), (topology.AUX, 4), (topology.REF, 5), (topology.LINK1, 6)):
        after[path]['phandle'] = word(handle)
    after[topology.UART] = {'compatible': b'apple,s5l-uart\0',
                            'reg': word(2, 0x0a0d4000, 0, 0x4000), 'reg-io-width': word(4),
                            'interrupts': word(0, 197, 4), 'clocks': word(1, 1),
                            'clock-names': b'uart\0clk_uart_baud0\0',
                            'power-domains': word(2), 'status': b'disabled\0'}
    after[topology.DART] = {'compatible': b'apple,s8000-dart\0apple,s5l8960x-dart\0',
                            'reg': word(6, 0x02008000, 0, 0x4000), 'interrupts': word(0, 248, 4),
                            '#iommu-cells': word(1), 'power-domains': word(3), 'status': b'disabled\0'}
    addresses = (0x610000000, 0x601000000, 0x601004000, 0x602000000, 0x602004000,
                 0x603000000, 0x603004000, 0x604000000, 0x604004000, 0x600000000, 0x600008000)
    sizes = (0x1000000,) + (0x4000,) * 8 + (0x8000, 0x4000)
    after[topology.PCIE] = {'compatible': b'apple,s8000-pcie\0',
                            'reg': b''.join(word(a >> 32, a & 0xffffffff, 0, s) for a, s in zip(addresses, sizes)),
                            'reg-names': b'ecam\0' + b''.join(f'adt-reg-{i}\0'.encode() for i in range(1, 11)),
                            'interrupts': word(0, 244, 4, 0, 247, 4, 0, 250, 4, 0, 253, 4),
                            'power-domains': word(3, 4, 5, 6),
                            'power-domain-names': b'pcie\0aux\0ref\0link1\0', 'status': b'disabled\0'}
    return before, after


def encode(nodes):
    names = {}
    strings = bytearray()
    for properties in nodes.values():
        for key in properties:
            if key not in names:
                names[key] = len(strings)
                strings.extend(key.encode() + b'\0')
    def emit(path):
        name = b'' if path == '/' else path.rsplit('/', 1)[1].encode()
        result = word(1) + name + b'\0'
        result += b'\0' * (-len(result) % 4)
        for key, value in nodes[path].items():
            result += word(3, len(value), names[key]) + value + b'\0' * (-len(value) % 4)
        children = [n for n in nodes if n != '/' and (n.rsplit('/', 1)[0] or '/') == path]
        for child in sorted(children):
            result += emit(child)
        return result + word(2)
    structure = emit('/') + word(9)
    names_offset = 56 + len(structure)
    header = word(0xd00dfeed, names_offset + len(strings), 56, names_offset, 40,
                  17, 16, 0, len(strings), len(structure))
    return header + b'\0' * 16 + structure + strings


def dart_phandle_model():
    before, after = model()
    before['/soc/pinned'] = {'phandle': word(100)}
    after['/soc/pinned'] = copy.deepcopy(before['/soc/pinned'])
    after[topology.DART]['phandle'] = word(101)
    return before, after


class TopologyContract(unittest.TestCase):
    def test_reserve_dart_phandle_validates_baseline_and_range(self):
        # Mutations captured: skip pin validation, reuse the max handle, or allow overflow.
        before, _ = model()
        self.assertEqual(topology.reserve_dart_phandle(before), 4)
        self.assertEqual(topology.reserve_dart_phandle({'/': {}}), 1)
        for value in (b'\x01', word(0), word(0xffffffff), word(0xfffffffe), word(1)):
            bad = copy.deepcopy(before)
            bad['/soc/extra'] = {'phandle': value}
            with self.subTest(value=value), self.assertRaises(ValueError):
                topology.reserve_dart_phandle(bad)

    def test_dart_phandle_is_explicit_exact_and_disabled(self):
        before, after = dart_phandle_model()
        self.assertEqual(topology.reserve_dart_phandle(before), 101)
        topology.verify_delta(before, after, dart_phandle=101)
        self.assertEqual(after[topology.DART]['status'], b'disabled\0')
        self.assertNotIn('iommu-map', after[topology.PCIE])
        with self.assertRaises(ValueError):
            topology.verify_delta(before, after)

    def test_dart_phandle_refusal_is_strict(self):
        # Mutations captured: accept a different reservation, incoming handle or collision.
        for index in range(7):
            before, after = dart_phandle_model()
            requested = 101
            if index == 0:
                requested = 102
                after[topology.DART]['phandle'] = word(102)
            elif index == 1:
                after[topology.DART]['phandle'] = word(102)
            elif index == 2:
                after[topology.AUX]['phandle'] = word(101)
                after[topology.PCIE]['power-domains'] = word(3, 101, 5, 6)
            elif index == 3:
                after[topology.DART]['status'] = b'okay\0'
            elif index == 4:
                after[topology.DART].pop('phandle')
            elif index == 5:
                after[topology.DART]['phandle'] = b'\x01'
            else:
                after[topology.PCIE]['iommu-map'] = word(8, 101, 0, 1)
            with self.subTest(index=index), self.assertRaises(ValueError):
                topology.verify_delta(before, after, dart_phandle=requested)

    def test_fdt_roundtrip_and_exact_disabled_addition(self):
        # Mutation captured: removing the baseline-property preservation guard.
        before, after = model()
        self.assertEqual(topology.parse_dtb(encode(before)), before)
        self.assertEqual(topology.parse_dtb(encode(after)), after)
        topology.verify_delta(before, after)
        self.assertEqual(after['/soc/usb'], before['/soc/usb'])
        self.assertEqual(set(after) - set(before), {topology.UART, topology.DART, topology.PCIE})

    def test_existing_usb_property_change_refused(self):
        before, after = model()
        after['/soc/usb']['status'] = b'disabled\0'
        with self.assertRaises(ValueError):
            topology.verify_delta(before, after)

    def test_enabled_or_missing_status_refused(self):
        # Mutation captured: accepting the candidate's status instead of disabled.
        for path in (topology.UART, topology.DART, topology.PCIE):
            for value in (b'okay\0', None):
                before, after = model()
                if value is None:
                    after[path].pop('status')
                else:
                    after[path]['status'] = value
                with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                    topology.verify_delta(before, after)

    def test_unrelated_new_node_refused(self):
        before, after = model()
        after['/soc/extra'] = {}
        with self.assertRaises(ValueError):
            topology.verify_delta(before, after)

    def test_a10_fallback_and_register_map_refused(self):
        for key, value in (('compatible', b'apple,t8010-pcie\0'), ('reg', word(6, 0x0a000000, 0, 0x40000))):
            before, after = model()
            after[topology.PCIE][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                topology.verify_delta(before, after)

    def test_wrong_uart_endian_address_and_irq_refused(self):
        for key, value in (('reg', struct.pack('<4I', 2, 0x0a0d4000, 0, 0x4000)),
                           ('reg', word(2, 0x0a0cc000, 0, 0x4000)), ('interrupts', word(0, 223, 4))):
            before, after = model()
            after[topology.UART][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                topology.verify_delta(before, after)

    def test_port2_dart_refused(self):
        before, after = model()
        after[topology.DART]['reg'] = word(6, 0x03008000, 0, 0x4000)
        with self.assertRaises(ValueError):
            topology.verify_delta(before, after)

    def test_wrong_clock_and_power_provider_refused(self):
        # Mutation captured: accepting incoming UART clocks without provider validation.
        for key, value in (('clocks', word(3, 3)), ('power-domains', word(3))):
            before, after = model()
            after[topology.UART][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                topology.verify_delta(before, after)

    def test_duplicate_provider_phandle_refused(self):
        before, after = model()
        after[topology.UART_PD]['phandle'] = word(3)
        after[topology.UART]['power-domains'] = word(3)
        with self.assertRaises(ValueError):
            topology.verify_delta(before, after)

    def test_exact_board_identification_required(self):
        before, after = model()
        before['/']['compatible'] = after['/']['compatible'] = b'apple,n71-unknown\0'
        with self.assertRaises(ValueError):
            topology.verify_delta(before, after)

    def test_reference_mismatch_refused(self):
        # Mutation captured: bypassing the exact Apple N71 reference comparison.
        topology.validate_reference(copy.deepcopy(topology.REFERENCE))
        for key in ('decoded_dt_sha256', 'nodes', 'arm_io_ranges'):
            reference = copy.deepcopy(topology.REFERENCE)
            reference[key] = None
            with self.subTest(key=key), self.assertRaises(ValueError):
                topology.validate_reference(reference)

    def test_parser_rejects_truncation_header_and_end(self):
        data = encode(model()[0])
        for bad in (data[:39], data[:-1], b'BAD!' + data[4:], data[:4] + word(len(data) + 4) + data[8:]):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                topology.parse_dtb(bad)
        damaged = bytearray(data)
        struct.pack_into('>I', damaged, 56, 9)
        with self.assertRaises(ValueError):
            topology.parse_dtb(damaged)

    def test_linked_input_refused_without_changing_target(self):
        # Mutation captured: removing the ancestor/file symlink refusal.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / 'source'
            target.write_bytes(b'PRESERVE')
            topology.regular(target)
            link = root / 'link'
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                topology.regular(link)
            parent = root / 'linked-parent'
            parent.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                topology.regular(parent / 'source')
            os.link(target, root / 'hardlink')
            with self.assertRaises(ValueError):
                topology.regular(target)
            self.assertEqual(target.read_bytes(), b'PRESERVE')


@unittest.skipUnless(SOURCE and os.name == 'posix' and __import__('sys').platform == 'linux',
                     'Opt-in pinned kernel source and existing GCC/dtc in dedicated Linux VM required')
class NativeCompilation(unittest.TestCase):
    def options(self, root):
        reference = root / 'reference.json'
        reference.write_text(json.dumps(topology.REFERENCE))
        return argparse.Namespace(source_dir=Path(SOURCE), reference=reference, output_dir=root / 'output')

    def test_phandle_pins_preserve_existing_references(self):
        # Mutation captured: omitting baseline phandle pins renumbers CPU/USB references.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            includes = '#include ' + json.dumps(str(Path(SOURCE) / 'arch/arm64/boot/dts/apple/s8000-n71.dts')) + '\n'
            wrapper = root / 'baseline.dts'
            wrapper.write_text(includes)
            topology.compile_dts((wrapper, Path(SOURCE)), root / 'baseline.dtb')
            before = topology.parse_dtb((root / 'baseline.dtb').read_bytes())
            wrapper = root / 'candidate.dts'
            wrapper.write_text(includes + topology.freeze_phandles(before) +
                               '#include ' + json.dumps(str(topology.FRAGMENT)) + '\n')
            topology.compile_dts((wrapper, Path(SOURCE)), root / 'candidate.dtb')
            after = topology.parse_dtb((root / 'candidate.dtb').read_bytes())
            for path, properties in before.items():
                for key, value in properties.items():
                    with self.subTest(path=path, property=key):
                        self.assertEqual(after[path][key], value)

    def test_real_n71_compile_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            options = self.options(Path(directory).resolve())
            report = topology.prepare(options)
            self.assertTrue(report['all_added_nodes_disabled'])
            self.assertFalse(report['boot_qualified'])
            self.assertEqual(set(report['added_nodes']), {topology.UART, topology.DART, topology.PCIE})
            self.assertEqual(options.output_dir.stat().st_mode & 0o777, 0o700)
            self.assertTrue((options.output_dir / 'candidate.dtb').is_file())

    def test_real_dart_phandle_is_unique_and_keeps_disabled_default(self):
        # Mutation captured: ignoring the explicit phandle preparation option.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            normal = self.options(root)
            normal.output_dir = root / 'default'
            baseline_report = topology.prepare(normal)
            self.assertNotIn('dart_phandle', baseline_report)
            default = topology.parse_dtb((normal.output_dir / 'candidate.dtb').read_bytes())
            self.assertNotIn('phandle', default[topology.DART])
            options = self.options(root)
            options.dart_phandle = True
            report = topology.prepare(options)
            self.assertIn('dart_phandle', report)
            before = topology.parse_dtb((options.output_dir / 'baseline.dtb').read_bytes())
            after = topology.parse_dtb((options.output_dir / 'candidate.dtb').read_bytes())
            handle = topology.reserve_dart_phandle(before)
            self.assertEqual(report['dart_phandle'], handle)
            self.assertEqual(after[topology.DART]['phandle'], word(handle))
            self.assertEqual(sum(node.get('phandle') == word(handle) for node in after.values()), 1)
            topology.verify_delta(before, after, dart_phandle=handle)
            self.assertEqual(baseline_report['baseline_sha256'], report['baseline_sha256'])
            for path in (topology.UART, topology.DART, topology.PCIE):
                self.assertEqual(after[path]['status'], b'disabled\0')
            for path, props in before.items():
                for key, value in props.items():
                    self.assertEqual(after[path][key], value)
            self.assertNotIn('iommu-map', after[topology.PCIE])

    def test_existing_and_linked_outputs_preserve_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            options = self.options(root)
            options.output_dir.mkdir()
            marker = options.output_dir / 'keep'
            marker.write_bytes(b'KEEP')
            with self.assertRaises(ValueError):
                topology.prepare(options)
            self.assertEqual(marker.read_bytes(), b'KEEP')
            options.output_dir = root / 'linked-output'
            options.output_dir.symlink_to(marker.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                topology.prepare(options)
            self.assertEqual(marker.read_bytes(), b'KEEP')

    def test_compiling_enabled_fragment_refuses_manifest(self):
        # Mutation captured: disabled-state enforcement after a successful real compile.
        original = topology.FRAGMENT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                options = self.options(root)
                altered = root / 'altered.dtsi'
                altered.write_text(original.read_text().replace('status = "disabled"', 'status = "okay"', 1))
                topology.FRAGMENT = altered
                with self.assertRaises(ValueError):
                    topology.prepare(options)
                self.assertTrue((options.output_dir / 'candidate.dtb').exists())
                self.assertFalse((options.output_dir / 'provenance.json').exists())
        finally:
            topology.FRAGMENT = original


if __name__ == '__main__':
    unittest.main()
