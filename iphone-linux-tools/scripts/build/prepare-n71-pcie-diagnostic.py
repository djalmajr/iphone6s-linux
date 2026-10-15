#!/usr/bin/env python3
"""Prepare a private, opt-in N71 PCIe diagnostic DTB without installing tools."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SHA = '9a4baf1b5f18d380d843e78bd39fb466abec313e078b5d6efe2825a5de5589c4'
BASE_SHA = 'b25b2b748d6f934d3b4ed51d9906ae86ae5e031756bfe9009073a4dea7537f58'
STAGED_SHA = '8c48f6e32b4d46aef8252530785c9a254802846cf80a979af22ef2f6843ab4b6'
GPIO = '/soc/pinctrl@20f100000'


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


TOPOLOGY = load_module('n71_topology', ROOT / 'scripts/build/prepare-n71-topology.py')
TUNABLES = load_module('n71_tunables', ROOT / 'scripts/research/n71_runtime_tunables.py')


def serialize_dtb(template, nodes):
    """Preserve reservation entries and boot CPU; re-encode ordered properties."""
    TOPOLOGY.parse_dtb(template)
    header = struct.unpack_from('>10I', template)
    reserve, start, names = header[4], header[2], header[3]
    position = reserve
    limit = min(value for value in (start, names, len(template)) if value > reserve)
    while position + 16 <= limit:
        address, size = struct.unpack_from('>QQ', template, position)
        position += 16
        if address == size == 0:
            break
    else:
        raise ValueError('Memory reservation terminator refused')
    reservations = template[reserve:position]
    strings, offsets, body = bytearray(), {}, bytearray()
    children = {path: [] for path in nodes}
    if '/' not in nodes or len(nodes) > 4000:
        raise ValueError('DT node count/root refused')
    for path in nodes:
        if path == '/':
            continue
        parent = path.rpartition('/')[0] or '/'
        if parent not in children:
            raise ValueError('Missing DT parent')
        children[parent].append(path)

    def align():
        body.extend(b'\0' * (-len(body) % 4))

    def node(path, depth):
        if depth > 63:
            raise ValueError('DT depth refused')
        body.extend(struct.pack('>I', 1))
        body.extend(('' if path == '/' else path.rsplit('/', 1)[1]).encode('ascii') + b'\0')
        align()
        for name, value in nodes[path].items():
            if not name or '\0' in name or not isinstance(value, bytes):
                raise ValueError('DT property refused')
            if name not in offsets:
                offsets[name] = len(strings)
                strings.extend(name.encode('ascii') + b'\0')
            body.extend(struct.pack('>III', 3, len(value), offsets[name]))
            body.extend(value)
            align()
        for child in children[path]:
            node(child, depth + 1)
        body.extend(struct.pack('>I', 2))

    node('/', 0)
    body.extend(struct.pack('>I', 9))
    start = 40 + len(reservations)
    names = start + len(body)
    total = names + len(strings)
    result = struct.pack('>10I', 0xd00dfeed, total, start, names, 40,
                         17, 16, header[7], len(strings), len(body))
    result += reservations + body + strings
    if TOPOLOGY.parse_dtb(result) != nodes:
        raise ValueError('DT round-trip differs')
    return result


def prepare(baseline, staged, capture):
    if (hashlib.sha256(baseline).hexdigest() != BASE_SHA or
            hashlib.sha256(staged).hexdigest() != STAGED_SHA or
            hashlib.sha256(capture).hexdigest() != CAPTURE_SHA):
        raise ValueError('Pinned N71 inputs required')
    before, nodes = TOPOLOGY.parse_dtb(baseline), TOPOLOGY.parse_dtb(staged)
    TOPOLOGY.verify_delta(before, nodes)
    tables = TUNABLES.parse_capture(capture)
    gpio = nodes.get(GPIO, {})
    if (gpio.get('reg') != TOPOLOGY.registers([[0x20f100000, 0x100000]]) or
            gpio.get('#gpio-cells') != TOPOLOGY.cells(2) or
            gpio.get('apple,npins') != TOPOLOGY.cells(208) or
            len(gpio.get('phandle', b'')) != 4):
        raise ValueError('Pinned N71 GPIO provider required')
    properties = dict(nodes[TOPOLOGY.PCIE])
    properties.update({'compatible': b'apple,n71-pcie-diagnostic\0',
                       'status': b'okay\0',
                       'perst-gpios': gpio['phandle'] + TOPOLOGY.cells(161, 1)})
    for label, table in tables.items():
        properties['n71,' + label + '-tunables'] = b''.join(
            TOPOLOGY.cells(record['offset'], record['mask'], record['value'])
            for record in table['records'])
    nodes[TOPOLOGY.PCIE] = properties
    # All existing properties/nodes except this diagnostic node remain identical.
    original = TOPOLOGY.parse_dtb(staged)
    if any(nodes[path] != values for path, values in original.items() if path != TOPOLOGY.PCIE):
        raise ValueError('Unrelated DT node changed')
    return serialize_dtb(staged, nodes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--staged', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    sources = [TUNABLES.private_path(path) for path in
               (options.baseline, options.staged, options.capture)]
    for path, bound in zip(sources, (4 * 1024 * 1024, 4 * 1024 * 1024, TUNABLES.MAX_CAPTURE)):
        if path.stat().st_size > bound:
            raise ValueError('Input size refused')
    destination = options.output_dir.absolute()
    runtime = TUNABLES.private_path(ROOT / 'runtime', directory=True)
    if destination.parent != runtime or destination.exists() or destination.is_symlink():
        raise ValueError('New private output directly under runtime required')
    result = prepare(*(path.read_bytes() for path in sources))
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    with (destination / 'diagnostic-private.dtb').open('xb') as file:
        file.write(result)
    with (destination / 'provenance-private.json').open('x') as file:
        json.dump({'format': 1, 'sha256': hashlib.sha256(result).hexdigest(),
                   'diagnostic_binding_only': True, 'driver_requires_explicit_run': True,
                   'unrelated_nodes_preserved': True, 'boot_qualified': False,
                   'wifi_verified': False, 'dma_enabled': False}, file, indent=2)
        file.write('\n')
    print('N71_DIAGNOSTIC_DTB_PREPARED; private; not boot qualified')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, struct.error) as error:
        raise SystemExit('N71_DIAGNOSTIC_REFUSED: ' + str(error)) from error
