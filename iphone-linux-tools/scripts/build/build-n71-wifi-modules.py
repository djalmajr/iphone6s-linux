#!/usr/bin/env python3
"""Build an isolated PCIe driver set against the preserved N71 bundle; never install."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import kernel_bundle

RELEASE = '7.2.0-iphone6s-dart-serdev1'
BROADCOM = 'drivers/net/wireless/broadcom/brcm80211'
MACRO_FILES = {BROADCOM + '/brcmfmac/' + name for name in ('Makefile', 'bus.h', 'msgbuf.h')}
KERNEL_FILES = {
    '.config': '178fd8a566bf58501fe82730b0a007cc4b5cf1be2cdf773169990fa9db69a6f8',
    'arch/arm64/boot/Image': 'dd03169d097dc47f3fc727d7904039abb39434b3b4b2ca9ff4457bd2f346013d',
    'vmlinux.symvers': '03b00b50ef19d434d3f4ea13b21f68f9e52bb163642421010edf76a0ddb6ce61',
}
BINDING_RELEASE = '7.2.0-iphone6s-dart-serdev-power2'
BINDING_KERNEL_FILES = {
    '.config': 'c4e421b28d9ff2f3c372fa0d13431742a69a922a47bde23d62e9036483ae36b8',
    'arch/arm64/boot/Image': 'f36963f9f2abcce8e93b8c912112deb4b2563b36c5cc781c46e1bc8e9b819eed',
    'vmlinux.symvers': '03b00b50ef19d434d3f4ea13b21f68f9e52bb163642421010edf76a0ddb6ce61',
}
REQUIRED = {'CONFIG_BRCMFMAC': 'm', 'CONFIG_BRCMFMAC_PCIE': 'n',
            'CONFIG_BRCMFMAC_PROTO_MSGBUF': 'n', 'CONFIG_BRCMFMAC_SDIO': 'y',
            'CONFIG_BRCMUTIL': 'm', 'CONFIG_CFG80211': 'm', 'CONFIG_FW_LOADER': 'y',
            'CONFIG_MODVERSIONS': 'n', 'CONFIG_PCI': 'y', 'CONFIG_RFKILL': 'm'}
ALIAS = 'pci:v000014E4d000043A3sv*sd*bc02sc80i*'
FLAGS = b'\nsubdir-ccflags-y += -DCONFIG_BRCMFMAC_PCIE=1 -DCONFIG_BRCMFMAC_PROTO_MSGBUF=1\n'
IRQ_TARGET = BROADCOM + '/brcmfmac/pcie.c'
IRQ_PATCH = kernel_bundle.ROOT / 'phone/kernel/patches/0008-brcmfmac-msi-error.patch'
IRQ_PATCH_SHA = '6f5702cd509bf076c1e69a2acfef49ab4938bc7edcd9d940bceff0f29439d29a'
IRQ_METHOD_SHA = '21b36a0e65c0385bb7cecf4aa92a784d8568727adc2bc2edc5f0dd4f7e5f8b28'
IRQ_SOURCE_SHA = '2bc4ff2f06eb515b404e08973a39c029ec975155a17a7baaf6f62e76ca181b4c'
IRQ_RESULT_SHA = 'a7cfdcdd40c317704b8e7799cc2aa6f776dfc856e7a6983e65fdb6a3c9a39ff1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def irq_patch_method():
    raw = kernel_bundle.kernel_patchset.plain_file(IRQ_PATCH)
    require(hashlib.sha256(raw).hexdigest() == IRQ_PATCH_SHA, 'Pinned IRQ patch differs')
    lines = raw.decode().splitlines()
    require(lines[:3] == ['--- a/' + IRQ_TARGET, '+++ b/' + IRQ_TARGET, '@@ -968,20 +968,25 @@'],
            'IRQ patch target or hunk differs')
    before, after = [], []
    for line in lines[3:]:
        require(line[:1] in (' ', '-', '+'), 'Unexpected IRQ patch framing')
        if line[0] in (' ', '-'):
            before.append(line[1:])
        if line[0] in (' ', '+'):
            after.append(line[1:])
    old = ('\n'.join(before) + '\n').encode()
    new = ('\n'.join(after) + '\n').encode()
    require(hashlib.sha256(old).hexdigest() == IRQ_METHOD_SHA, 'Pinned IRQ method differs')
    return old, new


def irq_patch_source(raw):
    require(hashlib.sha256(raw).hexdigest() == IRQ_SOURCE_SHA, 'Pinned PCIe source differs')
    before, after = irq_patch_method()
    require(raw.count(before) == 1, 'IRQ method is not unique')
    changed = raw.replace(before, after, 1)
    require(hashlib.sha256(changed).hexdigest() == IRQ_RESULT_SHA, 'Patched PCIe source differs')
    return changed


def configuration(text):
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r'(CONFIG_[A-Z0-9_]+)=(.*)', line)
        disabled = re.fullmatch(r'# (CONFIG_[A-Z0-9_]+) is not set', line)
        if match:
            values[match[1]] = match[2]
        elif disabled:
            values[disabled[1]] = 'n'
    require(all(values.get(name, 'n') == value for name, value in REQUIRED.items()),
            'Required preserved kernel configuration differs')
    return {name: values.get(name, 'n') for name in REQUIRED}


def macro_scope(paths):
    require(set(paths) == MACRO_FILES, 'PCIe/MSGBUF macros escaped the audited driver package')


def build_identity(profile):
    require(profile in (kernel_bundle.BUNDLE, kernel_bundle.BINDING_BUNDLE), 'Unsupported Wi-Fi kernel profile')
    if profile == kernel_bundle.BINDING_BUNDLE:
        return BINDING_RELEASE, BINDING_KERNEL_FILES
    return RELEASE, KERNEL_FILES


def kernel_state(output, *, profile=kernel_bundle.BUNDLE):
    release, hashes = build_identity(profile)
    require(output == output.resolve(strict=True) and output.stat().st_uid == os.geteuid(),
            'Owned kernel output without aliases required')
    for name, expected in hashes.items():
        raw = kernel_bundle.kernel_patchset.plain_file(output / name)
        require(hashlib.sha256(raw).hexdigest() == expected, 'Preserved kernel hash differs: ' + name)
    require((output / 'include/config/kernel.release').read_text().strip() == release,
            'Preserved kernel release differs')
    return configuration((output / '.config').read_text())


def destination(path, source, output):
    require(not path.exists() and not path.is_symlink(), 'New output directory required')
    parent = path.parent
    require(parent == parent.resolve(strict=True) and parent.stat().st_uid == os.geteuid()
            and not parent.stat().st_mode & 0o022, 'Owned output parent without writable aliases required')
    require(path != source and source not in path.parents and path != output and output not in path.parents,
            'Build outputs must remain outside preserved source and kernel output')
    require(shutil.disk_usage(parent).free >= 1024 * 1024 * 1024, 'At least 1 GiB free for module-only build required')


def copy_package(source, target, prefix):
    paths = kernel_bundle.kernel_patchset.git(source, 'ls-files', '-z', '--', prefix).decode().split('\0')
    target.mkdir(mode=0o700)
    hashes = {}
    for name in filter(None, paths):
        relative = Path(name).relative_to(prefix)
        raw = kernel_bundle.kernel_patchset.plain_file(source / name)
        copied = target / relative
        copied.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with copied.open('xb') as file:
            file.write(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    require(bool(hashes), 'Empty source package refused')
    return hashes


def make_command(output, package, exports, *, pcie=False):
    command = ['make', '-C', str(output), 'ARCH=arm64', 'LOCALVERSION=', '-j2', 'KCFLAGS=-Werror',
               'M=' + str(package), 'KBUILD_EXTRA_SYMBOLS=' + ' '.join(map(str, exports)), 'modules']
    if pcie:
        command += ['CONFIG_BRCMFMAC_PCIE=y', 'CONFIG_BRCMFMAC_PROTO_MSGBUF=y']
    return command


def verify_elf(raw, *, profile=kernel_bundle.BUNDLE):
    release, _ = build_identity(profile)
    magic = ('vermagic=' + release + ' SMP preempt mod_unload aarch64\0').encode()
    require(len(raw) >= 64 and raw[:7] == b'\x7fELF\x02\x01\x01'
            and struct.unpack_from('<HH', raw, 16) == (1, 183) and raw.count(magic) == 1,
            'Exact bundle ABI and relocatable AArch64 module required')


def verify_alias(aliases):
    require(ALIAS in aliases, 'PCI 14e4:43a3 with driver network-other class match required')


def build(source, output, target, *, profile=kernel_bundle.BUNDLE):
    release, hashes = build_identity(profile)
    kernel_bundle.inspect(source, profile=profile)
    config = kernel_state(output, profile=profile)
    paths = kernel_bundle.kernel_patchset.git(source, 'grep', '-l', '-E',
                                              'CONFIG_BRCMFMAC_(PCIE|PROTO_MSGBUF)').decode().splitlines()
    macro_scope(paths)
    destination(target, source, output)
    os.umask(0o077)
    target.mkdir(mode=0o700)
    exports = [output / 'vmlinux.symvers']
    source_hashes, commands = {}, []
    environment = {'PATH': os.environ['PATH'], 'LC_ALL': 'C'}
    for name, prefix in [('rfkill', 'net/rfkill'), ('cfg80211', 'net/wireless'), ('brcm80211', BROADCOM)]:
        package = target / name
        source_hashes.update(copy_package(source, package, prefix))
        if name == 'brcm80211':
            irq_source = package / 'brcmfmac/pcie.c'
            irq_source.write_bytes(irq_patch_source(kernel_bundle.kernel_patchset.plain_file(irq_source)))
            makefile = package / 'Makefile'
            makefile.write_bytes(makefile.read_bytes() + FLAGS)
        command = make_command(output, package, exports, pcie=name == 'brcm80211')
        commands.append(command)
        with (target / (name + '-build-private.log')).open('xb') as log:
            subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                           timeout=1200, check=True)
        require((package / 'Module.symvers').is_file(), 'Dependency export table missing')
        exports.append(package / 'Module.symvers')
        print('N71_WIFI_MODULE_PACKAGE_OK', name, flush=True)
    modules = {}
    for module in sorted(target.glob('**/*.ko')):
        raw = module.read_bytes()
        verify_elf(raw, profile=profile)
        depends = subprocess.check_output(['modinfo', '-F', 'depends', str(module)], text=True).strip()
        modules[str(module.relative_to(target))] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                                                   'depends': sorted(filter(None, depends.split(',')))}
    require(len(modules) == 8, 'Expected two rfkill, cfg80211 and five Broadcom modules')
    names = {Path(name).stem.replace('-', '_') for name in modules}
    require(all(set(record['depends']) <= names for record in modules.values()), 'Dependency module set incomplete')
    driver = target / 'brcm80211/brcmfmac/brcmfmac.ko'
    aliases = subprocess.check_output(['modinfo', '-F', 'alias', str(driver)], text=True).splitlines()
    verify_alias(aliases)
    symbols = subprocess.check_output(['nm', '--defined-only', str(driver)], text=True)
    for symbol in ('brcmf_pcie_register', 'brcmf_proto_msgbuf_attach'):
        require(re.search(r'\b[Tt]\s+' + symbol + r'$', symbols, re.M), 'PCIe/MSGBUF implementation not linked')
    kernel_bundle.inspect(source, profile=profile)
    require(kernel_state(output, profile=profile) == config, 'Preserved build changed')
    report = {'format': 1, 'source_commit': kernel_bundle.BASE, 'kernel_profile': profile, 'kernel_release': release,
              'preserved_kernel_sha256': hashes, 'config': config, 'macro_files': sorted(paths),
              'source_sha256': source_hashes, 'commands': commands, 'modules': modules,
              'irq_correction': {'target': IRQ_TARGET, 'patch_sha256': IRQ_PATCH_SHA,
                                 'source_sha256': IRQ_SOURCE_SHA, 'result_sha256': IRQ_RESULT_SHA,
                                 'applied_to_package_copy_only': True},
              'pci_alias_verified': ALIAS, 'pcie_msgbuf_symbols_linked': True,
              'werror_modpost_passed': True, 'kernel_source_and_image_preserved': True,
              'installed': False, 'loaded_on_phone': False, 'firmware_selected': False, 'wifi_verified': False}
    with (target / 'provenance-private.json').open('x') as file:
        json.dump(report, file, indent=2)
        file.write('\n')
    print('N71_WIFI_MODULE_SET_VERIFIED; not installed or loaded', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--kernel-output', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--profile', choices=(kernel_bundle.BUNDLE, kernel_bundle.BINDING_BUNDLE),
                        default=kernel_bundle.BUNDLE)
    options = parser.parse_args()
    require(sys.platform == 'linux' and platform.machine() == 'aarch64' and os.geteuid() != 0,
            'Run only as the dedicated Linux ARM64 VM user')
    build(options.source.absolute(), options.kernel_output.absolute(), options.output_dir.absolute(),
          profile=options.profile)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('N71_WIFI_BUILD_REFUSED: ' + str(error)) from error
