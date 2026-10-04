"""Validate direct BAR sizing independently of the module's reported sizes."""
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def summary(text):
    rows = re.findall(r'N71_PCIE_SIZING_RESULT error=(-?\d+) reads=(\d+) attempts=(\d+) writes=(\d+) refusals=(\d+); no DMA or radio', text)
    require(len(rows) == 1, 'Exactly one BAR sizing result required')
    result = dict(zip(('error', 'reads', 'attempts', 'writes', 'refusals'), map(int, rows[0])))
    require(0 <= result['reads'] <= 200 and 0 <= result['attempts'] <= 13
            and 0 <= result['writes'] <= result['attempts']
            and 0 <= result['refusals'] <= 1, 'BAR sizing accounting differs')
    return result


def cleanup(text):
    if 'N71_PCIE_SIZING_' not in text:
        errors = re.findall(r'N71_PCIE_(?:LINK|INVENTORY)_RESULT error=(-?\d+)', text)
        require(any(int(error) < 0 for error in errors), 'Missing sizing or earlier failure')
        return
    result = summary(text)
    restored = re.findall(r'N71_PCIE_SIZING_CONFIG_RESTORED error=(-?\d+); decode/readback checked', text)
    require(restored == ['0'] or (result['error'] < 0 and result['attempts'] == 0
                                 and result['writes'] == 0 and not restored),
            'BAR config restoration not proved')


def parse(text, expected_raw):
    result = summary(text)
    require(result['error'] == 0 and result['attempts'] == 13 and result['refusals'] == 0,
            'Successful complete BAR sizing with no refusals required')
    cleanup(text)
    rows = re.findall(r'N71_PCIE_SIZED_BAR index=(\d+) raw=([0-9a-f]{8}) mask=([0-9a-f]{8}) bytes=([0-9a-f]{16}); no MMIO', text)
    require([int(row[0]) for row in rows] == list(range(6)), 'Six unique ordered BAR words required')
    bars = [{'index': int(i), 'raw': int(raw, 16), 'mask': int(mask, 16), 'bytes': int(size, 16)}
            for i, raw, mask, size in rows]
    require([bar['raw'] for bar in bars] == expected_raw, 'Sizing originals differ from fresh inventory')
    index = 0
    while index < 6:
        bar = bars[index]
        attributes = bar['raw'] & 0xf
        kind = attributes & 6
        require(not (attributes & 1) and kind in (0, 4), 'Only memory BAR types are qualified')
        if kind == 0 and bar['raw'] == bar['mask'] == 0:
            require(bar['bytes'] == 0, 'Unimplemented BAR has a size')
            index += 1
            continue
        mask, width = bar['mask'] & ~0xf, 0xffffffff
        if kind == 4:
            require(index < 5 and bars[index + 1]['bytes'] == 0, 'Invalid 64-bit BAR upper word')
            mask |= bars[index + 1]['mask'] << 32
            width = 0xffffffffffffffff
        size = ((~mask) & width) + 1
        require(mask and bar['mask'] & 0xf == attributes and size >= 16
                and size & (size - 1) == 0
                and size <= (0x1a0000000 if kind == 4 else 0x40000000)
                and bar['bytes'] == size, 'BAR mask/type/size differs')
        index += 2 if kind == 4 else 1
    result['bars'] = bars
    return result
