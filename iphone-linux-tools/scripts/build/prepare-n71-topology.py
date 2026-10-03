#!/usr/bin/env python3
"""Compile disabled N71 resource nodes without modifying the kernel checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / 'phone/kernel/n71-peripherals.dtsi'
COMMIT = '958481f87fee0949ff6a9a4af77f7eb6dac8a149'
ADT_HASH = '5e7ad3a1df32acbb872bb18164f67c9903130e03e337b841f75ef7cacc6e979b'
UART = '/soc/serial@20a0d4000'
DART = '/soc/iommu@602008000'
PCIE = '/soc/pcie@610000000'
UART_PD = '/soc/power-management@20e000000/power-controller@80200'
PCIE_PD = '/soc/power-management@20e000000/power-controller@80310'
CLOCK_REF = '/clock-ref'
AUX = '/soc/power-management@20e000000/power-controller@80318'
REF = '/soc/power-management@20e000000/power-controller@80148'
LINK1 = '/soc/power-management@20e000000/power-controller@80328'
PCI_REGS = [[0x610000000, 0x1000000]]
PCI_REGS += [[address, 0x4000] for address in (
    0x601000000, 0x601004000, 0x602000000, 0x602004000,
    0x603000000, 0x603004000, 0x604000000, 0x604004000)]
PCI_REGS += [[0x600000000, 0x8000], [0x600008000, 0x4000]]
REFERENCE = {'format': 1, 'decoded_dt_sha256': ADT_HASH,
             'arm_io_ranges': [[0, 0x200000000, 0x100000000],
                               [0x600000000, 0x600000000, 0x200000000]],
             'nodes': {'uart5': {'reg': [[0x0a0d4000, 0x4000]], 'interrupts': [197]},
                       'dart_apcie1': {'reg': [[0x602008000, 0x4000]], 'interrupts': [248]},
                       'apcie': {'reg': PCI_REGS, 'interrupts': [244, 247, 250, 253]}}}


def validate_reference(reference):
    if reference != REFERENCE:
        raise ValueError('N71 reference hash, translation or resources differ.')


def cells(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def registers(pairs):
    return b''.join(cells(address >> 32, address & 0xffffffff,
                          size >> 32, size & 0xffffffff) for address, size in pairs)


def parse_dtb(data):
    if not 40 <= len(data) <= 4 * 1024 * 1024:
        raise ValueError('DTB length refused.')
    magic, total, start, names, reserve, version, compatible, cpu, names_size, size = struct.unpack_from('>10I', data)
    if (magic != 0xd00dfeed or total != len(data) or version != 17 or compatible > 17
            or min(start, names, reserve) < 40 or start % 4
            or max(start + size, names + names_size) > total
            or not (start + size <= names or names + names_size <= start)):
        raise ValueError('DTB header or blocks refused.')
    strings = data[names:names + names_size]
    nodes, stack = {}, []
    end = start + size
    offset = start
    while offset + 4 <= end:
        token = struct.unpack_from('>I', data, offset)[0]
        offset += 4
        if token == 1:
            stop = data.find(b'\0', offset, end)
            if stop < 0 or len(stack) >= 64 or len(nodes) >= 4000:
                raise ValueError('DTB node bounds refused.')
            name = data[offset:stop].decode('ascii')
            if '/' in name or (not stack and name):
                raise ValueError('DTB node name refused.')
            stack.append(name)
            path = '/'.join(stack) or '/'
            if path in nodes:
                raise ValueError('Duplicate DTB node refused.')
            nodes[path] = {}
            offset = (stop + 4) & ~3
        elif token == 2:
            if not stack:
                raise ValueError('DTB node stack refused.')
            stack.pop()
        elif token == 3:
            if not stack or offset + 8 > end:
                raise ValueError('DTB property header refused.')
            length, name_offset = struct.unpack_from('>II', data, offset)
            offset += 8
            stop = strings.find(b'\0', name_offset)
            if stop < 0 or offset + length > end:
                raise ValueError('DTB property bounds refused.')
            name = strings[name_offset:stop].decode('ascii')
            properties = nodes['/'.join(stack) or '/']
            if not name or name in properties:
                raise ValueError('DTB property name refused.')
            properties[name] = data[offset:offset + length]
            offset = (offset + length + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            if stack or not nodes or any(data[offset:end]):
                raise ValueError('DTB end refused.')
            return nodes
        else:
            raise ValueError('DTB token refused.')
    raise ValueError('DTB truncated before end.')


def verify_delta(before, after):
    if b'apple,n71' not in before.get('/', {}).get('compatible', b'').split(b'\0'):
        raise ValueError('Baseline is not N71.')
    if set(after) - set(before) != {UART, DART, PCIE} or set(before) - set(after):
        raise ValueError('Candidate must add exactly three staged resource nodes.')
    for path, properties in before.items():
        allowed = dict(properties)
        if path in (UART_PD, AUX, REF, LINK1) and 'phandle' not in allowed:
            if 'phandle' in after[path]:
                allowed['phandle'] = after[path]['phandle']
        if after[path] != allowed:
            raise ValueError('Existing DTB node or property changed: ' + path)
    expected = {
        UART: {'compatible': b'apple,s5l-uart\0', 'reg': registers([[0x20a0d4000, 0x4000]]),
               'reg-io-width': cells(4), 'interrupts': cells(0, 197, 4),
               'clock-names': b'uart\0clk_uart_baud0\0'},
        DART: {'compatible': b'apple,s8000-dart\0apple,s5l8960x-dart\0',
               'reg': registers([[0x602008000, 0x4000]]), 'interrupts': cells(0, 248, 4),
               '#iommu-cells': cells(1)},
        PCIE: {'compatible': b'apple,s8000-pcie\0', 'reg': registers(PCI_REGS),
               'reg-names': b'ecam\0' + b''.join(f'adt-reg-{i}\0'.encode() for i in range(1, 11)),
               'interrupts': b''.join(cells(0, irq, 4) for irq in (244, 247, 250, 253)),
               'power-domain-names': b'pcie\0aux\0ref\0link1\0'},
    }
    def phandle(path):
        value = after.get(path, {}).get('phandle', b'')
        if len(value) != 4 or not 0 < int.from_bytes(value, 'big') < 0xffffffff:
            raise ValueError('Provider phandle refused: ' + path)
        if sum(n.get('phandle') == value for n in after.values()) != 1:
            raise ValueError('Duplicate provider phandle refused.')
        return value
    for path, values in expected.items():
        values['status'] = b'disabled\0'
        values['power-domains'] = phandle(UART_PD if path == UART else PCIE_PD)
        if path == UART:
            values['clocks'] = phandle(CLOCK_REF) * 2
        elif path == PCIE:
            values['power-domains'] += phandle(AUX) + phandle(REF) + phandle(LINK1)
        if after[path] != values:
            raise ValueError('Staged resources, bindings or disabled state differ: ' + path)


def freeze_phandles(nodes):
    result, used = [], set()
    for path, properties in nodes.items():
        if 'phandle' not in properties:
            continue
        value = properties['phandle']
        if (len(value) != 4 or not re.fullmatch(r'/[A-Za-z0-9,._+@/\-]*', path)
                or not 0 < int.from_bytes(value, 'big') < 0xffffffff or value in used):
            raise ValueError('Baseline phandle cannot be pinned safely.')
        used.add(value)
        result.append(f'&{{{path}}} {{ phandle = <0x{int.from_bytes(value, "big"):x}>; }};\n')
    return ''.join(result)


def regular(path):
    path = Path(path).absolute()
    for parent in (path,) + tuple(path.parents):
        if parent.is_symlink():
            raise ValueError('Linked input or output path refused.')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4 * 1024 * 1024:
        raise ValueError('Input type, links or size refused.')
    return path


def compile_dts(source, output):
    wrapper, kernel = source
    preprocessed = output.with_suffix('.pp')
    with preprocessed.open('xb') as file:
        subprocess.run(['gcc', '-E', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                        '-I', str(kernel / 'arch/arm64/boot/dts'), '-I', str(kernel / 'include'),
                        str(wrapper)], stdout=file, check=True, timeout=30)
    log = output.with_suffix('.log')
    with log.open('xb') as file:
        subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(output), str(preprocessed)],
                       stderr=file, check=True, timeout=30)
    for path in (preprocessed, output, log):
        path.chmod(0o600)


def prepare(options):
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise ValueError('Run as an unprivileged user inside the dedicated Linux VM.')
    reference = regular(options.reference)
    validate_reference(json.loads(reference.read_bytes()))
    kernel = options.source_dir.absolute()
    regular(kernel / 'arch/arm64/boot/dts/apple/s8000-n71.dts')
    head = subprocess.check_output(['git', '-C', str(kernel), 'rev-parse', 'HEAD'], text=True).strip()
    def clean():
        return not subprocess.check_output(['git', '-C', str(kernel), 'status', '--porcelain',
                                            '--untracked-files=no'], text=True).strip()
    if head != COMMIT or not clean():
        raise ValueError('Pinned clean kernel checkout required.')
    destination = options.output_dir.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Choose a new output directory; never overwrite a build.')
    for parent in destination.parents:
        if parent.is_symlink():
            raise ValueError('Linked output ancestor refused.')
    if destination.is_relative_to(kernel):
        raise ValueError('Output must remain outside the kernel checkout.')
    fragment = regular(FRAGMENT).read_bytes()
    destination.mkdir(mode=0o700)
    # Serialize an absolute path as a CPP string rather than interpolating quotes.
    includes = '#include ' + json.dumps(str(kernel / 'arch/arm64/boot/dts/apple/s8000-n71.dts')) + '\n'
    for name, data in (('baseline.dts', includes.encode()), ('n71-peripherals.dtsi', fragment)):
        path = destination / name
        path.write_bytes(data)
        path.chmod(0o600)
    compile_dts((destination / 'baseline.dts', kernel), destination / 'baseline.dtb')
    baseline = (destination / 'baseline.dtb').read_bytes()
    before = parse_dtb(baseline)
    wrapper = destination / 'candidate.dts'
    wrapper.write_text(includes + freeze_phandles(before) + '#include "n71-peripherals.dtsi"\n')
    wrapper.chmod(0o600)
    compile_dts((wrapper, kernel), destination / 'candidate.dtb')
    candidate = (destination / 'candidate.dtb').read_bytes()
    verify_delta(before, parse_dtb(candidate))
    if not clean():
        raise ValueError('Kernel checkout changed during preparation.')
    manifest = {'format': 1, 'source_commit': head, 'reference_adt_sha256': ADT_HASH,
                'baseline_sha256': hashlib.sha256(baseline).hexdigest(),
                'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
                'fragment_sha256': hashlib.sha256(fragment).hexdigest(),
                'added_nodes': [UART, DART, PCIE], 'all_added_nodes_disabled': True,
                'existing_properties_preserved': True, 'kernel_checkout_unchanged': True,
                'hardware_probe_tested': False, 'boot_qualified': False,
                'wifi_enabled': False, 'charging_validation': 'unverified'}
    path = destination / 'provenance.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    path.chmod(0o600)
    print('N71_TOPOLOGY_COMPILED; disabled staging only; not boot qualified')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    try:
        prepare(parser.parse_args())
    except (OSError, ValueError, KeyError, struct.error, subprocess.SubprocessError) as error:
        raise SystemExit('N71_TOPOLOGY_REFUSED: ' + str(error)) from error


if __name__ == '__main__':
    main()
