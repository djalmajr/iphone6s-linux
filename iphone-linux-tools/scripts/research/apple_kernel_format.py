"""Bounded data-only IM4P/LZSS decoding; never loads or runs an image."""
import struct
import zlib

MAX_INPUT = 24 * 1024 * 1024
MAX_OUTPUT = 96 * 1024 * 1024


def der(data, offset):
    if offset < 0 or offset + 2 > len(data):
        raise ValueError('DER header truncated')
    tag, length = data[offset:offset + 2]
    start = offset + 2
    if length & 128:
        count = length & 127
        if not 1 <= count <= 4 or start + count > len(data):
            raise ValueError('DER length refused')
        length = int.from_bytes(data[start:start + count], 'big')
        start += count
    end = start + length
    if end > len(data):
        raise ValueError('DER value truncated')
    return tag, data[start:end], end


def im4p_payload(blob):
    if not 0 < len(blob) <= MAX_INPUT:
        raise ValueError('IM4P size refused')
    tag, outer, end = der(blob, 0)
    if tag != 0x30 or end != len(blob):
        raise ValueError('IM4P envelope refused')
    parts, offset = [], 0
    while offset < len(outer):
        if len(parts) >= 8:
            raise ValueError('IM4P field count refused')
        tag, value, offset = der(outer, offset)
        parts.append((tag, value))
    if (len(parts) < 4 or parts[0] != (0x16, b'IM4P')
            or parts[1] != (0x16, b'krnl') or parts[3][0] != 4):
        raise ValueError('IM4P kernel type refused')
    return parts[3][1]


def lzss(source, length):
    if not 0 < len(source) <= MAX_INPUT or not 0 < length <= MAX_OUTPUT:
        raise ValueError('LZSS size refused')
    ring = bytearray(b' ' * 4078 + b'\0' * 18)
    output = bytearray()
    position, flags, cursor = 4078, 0, 0
    while cursor < len(source):
        flags >>= 1
        if flags & 0x100 == 0:
            flags = source[cursor] | 0xff00
            cursor += 1
            if cursor >= len(source):
                raise ValueError('LZSS flag without token')
        if flags & 1:
            if len(output) >= length:
                raise ValueError('LZSS output overflow')
            value = source[cursor]
            cursor += 1
            output.append(value)
            ring[position] = value
            position = (position + 1) & 4095
        else:
            if cursor + 2 > len(source):
                raise ValueError('LZSS reference truncated')
            first, second = source[cursor:cursor + 2]
            cursor += 2
            offset = first | ((second & 0xf0) << 4)
            count = (second & 15) + 3
            if len(output) + count > length:
                raise ValueError('LZSS output overflow')
            for index in range(count):
                value = ring[(offset + index) & 4095]
                output.append(value)
                ring[position] = value
                position = (position + 1) & 4095
    if len(output) != length:
        raise ValueError('LZSS output length mismatch')
    return bytes(output)


def decode(blob):
    payload = im4p_payload(blob)
    if len(payload) < 384 or payload[:8] != b'complzss':
        raise ValueError('Expected complzss header')
    _, _, checksum, length, compressed, version = struct.unpack_from('>6I', payload)
    if version != 1 or not 0 < compressed <= MAX_INPUT or 384 + compressed > len(payload):
        raise ValueError('Compression header refused')
    image = lzss(payload[384:384 + compressed], length)
    if zlib.adler32(image) != checksum:
        raise ValueError('LZSS Adler32 mismatch')
    if image[:8] != b'\xcf\xfa\xed\xfe\x0c\x00\x00\x01':
        raise ValueError('Expected ARM64 Mach-O data')
    return image, {'lzss_adler32_verified': True, 'compressed_lzss_bytes': compressed,
                   'compression_header_bytes': 384,
                   'suffix_not_executed_or_decoded': len(payload) - 384 - compressed}
