"""Observe the PCI runtime contract; publication never proves firmware or radio."""
import re
import n71_msi_allocation_result

PCIE = '/sys/module/n71_pcie_diagnostic/parameters/'
MARKER = 'N71_PCIE_DRIVER '
PARAMETER = 'N71_HELD_PARAM driver_runtime='
FIELDS = ('requested', 'ready', 'held', 'pending', 'active', 'published', 'root', 'endpoint',
          'pm', 'root_override', 'endpoint_override', 'reads', 'operation_error', 'error', 'session_error')
OWNERS = ('active', 'root', 'endpoint', 'pm', 'root_override', 'endpoint_override')
FLAGS = FIELDS[:11]
ACTION_MARKER = 'N71_PCIE_DRIVER_RESULT '
ACTION_FIELDS = ('error', 'pending', 'active', 'published', 'root', 'endpoint', 'pm',
                 'root_override', 'endpoint_override', 'operation_error')
SUFFIX = '; not firmware or radio proof'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def capable(session):
    value = getattr(session, 'driver_runtime', False)
    require(type(value) is bool, 'Driver runtime selection must be an exact boolean')
    return value


def getter():
    return ('if test -e ' + PCIE + 'driver_runtime_status; then printf "' + MARKER + '"; '
            'cat ' + PCIE + 'driver_runtime_status; printf "' + PARAMETER + '"; '
            'cat ' + PCIE + 'driver_runtime; fi; ')


def row(text, shape):
    fields, marker = shape['fields'], shape['marker']
    prefix, suffix = shape.get('prefix', ''), shape.get('suffix', '')
    require(isinstance(text, str) and len(text) <= 2 * 1024 * 1024, 'Driver evidence exceeds budget')
    pattern = '^' + prefix + re.escape(marker) + '(?P<fields>' + ' '.join(
        name + r'=(-?[0-9]{1,10})' for name in fields) + ')' + re.escape(suffix) + '$'
    rows = list(re.finditer(pattern, text, re.M))
    require(len(rows) == text.count(marker) == 1, 'Unique complete driver record required')
    values = dict(zip(fields, map(int, rows[0].groups()[1:])))
    require(rows[0].group('fields') == ' '.join(f'{name}={values[name]}' for name in fields),
            'Driver record must use canonical integers')
    return values


def owners(state):
    require(all(state[name] in (0, 1) for name in ('pending', 'published') + OWNERS),
            'Driver ownership flags differ')
    require(state['pending'] == int(any(state[name] for name in OWNERS)),
            'Driver pending flag lost a partial owner')
    require(all(-4095 <= state[name] <= 0 for name in state if name.endswith('error')),
            'Driver errors differ')


def live(text, *, required=False):
    require(isinstance(text, str) and len(text) <= 2 * 1024 * 1024, 'Driver evidence exceeds budget')
    require(type(required) is bool, 'Driver getter requirement must be an exact boolean')
    if MARKER not in text:
        require(not required and PARAMETER not in text, 'Selected driver getter is missing')
        return None
    state = row(text, {'fields': FIELDS, 'marker': MARKER})
    owners(state)
    require(all(state[name] in (0, 1) for name in FLAGS), 'Driver selection/host flags differ')
    require(0 <= state['reads'] <= 4294967295, 'Driver read counter differs')
    require(not state['held'] or state['ready'], 'Held driver bus lacks its host')
    require(not state['operation_error'] or state['error'] < 0, 'Driver first cause was discarded')
    if not state['ready']:
        require(all(state[name] == 0 for name in FIELDS if name not in ('requested', 'error', 'session_error')),
                'Removed driver host still reports ownership')
    return state


def immutable(session, text, state):
    selected = capable(session)
    parameter = re.findall('^' + PARAMETER + r'([YN])$', text, re.M)
    require(len(parameter) == text.count(PARAMETER) == 1 and parameter[0] == ('Y' if selected else 'N')
            and state['requested'] == int(selected), 'Driver immutable selection changed')


def snapshot(session, text, observation):
    caller, held = observation['caller'], observation['held']
    selected = capable(session)
    state = live(text, required=selected)
    if state is None:
        return None
    immutable(session, text, state)
    require(state['ready'] == caller.get('scan_pending', 0) and state['held'] == held,
            'Driver host and caller disagree')
    require(state['session_error'] == caller.get('cleanup_error', 0), 'Driver cleanup error differs')
    primary = caller.get('primary_error', 0)
    allocation = n71_msi_allocation_result.live(text)
    causal = primary or state['operation_error'] or (allocation['error'] if allocation else 0)
    require(not causal or state['error'] == causal, 'Driver lost the caller first cause')
    if not selected:
        require(all(state[name] == 0 for name in OWNERS + ('published', 'reads', 'operation_error')),
                'Unselected driver runtime has effects')
    return state


def resume(session, current, prior):
    selected = capable(session)
    before, after = live(prior, required=selected), live(current, required=selected)
    for text, state in ((prior, before), (current, after)):
        if state is not None:
            immutable(session, text, state)
    if before is None or after is None or not selected:
        require(before == after, 'Driver getter presence or legacy state changed')
        return
    require(before['requested'] == after['requested'] == 1, 'Driver runtime selection changed')
    stable = tuple(name for name in FIELDS if name not in ('reads', 'operation_error', 'error'))
    require(all(before[name] == after[name] for name in stable), 'Unproved driver ownership/publication changed')
    require(after['reads'] >= before['reads'], 'Driver counter moved backwards')
    require(all(before[name] == 0 or before[name] == after[name] for name in ('operation_error', 'error')),
            'Driver first cause changed or disappeared')


def action(text, expected):
    require(expected in ('prepare', 'publish', 'release', 'cleanup'), 'Unknown driver action')
    state = row(text, {'fields': ACTION_FIELDS, 'marker': ACTION_MARKER + 'action=' + expected + ' ',
                       'prefix': r'(?:\[\s*[0-9]+\.[0-9]+\]\s*)?', 'suffix': SUFFIX})
    require(text.count(ACTION_MARKER) == 1, 'Another driver action in the proof delta')
    owners(state)
    if not state['error']:
        if expected in ('prepare', 'publish'):
            require(all(state[name] == 1 for name in OWNERS) and state['pending'] == 1
                    and state['published'] == int(expected == 'publish'), 'Driver action lacks complete owners')
        else:
            require(state['pending'] == 0, 'Successful driver release still owns resources')
    return state
