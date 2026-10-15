#!/usr/bin/env python3
"""Select a private phone deployment without changing the known defaults."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PHONE = '172.16.42.1'
FIELDS = frozenset(('format', 'payload', 'sha256', 'initramfs', 'initramfs_sha256',
                    'client_key', 'known_hosts', 'host_key_alias'))


def protected(path, directory=False):
    metadata = path.lstat()
    valid_type = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if (not valid_type or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o7077 or (not directory and metadata.st_nlink != 1)):
        raise ValueError('Perfil exige arquivos próprios privados, sem links ou permissões especiais.')


def public_wire(line):
    parts = line.split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('Perfil exige identidade Ed25519 explícita.')
    try:
        wire = base64.b64decode(parts[1], validate=True)
    except ValueError as error:
        raise ValueError('Chave pública do perfil inválida.') from error
    expected = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32)
    if len(wire) != 51 or not wire.startswith(expected):
        raise ValueError('Chave pública do perfil inválida.')
    return wire


def local_path(base, value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Caminho privado inválido no perfil.')
    relative = PurePosixPath(value)
    if not relative.parts or relative.is_absolute() or '..' in relative.parts or relative.as_posix() != value:
        raise ValueError('Caminho do perfil deve permanecer na sua pasta privada.')
    path = base
    for part in relative.parts[:-1]:
        path = path / part
        protected(path, directory=True)
    path = path / relative.parts[-1]
    protected(path)
    return path


def load(root=ROOT):
    selected = os.environ.get('IPHONE_LINUX_PROFILE')
    if selected is None:
        return {'explicit': False, 'client_key': root / 'keys/iphone_ed25519',
                'known_hosts': root / 'keys/known_hosts', 'host_key_alias': None,
                'payload': root / 'artifacts/m1n1-linux-iphone6s-loopback-server.bin',
                'sha256': '8b1a46dd67613c63aa6608dd3a0e73a73b358aaddc1818b423ff6009b55e3f66'}
    if not selected:
        raise ValueError('Seleção explícita de perfil vazia.')
    source = Path(selected).absolute()
    protected(source)
    protected(source.parent, directory=True)
    if source.stat().st_size > 65536:
        raise ValueError('Perfil excede o tamanho permitido.')
    data = json.loads(source.read_text())
    if (not isinstance(data, dict) or set(data) != FIELDS
            or type(data['format']) is not int or data['format'] != 1):
        raise ValueError('Formato de perfil inválido.')
    for field in ('sha256', 'initramfs_sha256'):
        if not isinstance(data[field], str) or not re.fullmatch('[a-f0-9]{64}', data[field]):
            raise ValueError('Hash inválido no perfil.')
    alias = data['host_key_alias']
    if not isinstance(alias, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', alias):
        raise ValueError('Alias de identidade inválido no perfil.')
    base = source.parent.resolve()
    for field in ('payload', 'initramfs', 'client_key', 'known_hosts'):
        data[field] = local_path(base, data[field])
    if data['known_hosts'].stat().st_size > 8192 or data['client_key'].stat().st_size > 65536:
        raise ValueError('Identidade do perfil excede o tamanho permitido.')
    lines = data['known_hosts'].read_text().splitlines()
    if len(lines) != 1 or len(lines[0].split()) < 3 or lines[0].split()[0] != alias:
        raise ValueError('Pin do perfil não corresponde ao alias explícito.')
    data['server_public'] = public_wire(' '.join(lines[0].split()[1:]))
    data['explicit'] = True
    return data


def ssh_options(root=ROOT):
    profile = load(root)
    command = ['ssh', '-4', '-F', '/dev/null', '-a', '-i', str(profile['client_key']),
               '-o', f'UserKnownHostsFile={profile["known_hosts"]}',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
               '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
               '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3',
               '-o', 'ForwardAgent=no', '-o', 'ForwardX11=no',
               '-o', 'ControlMaster=no', '-o', 'ControlPath=none']
    if profile['explicit']:
        command += ['-o', 'GlobalKnownHostsFile=/dev/null', '-o', f'HostKeyAlias={profile["host_key_alias"]}']
    return command


def verify():
    import profile_image
    profile = load()
    if not profile['explicit']:
        raise ValueError('Verificação de candidata exige IPHONE_LINUX_PROFILE explícito.')
    for field, hash_field in (('payload', 'sha256'), ('initramfs', 'initramfs_sha256')):
        with profile[field].open('rb') as file:
            if hashlib.file_digest(file, 'sha256').hexdigest() != profile[hash_field]:
                raise ValueError('Hash da imagem do perfil inválido; boot bloqueado.')
    key = subprocess.run(['ssh-keygen', '-y', '-P', '', '-f', str(profile['client_key'])],
                         capture_output=True, text=True, timeout=10)
    if key.returncode:
        raise ValueError('Não foi possível verificar a chave cliente do perfil.')
    profile_image.verify(profile, public_wire(key.stdout))
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'fields', 'ssh-config'))
    options = parser.parse_args()
    if options.command == 'check':
        verify()
        print('PROFILE_IMAGE_IDENTITIES_OK; no USB or remote action performed')
    elif options.command == 'fields':
        profile = load()
        for name in ('client_key', 'known_hosts', 'host_key_alias', 'payload', 'sha256'):
            print(profile[name] if profile[name] is not None else '')
    else:
        command = ssh_options() + ['-G', f'root@{PHONE}']
        subprocess.run(command, check=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('Perfil inválido: ' + str(error)) from error
