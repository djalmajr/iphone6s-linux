"""Keep the allocator's first failed write/readback tied to its original refusal."""
import re

FIELDS = ('failed', 'root', 'where', 'size', 'value', 'before', 'after_valid', 'after', 'write_error', 'read_error')
PATTERN = (r'N71_PCIE_ASSIGN_READBACK failed=([01]) root=([01]) where=([0-9a-f]{3}) size=([024]) '
           r'value=([0-9a-f]{8}) before=([0-9a-f]{8}) after_valid=([01]) after=([0-9a-f]{8}) '
           r'write_error=(-?\d+) read_error=(-?\d+); no additional IO$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(text, result, *, required=False):
    require(type(required) is bool, 'Readback requirement must be an exact boolean')
    found = list(re.finditer(PATTERN, text, re.M))
    require(len(found) == text.count('N71_PCIE_ASSIGN_') and len(found) <= 1,
            'Incomplete, unknown or repeated assignment readback')
    if not found:
        require(not required or result is None, 'Qualified module readback record missing')
        return None
    require(result is not None, 'Readback lacks an assignment result')
    row = found[0]
    require(text.index('N71_PCIE_SESSION_HELD ') < row.start()
            < text.index('N71_PCIE_RESOURCE_RESULT '), 'Readback is outside the assignment phase')
    data = dict(zip(FIELDS, (int(value, 16 if name in ('where', 'value', 'before', 'after') else 10)
                            for name, value in zip(FIELDS, row.groups()))))
    if not data['failed']:
        require(not any(data.values()), 'Absent write failure must have no fabricated fields')
        return data
    size = data['size']
    require(size in (2, 4) and data['where'] <= 0xfc and data['where'] % size == 0,
            'Write failure register/width differs')
    mask = (1 << (size * 8)) - 1
    require(all(data[name] <= mask for name in ('value', 'before', 'after'))
            and data['before'] != data['value'], 'Write failure values or no-op differ')
    write, read = data['write_error'], data['read_error']
    require(all(-4095 <= value <= 0x7fffffff for value in (write, read)), 'Raw callback error differs')
    if write or read:
        require(not data['after_valid'] and data['after'] == 0 and (not write or read == 0),
                'Failed callback cannot prove readback or a later read')
        raw = write or read
        error = raw if raw < 0 else -5
    else:
        require(data['after_valid'] == 1 and data['after'] != data['value'],
                'Readback mismatch must have a valid differing value')
        error = -5
    require(result['error'] == error and result['assigned'] == 0
            and result['pending'] == result['claimed'] == 1
            and result['writes'] < result['attempts'], 'Readback and first assignment error differ')
    refusals = list(re.finditer(r'N71_PCIE_SCAN_WRITE_REFUSED bus=(\d+) devfn=([0-9a-f]{2}) '
                               r'where=([0-9a-f]{3}) size=([124]) value=([0-9a-f]{8}) error=(-\d+)$', text, re.M))
    require(refusals and len(refusals) == text.count('N71_PCIE_SCAN_WRITE_REFUSED '),
            'Write readback lacks its complete original refusal')
    first = refusals[0]
    bus, devfn, where, width, value, refusal_error = first.groups()
    require((int(bus), int(devfn, 16), int(where, 16), int(width), int(value, 16), int(refusal_error))
            == (0 if data['root'] else 1, 8 if data['root'] else 0, data['where'], size, data['value'], error)
            and text.index('N71_PCIE_SESSION_HELD ') < first.start() < row.start(),
            'Readback does not match the first refused write')
    return data
