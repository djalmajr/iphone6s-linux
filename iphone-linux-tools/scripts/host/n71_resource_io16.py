"""Bind the IO16 upper noop proof to one measured resource assignment."""
import re

FIELDS = ('captured', 'enabled', 'noops')
PATTERN = (r'N71_PCIE_IO16_UPPER captured=([01]) enabled=([01]) noops=(\d+); '
           r'temporary upper disable without hardware write$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(text, result, *, required=False):
    require(type(required) is bool, 'IO16 requirement must be an exact boolean')
    found = list(re.finditer(PATTERN, text, re.M))
    require(len(found) == text.count('N71_PCIE_IO16_') and len(found) <= 1,
            'Incomplete, unknown or repeated IO16 report')
    if not found:
        require(not required or result is None, 'Qualified IO16 report missing')
        return None
    require(result is not None and 'optional_windows' in result,
            'IO16 report lacks its assignment or optional-window proof')
    row = found[0]
    require(text.count('N71_PCIE_OPTIONAL_WINDOWS ') == 1
            and text.count('N71_PCIE_ASSIGN_READBACK ') == 1
            and text.index('N71_PCIE_SESSION_HELD ')
            < text.index('N71_PCIE_OPTIONAL_WINDOWS ') < row.start()
            < text.index('N71_PCIE_ASSIGN_READBACK ') < text.index('N71_PCIE_RESOURCE_RESULT '),
            'IO16 report is outside the assignment phase')
    data = dict(zip(FIELDS, map(int, row.groups())))
    optional = result['optional_windows']
    require(data['captured'] == result['pending'], 'IO16 capture and rollback differ')
    if not data['captured']:
        require(not any(data.values()) and not result['attempts'], 'Uncaptured IO16 fields invented')
    require(data['enabled'] or data['noops'] == 0, 'Disabled IO16 cannot claim a noop')
    require(not data['enabled'] or optional['io_absent'] == 0, 'Absent IO range cannot claim IO16 support')
    require(data['noops'] + optional['io_noops'] + optional['pref_noops']
            <= result['attempts'] - result['writes'], 'Combined noop count exceeds unverified attempts')
    if result['assigned']:
        require(not data['enabled'] or data['noops'] > 0, 'Assigned IO16 requires its disable noop proof')
    return data
