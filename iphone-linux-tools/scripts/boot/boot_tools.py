"""Verify preserved host boot executables before launching them."""
import hashlib
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    'palera1n-macos-arm64': (4874592, '950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9'),
    'pongoterm': (53608, 'ad4d66f1e2908090cc52a07ce5a58076b5ae877bb3d50b2a8d8e267b63113a56'),
}


def verify_path(path, pin):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid() or info.st_mode & 0o7022
            or not info.st_mode & stat.S_IXUSR):
        raise ValueError('Ferramenta de boot exige arquivo próprio executável, sem links ou escrita pública.')
    size, expected = pin
    if info.st_size != size:
        raise ValueError('Tamanho inesperado da ferramenta de boot: ' + path.name)
    with path.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    if digest != expected:
        raise ValueError('Hash inesperado da ferramenta de boot: ' + path.name)
    return path


def verify(name, root=ROOT):
    if name not in PINS:
        raise ValueError('Ferramenta de boot desconhecida.')
    directory = root / 'bin'
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise ValueError('Ferramentas de boot exigem diretório real, sem symlink.')
    return verify_path(directory / name, PINS[name])


if __name__ == '__main__':
    try:
        if not sys.argv[1:]:
            raise ValueError('Informe as ferramentas de boot a verificar.')
        for name in sys.argv[1:]:
            verify(name)
    except (OSError, ValueError) as error:
        raise SystemExit('Ferramenta de boot inválida: ' + str(error)) from error
