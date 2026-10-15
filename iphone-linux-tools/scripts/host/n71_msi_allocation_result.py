"""Read saved MSI ownership without issuing actions or claiming IRQ delivery."""
import re

FIELDS = ('ready', 'held', 'owner', 'phase', 'vector', 'default_irq', 'software_enabled',
          'slots', 'mappings', 'child', 'error', 'session_error')
MARKER = 'N71_PCIE_MSI_ALLOCATION '
PCIE = '/sys/module/n71_pcie_diagnostic/parameters/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def getter():
    return ('if test -e ' + PCIE + 'msi_allocation; then printf "' + MARKER + '"; '
            'cat ' + PCIE + 'msi_allocation; fi; ')


def live(text):
    require(len(text) <= 2 * 1024 * 1024, 'MSI getter evidence exceeds budget')
    if MARKER not in text:
        return None
    pattern = '^' + MARKER + ' '.join(name + r'=(-?[0-9]{1,10})' for name in FIELDS) + '$'
    rows = list(re.finditer(pattern, text, re.M))
    require(len(rows) == text.count(MARKER) == 1, 'Unique complete MSI allocation getter required')
    state = dict(zip(FIELDS, map(int, rows[0].groups())))
    require(rows[0].group() == MARKER + ' '.join(f'{name}={state[name]}' for name in FIELDS),
            'MSI allocation getter must use canonical integers')
    require(all(state[name] in (0, 1) for name in ('ready', 'held', 'owner', 'software_enabled', 'child')),
            'MSI allocation flags differ')
    require(0 <= state['phase'] <= 2, 'MSI allocation phase differs')
    require(all(0 <= state[name] <= 2147483647 for name in ('vector', 'default_irq')),
            'MSI allocation IRQ range differs')
    require(0 <= state['slots'] <= 0xff and 0 <= state['mappings'] <= 8, 'MSI allocation grant budget differs')
    require(all(-4095 <= state[name] <= 0 for name in ('error', 'session_error')), 'MSI allocation errors differ')
    require(not state['held'] or state['ready'], 'Held MSI allocation lacks its host')
    if not state['ready']:
        require(all(state[name] == 0 for name in FIELDS if name not in ('error', 'session_error')),
                'Removed MSI host still reports ownership')
    return state


def snapshot(text, caller, held):
    state = live(text)
    if state is None:
        return
    require(state['ready'] == caller.get('scan_pending', 0), 'MSI allocation host and caller disagree')
    require(state['held'] == held, 'MSI allocation held bus differs')
    require(state['session_error'] == caller.get('cleanup_error', 0), 'MSI allocation cleanup error differs')
    require(not caller.get('primary_error', 0) or state['error'] == caller['primary_error'],
            'MSI allocation lost the caller first error')


def resume(current, prior):
    require(live(current) == live(prior), 'MSI allocation ownership or getter presence changed; no cleanup attempted')
