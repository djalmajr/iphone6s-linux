#!/usr/bin/env python3
"""Compose a private opt-in PCI OF calibration profile without booting a phone."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_cli as runtime

SPEC = importlib.util.spec_from_file_location('calibration_diagnostic', Path(__file__).with_name('compose-n71-diagnostic.py'))
DIAGNOSTIC = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(DIAGNOSTIC)
PCIE = '/soc/pcie@610000000'
PORT = PCIE + '/pci@1,0'
WIFI = PORT + '/wifi@0,0'
CORE_FILES = {'payload.bin', 'initramfs.gz', 'client_ed25519', 'known_hosts', 'deployment.json', 'provenance.json'}
CAL_FIELDS = {'format', 'board', 'path', 'property', 'capture_sha256', 'bytes', 'sha256',
              'hardware_writes', 'firmware_executed', 'physical_acceptance'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def calibration(root, directory):
    require(isinstance(directory, Path) and directory.is_absolute() and directory.parent == root / 'runtime',
            'Calibration directory must be private and directly under runtime')
    runtime.device_profile.protected(directory, directory=True)
    require({p.name for p in directory.iterdir()} == {'calibration-private.bin', 'provenance-private.json'},
            'Exact private calibration files required')
    path = directory / 'provenance-private.json'; runtime.device_profile.protected(path)
    require(path.stat().st_size <= 4096, 'Calibration provenance exceeds budget')
    report = json.loads(path.read_text())
    require(isinstance(report, dict) and set(report) == CAL_FIELDS and type(report['format']) is int
        and report['format'] == 1 and report['board'] == 'N71/S8000'
        and report['path'] == '/device-tree/arm-io/uart4/wlan' and report['property'] == 'wifi-calibration-msf'
        and report['capture_sha256'] == DIAGNOSTIC.DIAGNOSTIC.CAPTURE_SHA and type(report['bytes']) is int
        and report['bytes'] == 1024 and all(report[name] is False for name in
            ('hardware_writes', 'firmware_executed', 'physical_acceptance')), 'Calibration source or scope differs')
    path = directory / 'calibration-private.bin'; runtime.device_profile.protected(path)
    require(path.stat().st_size == 1024, 'Exact private calibration length required')
    blob = path.read_bytes()
    require(hashlib.sha256(blob).hexdigest() == report['sha256'], 'Calibration bytes differ from provenance')
    return report, blob


def additions(blob):
    require(isinstance(blob, bytes) and len(blob) == 1024, 'Immutable exact calibration required')
    cells = DIAGNOSTIC.TOPOLOGY.cells
    return {PORT: {'reg': cells(0x800, 0, 0, 0, 0), 'device_type': b'pci\0',
                   '#address-cells': cells(3), '#size-cells': cells(2), 'ranges': b'', 'status': b'okay\0'},
            WIFI: {'reg': cells(0, 0, 0, 0, 0), 'status': b'okay\0', 'brcm,cal-blob': blob}}


def validate_dtb(source, candidate, blob):
    before = DIAGNOSTIC.TOPOLOGY.parse_dtb(source); after = DIAGNOSTIC.TOPOLOGY.parse_dtb(candidate)
    expected = additions(blob)
    require(set(after) == set(before) | set(expected) and not set(before) & set(expected), 'Calibration node set differs')
    restored = {path: dict(properties) for path, properties in after.items()}
    for path, properties in expected.items():
        actual = restored.pop(path)
        require(actual == properties, 'Calibration PCI node properties differ')
    pcie = restored[PCIE]
    address_cells = pcie.pop('#address-cells', None); size_cells = pcie.pop('#size-cells', None)
    require(address_cells == DIAGNOSTIC.TOPOLOGY.cells(3)
        and size_cells == DIAGNOSTIC.TOPOLOGY.cells(2), 'Calibration PCI cell counts differ')
    require(restored == before, 'Calibration profile changed preserved DT nodes')


def dtb(source, blob):
    nodes = DIAGNOSTIC.TOPOLOGY.parse_dtb(source)
    require(PCIE in nodes and nodes[PCIE].get('compatible') == b'apple,n71-pcie-diagnostic\0'
        and nodes[PCIE].get('status') == b'okay\0' and not any(path.startswith(PCIE + '/') for path in nodes)
        and '#address-cells' not in nodes[PCIE] and '#size-cells' not in nodes[PCIE],
        'Uncalibrated diagnostic PCI topology required')
    nodes[PCIE] = dict(nodes[PCIE], **{'#address-cells': DIAGNOSTIC.TOPOLOGY.cells(3),
                                    '#size-cells': DIAGNOSTIC.TOPOLOGY.cells(2)})
    nodes.update(additions(blob))
    result = DIAGNOSTIC.DIAGNOSTIC.serialize_dtb(source, nodes)
    validate_dtb(source, result, blob)
    return result


def local_request(profile, output=None):
    return {'action': 'acquire', 'check': True, 'profile': profile, 'source': None, 'output': output}


def compose(root, request):
    require(isinstance(request, dict) and set(request) == {'source', 'calibration', 'output'}, 'Exact composition request required')
    require(isinstance(request['output'], Path), 'Explicit new composition output required')
    runtime.paths(root, local_request(request['source'], request['output']))
    metadata, selected = runtime.selection(root, request['source'])
    require(metadata.get('pcie_calibration') is None and metadata.get('wifi_verified') is False
        and metadata.get('physical_boot_tested') is False, 'Uncalibrated C4 source required')
    report, blob = calibration(root, request['calibration'])
    folder = request['source'].parent
    names = CORE_FILES | {record['module'] for record in selected['diagnostics'] + [record for record, _ in selected['drivers']]}
    require(len(names) == 13 and {p.name for p in folder.iterdir()} == names, 'Exact thirteen source profile files required')
    data = {}; total = 0
    for name in sorted(names):
        path = folder / name; runtime.device_profile.protected(path)
        size = path.stat().st_size
        require(size <= 64 * 1024 * 1024, 'Source profile file exceeds budget')
        total += size; require(total <= 96 * 1024 * 1024, 'Source profile exceeds total budget')
        data[name] = path.read_bytes()
    require(len(data['deployment.json']) <= 8192, 'Source deployment exceeds budget')
    deployment = json.loads(data['deployment.json'])
    require(all(deployment.get(key) == name for key, name in [('payload', 'payload.bin'), ('initramfs', 'initramfs.gz'),
        ('client_key', 'client_ed25519'), ('known_hosts', 'known_hosts')]), 'Canonical source identity paths required')
    require(hashlib.sha256(data['payload.bin']).hexdigest() == deployment.get('sha256') == metadata.get('payload_sha256')
        and hashlib.sha256(data['initramfs.gz']).hexdigest() == deployment.get('initramfs_sha256'), 'Source snapshot hashes differ')
    runtime.run(root, local_request(request['source']))
    link = runtime.link_module(root); prefix = link.aspm_payload({'payload': folder / 'payload.bin'}, metadata)
    raw = data['payload.bin']; require(len(raw) >= prefix + 8, 'Source payload FDT missing')
    magic, length = struct.unpack_from('>II', raw, prefix)
    require(magic == 0xd00dfeed and 40 <= length <= 4 * 1024 * 1024 and prefix + length <= len(raw), 'Source FDT boundary differs')
    original = raw[prefix:prefix + length]
    require(hashlib.sha256(original).hexdigest() == metadata.get('dtb_sha256'), 'Source FDT differs from provenance')
    candidate = dtb(original, blob)
    data['payload.bin'] = raw[:prefix] + candidate + raw[prefix + length:]
    sha = hashlib.sha256(data['payload.bin']).hexdigest()
    deployment['sha256'] = sha
    metadata.update({'payload_sha256': sha, 'dtb_sha256': hashlib.sha256(candidate).hexdigest(),
                     'pcie_calibration': True, 'calibration_blob_sha256': report['sha256'],
                     'calibration_capture_sha256': report['capture_sha256']})
    data['deployment.json'] = (json.dumps(deployment, indent=2) + '\n').encode()
    data['provenance.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    data['calibration-private.bin'] = blob
    previous = os.umask(0o077)
    try:
        request['output'].mkdir(mode=0o700)
        for name, value in data.items():
            with (request['output'] / name).open('xb') as file:
                file.write(value)
        runtime.run(root, local_request(request['output'] / 'deployment.json'))
    finally:
        os.umask(previous)
    print('N71_CALIBRATION_PROFILE_CREATED; private opt-in; no hardware action', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-profile', required=True, type=Path)
    parser.add_argument('--calibration-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    options = parser.parse_args()
    compose(ROOT, {'source': options.source_profile.absolute(), 'calibration': options.calibration_dir.absolute(),
                   'output': options.output_dir.absolute()})


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, struct.error) as error:
        raise SystemExit('N71_CALIBRATION_PROFILE_REFUSED: ' + str(error)) from error
