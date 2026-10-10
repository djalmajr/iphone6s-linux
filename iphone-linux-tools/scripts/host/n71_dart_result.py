"""A stable DART snapshot proves observation, never DMA or stream routing."""
import hashlib
import re
import struct


def require(condition, message):
    if not condition:
        raise ValueError(message)


def summary(text):
    rows = re.findall(r'N71_DART_RESULT error=(-?\d+) reads=(\d+) guards=(\d+); no DART writes or DMA', text)
    require(len(rows) == 1, 'Exactly one DART result required')
    result = dict(zip(('error', 'reads', 'guards'), map(int, rows[0])))
    require(result['error'] <= 0 and 0 <= result['reads'] <= 38
            and result['guards'] in (result['reads'], result['reads'] + 1),
            'DART observation budget or quiet guards differ')
    return result


def cleanup(text):
    if 'N71_DART_' not in text:
        errors = re.findall(r'N71_PCIE_(?:LINK|INVENTORY)_RESULT error=(-?\d+)', text)
        require(any(int(error) < 0 for error in errors), 'Missing DART or earlier failure')
        return
    summary(text)
    require(re.findall(r'N71_DART_MAP_RELEASED mapped=(\d+) claimed=(\d+)', text) == [('0', '0')],
            'DART mapping/resource release not proved')


def parse(text):
    result = summary(text)
    require(result['error'] == 0 and result['reads'] == 38 and result['guards'] == 39,
            'Two complete guarded DART snapshots required')
    cleanup(text)
    rows = re.findall(r'N71_DART_SOURCE physical=([0-9a-f]{16}) bytes=([0-9a-f]{8}) irq=(\d+) provider=disabled owner=none', text)
    require(rows == [('0000000602008000', '00004000', '248')], 'Separate unowned N71 DART source required')
    rows = re.findall(r'N71_DART_STATE command=([0-9a-f]{8}) tcr=([0-9a-f]{8}) error=([0-9a-f]{8}) enabled=([0-9a-f]) ttbr-valid=([0-9a-f]{4}); stable', text)
    require(len(rows) == 1, 'Exactly one stable DART state required')
    command, tcr, error, enabled, valid_ttbrs = map(lambda value: int(value, 16), rows[0])
    require(all(value != 0xffffffff for value in (command, tcr, error)) and not command & 8,
            'Unavailable or busy DART state refused')
    expected = sum(1 << index for index in range(4) if (tcr >> (index * 8)) & 0x80)
    require(enabled == expected, 'Packed TCR enable mask differs')
    rows = re.findall(r'N71_DART_TTBR index=(\d{2}) value=([0-9a-f]{8}); stable', text)
    require([int(index) for index, _ in rows] == list(range(16)),
            'Sixteen unique ordered stable TTBR words required')
    words = [int(value, 16) for _, value in rows]
    require(all(value != 0xffffffff for value in words), 'Unavailable TTBR refused')
    expected = sum(1 << index for index, word in enumerate(words) if word & 0x80000000)
    require(valid_ttbrs == expected, 'TTBR valid mask differs from preserved words')
    result.update(command=command, tcr=tcr, fault_raw=error, enabled_streams=enabled,
                  valid_ttbr_mask=valid_ttbrs, valid_ttbr_count=valid_ttbrs.bit_count(),
                  ttbr_words_preserved=len(words),
                  ttbr_sha256=hashlib.sha256(struct.pack('<16I', *words)).hexdigest(),
                  fault_flag=bool(error & 0x80000000), fault_stream=(error >> 24) & 3,
                  fault_code=error & 0xff)
    return result
