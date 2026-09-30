#!/usr/bin/env python3
"""Compose a RAM boot payload from the preserved, device-specific inputs."""

import argparse
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('initramfs', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
blob = b''.join([
    (root / 'm1n1.bin').read_bytes(),
    b'chosen.bootargs=rdinit=/init console=ttySAC0,115200 loglevel=7\n',
    (root / 's8000-n71.dtb').read_bytes(),
    (root / 'vmlinuz-apple-16k').read_bytes(),
    args.initramfs.read_bytes(),
])
if args.output.exists() and args.output.read_bytes() != blob:
    raise SystemExit('O destino já existe com outro conteúdo; escolha outro nome.')
args.output.write_bytes(blob)
args.output.chmod(0o600)
print(hashlib.sha256(blob).hexdigest(), args.output.name, len(blob))
