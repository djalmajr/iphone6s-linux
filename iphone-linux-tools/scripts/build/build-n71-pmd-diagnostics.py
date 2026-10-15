"""Build the sealed N71 diagnostics for the qualified PMD kernel; never install."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tarfile

HOME = Path('/home/ubuntu')
SOURCE = HOME / 'kernel-n71-pmd-source-20261015'
BUILD = HOME / 'kernel-n71-pmd-build-20261015'
TOOLS = HOME / 'n71-pmd-qualification-20261015/scripts/build'
RELEASE = '7.2.0-iphone6s-dart-serdev-pmd1'
INPUT_SHA = 'ced3f7ea5957a8baf641a3aff7db03b35c40b8eec45edbd9afc5e3832af71820'
NAMES = {'n71_pcie_diagnostic', 'n71_wlan_power_diagnostic', 'n71_hdq_gpio_observe',
         'n71_i2c_topology_observe', 'n71_pmgr_power_observe',
         'n71_i2c_power_diagnostic', 'n71_i2c_pin_cycle'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def plain(path):
    require(path == path.resolve(strict=True) and path.is_file()
            and path.stat().st_uid == os.geteuid() and path.stat().st_nlink == 1,
            'Owned regular file without aliases required')
    return path.read_bytes()


def sha(path):
    return hashlib.sha256(plain(path)).hexdigest()


def inputs(path):
    raw = plain(path)
    require(len(raw) == 389120 and hashlib.sha256(raw).hexdigest() == INPUT_SHA,
            'Sealed diagnostic input archive differs')
    result = {}
    with tarfile.open(path) as package:
        for member in package.getmembers():
            name = Path(member.name)
            require(member.isfile() and not name.is_absolute() and '..' not in name.parts
                    and name.parts[:2] == ('phone', 'kernel') and str(name) == member.name
                    and (name.suffix in ('.c', '.h') or name.name == 'Makefile')
                    and member.name not in result and 0 < member.size <= 128 * 1024,
                    'Diagnostic member path, kind or budget differs')
            result[member.name] = package.extractfile(member).read()
    require(len(result) == 62, 'Exact diagnostic source set required')
    return result


def qualified_build_record(record, selected):
    # JSON encodes the checker's tuple pairs as arrays; retain exact source pins.
    expected_source = dict(selected, files={name: list(pair) for name, pair in selected['files'].items()})
    data = record['build']
    require(record['status'] == 'compiled_verified' and record['source'] == expected_source
            and data['exit_code'] == 0 and data['kernel_release'] == RELEASE
            and data['full_image_linked'] is True and data['vmlinux_modpost_verified'] is True
            and data['serdev_stop_bits_export_verified'] is True
            and data['embedded_config_exact_match'] is True
            and data['source_before_equals_after'] is True
            and data['modules_prepare_executed'] is True and record['installed'] is False,
            'Full isolated PMD kernel qualification required')
    return data


def kernel():
    # Reuse the sealed patch checker; do not import from an arbitrary tools directory.
    raw = plain(TOOLS / 'kernel_bundle.py')
    require(hashlib.sha256(raw).hexdigest() == '0f18ca78f960800214dbb34c3b956e6a6679a455fac830e502fbcd969520e2f6',
            'Sealed bundle checker differs')
    raw = plain(TOOLS / 'kernel_patchset.py')
    require(hashlib.sha256(raw).hexdigest() == '51b79728f2ebd09ff1bcfd5cf5e8d144cdebc1177c2f1962459c784a9ecac817',
            'Sealed base checker differs')
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location('pmd_diagnostic_bundle', TOOLS / 'kernel_bundle.py')
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    selected = bundle.inspect(SOURCE, profile=bundle.PMD_BUNDLE)[1]
    record = json.loads(plain(BUILD / 'artifacts/build-result-private.json'))
    data = qualified_build_record(record, selected)
    expected = {'.config': data['outputs']['config']['sha256'],
                'arch/arm64/boot/Image': data['outputs']['Image']['sha256'],
                'vmlinux.symvers': data['vmlinux_symvers_sha256']}
    require({name: sha(BUILD / name) for name in expected} == expected,
            'PMD kernel output hashes differ')
    require((BUILD / 'include/config/kernel.release').read_text().strip() == RELEASE,
            'PMD kernel release differs')
    return bundle, selected, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Validate only; no extraction or compilation')
    options = parser.parse_args()
    require(sys.platform == 'linux' and platform.machine() == 'aarch64' and os.geteuid() != 0,
            'Dedicated unprivileged ARM64 Linux guest required')
    target = options.output_dir.absolute()
    require(target.parent == HOME and target.parent == target.parent.resolve()
            and target.parent.stat().st_uid == os.geteuid()
            and not target.exists() and not target.is_symlink(), 'New owned output directly under guest home required')
    data = inputs(options.inputs.absolute())
    bundle, selected, expected = kernel()
    require(shutil.disk_usage(HOME).free >= 1024**3, 'At least 1 GiB free for diagnostic build required')
    if options.check:
        print('N71_PMD_DIAGNOSTICS_CHECK_OK; no files created or hardware action', flush=True)
        return
    os.umask(0o077)
    target.mkdir(mode=0o700)
    source = target / 'sources'
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()}
    for name, raw in data.items():
        path = source / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    try:
        for relative in ('phone/kernel', 'phone/kernel/i2c-pins'):
            path = source / relative
            command = ['make', '-C', str(SOURCE), 'O=' + str(BUILD), 'ARCH=arm64', 'LOCALVERSION=',
                       '-j2', 'W=1', 'KCFLAGS=-Werror', 'M=' + str(path),
                       'KBUILD_EXTRA_SYMBOLS=' + str(BUILD / 'vmlinux.symvers'), 'modules']
            with (target / (path.name + '-build-private.log')).open('x') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        exports = {line.split()[1] for line in (BUILD / 'vmlinux.symvers').read_text().splitlines()}
        records = {}
        for module in source.rglob('*.ko'):
            raw = plain(module)
            magic = ('vermagic=' + RELEASE + ' SMP preempt mod_unload aarch64\0').encode()
            require(len(raw) >= 64 and raw[:7] == b'\x7fELF\x02\x01\x01'
                    and struct.unpack_from('<HH', raw, 16) == (1, 183) and raw.count(magic) == 1,
                    'AArch64 relocatable diagnostic with exact PMD ABI required')
            imports = {line.split()[-1] for line in subprocess.check_output(['nm', '-u', str(module)], text=True).splitlines()}
            require(imports and imports <= exports, 'Diagnostic contains unresolved kernel imports')
            name = subprocess.check_output(['modinfo', '-F', 'name', str(module)], text=True).strip()
            require(name in NAMES and name not in records, 'Unexpected or duplicate diagnostic module')
            records[name] = {'path': str(module.relative_to(target)), 'bytes': len(raw),
                             'sha256': hashlib.sha256(raw).hexdigest(), 'vermagic': magic[9:-1].decode(),
                             'imports': sorted(imports), 'elf64_aarch64_relocatable': True,
                             'parameters': subprocess.check_output(['modinfo', '-p', str(module)], text=True).splitlines()}
        require(set(records) == NAMES, 'Seven qualified diagnostics required')
        require(all(sha(source / name) == value for name, value in hashes.items()), 'Diagnostic inputs changed')
        (target / 'build-result-private.json').write_text(json.dumps({
            'format': 1, 'kernel_release': RELEASE, 'source_bundle': selected,
            'kernel_hashes': expected, 'inputs_sha256': hashes, 'modules': records,
            'w1_werror': True, 'modpost_passed': True, 'loaded': False, 'installed': False,
            'physical_boot_tested': False}, indent=2) + '\n')
        print('N71_PMD_DIAGNOSTICS_BUILT modules=7; not installed or loaded', flush=True)
    finally:
        require(bundle.inspect(SOURCE, profile=bundle.PMD_BUNDLE)[1] == selected,
                'PMD source changed during diagnostic build')
        require({name: sha(BUILD / name) for name in expected} == expected,
                'PMD Image/config/exports changed during diagnostic build')
        print('N71_PMD_KERNEL_PRESERVED', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('N71_PMD_DIAGNOSTICS_REFUSED: ' + str(error)) from error
