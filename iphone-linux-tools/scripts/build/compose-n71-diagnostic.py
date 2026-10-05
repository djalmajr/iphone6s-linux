#!/usr/bin/env python3
"""Compose a private diagnostic profile, preserving kernel, userspace and keys."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import device_profile
import profile_image


def module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(result)
    return result


KERNEL = module('n71_kernel_inputs', ROOT / 'scripts/build/integrate-source-kernel.py')
DIAGNOSTIC = module('n71_private_diagnostic', ROOT / 'scripts/build/prepare-n71-pcie-diagnostic.py')
TOPOLOGY = DIAGNOSTIC.TOPOLOGY


def validate_dtb(baseline, candidate):
    before, after = TOPOLOGY.parse_dtb(baseline), TOPOLOGY.parse_dtb(candidate)
    if TOPOLOGY.PCIE not in after:
        raise ValueError('Diagnostic PCIe node missing')
    pcie = dict(after[TOPOLOGY.PCIE])
    if pcie.get('compatible') != b'apple,n71-pcie-diagnostic\0' or pcie.get('status') != b'okay\0':
        raise ValueError('Explicit diagnostic binding required')
    gpio = after.get(DIAGNOSTIC.GPIO, {})
    if (gpio.get('reg') != TOPOLOGY.registers([[0x20f100000, 0x100000]]) or
            len(gpio.get('phandle', b'')) != 4 or
            pcie.pop('perst-gpios', None) != gpio['phandle'] + TOPOLOGY.cells(161, 1)):
        raise ValueError('N71 PERST provider or polarity differs')
    for name, aperture in (('phy', 0x4000), ('common', 0x8000), ('port1', 0x4000), ('config1', 0x1000)):
        raw = pcie.pop('n71,' + name + '-tunables', b'')
        if not raw or len(raw) % 12 or len(raw) > 512 * 12:
            raise ValueError('Diagnostic table framing refused')
        for offset, mask, value in struct.iter_unpack('>III', raw):
            if offset % 4 or offset > aperture - 4 or value & ~mask:
                raise ValueError('Diagnostic table bounds/mask refused')
    pcie.update({'compatible': b'apple,s8000-pcie\0', 'status': b'disabled\0'})
    restored = dict(after)
    restored[TOPOLOGY.PCIE] = pcie
    TOPOLOGY.verify_delta(before, restored)


def bootargs(pcie_aspm_off):
    if type(pcie_aspm_off) is not bool:
        raise ValueError('ASPM selection must be an explicit boolean')
    return KERNEL.BOOTARGS.rstrip(b'\n') + b' pcie_aspm=off\n' if pcie_aspm_off else KERNEL.BOOTARGS


def compose(original, loader, baseline_dtb, diagnostic_dtb, kernel, initramfs, *, pcie_aspm_off=False):
    validate_dtb(baseline_dtb, diagnostic_dtb)
    expected = loader + KERNEL.BOOTARGS + baseline_dtb + kernel + initramfs
    if original != expected:
        raise ValueError('Source payload is not the exact preserved layout')
    return loader + bootargs(pcie_aspm_off) + diagnostic_dtb + kernel + initramfs


def validate_module(raw, *, kernel_release='7.2.0-iphone6s-source'):
    known = ('7.2.0-iphone6s-source', '7.2.0' + KERNEL.kernel_bundle.LOCALVERSION,
             '7.2.0' + KERNEL.kernel_bundle.POWER_LOCALVERSION,
             '7.2.0' + KERNEL.kernel_bundle.BINDING_LOCALVERSION)
    if kernel_release not in known:
        raise ValueError('Only a recorded baseline or explicit bundle ABI is accepted')
    vermagic = ('vermagic=' + kernel_release + ' SMP preempt mod_unload aarch64\0').encode()
    if (not 64 <= len(raw) <= 4 * 1024 * 1024 or raw[:7] != b'\x7fELF\x02\x01\x01' or
            struct.unpack_from('<HH', raw, 16) != (1, 183) or raw.count(vermagic) != 1):
        raise ValueError('Relocatable AArch64 module with exact preserved ABI required')


def private_write(path, raw):
    with path.open('xb') as file:
        file.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-profile', type=Path, required=True)
    parser.add_argument('--kernel-dir', type=Path, required=True)
    parser.add_argument('--kernel-patchset', choices=(KERNEL.kernel_patchset.PATCHSET, KERNEL.kernel_bundle.BUNDLE,
                                                     KERNEL.kernel_bundle.POWER_BUNDLE, KERNEL.kernel_bundle.BINDING_BUNDLE))
    parser.add_argument('--diagnostic-dir', type=Path, required=True)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--module-sha256', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--pcie-aspm-off', action='store_true', help='Disable ASPM only in this diagnostic RAM boot candidate')
    options = parser.parse_args()
    previous = os.environ.get('IPHONE_LINUX_PROFILE')
    try:
        os.environ['IPHONE_LINUX_PROFILE'] = str(options.source_profile.absolute())
        source = device_profile.verify()
    finally:
        if previous is None:
            os.environ.pop('IPHONE_LINUX_PROFILE', None)
        else:
            os.environ['IPHONE_LINUX_PROFILE'] = previous
    kernel, record = KERNEL.kernel_inputs(options.kernel_dir.absolute(), options.kernel_patchset)
    folder = DIAGNOSTIC.TUNABLES.private_path(options.diagnostic_dir, directory=True)
    path = DIAGNOSTIC.TUNABLES.private_path(folder / 'diagnostic-private.dtb')
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Diagnostic DTB size refused')
    dtb = path.read_bytes()
    metadata = DIAGNOSTIC.TUNABLES.private_path(folder / 'provenance-private.json')
    if metadata.stat().st_size > 8192:
        raise ValueError('Diagnostic manifest size refused')
    if json.loads(metadata.read_text()).get('sha256') != KERNEL.digest(dtb):
        raise ValueError('Diagnostic manifest hash differs')
    path = DIAGNOSTIC.TUNABLES.private_path(options.module)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Module size refused')
    driver = path.read_bytes()
    if hashlib.sha256(driver).hexdigest() != options.module_sha256:
        raise ValueError('Module differs from recorded build hash')
    validate_module(driver, kernel_release=record['build']['kernel_release'])
    loader = (ROOT / 'artifacts/m1n1.bin').read_bytes()
    expected = json.loads((ROOT / 'docs/evidence/m1n1-rebuild.json').read_text())['shallow_clone']
    if not expected['matches_original'] or KERNEL.digest(loader) != expected['sha256']:
        raise ValueError('Preserved loader hash differs')
    initramfs = source['initramfs'].read_bytes()
    if source['payload'].stat().st_size > profile_image.MAX_IMAGE_BYTES:
        raise ValueError('Payload size refused')
    payload = compose(source['payload'].read_bytes(), loader, kernel['s8000-n71.dtb'],
                      dtb, kernel['Image.gz'], initramfs, pcie_aspm_off=options.pcie_aspm_off)
    destination = options.output_dir.absolute()
    runtime = DIAGNOSTIC.TUNABLES.private_path(ROOT / 'runtime', directory=True)
    if destination.parent != runtime or destination.exists() or destination.is_symlink():
        raise ValueError('New private output directly under runtime required')
    os.umask(0o077)
    destination.mkdir(mode=0o700)
    for name, data in (('payload.bin', payload), ('initramfs.gz', initramfs),
                       ('client_ed25519', source['client_key'].read_bytes()),
                       ('known_hosts', source['known_hosts'].read_bytes()),
                       ('n71-pcie-diagnostic.ko', driver)):
        private_write(destination / name, data)
    profile = {'format': 1, 'payload': 'payload.bin', 'sha256': KERNEL.digest(payload),
               'initramfs': 'initramfs.gz', 'initramfs_sha256': KERNEL.digest(initramfs),
               'client_key': 'client_ed25519', 'known_hosts': 'known_hosts',
               'host_key_alias': source['host_key_alias']}
    pending = destination / 'deployment.pending.json'
    private_write(pending, (json.dumps(profile, indent=2) + '\n').encode())
    try:
        os.environ['IPHONE_LINUX_PROFILE'] = str(pending)
        device_profile.verify()
    finally:
        if previous is None:
            os.environ.pop('IPHONE_LINUX_PROFILE', None)
        else:
            os.environ['IPHONE_LINUX_PROFILE'] = previous
    pending.rename(destination / 'deployment.json')
    private_write(destination / 'provenance.json', (json.dumps({
        'format': 1, 'kernel_source_commit': record['source']['commit'],
        'kernel_patchset': options.kernel_patchset,
        'kernel_release': record['build']['kernel_release'],
        'payload_sha256': KERNEL.digest(payload), 'dtb_sha256': KERNEL.digest(dtb),
        'module_sha256': options.module_sha256, 'kernel_initramfs_identities_preserved': True,
        'pcie_aspm_off': options.pcie_aspm_off, 'bootargs_sha256': KERNEL.digest(bootargs(options.pcie_aspm_off)),
        'module_automatic_load': False, 'requires_explicit_run': True,
        'requires_explicit_enumerate': True, 'physical_boot_tested': False,
        'default_profile_changed': False, 'wifi_verified': False}, indent=2) + '\n').encode())
    print('N71_DIAGNOSTIC_PROFILE_VERIFIED; no USB action; not boot qualified')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, struct.error) as error:
        raise SystemExit('N71_COMPOSE_REFUSED: ' + str(error)) from error
