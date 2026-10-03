"""Apply/check one pinned patchset in a separate kernel worktree, without builds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = '958481f87fee0949ff6a9a4af77f7eb6dac8a149'
PATCHSET = 'n71-dart-tcr-v1'
TARGET = 'drivers/iommu/apple-dart.c'
PATCH = ROOT / 'phone/kernel/patches/0001-s5l8960x-dart-stream-tcr.patch'
PATCH_SHA = 'da321ed0e213a5ab4e3e27691f64d529b186474c556a00a2e7ee90957c785f74'
METHOD_SHA = 'ec7576ce878cc5b92c419eeab81f7a4141e816a8657fbfe33162e87d62a4a5ad'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *arguments):
    return subprocess.check_output(
        ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
         '-c', 'core.autocrlf=false', '-C', str(root), *arguments],
        stderr=subprocess.PIPE, timeout=30)


def plain_file(path):
    metadata = path.lstat()
    if (path.absolute() != path.resolve() or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid() or metadata.st_nlink != 1):
        raise ValueError('Owned regular file without links required.')
    return path.read_bytes()


def patch_method():
    raw = plain_file(PATCH)
    if digest(raw) != PATCH_SHA:
        raise ValueError('Pinned patch hash differs.')
    lines = raw.decode().splitlines()
    if (lines[:2] != ['--- a/' + TARGET, '+++ b/' + TARGET]
            or sum(line.startswith('@@ ') for line in lines) != 1):
        raise ValueError('Only the pinned single-file hunk is allowed.')
    old, new = [], []
    for line in lines[3:]:
        if line[:1] not in (' ', '-', '+'):
            raise ValueError('Unexpected patch framing.')
        if line[0] in (' ', '-'):
            old.append(line[1:])
        if line[0] in (' ', '+'):
            new.append(line[1:])
    before = ('\n'.join(old) + '\n').encode()
    after = ('\n'.join(new) + '\n').encode()
    if digest(before) != METHOD_SHA:
        raise ValueError('Pinned original method differs.')
    return before, after


def inspect(checkout, *, allow_original=False):
    root = Path(checkout).absolute()
    if root != root.resolve(strict=True) or root.stat().st_uid != os.geteuid():
        raise ValueError('Owned checkout without symlink traversal required.')
    # Linked worktrees have a .git file; never patch/build the preserved checkout.
    plain_file(root / '.git')
    if git(root, 'rev-parse', 'HEAD').decode().strip() != BASE:
        raise ValueError('Base commit differs.')
    # Explicit index flags can hide tracked mutations from status/diff.
    if any(line[:1].islower() or line[:1] == b'S'
           for line in git(root, 'ls-files', '-v', '-z').split(b'\0') if line):
        raise ValueError('Hidden tracked-file index flags refused.')
    before, after = patch_method()
    original = git(root, 'show', 'HEAD:' + TARGET)
    if original.count(before) != 1:
        raise ValueError('Pinned source method is not unique.')
    expected = original.replace(before, after, 1)
    actual = plain_file(root / TARGET)
    stage = 'original' if actual == original else 'patched' if actual == expected else None
    if stage is None or (stage == 'original' and not allow_original):
        raise ValueError('Full target blob does not match patchset.')
    entries = git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all').split(b'\0')
    required = [b' M ' + TARGET.encode()] if stage == 'patched' else []
    if [entry for entry in entries if entry] != required:
        raise ValueError('Other staged/tracked/untracked mutations refused.')
    report = {'format': 1, 'base_commit': BASE, 'patchset': PATCHSET,
              'patch_sha256': PATCH_SHA, 'target': TARGET,
              'original_blob_sha256': digest(original), 'patched_blob_sha256': digest(expected),
              'stage': stage, 'physical_boot_tested': False}
    return root, expected, report


def apply(checkout):
    root, expected, report = inspect(checkout, allow_original=True)
    if report['stage'] == 'patched':
        return report
    target = root / TARGET
    metadata = target.stat()
    descriptor, temporary = tempfile.mkstemp(prefix='.n71-patch-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as file:
            file.write(expected)
            os.fchmod(file.fileno(), stat.S_IMODE(metadata.st_mode))
        Path(temporary).replace(target)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return inspect(root)[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('apply', 'check'))
    parser.add_argument('checkout', type=Path)
    parser.add_argument('patchset', choices=(PATCHSET,))
    options = parser.parse_args()
    try:
        if options.command == 'apply':
            if sys.platform != 'linux' or os.geteuid() == 0:
                raise ValueError('Apply only as the dedicated Linux VM user.')
            report = apply(options.checkout)
        else:
            report = inspect(options.checkout)[2]
        print(json.dumps(report, sort_keys=True))
    except (ValueError, OSError, subprocess.SubprocessError):
        print('KERNEL_PATCHSET_REFUSED: checkout, scope or integrity mismatch.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
