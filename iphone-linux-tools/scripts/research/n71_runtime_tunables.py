#!/usr/bin/env python3
"""Extract selected N71 tunables privately from a complete Pongo dt capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

ROOT = Path(__file__).resolve().parents[2]
MAX_CAPTURE = 2 * 1024 * 1024
TABLES = {
    ('/device-tree/arm-io/apcie', 'apcie-common-tunables'): ('common', 0x8000),
    ('/device-tree/arm-io/apcie', 'apcie-phy-tunables'): ('phy', 0x4000),
    ('/device-tree/arm-io/apcie/pci-bridge1', 'apcie-config-tunables'): ('port1', 0x4000),
    ('/device-tree/arm-io/apcie/pci-bridge1', 'pcie-rc-tunables'): ('config1', 0x1000),
}


def decode_records(data, aperture):
    if not data or len(data) % 24 or len(data) > 24 * 512:
        raise ValueError('Tunable record count or stride refused')
    result = []
    for offset, width, mask, value in struct.iter_unpack('<IIQQ', data):
        if (width != 4 or offset % 4 or aperture < 4 or offset > aperture - 4
                or mask > 0xffffffff or value > 0xffffffff):
            raise ValueError('Tunable width, alignment, aperture or high bits refused')
        # Apple masks both old and requested values. Preserve order/repeated offsets.
        result.append({'offset': offset, 'mask': mask, 'value': value & mask})
    return result


def properties_capture(data, selections):
    if not isinstance(selections, dict) or not selections or len(selections) > 32:
        raise ValueError('Bounded property selection required')
    labels = set()
    for pair, item in selections.items():
        if (not isinstance(pair, tuple) or len(pair) != 2
                or not isinstance(item, tuple) or len(item) != 2):
            raise ValueError('Property selection shape refused')
        path, key = pair
        label, limit = item
        if (not isinstance(path, str) or not re.fullmatch(r'/device-tree(?:/[A-Za-z0-9,_.+-]+)*', path)
                or any(part in ('.', '..') for part in path.split('/'))
                or not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9,_.+-]{0,31}', key)
                or not isinstance(label, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', label)
                or label in labels or type(limit) is not int or not 0 < limit <= 131072):
            raise ValueError('Property selection scope or budget refused')
        labels.add(label)
    if (not isinstance(data, (bytes, bytearray)) or not data or len(data) > MAX_CAPTURE
            or not data.rstrip().endswith(b'pongoOS>')):
        raise ValueError('Complete bounded Pongo capture required')
    text = data.decode('ascii', errors='replace')
    blocks = re.split(r'(?m)^-{128}\r?$', text)
    if len(blocks) > 4000:
        raise ValueError('DT node count refused')
    stack, selected = [], {}
    for block in blocks:
        lines = block.splitlines()
        names = [re.fullmatch(r'( *)name {28} (\S+)', line) for line in lines]
        names = [match for match in names if match]
        if not names:
            continue
        if len(names) != 1:
            raise ValueError('Ambiguous DT node name refused')
        indent, name = names[0].groups()
        depth = len(indent) // 4
        if (len(indent) % 4 or depth > 63 or depth > len(stack)
                or '/' in name or (depth == 0 and (stack or name != 'device-tree'))):
            raise ValueError('DT node hierarchy refused')
        stack = stack[:depth] + [name]
        path = '/' + '/'.join(stack)
        wanted = {key: item for (node, key), item in selections.items() if node == path}
        if not wanted:
            continue
        current = None
        chunks = {}
        for line in lines:
            if line.strip() == 'pongoOS>':
                current = None
                continue
            prefix = line[len(indent):len(indent) + 32]
            key = prefix.rstrip()
            if key and key in wanted:
                if key in chunks or not line.startswith(indent + key):
                    raise ValueError('Duplicate tunable property refused')
                current = key
                chunks[current] = bytearray()
            elif key:
                current = None
            if current is None:
                continue
            payload = line[len(indent) + 33:].partition('|')[0].strip()
            if not re.fullmatch(r'(?:[0-9a-f]{2}(?: +|$)){1,16}', payload):
                raise ValueError('Tunable hexdump row refused')
            chunks[current].extend(bytes.fromhex(payload))
            if len(chunks[current]) > wanted[current][1]:
                raise ValueError('Selected property bound refused')
        for key, raw in chunks.items():
            label, _ = wanted[key]
            if label in selected:
                raise ValueError('Repeated selected node refused')
            selected[label] = bytes(raw)
    if set(selected) != labels:
        raise ValueError('All selected properties required')
    return selected


def parse_capture(data):
    selections = {pair: (item[0], 24 * 512) for pair, item in TABLES.items()}
    metadata = {label: (path, key, aperture) for (path, key), (label, aperture) in TABLES.items()}
    result = {}
    for label, raw in properties_capture(data, selections).items():
        path, key, aperture = metadata[label]
        result[label] = {'path': path, 'property': key, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                         'bytes': len(raw), 'aperture': aperture, 'records': decode_records(raw, aperture)}
    return result


def private_path(path, directory=False):
    path = path.absolute()
    runtime = ROOT / 'runtime'
    if '..' in path.parts or not path.is_relative_to(runtime):
        raise ValueError('Private input/output must remain under project runtime')
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError('Linked private ancestor refused')
    info = path.lstat()
    proper_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (not proper_type or info.st_uid != os.geteuid() or info.st_mode & 0o7077
            or not directory and info.st_nlink != 1):
        raise ValueError('Own private regular input/directory required')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    source = private_path(options.input)
    if source.stat().st_size > MAX_CAPTURE:
        raise ValueError('Capture input bound refused')
    output = options.output_dir.absolute()
    runtime = private_path(ROOT / 'runtime', directory=True)
    if output.parent != runtime or output.exists() or output.is_symlink():
        raise ValueError('Choose a new private output directory directly under runtime')
    raw = source.read_bytes()
    tables = parse_capture(raw)
    report = {'format': 1, 'board': 'N71/S8000',
              'capture_sha256': hashlib.sha256(raw).hexdigest(), 'tables': tables,
              'record_format_validated': True, 'register_semantics_verified': False,
              'hardware_writes_performed': False, 'firmware_or_payload_executed': False}
    os.umask(0o077)
    output.mkdir(mode=0o700)
    with (output / 'tunables-private.json').open('x') as file:
        file.write(json.dumps(report, indent=2) + '\n')
    print('N71_TUNABLE_FORMAT_OK; private tables; no hardware writes')
    print(json.dumps({label: len(table['records']) for label, table in tables.items()}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, struct.error) as error:
        raise SystemExit('N71_TUNABLES_REFUSED: ' + str(error)) from error
