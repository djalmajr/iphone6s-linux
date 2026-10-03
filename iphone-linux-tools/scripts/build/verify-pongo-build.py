"""Verify a bounded ARM64 preload Mach-O against its raw Pongo mapping."""
from pathlib import Path
import stat
import struct
import sys

MAX_MACHO = 32 * 1024 * 1024
MAX_MAPPING = 0x80000


def read_regular(path, maximum):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
        raise ValueError('Unexpected input type or size.')
    return path.read_bytes()


def mapping(blob):
    if len(blob) < 32:
        raise ValueError('Truncated Mach-O header.')
    header = struct.unpack_from('<8I', blob)
    magic, cpu, _, kind, count, length, _, _ = header
    if magic != 0xfeedfacf or cpu != 0x100000c or kind != 5 or count > 4096:
        raise ValueError('Expected an ARM64 preload Mach-O.')
    end = 32 + length
    if end > len(blob) or length > 2 * 1024 * 1024:
        raise ValueError('Load command region exceeds input.')
    offset, spans = 32, []
    for _ in range(count):
        if offset + 8 > end:
            raise ValueError('Truncated load command.')
        command, size = struct.unpack_from('<II', blob, offset)
        if size < 8 or size % 8 or offset + size > end:
            raise ValueError('Invalid load command size.')
        if command == 0x19:
            if size < 72:
                raise ValueError('Truncated 64-bit segment.')
            fields = struct.unpack_from('<II16sQQQQiiII', blob, offset)
            address, file_offset, file_size, sections = fields[3], fields[5], fields[6], fields[9]
            if size != 72 + sections * 80 or file_offset + file_size > len(blob):
                raise ValueError('Invalid segment or section region.')
            mapped = []
            for index in range(sections):
                section = struct.unpack_from('<16s16sQQ8I', blob, offset + 72 + index * 80)
                start, amount, data_offset, flags = section[2], section[3], section[4], section[8]
                if flags & 0xff == 1 or amount == 0:
                    continue
                if start < address or start + amount > address + file_size:
                    raise ValueError('Section extends beyond mapped segment.')
                if data_offset != file_offset + start - address:
                    raise ValueError('Section offset does not match segment mapping.')
                mapped.append((start, start + amount))
            if mapped:
                first, last = min(part[0] for part in mapped), max(part[1] for part in mapped)
                spans.append((first, last, file_offset + first - address))
        offset += size
    if offset != end or not spans:
        raise ValueError('Load command count or mapped sections invalid.')
    spans.sort()
    base, limit = spans[0][0], max(span[1] for span in spans)
    if base != 0x100000000 or not 0 < limit - base <= MAX_MAPPING:
        raise ValueError('Unexpected mapping address or size.')
    raw, previous = bytearray(limit - base), base
    for start, stop, data_offset in spans:
        if start < previous or data_offset + stop - start > len(blob):
            raise ValueError('Overlapping or truncated mapped data.')
        raw[start - base:stop - base] = blob[data_offset:data_offset + stop - start]
        previous = stop
    return bytes(raw)


def main():
    if len(sys.argv) != 3:
        print('Usage: verify-pongo-build.py MACHO RAW_BINARY', file=sys.stderr)
        return 2
    try:
        macho = read_regular(Path(sys.argv[1]), MAX_MACHO)
        raw = read_regular(Path(sys.argv[2]), MAX_MAPPING)
        if mapping(macho) != raw:
            raise ValueError('Raw binary differs from Mach-O mapping.')
        if b'bootm\0' not in raw or b'2.6.3-bb492b00' not in raw:
            raise ValueError('Expected m1n1 command and pinned version markers.')
    except (OSError, ValueError, struct.error) as error:
        print('PONGO_BUILD_VERIFICATION_FAILED: ' + str(error), file=sys.stderr)
        return 1
    print('PONGO_MACHO_MAPPING_VERIFIED; ARM64 preload and bootm markers')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
