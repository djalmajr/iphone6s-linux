#!/usr/bin/env python3
"""Read the pinned Apple N71 board reference; keep all firmware data private."""
import argparse
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import urllib.request
import zipfile
ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    destination = options.output_dir.absolute()
    if sys.platform != 'darwin':
        raise ValueError('This reader uses the existing Apple Compression library on macOS.')
    if destination.parent != ROOT / 'runtime' or destination.exists() or destination.is_symlink():
        raise ValueError('Choose a new private output directory directly under runtime.')
    info = destination.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o7077:
        raise ValueError('Private caller-owned runtime directory required.')
    destination.mkdir(mode=0o700)
    meta = {'url': 'https://updates.cdn-apple.com/2025FallFCS/fullrestores/122-77510/5D4563BF-445C-4D8D-AF56-0BAC336265F3/iPhone_4.7_15.8.8_19H422_Restore.ipsw', 'filesize': 5270350276, 'version': '15.8.8', 'buildid': '19H422'}

    class Remote(io.RawIOBase):

        def __init__(self):
            self.pos = 0
            self.total = 0

        def readable(self):
            return True

        def seekable(self):
            return True

        def tell(self):
            return self.pos

        def seek(self, offset, whence=0):
            position = (0 if whence == 0 else self.pos if whence == 1 else meta['filesize']) + offset
            if not 0 <= position <= meta['filesize']:
                raise ValueError('ZIP offset refused')
            self.pos = position
            return position

        def read(self, n=-1):
            if n == 0:
                return b''
            if not 0 < n <= 4 * 1024 * 1024:
                raise ValueError('ZIP read bound refused')
            end = min(self.pos + n, meta['filesize']) - 1
            if end < self.pos:
                return b''
            request = urllib.request.Request(meta['url'], headers={'Range': f'bytes={self.pos}-{end}', 'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(request, timeout=25) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f"bytes {self.pos}-{end}/{meta['filesize']}":
                    raise ValueError('Server range response refused')
                blob = response.read(n + 1)
            if len(blob) != end - self.pos + 1:
                raise ValueError('ZIP range size refused')
            self.total += len(blob)
            if self.total > 32 * 1024 * 1024:
                raise ValueError('Total download bound refused')
            self.pos = end + 1
            return blob
    stream = Remote()
    with zipfile.ZipFile(stream) as archive:
        entries = [i for i in archive.infolist() if re.fullmatch('Firmware/all_flash/DeviceTree\\.n71ap\\.im4p', i.filename)]
        if len(entries) != 1:
            raise ValueError('Exact N71 DeviceTree member missing')
        entry = entries[0]
        if entry.file_size > 2 * 1024 * 1024 or entry.compress_size > 2 * 1024 * 1024:
            raise ValueError('DeviceTree size refused')
        with archive.open(entry) as file:
            blob = file.read(2 * 1024 * 1024 + 1)
        if len(blob) != entry.file_size:
            raise ValueError('DeviceTree length refused')
        if hashlib.sha256(blob).hexdigest() != '739aeb1b52a76ac9147b2479e86a06b3c49b1e09499377ea73f1329a034b5184':
            raise ValueError('Pinned DeviceTree hash refused')
        path = destination / 'DeviceTree.n71ap.im4p'
        path.write_bytes(blob)
        path.chmod(0o600)
        report = {'source': 'Pinned Apple HTTPS distribution', 'version': meta['version'], 'buildid': meta['buildid'], 'member': entry.filename, 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob), 'range_download_bytes': stream.total, 'archive_crc_verified': True, 'cryptographic_signature_verified': False, 'flashed': False, 'url': meta['url']}
        (destination / 'dt-source.json').write_text(json.dumps(report, indent=2) + '\n')
        (destination / 'dt-source.json').chmod(0o600)
    blob = (destination / 'DeviceTree.n71ap.im4p').read_bytes()

    def der(data, pos):
        if pos + 2 > len(data):
            raise ValueError('DER header truncated')
        tag = data[pos]
        length = data[pos + 1]
        start = pos + 2
        if length & 128:
            size = length & 127
            if not 1 <= size <= 4:
                raise ValueError('DER length bound')
            if start + size > len(data):
                raise ValueError('DER length truncated')
            length = int.from_bytes(data[start:start + size], 'big')
            start += size
        end = start + length
        if end > len(data):
            raise ValueError('DER truncated')
        return (tag, data[start:end], end)
    tag, outer, end = der(blob, 0)
    if tag != 48 or end != len(blob):
        raise ValueError('IM4P DER envelope refused')
    parts = []
    pos = 0
    while pos < len(outer):
        tag, value, pos = der(outer, pos)
        parts.append((tag, value))
    if len(parts) < 4 or parts[0] != (22, b'IM4P') or parts[1] != (22, b'dtre'):
        raise ValueError('IM4P DeviceTree type refused')
    encoded = parts[3][1]
    if parts[3][0] != 4 or encoded[:4] != b'bvx2':
        raise ValueError('LZFSE payload refused')
    lib = ctypes.CDLL('/usr/lib/libcompression.dylib')
    lib.compression_decode_buffer.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
    lib.compression_decode_buffer.restype = ctypes.c_size_t
    out = ctypes.create_string_buffer(4 * 1024 * 1024)
    inp = ctypes.create_string_buffer(encoded)
    size = lib.compression_decode_buffer(out, len(out), inp, len(encoded), None, 0x801)
    if not 0 < size < len(out):
        raise ValueError('LZFSE output bound')
    raw = out.raw[:size]
    (destination / 'n71-adt-private.bin').write_bytes(raw)
    (destination / 'n71-adt-private.bin').chmod(0o600)
    nodes = []

    def node(pos, parent, depth=0):
        if depth > 40 or len(nodes) > 4000:
            raise ValueError('ADT tree bound')
        properties, children = struct.unpack_from('<II', raw, pos)
        pos += 8
        if properties > 512 or children > 512:
            raise ValueError('ADT count bound')
        props = {}
        for _ in range(properties):
            name = raw[pos:pos + 32].split(b'\x00', 1)[0].decode('ascii')
            length = struct.unpack_from('<I', raw, pos + 32)[0] & 0x7fffffff
            pos += 36
            if length > 1024 * 1024 or pos + length > len(raw):
                raise ValueError('ADT property bound')
            props[name] = raw[pos:pos + length]
            pos += (length + 3) & ~3
        name = props.get('name', b'?').split(b'\x00', 1)[0].decode('ascii')
        path = parent + '/' + name
        nodes.append({'path': path, 'properties': props})
        for _ in range(children):
            pos = node(pos, path, depth + 1)
        return pos
    end = node(0, '')
    if end != len(raw):
        raise ValueError('ADT trailing data refused')
    terms = ('pci', 'wlan', 'wifi', 'wireless', 'dart', 'hdq', 'charger', 'battery', 'sn2400', 'bq', 'gas', 'uart', 'pmu')
    selected = []
    for n in nodes:
        props = n['properties']
        compatible = props.get('compatible', b'').replace(b'\x00', b',').decode('ascii', errors='replace')
        if not any((t in (n['path'] + ' ' + compatible).lower() for t in terms)):
            continue
        wanted = {}
        for key, val in props.items():
            if any((t in key.lower() for t in ('reg', 'interrupt', 'clock', 'gpio', 'power', 'device-id', 'vendor-id', 'iommu', 'dart', 'compatible'))):
                if len(val) <= 256:
                    wanted[key] = {'bytes': len(val), 'hex': val.hex()}
        selected.append({'path': n['path'], 'compatible': compatible, 'property_names': list(props), 'hardware_properties': wanted})
    report = {'source_dt_sha256': hashlib.sha256(raw).hexdigest(), 'decoded_bytes': len(raw), 'nodes': len(nodes), 'selected_nodes': selected, 'board_reference_only': True, 'device_calibration': False, 'writes_performed': False}
    (destination / 'map-private.json').write_text(json.dumps(report, indent=2) + '\n')
    (destination / 'map-private.json').chmod(0o600)
    print('APPLE_N71_BOARD_MAP_SAVED; private reference; no device writes')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, AssertionError, zipfile.BadZipFile, struct.error) as error:
        raise SystemExit('APPLE_N71_MAP_REFUSED: ' + str(error)) from error
