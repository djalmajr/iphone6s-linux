"""Reproduce the pinned PMD candidate only in the dedicated unprivileged ARM64 VM."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import time

home = Path('/home/ubuntu')
root = home / 'n71-pmd-qualification-20261015'
archive = home / 'n71-pmd-qualification-inputs-20261015.tar'
work = home / 'kernel-n71-pmd-source-20261015'
out = home / 'kernel-n71-pmd-build-20261015'
legacy = home / 'kernel-n71-binding-source-20261005'
oldout = home / 'kernel-n71-binding-build-20261005'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--resume-source', action='store_true',
                    help='Reuse only the exact checkout and inputs after an interrupted source preparation')
options = parser.parse_args()
os.umask(0o077)
assert sys.platform == 'linux' and platform.machine() == 'aarch64' and os.geteuid() != 0
assert not out.exists()
if options.resume_source:
    assert root.is_dir() and root == root.resolve() and work.is_dir() and work == work.resolve()
else:
    assert not root.exists() and not work.exists()
assert hashlib.sha256(archive.read_bytes()).hexdigest() in {
    '918c2e5e61933df2d8aea15963b9c80739b985caac5232de94c5614e67461177',
    'b88de095c1a6d54db51c9926a6ee1609cbbc8404b7b2783d44fb9c9882568806'}
if not options.resume_source:
    root.mkdir(mode=0o700)
with tarfile.open(archive) as package:
    members = package.getmembers()
    assert len(members) == 16 and sum(m.size for m in members) < 512 * 1024
    for member in members:
        assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
        path = root / member.name
        data = package.extractfile(member).read()
        if options.resume_source:
            assert path == path.resolve() and path.is_file() and path.read_bytes() == data
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
sys.path.insert(0, str(root / 'scripts/build'))
import kernel_bundle

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

selected_before = kernel_bundle.inspect(legacy, profile=kernel_bundle.BINDING_BUNDLE)[1]
protected = {name: sha(oldout / name) for name in ('.config', 'arch/arm64/boot/Image', 'vmlinux.symvers')}
assert protected == {'.config': 'c4e421b28d9ff2f3c372fa0d13431742a69a922a47bde23d62e9036483ae36b8',
    'arch/arm64/boot/Image': 'f36963f9f2abcce8e93b8c912112deb4b2563b36c5cc781c46e1bc8e9b819eed',
    'vmlinux.symvers': '03b00b50ef19d434d3f4ea13b21f68f9e52bb163642421010edf76a0ddb6ce61'}
start = time.monotonic()
start_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
free = shutil.disk_usage(home).free
# Source and object footprints are measured; keep a 2 GiB margin beyond both estimates.
sizes = {name: int(subprocess.check_output(['du', '-sk', str(path)], text=True).split()[0]) * 1024
         for name, path in (('source', legacy), ('build', oldout))}
source_reserve = 0 if options.resume_source else sizes['source']
assert free > source_reserve + sizes['build'] + 2 * 1024**3, (free, sizes)
try:
    if not options.resume_source:
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(legacy), 'worktree',
                        'add', '--detach', str(work), kernel_bundle.BASE], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    # Full-blob and Git checks refuse an incomplete checkout or foreign edits before apply.
    selected = kernel_bundle.apply(work, profile=kernel_bundle.PMD_BUNDLE)
    (root / 'source-private.json').write_text(json.dumps(selected, indent=2) + '\n')
    print('PMD_FULL_SOURCE_APPLIED_ALL_BLOBS_VERIFIED', flush=True)
    for test in ('test_n71_dart_pmd', 'test_kernel_pmd_bundle'):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        if test == 'test_n71_dart_pmd':
            env['N71_DART_PMD_SOURCE'] = str(work)
        with (root / ('arm-' + test + '-private.log')).open('w') as stream:
            subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(root / 'tests'),
                            '-p', test + '.py', '-v'], env=env, stdout=stream,
                           stderr=subprocess.STDOUT, check=True, timeout=240)
        print('PMD_ARM_GATE_PASS ' + test, flush=True)
    out.mkdir(mode=0o700)
    config = (oldout / '.config').read_text()
    assert config.count('CONFIG_LOCALVERSION="-iphone6s-dart-serdev-power2"') == 1
    desired = config.replace('CONFIG_LOCALVERSION="-iphone6s-dart-serdev-power2"',
                             'CONFIG_LOCALVERSION="' + kernel_bundle.PMD_LOCALVERSION + '"')
    (out / '.config').write_text(desired)
    epoch = int(kernel_bundle.kernel_patchset.git(work, 'show', '-s', '--format=%ct', 'HEAD'))
    env = dict(os.environ, LOCALVERSION='', SOURCE_DATE_EPOCH=str(epoch),
               KBUILD_BUILD_TIMESTAMP=time.strftime('%a %b %e %T %Y', time.gmtime(epoch)),
               KBUILD_BUILD_USER='build', KBUILD_BUILD_HOST='iphone6s-kernel-source',
               KBUILD_BUILD_VERSION='1', LC_ALL='C')
    def make(log, targets, timeout, *, warnings=False):
        args = ['make', '-C', str(work), 'O=' + str(out), 'ARCH=arm64', '-j2', 'KCFLAGS=-Werror']
        if warnings:
            args.append('W=1')
        with (root / log).open('w') as stream:
            subprocess.run(args + targets, env=env, stdout=stream, stderr=subprocess.STDOUT,
                           check=True, timeout=timeout)
    make('config-private.log', ['olddefconfig'], 180)
    assert (out / '.config').read_text() == desired
    make('objects-private.log', ['drivers/iommu/apple-dart.o', 'drivers/iommu/io-pgtable-dart.o'],
         900, warnings=True)
    for name in ('drivers/iommu/apple-dart.o', 'drivers/iommu/io-pgtable-dart.o'):
        header = (out / name).read_bytes()[:20]
        assert header[:7] == b'\x7fELF\x02\x01\x01' and struct.unpack_from('<HH', header, 16) == (1, 183)
    print('PMD_REAL_ARM64_OBJECTS_W1_WERROR_PASS FULL_LINK_STARTED', flush=True)
    make('full-build-private.log', ['Image', 'apple/s8000-n71.dtb'], 5400)
    assert 'MODPOST vmlinux.symvers' in (root / 'full-build-private.log').read_text()
    release = (out / 'include/config/kernel.release').read_text().strip()
    assert release == '7.2.0' + kernel_bundle.PMD_LOCALVERSION
    image = out / 'arch/arm64/boot/Image'
    dtb = out / 'arch/arm64/boot/dts/apple/s8000-n71.dtb'
    header = image.read_bytes()[:64]
    assert header[56:60] == b'ARM\x64' and (struct.unpack_from('<Q', header, 24)[0] >> 1) & 3 == 2
    embedded = subprocess.check_output([str(work / 'scripts/extract-ikconfig'), str(image)], timeout=60)
    assert embedded == (out / '.config').read_bytes()
    assert sha(dtb) == 'b25b2b748d6f934d3b4ed51d9906ae86ae5e031756bfe9009073a4dea7537f58'
    compatible = subprocess.check_output(['fdtget', str(dtb), '/', 'compatible'], text=True).strip()
    symbols = subprocess.check_output(['nm', str(out / 'vmlinux')], text=True, timeout=120)
    assert len([line for line in symbols.splitlines() if line.split()[-2:] == ['T', 'serdev_device_set_stop_bits']]) == 1
    assert len([line for line in (out / 'vmlinux.symvers').read_text().splitlines()
                if line.split()[1:4] == ['serdev_device_set_stop_bits', 'vmlinux', 'EXPORT_SYMBOL_GPL']]) == 1
    artifacts = out / 'artifacts'
    artifacts.mkdir(mode=0o700)
    for name, source in (('Image', image), ('s8000-n71.dtb', dtb), ('config', out / '.config')):
        shutil.copyfile(source, artifacts / name)
    (artifacts / 'config-embedded').write_bytes(embedded)
    (artifacts / 'Image.gz').write_bytes(gzip.compress(image.read_bytes(), compresslevel=9, mtime=0))
    before_prepare = {name: sha(out / name) for name in protected}
    make('modules-prepare-private.log', ['modules_prepare'], 180)
    assert {name: sha(out / name) for name in protected} == before_prepare
    assert kernel_bundle.inspect(work, profile=kernel_bundle.PMD_BUNDLE)[1] == selected
    report = {'format': 1, 'status': 'compiled_verified', 'source': selected,
        'build': {'exit_code': 0, 'kernel_release': release, 'full_image_linked': True,
            'vmlinux_modpost_verified': True, 'serdev_stop_bits_export_verified': True,
            'page_size_kib': 16, 'dtb_compatible': compatible, 'config_only_localversion_changed': True,
            'embedded_config_exact_match': True, 'source_before_equals_after': True,
            'preflight_free_bytes': free, 'estimated_footprints': sizes, 'start_utc': start_utc,
            'elapsed_seconds': round(time.monotonic() - start), 'compiler_version': subprocess.check_output(['gcc', '-dumpfullversion'], text=True).strip(),
            'outputs': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in artifacts.iterdir()},
            'vmlinux_symvers_sha256': sha(out / 'vmlinux.symvers'), 'modules_prepare_executed': True},
        'legacy_output_preserved': protected, 'physical_boot_tested': False, 'installed': False,
        'default_profile_changed': False, 'wifi_verified': False, 'telemetry_verified': False,
        'linux_charging_validated': False}
    (artifacts / 'build-result-private.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PMD_FULL_IMAGE_VERIFIED ' + release + ' ' + sha(image), flush=True)
finally:
    assert kernel_bundle.inspect(legacy, profile=kernel_bundle.BINDING_BUNDLE)[1] == selected_before
    assert {name: sha(oldout / name) for name in protected} == protected
    print('PMD_LEGACY_SOURCE_CONFIG_IMAGE_EXPORTS_PRESERVED', flush=True)
