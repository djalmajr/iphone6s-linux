"""Compose a private source-kernel candidate without executing its userspace."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/host'))
sys.path.insert(0, str(ROOT / 'scripts/build'))
import device_profile
import profile_image
import kernel_patchset
import kernel_bundle

OLD_LOAD = b'insmod /lib/modules/usb_f_ncm.ko || echo "usb_f_ncm module load failed"\n'
BUILTIN_LOAD = b'echo "USB NCM built into source kernel"\n'
MODULE = 'lib/modules/usb_f_ncm.ko'
BOOTARGS = b'chosen.bootargs=rdinit=/init console=ttySAC0,115200 loglevel=7\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decompress(data):
    decoder = zlib.decompressobj(31)
    raw = decoder.decompress(data, profile_image.MAX_IMAGE_BYTES + 1)
    if (len(raw) > profile_image.MAX_IMAGE_BYTES or not decoder.eof
            or decoder.unused_data or decoder.unconsumed_tail):
        raise ValueError('Compressão excede o limite ou contém streams adicionais.')
    return raw


def migrate(raw, *, forbid_extra_modules=False):
    before = profile_image.records(raw)
    old = before['init']
    legacy = old.count(OLD_LOAD) == 1 and BUILTIN_LOAD not in old
    already_builtin = old.count(BUILTIN_LOAD) == 1 and OLD_LOAD not in old
    if not legacy and not already_builtin:
        raise ValueError('Init não corresponde à migração NCM conhecida.')
    new = old.replace(OLD_LOAD, BUILTIN_LOAD) if legacy else old
    result, removed, offset = [], 0, 0
    while True:
        start = offset
        header = raw[offset:offset + 110]
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        name = raw[offset + 110:offset + 110 + namesize - 1].decode()
        content = (offset + 110 + namesize + 3) & ~3
        offset = (content + size + 3) & ~3
        normalized = str(PurePosixPath(name))
        if forbid_extra_modules and normalized != MODULE:
            under_modules = normalized.startswith('lib/modules/') and fields[1] & 0o170000 != 0o040000
            if under_modules or normalized.endswith(('.ko', '.ko.gz', '.ko.xz', '.ko.zst')):
                raise ValueError('Bundle com ABI nova exige initramfs sem módulos extras da ABI anterior.')
        if normalized == MODULE:
            if fields[1] not in (0o100600, 0o100644) or fields[4] != 1:
                raise ValueError('Módulo NCM não é um arquivo regular conhecido.')
            removed += 1
            continue
        if normalized == 'init' and legacy:
            replacement = header[:54] + f'{len(new):08x}'.encode() + header[62:]
            replacement += raw[start + 110:content]
            replacement += new + b'\0' * (-len(new) % 4)
            result.append(replacement)
        else:
            result.append(raw[start:offset])
        if name == 'TRAILER!!!':
            break
    if removed != int(legacy):
        raise ValueError('Quantidade de módulos NCM inesperada no initramfs.')
    migrated = b''.join(result)
    migrated += b'\0' * (-len(migrated) % 512)
    after = profile_image.records(migrated)
    if after != dict(before, init=new):
        raise ValueError('Migração alterou identidades ou entradas protegidas.')
    return migrated, ['init', MODULE] if legacy else []


def kernel_inputs(folder, patchset=None):
    if patchset not in (None, kernel_patchset.PATCHSET, kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE):
        raise ValueError('Patchset de integração desconhecido.')
    bundle = patchset in (kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE)
    record_name = ('kernel-n71-binding-build.json' if patchset == kernel_bundle.BINDING_BUNDLE else
                   ('kernel-n71-power-bundle-build.json' if patchset == kernel_bundle.POWER_BUNDLE else
                   ('kernel-n71-bundle-build.json' if bundle else
                    ('kernel-dart-build.json' if patchset else 'kernel-source-build.json'))))
    record = json.loads((ROOT / 'docs/evidence' / record_name).read_text())
    if record['status'] != 'compiled_verified' or record['build']['exit_code'] != 0:
        raise ValueError('Registro público exige kernel compilado e verificado.')
    if bundle:
        version, files, patches = kernel_bundle.bundle_spec(patchset)
        source = record['source']
        if record['build'].get('full_image_linked') is not True or record['build'].get('vmlinux_modpost_verified') is not True:
            raise ValueError('Bundle exige Image completo e modpost conferidos.')
        if source['commit'] != kernel_bundle.BASE:
            raise ValueError('Base do bundle de integração divergente.')
        if source['bundle'] != patchset or source['required_localversion'] != version:
            raise ValueError('Identidade do bundle de integração divergente.')
        if source['patches'] != patches or source['files'] != {key: list(value) for key, value in files.items()}:
            raise ValueError('Patches ou blobs do bundle de integração divergentes.')
        if record['build']['kernel_release'] != '7.2.0' + version:
            raise ValueError('Release do bundle exige ABI distinta.')
        if record['build'].get('serdev_stop_bits_export_verified') is not True:
            raise ValueError('Bundle exige export serdev conferido no kernel linkado.')
    elif patchset:
        source = record['source']
        if source['commit'] != kernel_patchset.BASE:
            raise ValueError('Base do patchset de integração divergente.')
        if source['patchset'] != patchset or source['patch_sha256'] != kernel_patchset.PATCH_SHA:
            raise ValueError('Identidade do patchset de integração divergente.')
    device_profile.protected(folder, directory=True)
    blobs = {}
    for name in ('Image', 'Image.gz', 's8000-n71.dtb', 'config', 'config-embedded'):
        file = folder / name
        device_profile.protected(file)
        expected = record['build']['outputs'][name]
        if file.stat().st_size != expected['bytes'] or expected['bytes'] > profile_image.MAX_IMAGE_BYTES:
            raise ValueError('Tamanho de artefato de kernel inesperado.')
        blobs[name] = file.read_bytes()
        if digest(blobs[name]) != expected['sha256']:
            raise ValueError('Hash de artefato de kernel inesperado.')
    header = blobs['Image'][:64]
    if len(header) != 64 or header[56:60] != b'ARM\x64' or (struct.unpack_from('<Q', header, 24)[0] >> 1) & 3 != 2:
        raise ValueError('Image exige ARM64 e páginas de 16 KiB.')
    if decompress(blobs['Image.gz']) != blobs['Image']:
        raise ValueError('Kernel comprimido não corresponde ao Image.')
    if blobs['config'] != blobs['config-embedded']:
        raise ValueError('Configuração embutida não corresponde ao build.')
    config = blobs['config'].decode().splitlines()
    for name in ('ARM64_16K_PAGES', 'USB_F_NCM', 'USB_CONFIGFS_NCM', 'APPLE_WATCHDOG'):
        if f'CONFIG_{name}=y' not in config:
            raise ValueError('Configuração obrigatória do kernel ausente.')
    if patchset and 'CONFIG_APPLE_DART=y' not in config:
        raise ValueError('Patchset DART exige driver incorporado no kernel.')
    if bundle:
        required = (f'CONFIG_LOCALVERSION="{version}"',
                    '# CONFIG_LOCALVERSION_AUTO is not set',
                    'CONFIG_SERIAL_DEV_BUS=y', 'CONFIG_SERIAL_DEV_CTRL_TTYPORT=y')
        if any(line not in config for line in required):
            raise ValueError('Bundle exige identidade explícita e serdev incorporado.')
    if patchset in (kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE) and any(
            line not in config for line in ('CONFIG_PINCTRL_APPLE_GPIO=y', 'CONFIG_APPLE_PMGR_PWRSTATE=y')):
        raise ValueError('Bundle power exige GPIO e PMGR incorporados.')
    if 'apple,n71' not in record['build']['dtb_compatible'].split():
        raise ValueError('Registro público não identifica N71.')
    return blobs, record


def write_private(path, data):
    with path.open('xb') as file:
        file.write(data)
    path.chmod(0o600)


def integrate(options):
    output = options.output_dir.absolute()
    if output.parent != ROOT / 'runtime' or output.exists() or output.is_symlink():
        raise ValueError('Destino exige pasta nova diretamente sob runtime/.')
    device_profile.protected(output.parent, directory=True)
    source = device_profile.verify()
    blobs, record = kernel_inputs(options.kernel_dir.absolute(), options.kernel_patchset)
    m1n1 = (ROOT / 'artifacts/m1n1.bin').read_bytes()
    expected = json.loads((ROOT / 'docs/evidence/m1n1-rebuild.json').read_text())['shallow_clone']
    if not expected['matches_original'] or digest(m1n1) != expected['sha256']:
        raise ValueError('Hash do m1n1 preservado inesperado.')
    raw, changes = migrate(decompress(source['initramfs'].read_bytes()),
                           forbid_extra_modules=options.kernel_patchset in (kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE))
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    payload = m1n1 + BOOTARGS + blobs['s8000-n71.dtb'] + blobs['Image.gz'] + compressed
    os.umask(0o077)
    output.mkdir(mode=0o700)
    write_private(output / 'initramfs.gz', compressed)
    write_private(output / 'payload.bin', payload)
    write_private(output / 'client_ed25519', source['client_key'].read_bytes())
    write_private(output / 'known_hosts', source['known_hosts'].read_bytes())
    profile = {'format': 1, 'payload': 'payload.bin', 'sha256': digest(payload),
               'initramfs': 'initramfs.gz', 'initramfs_sha256': digest(compressed),
               'client_key': 'client_ed25519', 'known_hosts': 'known_hosts',
               'host_key_alias': source['host_key_alias']}
    pending = output / 'deployment.pending.json'
    write_private(pending, (json.dumps(profile, indent=2) + '\n').encode())
    previous = os.environ.get('IPHONE_LINUX_PROFILE')
    try:
        os.environ['IPHONE_LINUX_PROFILE'] = str(pending)
        device_profile.verify()
    finally:
        if previous is None:
            os.environ.pop('IPHONE_LINUX_PROFILE', None)
        else:
            os.environ['IPHONE_LINUX_PROFILE'] = previous
    pending.rename(output / 'deployment.json')
    report = {'format': 1, 'kernel_source_commit': record['source']['commit'],
              'kernel_patchset': options.kernel_patchset,
              'kernel_release': record['build']['kernel_release'], 'initramfs_changed_paths': changes,
              'identities_preserved': True, 'client_private_key_copied_to_vm': False,
              'payload_sha256': digest(payload), 'payload_bytes': len(payload),
              'initramfs_sha256': digest(compressed), 'initramfs_bytes': len(compressed),
              'profile_verified': True, 'physical_boot_tested': False, 'default_payload_changed': False}
    write_private(output / 'provenance.json', (json.dumps(report, indent=2) + '\n').encode())
    print('KERNEL_INTEGRATION_VERIFIED; private deployment.json ready; no USB action')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--kernel-patchset', choices=(kernel_patchset.PATCHSET, kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE))
    options = parser.parse_args()
    try:
        integrate(options)
    except (OSError, ValueError, KeyError, struct.error, zlib.error, subprocess.SubprocessError):
        print('KERNEL_INTEGRATION_FAILED: input, integrity or private profile validation.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
