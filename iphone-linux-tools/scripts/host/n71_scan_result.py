"""Validate the selected temporary PCI scan and its removal/restoration proof."""
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def summary(text):
    rows = re.findall(r'N71_PCIE_SCAN_RESULT error=(-?\d+) devices=(\d+) endpoints=(\d+) reads=(\d+) attempts=(\d+) writes=(\d+) refusals=(\d+); no DMA or radio', text)
    require(len(rows) == 1, 'Exactly one completed PCI-core scan required')
    result = dict(zip(('error', 'devices', 'endpoints', 'reads', 'attempts', 'writes', 'refusals'),
                      map(int, rows[0])))
    require(0 <= result['attempts'] <= 129 and 0 <= result['writes'] <= result['attempts']
            and 0 <= result['reads'] <= 4200 and 0 <= result['refusals'] <= result['attempts'] + 1,
            'PCI scan accounting differs')
    return result


def cleanup(text):
    if 'N71_PCIE_SCAN_' not in text:
        # Earlier link/inventory failure never enters the host scan.
        earlier = re.findall(r'N71_PCIE_(?:LINK|INVENTORY)_RESULT error=(-?\d+)', text)
        require(any(int(error) < 0 for error in earlier), 'Missing host scan or earlier failure')
        return
    result = summary(text)
    removed = re.findall(r'N71_PCIE_SCAN_BUS_REMOVED bus-null=(\d+)', text)
    restored = re.findall(r'N71_PCIE_SCAN_CONFIG_RESTORED error=(-?\d+); decode/readback checked', text)
    if result['devices'] or result['attempts'] or result['writes'] or result['error'] == 0:
        require(removed == ['1'] and restored == ['0'], 'PCI bus removal/config restoration not proved')
    else:
        require(result['error'] < 0 and not removed and restored in ([], ['0']),
                'Failed scan preflight/registration is not consistent')


def parse(text):
    result = summary(text)
    require(result['error'] == 0 and result['devices'] == 2 and result['endpoints'] == 1
            and 1 <= result['attempts'] <= 128 and result['refusals'] == 0,
            'Successful PCI-core scan with no refused writes required')
    cleanup(text)
    result.update(device_resources(text))
    return result


def device_resources(text):
    result = {}
    devices = re.findall(r'N71_PCIE_SCAN_DEVICE bus=(\d+) devfn=([0-9a-f]{2}) id=([0-9a-f]{8}) class=([0-9a-f]{6}) command=([0-9a-f]{4}) driver=none(?=\n|$)', text)
    require([row[:4] for row in devices] == [('0', '08', '1004106b', '060400'),
                                           ('1', '00', '43a314e4', '028000')]
            and all(not (int(row[4], 16) & 4) for row in devices),
            'Exact PCI topology, class and bus-master clear required')
    bars = re.findall(r'N71_PCIE_SCAN_BAR index=(\d+) start=([0-9a-f]{16}) end=([0-9a-f]{16}) flags=([0-9a-f]{8,16}); no MMIO(?=\n|$)', text)
    require([int(row[0]) for row in bars] == list(range(6)), 'Six ordered unique sized BAR resources required')
    result['bars'] = []
    for index, start, end, flags in bars:
        start, end, flags = int(start, 16), int(end, 16), int(flags, 16)
        require((flags == start == end == 0) or (flags & 0x700 == 0x200 and end >= start),
                'Invalid or non-memory BAR resource')
        size = end - start + 1 if flags else 0
        require(not size or (size & (size - 1) == 0 and size <= 0x1a0000000),
                'BAR size is not bounded/power-of-two')
        result['bars'].append({'index': int(index), 'start': start, 'end': end,
                               'flags': flags, 'bytes': size})
    result['device_details'] = [{'bus': int(row[0]), 'devfn': int(row[1], 16),
                          'identity': row[2], 'class': row[3], 'command': int(row[4], 16)}
                         for row in devices]
    return result
