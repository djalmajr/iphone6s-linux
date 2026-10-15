"""Bind the complete typed PREF disable proof to its captured assignment."""
import re

FIELDS = ('captured', 'enabled', 'writes')
PATTERN = (r'N71_PCIE_PREF64_DISABLE captured=([01]) enabled=([01]) writes=(\d+); '
           r'full disabled readback with preserved types$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(text, result, *, required=False):
    require(type(required) is bool, 'PREF64 requirement must be an exact boolean')
    found = list(re.finditer(PATTERN, text, re.M))
    require(len(found) == text.count('N71_PCIE_PREF64_') and len(found) <= 1,
            'Incomplete, unknown or repeated PREF64 report')
    if not found:
        require(not required or result is None, 'Qualified PREF64 report missing')
        return None
    require(result is not None and 'optional_windows' in result and 'io16_upper' in result,
            'PREF64 report lacks its assignment or prior window proofs')
    row = found[0]
    require(all(text.count(marker) == 1 for marker in ('N71_PCIE_SESSION_HELD ',
            'N71_PCIE_OPTIONAL_WINDOWS ', 'N71_PCIE_IO16_UPPER ', 'N71_PCIE_ASSIGN_READBACK ',
            'N71_PCIE_RESOURCE_RESULT '))
            and text.index('N71_PCIE_SESSION_HELD ') < text.index('N71_PCIE_OPTIONAL_WINDOWS ')
            < text.index('N71_PCIE_IO16_UPPER ') < row.start()
            < text.index('N71_PCIE_ASSIGN_READBACK ') < text.index('N71_PCIE_RESOURCE_RESULT '),
            'PREF64 report is outside the assignment phase')
    data = dict(zip(FIELDS, map(int, row.groups())))
    require(data['captured'] == result['pending'], 'PREF64 capture and rollback differ')
    if not data['captured']:
        require(not any(data.values()) and not result['attempts'], 'Uncaptured PREF64 fields invented')
    require(data['enabled'] or data['writes'] == 0, 'Disabled PREF64 cannot claim a typed write')
    require(not data['enabled'] or result['optional_windows']['pref_absent'] == 0,
            'Absent PREF range cannot claim typed disable support')
    require(data['writes'] <= result['writes'], 'Typed writes exceed verified writes')
    if result['assigned']:
        require(not data['enabled'] or data['writes'] > 0, 'Assigned PREF64 requires its typed write proof')
    return data
