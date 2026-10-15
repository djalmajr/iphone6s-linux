#!/usr/bin/env python3
"""Require assertion failures for updater boundary/rollback source mutations."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('answer-address-exact', 'scripts/host/dev.py', 'answers == [address]', 'any(item.startswith(address) for item in answers)'),
    ('duplicate', 'scripts/host/dev.py', 'if name in records:', 'if False:'),
    ('health-record', 'scripts/host/dev.py', "if records.get('iphone-usb.home.arpa') != device_profile.PHONE:", 'if False:'),
    ('source-link', 'scripts/host/dev.py', 'if ancestor.is_symlink():', 'if False:'),
    ('source-hardlink', 'scripts/host/dev.py', 'info.st_nlink != 1', 'False'),
    ('source-size', 'scripts/host/dev.py', 'info.st_size > MAX_BYTES', 'False'),
    ('bundle-manager', 'scripts/host/dev.py', "if not manager.startswith(b'#!/bin/sh\\n') or len(manager) > MAX_BYTES:", 'if False:'),
]
VM_MUTATIONS = [
    ('manager-digest', 'phone/dev/update-dns.sh', 'verify "$stage/manager" "$manager_hash"', ':'),
    ('old-digest', 'phone/dev/update-dns.sh', 'verify "$base/manage-dns.sh" "$old_manager_hash"\nverify "$base/hosts"', ':\nverify "$base/hosts"'),
    ('rollback-hosts', 'phone/dev/update-dns.sh', 'mv "$base/.dev-hosts-$suffix" "$base/hosts"\n        if', 'rm "$base/.dev-hosts-$suffix"\n        if'),
    ('target-link', 'phone/dev/update-dns.sh', '[ ! -L "$1" ]', ':'),
    ('temporary-link', 'phone/dev/update-dns.sh', '[ ! -e "$temporary" ] && [ ! -L "$temporary" ] || exit 2', ':'),
]


def suite(root):
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                             '-s', str(root / 'tests'), '-p', 'test_dev.py', '-v'],
                            capture_output=True, text=True, timeout=80)
    return result.returncode, result.stdout + result.stderr


def main():
    code, output = suite(ROOT)
    if code:
        raise RuntimeError('Baseline failed:\n' + output)
    mutations = MUTATIONS + (VM_MUTATIONS if os.environ.get('IPHONE_DEV_VM_TESTS') == '1' else [])
    for name, file, before, after in mutations:
        with tempfile.TemporaryDirectory(prefix='iphone-dev-mutant-') as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'scripts/host', root / 'scripts/host', ignore=shutil.ignore_patterns('__pycache__'))
            (root / 'phone/dev').mkdir(parents=True)
            shutil.copyfile(ROOT / 'phone/dev/update-dns.sh', root / 'phone/dev/update-dns.sh')
            (root / 'tests').mkdir()
            shutil.copyfile(ROOT / 'tests/test_dev.py', root / 'tests/test_dev.py')
            target = root / file
            source = target.read_text()
            if source.count(before) != 1:
                raise ValueError('Mutation anchor ambiguous: ' + name)
            changed = source.replace(before, after, 1)
            if name == 'source-size':
                # Remove both size guards; the post-read guard intentionally backs up stat.
                changed = changed.replace('data = path.read_bytes()\n    if len(data) > MAX_BYTES:',
                                          'data = path.read_bytes()\n    if False:', 1)
            target.write_text(changed)
            code, output = suite(root)
            if not code or '\nFAIL:' not in output or '\nERROR:' in output:
                raise RuntimeError('No assertion-only kill: ' + name + '\n' + output)
            print('DEV_MUTATION_KILLED_BY_ASSERTION ' + name, flush=True)
    print('DEV_MUTATION_GATE_OK ' + str(len(mutations)), flush=True)


if __name__ == '__main__':
    main()
