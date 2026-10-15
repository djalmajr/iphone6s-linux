#!/usr/bin/env python3
"""Compose a private N71 DMA aperture candidate without touching hardware."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('dma_calibration', Path(__file__).with_name('compose-n71-calibration.py'))
CAL = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CAL)
runtime = CAL.runtime
DART = '/soc/iommu@602008000'
PROPERTY = 'apple,dma-range'
START = 0x80000000
LENGTH = 0x3ffff000
REFERENCE_SHA = '7e71222b78099dbca7b2487dcc4b727f8a922c3b1885fc47f086d518eefef040'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reference(root):
    path = root / 'docs/evidence/n71-dart-apple-stream-reference.json'
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8192,
            'Pinned board reference required')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == REFERENCE_SHA, 'Board reference digest differs')
    data = json.loads(raw); chain = data['adt_chain']
    require(data['format'] == 1 and data['apple_intended_stream'] == chain['mapper_reg'] == 0
        and chain['dart_path'] == '/device-tree/arm-io/dart-apcie1'
        and chain['dart_mmio'] == '0x602008000' and chain['dart_bytes'] == 16384
        and chain['page_bytes'] == 4096 and chain['dart_irq'] == 248
        and chain['vm_offset_u32_pair'] == ['0x80000000', '0x08000000']
        and chain['vm_size'] == '0x3ffff000', 'Board DMA premises differ')
    require(START == int(chain['vm_offset_u32_pair'][0], 16) and LENGTH == int(chain['vm_size'], 16)
        and START + LENGTH == 0xbffff000 and LENGTH % chain['page_bytes'] == 0,
        'Exact DMA window and excluded MSI page required')
    return struct.pack('>QQ', START, LENGTH)


def source_nodes(source):
    nodes = CAL.DIAGNOSTIC.TOPOLOGY.parse_dtb(source)
    dart = nodes.get(DART, {})
    require(b'apple,n71' in nodes.get('/', {}).get('compatible', b'').split(b'\0')
        and dart.get('compatible') == b'apple,s8000-dart\0apple,s5l8960x-dart\0'
        and dart.get('status') == b'disabled\0'
        and dart.get('reg') == struct.pack('>QQ', 0x602008000, 0x4000)
        and dart.get('interrupts') == struct.pack('>III', 0, 248, 4)
        and dart.get('#iommu-cells') == struct.pack('>I', 1)
        and PROPERTY not in dart, 'Unmodified disabled N71 DART required')
    return nodes


def validate_dtb(source, candidate, window):
    before = source_nodes(source); after = CAL.DIAGNOSTIC.TOPOLOGY.parse_dtb(candidate)
    require(window == struct.pack('>QQ', START, LENGTH) and len(window) == 16,
            'Canonical big-endian DMA cells required')
    restored = {path: dict(properties) for path, properties in after.items()}
    actual = restored.get(DART, {}).pop(PROPERTY, None)
    require(actual == window, 'DMA window bytes differ')
    require(restored == before, 'DMA candidate changed preserved DT data')


def dtb(source, window):
    nodes = source_nodes(source)
    nodes[DART] = dict(nodes[DART], **{PROPERTY: window})
    raw = CAL.DIAGNOSTIC.DIAGNOSTIC.serialize_dtb(source, nodes)
    validate_dtb(source, raw, window)
    return raw


def compose(root, request):
    require(isinstance(request, dict) and set(request) == {'source', 'output'}, 'Exact DMA composition request required')
    runtime.paths(root, CAL.local_request(request['source'], request['output']))
    require(isinstance(request['output'], Path), 'Explicit new DMA output required')
    metadata, selected = runtime.selection(root, request['source'])
    require(metadata.get('pcie_calibration') is True and metadata.get('dart_dma_window') is None
        and metadata.get('wifi_verified') is False, 'Calibrated source without DMA override required')
    window = reference(root); folder = request['source'].parent
    names = CAL.CORE_FILES | {'calibration-private.bin'} | {
        record['module'] for record in selected['diagnostics'] + [record for record, _ in selected['drivers']]}
    require(len(names) == 14 and {p.name for p in folder.iterdir()} == names,
            'Exact fourteen source profile files required')
    data = {}; total = 0
    for name in sorted(names):
        path = folder / name; runtime.device_profile.protected(path)
        size = path.stat().st_size
        require(size <= 64 * 1024 * 1024, 'DMA source file exceeds budget')
        total += size; require(total <= 96 * 1024 * 1024, 'DMA source exceeds total budget')
        data[name] = path.read_bytes()
    require(len(data['deployment.json']) <= 8192, 'DMA source deployment exceeds budget')
    deployment = json.loads(data['deployment.json'])
    require(all(deployment.get(key) == name for key, name in [('payload', 'payload.bin'), ('initramfs', 'initramfs.gz'),
        ('client_key', 'client_ed25519'), ('known_hosts', 'known_hosts')]), 'Canonical source identity paths required')
    require(hashlib.sha256(data['payload.bin']).hexdigest() == deployment.get('sha256') == metadata.get('payload_sha256')
        and hashlib.sha256(data['initramfs.gz']).hexdigest() == deployment.get('initramfs_sha256'),
        'DMA source snapshot hashes differ')
    require(len(data['calibration-private.bin']) == 1024
        and hashlib.sha256(data['calibration-private.bin']).hexdigest() == metadata.get('calibration_blob_sha256'),
        'Source calibration bytes differ')
    runtime.run(root, CAL.local_request(request['source']))
    prefix = runtime.link_module(root).aspm_payload({'payload': folder / 'payload.bin'}, metadata)
    raw = data['payload.bin']; require(len(raw) >= prefix + 8, 'DMA source FDT header missing')
    magic, length = struct.unpack_from('>II', raw, prefix)
    require(magic == 0xd00dfeed and 40 <= length <= 4 * 1024 * 1024 and prefix + length <= len(raw),
            'DMA source FDT boundary differs')
    original = raw[prefix:prefix + length]
    require(hashlib.sha256(original).hexdigest() == metadata.get('dtb_sha256'), 'DMA source FDT digest differs')
    nodes = source_nodes(original)
    require(nodes.get(CAL.WIFI, {}).get('brcm,cal-blob') == data['calibration-private.bin'],
            'Source FDT calibration differs')
    candidate = dtb(original, window)
    data['payload.bin'] = raw[:prefix] + candidate + raw[prefix + length:]
    sha = hashlib.sha256(data['payload.bin']).hexdigest(); deployment['sha256'] = sha
    metadata.update({'payload_sha256': sha, 'dtb_sha256': hashlib.sha256(candidate).hexdigest(),
        'physical_boot_tested': False, 'dart_dma_window': {'start': START, 'length': LENGTH,
            'end_exclusive': START + LENGTH, 'reference_sha256': REFERENCE_SHA, 'physical_acceptance': False}})
    data['deployment.json'] = (json.dumps(deployment, indent=2) + '\n').encode()
    data['provenance.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    previous = os.umask(0o077)
    try:
        request['output'].mkdir(mode=0o700)
        for name, value in data.items():
            with (request['output'] / name).open('xb') as file:
                file.write(value)
        runtime.run(root, CAL.local_request(request['output'] / 'deployment.json'))
    finally:
        os.umask(previous)
    print('N71_DMA_WINDOW_PROFILE_CREATED; private opt-in; no hardware action', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-profile', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    options = parser.parse_args()
    compose(ROOT, {'source': options.source_profile.absolute(), 'output': options.output_dir.absolute()})


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, struct.error) as error:
        raise SystemExit('N71_DMA_WINDOW_PROFILE_REFUSED: ' + str(error)) from error
