"""Apply/check a selected pinned N71 bundle in an isolated source worktree."""
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
POWER_BUNDLE = 'n71-dart-serdev-power-v1'
POWER_LOCALVERSION = '-iphone6s-dart-serdev-power1'
POWER_PATCHES = {
    '0003-apple-gpio-write-errors.patch': '739b9fc44bec4bad00bea367af70decef5fb56248a636d822d51396343088094',
    '0004-apple-pmgr-errors.patch': 'd8202c48516faec2bf4506af486ca2fd1b256360a41aad2d4df584c140d7e135',
    '0005-apple-pmgr-probe-errors.patch': 'b005ddf799b9cdea7149b38d850936c30c16342af47d11a61595157d14e24b2f',
    '0006-apple-pmgr-provider-cleanup.patch': 'e0159ec77cec26beafb1332526f9ba7f287f53c05f70a6dcd2376abca6dc445b',
}
POWER_FILES = {
    'drivers/pinctrl/pinctrl-apple-gpio.c': (
        '9e387713c4443d0af50fde108ae46d35e2f57adc2738c005b3de5bf8d4c7533c',
        '81767e760802ce9fc1a9d9383268ccefd930aff821e59f414d2f8e99193e603a'),
    'drivers/pmdomain/apple/pmgr-pwrstate.c': (
        '4b0adc3013e2fabe9ca1cb8228f8f6b7934af4b667f7f0f893b675102d8710df',
        'ec4841316d8c3a8dad7ac44d93edac0209c581b4e4c0d2fb9dcfb89853754414'),
}
BINDING_BUNDLE = 'n71-dart-serdev-power-v2'
BINDING_LOCALVERSION = '-iphone6s-dart-serdev-power2'
BINDING_PATCHES = {
    '0007-apple-pmgr-no-manual-bind.patch': '3f5a3e4c97a6cf898eaf90d53fcdc45a9796707c4123a14b1d0e043b58934aaa',
}
BINDING_FILES = {
    'drivers/pmdomain/apple/pmgr-pwrstate.c': (
        '4b0adc3013e2fabe9ca1cb8228f8f6b7934af4b667f7f0f893b675102d8710df',
        '0d84693ae4f5a24df9f8c9499ecd0f8f6725566223428dfe7af686cf7a21f5b2'),
}


def bundle_spec(profile):
    if profile == BUNDLE:
        return LOCALVERSION, FILES, PATCHES
    if profile == POWER_BUNDLE:
        return POWER_LOCALVERSION, {**FILES, **POWER_FILES}, {**PATCHES, **POWER_PATCHES}
    if profile == BINDING_BUNDLE:
        return BINDING_LOCALVERSION, {**FILES, **POWER_FILES, **BINDING_FILES}, {**PATCHES, **POWER_PATCHES, **BINDING_PATCHES}
    raise ValueError('Unknown bundle profile.')


def patch_bytes(*, profile=BUNDLE):
    _, _, patches = bundle_spec(profile)
    parts = []
    for name, expected in patches.items():
        raw = kernel_patchset.plain_file(ROOT / 'phone/kernel/patches' / name)
        if kernel_patchset.digest(raw) != expected:
            raise ValueError('Pinned bundle patch differs.')
        # Discard mail metadata; preserve the verified unified diff exactly.
        marker = raw.find(b'--- a/')
        if marker < 0:
            raise ValueError('Unified diff absent.')
        parts.append(raw[marker:])
    return b'\n'.join(parts)


def inspect(checkout, *, allow_original=False, profile=BUNDLE):
    version, files, patches = bundle_spec(profile)
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
    patch_bytes(profile=profile)
    stages = set()
    for name, (before, after) in files.items():
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
    required = [b' M ' + name.encode() for name in files] if stage == 'patched' else []
    if sorted(entries) != sorted(required):
        raise ValueError('External mutations refused.')
    return root, {'format': 1, 'base_commit': BASE, 'bundle': profile,
                  'required_localversion': version, 'stage': stage,
                  'patches': patches, 'files': files,
                  'physical_boot_tested': False, 'kernel_image_linked': False}


def apply(checkout, *, profile=BUNDLE):
    root, report = inspect(checkout, allow_original=True, profile=profile)
    if report['stage'] == 'patched':
        return report
    command = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
               '-c', 'core.autocrlf=false', '-C', str(root), 'apply']
    raw = patch_bytes(profile=profile)
    subprocess.run(command + ['--check', '-'], input=raw, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    subprocess.run(command + ['-'], input=raw, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return inspect(root, profile=profile)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('apply', 'check'))
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--profile', choices=(BUNDLE, POWER_BUNDLE, BINDING_BUNDLE), default=BUNDLE)
    options = parser.parse_args()
    try:
        if options.command == 'apply':
            if sys.platform != 'linux' or os.geteuid() == 0:
                raise ValueError('Apply only as the dedicated Linux VM user.')
            report = apply(options.checkout, profile=options.profile)
        else:
            report = inspect(options.checkout, profile=options.profile)[1]
        print(json.dumps(report, sort_keys=True))
    except (ValueError, OSError, subprocess.SubprocessError):
        print('KERNEL_BUNDLE_REFUSED: scope or integrity mismatch.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
