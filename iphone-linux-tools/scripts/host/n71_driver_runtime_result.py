"""Observe the PCI runtime contract; publication never proves firmware or radio."""
import re
import n71_msi_allocation_result
import n71_scan_target_result

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


def association(session, text, observation):
    require(capable(session) and type(observation['published']) is bool,
            'Driver association requires explicit publication proof')
    state = live(text, required=True)
    immutable(session, text, state)
    require(not state['published'] or observation['published'], 'Driver publication lacks its journal proof')
    exposed = observation['published'] and state['ready'] == state['held'] == state['published'] == 1 \
        and all(state[name] == 1 for name in OWNERS)
    if not exposed:
        return False
    actual, initial = observation['actual'], observation['initial']
    require(actual['iommu'] == initial['iommu'], 'Published driver changed its IOMMU providers')
    require({name: value for name, value in actual['msi'].items() if name not in ('mappings', 'child')}
            == {name: value for name, value in initial['msi'].items() if name not in ('mappings', 'child')},
            'Published driver changed its MSI providers')
    require(actual['msi']['mappings'] in (0, 1) and actual['msi']['child'] in (0, 1)
            and (not actual['msi']['mappings'] or actual['msi']['child']), 'Driver vector budget or domain differs')
    allocation = n71_msi_allocation_result.live(text)
    require(allocation is not None and all(allocation[name] == 0 for name in
            ('owner', 'phase', 'vector', 'default_irq', 'software_enabled')), 'Driver mixed the manual MSI lease')
    require(allocation['slots'] in (0, 1) and allocation['mappings'] in (0, 1)
            and (not (allocation['slots'] or allocation['mappings']) or allocation['child']),
            'Driver allocation exceeds its vector or domain budget')
    return True


def association_resume(session, observation):
    current, prior = observation['current'], observation['prior']
    resume(session, current, prior)
    exposed = [association(session, text, {'published': observation['published'], 'actual': actual,
               'initial': observation['initial']}) for text, actual in
               ((prior, observation['before']), (current, observation['after']))]
    if not all(exposed):
        require(observation['before'] == observation['after'], 'Unproved driver changed MSI/IOMMU ownership')
        n71_msi_allocation_result.resume(current, prior)
        return
    before, after = n71_msi_allocation_result.live(prior), n71_msi_allocation_result.live(current)
    stable = tuple(name for name in before if name not in ('slots', 'mappings', 'child', 'error'))
    require(all(before[name] == after[name] for name in stable), 'Driver changed manual MSI ownership')
    require(not before['child'] or after['child'], 'Driver removed its retained MSI device domain')
    require(not observation['before']['msi']['child'] or observation['after']['msi']['child'],
            'Driver association lost its device domain')
    old_caller, new_caller = n71_scan_target_result.live_status(prior), n71_scan_target_result.live_status(current)
    override = old_caller.get('primary_error', 0) == 0 and new_caller.get('primary_error', 0) < 0 \
        and after['error'] == new_caller['primary_error'] == live(current, required=True)['error']
    require(before['error'] == 0 or before['error'] == after['error'] or override,
            'Driver allocation lost its error without caller precedence')


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


def cleanup_cause(session, text):
    if not capable(session):
        return 0
    import n71_driver_runtime_stage as stage
    import n71_session_history as history
    entries = stage.fields(session)['driver_runtime_journal']
    state = live(text, required=True); immutable(session, text, state)
    require(re.findall(r'^N71_BOOT_ID (' + stage.BOOT + ')$', text, re.M) == [session.result.get('boot_id')],
            'Driver cleanup belongs to another boot')
    if not entries:
        require(not state['pending'] and not state['published'], 'Driver cleanup lacks its native lifetime')
        return 0
    entry = entries[-1]; completion = entry['completion']
    require(entry['action'] == 'release' and completion is not None and completion['native']['error'] == 0
            and not completion['state']['pending'], 'Driver cleanup lacks a proved successful release')
    require(not state['pending'] and not state['held'] and not state['ready'], 'Driver cleanup still owns its host')
    lines = history.kernel_lines(text)
    require(lines[:len(entry['history'])] == entry['history'], 'Driver cleanup release prefix changed')
    native = action('\n'.join(line for line in lines[len(entry['history']):] if ACTION_MARKER in line), 'release')
    require(native == completion['native'], 'Driver cleanup release result differs')
    error = completion['state']['error']
    require(not error or state['error'] == error, 'Driver cleanup discarded its first cause')
    return error
