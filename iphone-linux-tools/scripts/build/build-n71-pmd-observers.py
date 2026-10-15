"""Build sealed DMA/I2C observers against the preserved PMD kernel, never install."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import struct
import subprocess
import sys
import tarfile

HOME = Path('/home/ubuntu')
SOURCE_HEAD = '6c682b701f2642ac795fca056354b6c08a238c83'
TAR_BYTES = 399360
TAR_SHA = 'c4c0f18a46a06597379866d40281fa0027a37997c61e65ac01818d4295ec5cba'
INPUTS_PIN = '3000b4ac5144991a2a51864375db9c3b0480541221eb3f8a30b376f041cdb606'
BASE_SHA = '5a8ff690692872f64dca8de1db5a0c5c7bca45dccba3291bc8763cb0431298dc'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def plain(path):
    require(path == path.resolve(strict=True) and path.is_file()
            and path.stat().st_uid == os.geteuid() and path.stat().st_nlink == 1,
            'Owned regular file without aliases required')
    return path.read_bytes()


def inputs(path):
    raw = plain(path)
    require(len(raw) == TAR_BYTES and hashlib.sha256(raw).hexdigest() == TAR_SHA,
            'Sealed observer archive differs')
    data = {}
    with tarfile.open(path) as package:
        for member in package:
            name = PurePosixPath(member.name)
            require(member.isfile() and not name.is_absolute() and '..' not in name.parts
                    and name.parts[:2] == ('phone', 'kernel') and name.as_posix() == member.name
                    and (name.suffix in ('.c', '.h') or name.name == 'Makefile')
                    and member.name not in data and 0 < member.size <= 128 * 1024,
                    'Observer archive member refused')
            stream = package.extractfile(member)
            with stream:
                data[member.name] = stream.read()
    records = {name: {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
               for name, value in data.items()}
    require(len(data) == 64 and hashlib.sha256(json.dumps(records, sort_keys=True,
            separators=(',', ':')).encode()).hexdigest() == INPUTS_PIN, 'Observer source manifest differs')
    return data


def base_builder():
    path = Path(__file__).resolve().with_name('build-n71-pmd-diagnostics.py')
    require(hashlib.sha256(plain(path)).hexdigest() == BASE_SHA, 'Qualified PMD build checker differs')
    spec = importlib.util.spec_from_file_location('observer_pmd_base', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    options = parser.parse_args()
    require(sys.platform == 'linux' and platform.machine() == 'aarch64' and os.geteuid() != 0,
            'Dedicated unprivileged ARM64 guest required')
    target = options.output_dir.absolute()
    require(target.parent == HOME and HOME.resolve() == HOME and HOME.stat().st_uid == os.geteuid()
            and target.name.startswith('n71-pmd-observers-') and not target.exists()
            and not target.is_symlink(), 'New observer output directly under guest home required')
    data = inputs(options.inputs.absolute())
    base = base_builder(); bundle, selected, expected = base.kernel()
    require(shutil.disk_usage(HOME).free >= 1024**3, 'At least 1 GiB free required')
    if options.check:
        print('N71_OBSERVERS_CHECK_OK; no output or hardware action', flush=True)
        return
    os.umask(0o077); target.mkdir(mode=0o700)
    source = target / 'sources'
    for name, raw in data.items():
        path = source / name; path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    try:
        for relative in ('phone/kernel', 'phone/kernel/i2c-pins'):
            folder = source / relative
            command = ['make', '-C', str(base.SOURCE), 'O=' + str(base.BUILD), 'ARCH=arm64',
                       'LOCALVERSION=', '-j1', 'W=1', 'KCFLAGS=-Werror', 'M=' + str(folder),
                       'KBUILD_EXTRA_SYMBOLS=' + str(base.BUILD / 'vmlinux.symvers'), 'modules']
            with (target / (folder.name + '-build-private.log')).open('x') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        exports = {line.split()[1] for line in (base.BUILD / 'vmlinux.symvers').read_text().splitlines()}
        modules = {}
        for path in source.rglob('*.ko'):
            raw = plain(path); magic = ('vermagic=' + base.RELEASE + ' SMP preempt mod_unload aarch64\0').encode()
            require(raw[:7] == b'\x7fELF\x02\x01\x01' and struct.unpack_from('<HH', raw, 16) == (1, 183)
                    and raw.count(magic) == 1, 'AArch64 ELF and exact PMD ABI required')
            imports = {line.split()[-1] for line in subprocess.check_output(['nm', '-u', str(path)], text=True).splitlines()}
            require(imports and imports <= exports, 'Unresolved kernel imports')
            name = subprocess.check_output(['modinfo', '-F', 'name', str(path)], text=True).strip()
            require(name in base.NAMES and name not in modules, 'Unexpected or duplicate module')
            parameters = subprocess.check_output(['modinfo', '-p', str(path)], text=True).splitlines()
            if name == 'n71_pcie_diagnostic':
                require({'iommu_iova_to_phys', 'iommu_get_domain_for_dev'} <= imports
                        and all(any(row.startswith(key + ':') for row in parameters)
                                for key in ('dma_observe', 'dma_iova', 'dma_observation')),
                        'DMA observer imports and parameters missing')
            if name == 'n71_i2c_power_diagnostic':
                require(b'N71_I2C_RESET_TRACE attempts=' in raw, 'I2C reset report missing')
            modules[name] = {'path': str(path.relative_to(target)), 'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(), 'vermagic': magic[9:-1].decode(),
                'imports': sorted(imports), 'parameters': parameters, 'elf64_aarch64_relocatable': True}
        require(set(modules) == base.NAMES, 'Seven diagnostics required')
        require(all(plain(source / name) == raw for name, raw in data.items()), 'Observer inputs changed')
        record = {'format': 1, 'diagnostic_variant': 'pmd-observers-v1', 'source_head': SOURCE_HEAD,
            'inputs_manifest_sha256': INPUTS_PIN, 'inputs_sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()},
            'source_bundle': selected, 'kernel_hashes': expected, 'kernel_release': base.RELEASE,
            'modules': modules, 'w1_werror': True, 'jobs': 1, 'modpost_passed': True,
            'loaded': False, 'installed': False, 'physical_boot_tested': False}
        (target / 'build-result-private.json').write_text(json.dumps(record, indent=2) + '\n')
        print('N71_OBSERVERS_BUILT modules=7; not installed or loaded', flush=True)
    finally:
        require(bundle.inspect(base.SOURCE, profile=bundle.PMD_BUNDLE)[1] == selected, 'PMD source changed')
        require({name: base.sha(base.BUILD / name) for name in expected} == expected, 'PMD build changed')
        print('N71_OBSERVER_KERNEL_PRESERVED', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('N71_OBSERVERS_REFUSED: ' + str(error)) from error
