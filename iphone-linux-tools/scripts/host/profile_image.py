"""Read bounded initramfs records to bind a candidate to its SSH identities."""
from pathlib import PurePosixPath
import stat
import struct
import zlib

MAX_IMAGE_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 50000
WANTED = frozenset(('root', 'root/.ssh', 'root/.ssh/authorized_keys',
                    'etc/dropbear/dropbear_ed25519_host_key', 'init'))


def records(raw):
    found, seen = {}, set()
    offset = 0
    while len(seen) < MAX_ENTRIES:
        header = raw[offset:offset + 110]
        if len(header) != 110 or header[:6] != b'070701':
            raise ValueError('Initramfs do perfil contém cabeçalho inválido.')
        values = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        mode, uid, gid, links, size, namesize = values[1:5] + [values[6], values[11]]
        offset += 110
        if not 1 <= namesize <= 4096 or offset + namesize > len(raw):
            raise ValueError('Nome inválido no initramfs do perfil.')
        name = raw[offset:offset + namesize - 1].decode()
        if raw[offset + namesize - 1] != 0:
            raise ValueError('Nome inválido no initramfs do perfil.')
        offset = (offset + namesize + 3) & ~3
        if offset + size > len(raw):
            raise ValueError('Initramfs do perfil está truncado.')
        if name == 'TRAILER!!!':
            if size != 0 or any(raw[offset:]):
                raise ValueError('Initramfs do perfil contém dados adicionais após o trailer.')
            if set(found) != WANTED:
                raise ValueError('Initramfs do perfil não contém as identidades necessárias.')
            return found
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or str(path) in seen:
            raise ValueError('Caminho duplicado ou fora do escopo no initramfs do perfil.')
        normalized = str(path)
        seen.add(normalized)
        if normalized in WANTED:
            directory = normalized in ('root', 'root/.ssh')
            expected = stat.S_IFDIR | 0o700 if directory else stat.S_IFREG | (0o755 if normalized == 'init' else 0o600)
            if mode != expected or uid != 0 or gid != 0 or (not directory and links != 1):
                raise ValueError('Permissões ou identidade inseguras no initramfs do perfil.')
            found[normalized] = raw[offset:offset + size]
        offset = (offset + size + 3) & ~3
    raise ValueError('Initramfs do perfil excede o limite de arquivos.')


def dropbear_public(raw):
    kind = struct.pack('>I', 11) + b'ssh-ed25519'
    if len(raw) != 83 or not raw.startswith(kind + struct.pack('>I', 64)):
        raise ValueError('Chave do servidor embutida não tem o formato Dropbear Ed25519 esperado.')
    return kind + struct.pack('>I', 32) + raw[-32:]


def verify(profile, client_public):
    import device_profile
    path = profile['initramfs']
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError('Initramfs comprimido do perfil excede o limite.')
    compressed = path.read_bytes()
    with profile['payload'].open('rb') as payload:
        if profile['payload'].stat().st_size <= len(compressed):
            raise ValueError('Payload do perfil não contém o initramfs selecionado.')
        payload.seek(-len(compressed), 2)
        if payload.read() != compressed:
            raise ValueError('Payload e initramfs do perfil não correspondem.')
    try:
        decoder = zlib.decompressobj(31)
        raw = decoder.decompress(compressed, MAX_IMAGE_BYTES + 1)
        if len(raw) > MAX_IMAGE_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('Initramfs do perfil excede o limite ou contém streams adicionais.')
    except zlib.error as error:
        raise ValueError('Compressão inválida no initramfs do perfil.') from error
    entries = records(raw)
    authorized = entries['root/.ssh/authorized_keys'].decode().splitlines()
    if len(authorized) != 1 or device_profile.public_wire(authorized[0]) != client_public:
        raise ValueError('Chave cliente não corresponde à autorização da imagem.')
    if dropbear_public(entries['etc/dropbear/dropbear_ed25519_host_key']) != profile['server_public']:
        raise ValueError('Pin do servidor não corresponde à identidade da imagem.')
    if b'telnetd' in entries['init'] or b'ip link set lo up' not in entries['init']:
        raise ValueError('Perfil exige imagem integrada com loopback e SSH, sem Telnet.')
