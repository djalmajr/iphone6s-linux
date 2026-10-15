#!/usr/bin/env python3
"""Compose a RAM boot payload without following output redirects."""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BOOTARGS = b'chosen.bootargs=rdinit=/init console=ttySAC0,115200 loglevel=7\n'


def regular_output(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1 or info.st_mode & 0o7000):
        raise ValueError('Destino deve ser arquivo regular próprio, sem links ou permissões especiais.')


def destination(path):
    if '..' in path.parts:
        raise ValueError('Use um caminho literal sem componentes .. para o destino.')
    path = path.absolute()
    for parent in path.parents:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('Pais do destino devem ser diretórios reais, sem symlinks.')
    directory = path.parent.stat()
    if directory.st_uid != os.geteuid() or directory.st_mode & 0o7022:
        raise ValueError('Pasta de saída deve ser própria, sem escrita por outros ou permissões especiais.')
    try:
        regular_output(path.lstat())
    except FileNotFoundError:
        pass
    return path


def publish(path, blob):
    path = destination(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        descriptor = None
    if descriptor is not None:
        with os.fdopen(descriptor, 'rb') as existing:
            regular_output(os.fstat(existing.fileno()))
            if existing.read() != blob:
                raise ValueError('O destino já existe com outro conteúdo; escolha outro nome.')
            os.fchmod(existing.fileno(), 0o600)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.compose-', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(blob)
            output.flush()
            os.fsync(output.fileno())
        destination(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def compose(initramfs, output, artifacts):
    output = destination(output)
    blob = b''.join([(artifacts / 'm1n1.bin').read_bytes(), BOOTARGS,
                     (artifacts / 's8000-n71.dtb').read_bytes(),
                     (artifacts / 'vmlinuz-apple-16k').read_bytes(), initramfs.read_bytes()])
    publish(output, blob)
    return hashlib.sha256(blob).hexdigest(), output.name, len(blob)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('initramfs', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        print(*compose(args.initramfs, args.output, ROOT / 'artifacts'))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == '__main__':
    main()
