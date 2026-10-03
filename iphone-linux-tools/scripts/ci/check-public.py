#!/usr/bin/env python3
"""Reject project-private paths and private keys in the staged Git tree."""
import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

PRIVATE = {'backups', 'keys', 'logs', 'runtime', '__pycache__'}
ARTIFACTS = {'.apk', '.bin', '.dtb', '.gz', '.log', '.pyc', '.zst'}
KEY = re.compile(rb'(?m)^-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----\r?$|^PuTTY-User-Key-File-[23]:')


def check(repo):
    listing = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '--stage', '-z'])
    rejected = []
    for entry in listing.split(b'\0'):
        if not entry:
            continue
        metadata, encoded = entry.split(b'\t', 1)
        mode, digest, stage = metadata.decode('ascii').split()
        name = encoded.decode('utf-8', errors='surrogateescape')
        path = PurePosixPath(name)
        parts = {part.lower() for part in path.parts}
        private_path = bool(parts & PRIVATE) or path.suffix.lower() in ARTIFACTS
        private_path = private_path or path.parts[:2] in (
            ('iphone-linux-tools', 'bin'), ('iphone-linux-tools', 'artifacts'))
        if private_path or mode != '100644' and mode != '100755' or stage != '0':
            rejected.append((name, 'private path, link or unresolved index entry'))
            continue
        content = subprocess.check_output(['git', '-C', str(repo), 'cat-file', 'blob', digest])
        if KEY.search(content):
            rejected.append((name, 'private key material'))
    for name, reason in rejected:
        print(f'PUBLIC_TREE_REJECTED {name!r}: {reason}', file=sys.stderr)
    if rejected:
        return 1
    print('PUBLIC_TREE_OK')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    options = parser.parse_args()
    try:
        return check(options.repo)
    except (OSError, ValueError, subprocess.SubprocessError):
        print('PUBLIC_TREE_ERROR: unable to inspect the complete Git index', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
