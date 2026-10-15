#!/usr/bin/env python3
"""Prepare a private USB-budget candidate with an exact init-only delta."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import device_profile
import profile_image

BUDGET = (b'echo 500 > "$gadget/configs/c.1/MaxPower"\n'
          b'echo 0x80 > "$gadget/configs/c.1/bmAttributes"\n')
ANCHOR = b'mkdir -p "$gadget/functions/ncm.usb0"\n'
OLD_UDC = b'udc=$(ls /sys/class/udc | head -n 1)\n'
NEW_UDC = (b'udc=$(find /sys/class/udc -mindepth 1 -maxdepth 1 -print | head -n 1)\n'
           b'udc=${udc##*/}\n')


def patch(raw):
    before = profile_image.records(raw)
    init = before['init']
    if init.count(ANCHOR) != 1 or init.count(OLD_UDC) != 1 or b'MaxPower' in init or b'bmAttributes' in init:
        raise ValueError('Init differs from the known pre-budget source.')
    for name in ('init', 'init-server'):
        source = (ROOT / 'phone/init' / name).read_bytes()
        if source.count(BUDGET) != 1 or source.count(NEW_UDC) != 1:
            raise ValueError('Versioned init budget differs from the declared candidate delta.')
    new_init = init.replace(ANCHOR, BUDGET + ANCHOR, 1).replace(OLD_UDC, NEW_UDC, 1)
    result = []
    offset = 0
    while True:
        start = offset
        header = raw[offset:offset + 110]
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        name = raw[offset + 110:offset + 110 + namesize - 1].decode()
        content = (offset + 110 + namesize + 3) & ~3
        offset = (content + size + 3) & ~3
        if str(PurePosixPath(name)) == 'init':
            replacement = header[:54] + f'{len(new_init):08x}'.encode() + header[62:]
            result.append(replacement + raw[start + 110:content] + new_init + b'\0' * (-len(new_init) % 4))
        else:
            result.append(raw[start:offset])
        if name == 'TRAILER!!!':
            break
    candidate = b''.join(result)
    candidate += b'\0' * (-len(candidate) % 512)
    if profile_image.records(candidate) != dict(before, init=new_init):
        raise ValueError('Candidate altered entries beyond init.')
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    destination = options.output_dir.absolute()
    if destination.parent != ROOT / 'runtime' or destination.exists() or destination.is_symlink():
        raise ValueError('A new private directory directly under runtime is required.')
    device_profile.protected(destination.parent, directory=True)
    profile = device_profile.verify()
    old_compressed = profile['initramfs'].read_bytes()
    decoder = zlib.decompressobj(31)
    raw = decoder.decompress(old_compressed, profile_image.MAX_IMAGE_BYTES + 1)
    if (len(raw) > profile_image.MAX_IMAGE_BYTES or not decoder.eof
            or decoder.unconsumed_tail or decoder.unused_data):
        raise ValueError('Initramfs compression bounds refused.')
    compressed = gzip.compress(patch(raw), compresslevel=9, mtime=0)
    original = profile['payload'].read_bytes()
    if not original.endswith(old_compressed):
        raise ValueError('Profile payload layout refused.')
    payload = original[:-len(old_compressed)] + compressed
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    for name, data in (('initramfs.gz', compressed), ('payload.bin', payload),
                       ('client_ed25519', profile['client_key'].read_bytes()),
                       ('known_hosts', profile['known_hosts'].read_bytes())):
        (destination / name).write_bytes(data)
        (destination / name).chmod(0o600)
    def digest(data):
        return hashlib.sha256(data).hexdigest()
    selected = {'format': 1, 'payload': 'payload.bin', 'sha256': digest(payload),
                'initramfs': 'initramfs.gz', 'initramfs_sha256': digest(compressed),
                'client_key': 'client_ed25519', 'known_hosts': 'known_hosts',
                'host_key_alias': profile['host_key_alias']}
    pending = destination / 'deployment.pending.json'
    pending.write_text(json.dumps(selected, indent=2) + '\n')
    pending.chmod(0o600)
    previous = os.environ['IPHONE_LINUX_PROFILE']
    try:
        os.environ['IPHONE_LINUX_PROFILE'] = str(pending)
        device_profile.verify()
    finally:
        os.environ['IPHONE_LINUX_PROFILE'] = previous
    pending.rename(destination / 'deployment.json')
    report = {'changed_paths': ['init'], 'identities_preserved': True,
              'kernel_dtb_loader_prefix_unchanged': True,
              'payload_sha256': digest(payload), 'initramfs_sha256': digest(compressed),
              'usb_budget_mA': 500, 'physical_boot_tested': False,
              'charging_validation': 'unverified', 'default_profile_changed': False}
    (destination / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    (destination / 'provenance.json').chmod(0o600)
    print('USB_BUDGET_CANDIDATE_VERIFIED; no USB or reboot action')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, zlib.error, subprocess.SubprocessError) as error:
        raise SystemExit('USB_BUDGET_REFUSED: ' + str(error)) from error
