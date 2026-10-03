"""Select only a pinned Pongo image before any USB process starts."""
import hashlib
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHA256 = '1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575'
SOURCE_SHA256 = '17d3df93213bb24f8ba73a8ad390e6bcc56351b41d87a315d47d37aa51100efd'
IMAGE_BYTES = 238096


def select(root=ROOT):
    selected = os.environ.get('IPHONE_LINUX_PONGO')
    if selected is not None and (not selected or any(ord(c) < 32 or ord(c) == 127 for c in selected)):
        raise ValueError('Seleção explícita de Pongo vazia ou inválida.')
    path = Path(selected).absolute() if selected is not None else root / 'artifacts/Pongo.bin'
    for parent in path.parents:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('Pongo exige diretórios reais, sem symlinks.')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid() or info.st_mode & 0o7022):
        raise ValueError('Pongo exige arquivo próprio regular, sem links ou escrita pública.')
    if info.st_size != IMAGE_BYTES:
        raise ValueError('Tamanho do Pongo inesperado.')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = SOURCE_SHA256 if selected is not None else DEFAULT_SHA256
    if digest != expected:
        raise ValueError('Hash do Pongo inesperado; nenhuma ação USB iniciada.')
    return path


if __name__ == '__main__':
    try:
        print(select())
    except (OSError, ValueError) as error:
        raise SystemExit('Pongo inválido: ' + str(error)) from error
