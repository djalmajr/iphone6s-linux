"""Bind absent optional ranges and emulated requests to one PCI assignment."""
import re

FIELDS = ('captured', 'io_absent', 'pref_absent', 'io_noops', 'pref_noops')
PATTERN = (r'N71_PCIE_OPTIONAL_WINDOWS captured=([01]) io_absent=([01]) pref_absent=([01]) '
           r'io_noops=(\d+) pref_noops=(\d+); absent ranges are emulated without hardware writes$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(text, result, *, required=False):
    require(type(required) is bool, 'Optional window requirement must be an exact boolean')
    found = list(re.finditer(PATTERN, text, re.M))
    require(len(found) == text.count('N71_PCIE_OPTIONAL_') and len(found) <= 1,
            'Incomplete, unknown or repeated optional window report')
    if not found:
        require(not required or result is None, 'Qualified optional window report missing')
        return None
    require(result is not None, 'Optional windows lack an assignment result')
    row = found[0]
    require(text.count('N71_PCIE_ASSIGN_READBACK ') == 1
            and text.index('N71_PCIE_SESSION_HELD ') < row.start()
            < text.index('N71_PCIE_ASSIGN_READBACK ') < text.index('N71_PCIE_RESOURCE_RESULT '),
            'Optional windows are outside the assignment phase')
    data = dict(zip(FIELDS, map(int, row.groups())))
    require(data['captured'] == result['pending'], 'Optional windows and captured rollback differ')
    if not data['captured']:
        require(not any(data.values()) and not result['attempts'], 'Uncaptured optional fields invented')
    require((data['io_absent'] or data['io_noops'] == 0)
            and (data['pref_absent'] or data['pref_noops'] == 0),
            'Implemented ranges cannot claim absent-range noops')
    require(data['io_noops'] + data['pref_noops'] <= result['attempts'] - result['writes'],
            'Optional noop count exceeds unverified attempts')
    if result['assigned']:
        require((not data['io_absent'] or data['io_noops'] > 0)
                and (not data['pref_absent'] or data['pref_noops'] > 0),
                'Assigned absent ranges require their disable request proof')
    return data
