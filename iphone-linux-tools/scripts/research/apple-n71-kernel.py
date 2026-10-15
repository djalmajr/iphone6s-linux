#!/usr/bin/env python3
"""Fetch/decode the pinned Apple N71 reference as private data, never execute it."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import urllib.request
import zipfile

from apple_kernel_format import decode

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://updates.cdn-apple.com/2025FallFCS/fullrestores/122-77510/5D4563BF-445C-4D8D-AF56-0BAC336265F3/iPhone_4.7_15.8.8_19H422_Restore.ipsw'
ZIP_BYTES = 5270350276
MEMBER = 'kernelcache.release.n71'
MEMBER_BYTES = 20844035
MEMBER_SHA = '5eb352b649bc9a8b3d3af1ceb1d07f15d506b87400276c4f98e93dc2d65c76cf'
IMAGE_SHA = '0a9b98d58c5c606030c394bee37b6ddd58e0d82468203f7de9ab3fe6c63a8b9a'


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
        if whence not in (0, 1, 2):
            raise ValueError('ZIP seek origin refused')
        position = (0 if whence == 0 else self.pos if whence == 1 else ZIP_BYTES) + offset
        if not 0 <= position <= ZIP_BYTES:
            raise ValueError('ZIP offset refused')
        self.pos = position
        return position

    def read(self, n=-1):
        if n == 0:
            return b''
        if not 0 < n <= 4 * 1024 * 1024:
            raise ValueError('ZIP read bound refused')
        end = min(self.pos + n, ZIP_BYTES) - 1
        if end < self.pos:
            return b''
        request = urllib.request.Request(URL, headers={
            'Range': f'bytes={self.pos}-{end}', 'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(request, timeout=25) as response:
            if (response.status != 206 or response.headers.get('Content-Range')
                    != f'bytes {self.pos}-{end}/{ZIP_BYTES}'):
                raise ValueError('Server range response refused')
            blob = response.read(n + 1)
        if len(blob) != end - self.pos + 1 or self.total + len(blob) > 32 * 1024 * 1024:
            raise ValueError('Download size refused')
        self.total += len(blob)
        self.pos = end + 1
        return blob


def fetch():
    stream = Remote()
    with zipfile.ZipFile(stream) as archive:
        entries = [entry for entry in archive.infolist() if entry.filename == MEMBER]
        if len(entries) != 1:
            raise ValueError('Exact N71 kernel member missing')
        entry = entries[0]
        if (entry.file_size, entry.compress_size, entry.CRC) != (MEMBER_BYTES, 19565302, 0x660cb9ea):
            raise ValueError('Pinned member metadata refused')
        parts, length = [], 0
        with archive.open(entry) as file:
            while chunk := file.read(1024 * 1024):
                length += len(chunk)
                if length > MEMBER_BYTES:
                    raise ValueError('Kernel member size refused')
                parts.append(chunk)
    return b''.join(parts), stream.total


def private_file(path):
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError('Input parent symlink refused')
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o7077
            or metadata.st_size != MEMBER_BYTES):
        raise ValueError('Expected a private regular pinned member')
    with path.open('rb') as file:
        return file.read(MEMBER_BYTES + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--input', type=Path, help='Reuse a private pinned IM4P; no network')
    options = parser.parse_args()
    runtime = ROOT / 'runtime'
    destination = options.output_dir.absolute()
    for parent in (runtime,) + tuple(runtime.parents):
        if parent.is_symlink():
            raise ValueError('Private output parent symlink refused')
    info = runtime.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o7077 or destination.parent != runtime
            or destination.exists() or destination.is_symlink()):
        raise ValueError('Choose a new caller-owned private directory directly under runtime')
    blob, downloaded = (private_file(options.input.absolute()), 0) if options.input else fetch()
    if len(blob) != MEMBER_BYTES or hashlib.sha256(blob).hexdigest() != MEMBER_SHA:
        raise ValueError('Pinned N71 kernel member hash refused')
    image, report = decode(blob)
    if len(image) != 42827776 or hashlib.sha256(image).hexdigest() != IMAGE_SHA:
        raise ValueError('Pinned decoded N71 image hash refused')
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    for name, data in ((MEMBER + '.im4p', blob), ('kernelcache.n71.macho', image)):
        with (destination / name).open('xb') as file:
            file.write(data)
    report.update({'url': URL, 'version': '15.8.8', 'buildid': '19H422', 'member': MEMBER,
                   'member_bytes': len(blob), 'member_sha256': MEMBER_SHA,
                   'decoded_bytes': len(image), 'decoded_sha256': IMAGE_SHA,
                   'range_download_bytes': downloaded, 'archive_crc_verified': not bool(options.input),
                   'cryptographic_signature_verified': False, 'executed': False, 'flashed': False})
    with (destination / 'kernel-source.json').open('x') as file:
        file.write(json.dumps(report, indent=2) + '\n')
    print('APPLE_N71_KERNEL_DATA_VERIFIED; private; no execution or device action')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit('APPLE_N71_KERNEL_REFUSED: ' + str(error)) from error
