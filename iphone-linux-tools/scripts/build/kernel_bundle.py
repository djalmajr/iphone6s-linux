"""Apply/check the pinned DART+serdev bundle in an isolated source worktree."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import kernel_patchset

ROOT = Path(__file__).resolve().parents[2]
BASE = kernel_patchset.BASE
BUNDLE = 'n71-dart-serdev-v1'
LOCALVERSION = '-iphone6s-dart-serdev1'
PATCHES = {
    '0001-s5l8960x-dart-stream-tcr.patch': kernel_patchset.PATCH_SHA,
    '0002-serdev-stop-bits.patch': 'f987f64912a410d588ac0d1d9a47c7cc275a0dc234fbe27549011255e98e0d11',
}
FILES = {
    'drivers/iommu/apple-dart.c': (
        'f19d3c2a7ada7451956f2a87fea09c174584bfd68ba7a1f6e8793db653047f85',
        '059546b68b266a5fb30c230a4d805572b2f601076cf04f06dfb41250312c67cc'),
    'include/linux/serdev.h': (
        '54a3e78e8ca0e29311070c87b6811e486a15453b1b938f221655a1ed3278e2c3',
        'fbf86a763c535f07646beb49c14ac3582e7ba2f4d9a7bd0b680aecf32d11dd0c'),
    'drivers/tty/serdev/core.c': (
        'b3130abc6078d5353c38a0ef029c7afee4989cbccbb784e785dc7ebefa882e6c',
        'fefe1fdbc17a0c7239df964ba0eee7fd8ec95f2e7ee157be451630c167e9d340'),
    'drivers/tty/serdev/serdev-ttyport.c': (
        'e4c9d73545e27fe8c995ef7a0d8ae23381fede11909f4b250c34a8004b1a437d',
        '4643ddeac9973176346c04dd7054027153d49291960f1d89cd8e7280e45e7068'),
}


def patch_bytes():
    parts = []
    for name, expected in PATCHES.items():
        raw = kernel_patchset.plain_file(ROOT / 'phone/kernel/patches' / name)
        if kernel_patchset.digest(raw) != expected:
            raise ValueError('Pinned bundle patch differs.')
        # Discard mail metadata; preserve the verified unified diff exactly.
        marker = raw.find(b'--- a/')
        if marker < 0:
            raise ValueError('Unified diff absent.')
        parts.append(raw[marker:])
    return b'\n'.join(parts)


def inspect(checkout, *, allow_original=False):
    root = Path(checkout).absolute()
    if root != root.resolve(strict=True) or root.stat().st_uid != os.geteuid():
        raise ValueError('Owned checkout without aliases required.')
    kernel_patchset.plain_file(root / '.git')
    git = kernel_patchset.git
    if git(root, 'rev-parse', 'HEAD').decode().strip() != BASE:
        raise ValueError('Bundle base differs.')
    if any(line[:1].islower() or line[:1] == b'S'
           for line in git(root, 'ls-files', '-v', '-z').split(b'\0') if line):
        raise ValueError('Hidden tracked-file flags refused.')
    patch_bytes()
    stages = set()
    for name, (before, after) in FILES.items():
        if kernel_patchset.digest(git(root, 'show', 'HEAD:' + name)) != before:
            raise ValueError('Original full blob differs.')
        actual = kernel_patchset.digest(kernel_patchset.plain_file(root / name))
        if actual == before:
            stages.add('original')
        elif actual == after:
            stages.add('patched')
        else:
            raise ValueError('Candidate full blob differs.')
    if len(stages) != 1:
        raise ValueError('Partial bundle refused.')
    stage = stages.pop()
    if stage == 'original' and not allow_original:
        raise ValueError('Unapplied bundle refused.')
    entries = [entry for entry in git(root, 'status', '--porcelain=v1', '-z',
                                      '--untracked-files=all').split(b'\0') if entry]
    required = [b' M ' + name.encode() for name in FILES] if stage == 'patched' else []
    if sorted(entries) != sorted(required):
        raise ValueError('External mutations refused.')
    return root, {'format': 1, 'base_commit': BASE, 'bundle': BUNDLE,
                  'required_localversion': LOCALVERSION, 'stage': stage,
                  'patches': PATCHES, 'files': FILES,
                  'physical_boot_tested': False, 'kernel_image_linked': False}


def apply(checkout):
    root, report = inspect(checkout, allow_original=True)
    if report['stage'] == 'patched':
        return report
    command = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
               '-c', 'core.autocrlf=false', '-C', str(root), 'apply']
    raw = patch_bytes()
    subprocess.run(command + ['--check', '-'], input=raw, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    subprocess.run(command + ['-'], input=raw, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return inspect(root)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('apply', 'check'))
    parser.add_argument('checkout', type=Path)
    options = parser.parse_args()
    try:
        if options.command == 'apply':
            if sys.platform != 'linux' or os.geteuid() == 0:
                raise ValueError('Apply only as the dedicated Linux VM user.')
            report = apply(options.checkout)
        else:
            report = inspect(options.checkout)[1]
        print(json.dumps(report, sort_keys=True))
    except (ValueError, OSError, subprocess.SubprocessError):
        print('KERNEL_BUNDLE_REFUSED: scope or integrity mismatch.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
