"""Qualify provider removal and table restoration without publishing pointers."""
import hashlib
import json
import re
import struct
import n71_dart_result
import n71_session_history


def require(condition, message):
    if not condition:
        raise ValueError(message)


def previous(directory):
    read = n71_session_history.read_private
    result = json.loads(read(directory, 'result-private.json'))
    known = frozenset(n71_session_history.kernel_lines(read(directory, 'preflight-private.log')))
    fresh = '\n'.join(line for line in read(directory, 'pcie-cleanup-private.log').splitlines()
                      if line not in known)
    observed = n71_dart_result.parse(fresh)
    require(observed == result.get('dart_observation') and observed['ttbr_words_preserved'] == 16,
            'Previous complete private table differs or is missing')


def summary(text):
    pattern = (r'N71_DART_CYCLE_RESULT error=(-?\d+) snapshots=(\d+) reads=(\d+) guards=(\d+) '
               r'quiet=(\d+) writes=(\d+) attempted=([01]) stopped=([01]) restored=([01]) '
               r'control-changed=([01]); no DMA')
    rows = re.findall(pattern, text)
    require(len(rows) == 1, 'Exactly one provider cycle result required')
    result = dict(zip(('error', 'snapshots', 'reads', 'guards', 'quiet', 'writes',
                       'attempted', 'stopped', 'restored', 'control_changed'), map(int, rows[0])))
    require(result['error'] <= 0 and 0 <= result['snapshots'] <= 4 and
            0 <= result['reads'] <= 152 and 0 <= result['guards'] <= 156 and
            0 <= result['quiet'] <= 17 and 0 <= result['writes'] <= 16,
            'Provider cycle budgets differ')
    return result


def cleanup(text):
    if 'N71_DART_CYCLE_' not in text:
        errors = re.findall(r'N71_PCIE_(?:LINK|INVENTORY)_RESULT error=(-?\d+)', text)
        require(any(int(error) < 0 for error in errors), 'Missing cycle or earlier failure')
        return
    result = summary(text)
    require(re.findall(r'N71_DART_CYCLE_RELEASED device=(\d+) mapping-new=(\d+) claimed=(\d+) mapped=(\d+)', text)
            == [('0', '0', '0', '0')], 'Provider, IRQ mapping or MMIO ownership remains')
    if result['attempted']:
        require(result['stopped'] == result['restored'] == 1,
                'Attempted provider lacks removal or verified table restoration')
        require(re.findall(r'N71_DART_CYCLE_REMOVED device=(\d+) mapping-new=(\d+) claimed=(\d+); restore ownership held', text)
                == [('0', '0', '1')], 'Restoration resource ownership not proved')


def parse(text):
    result = summary(text)
    require(result == dict(error=0, snapshots=4, reads=152, guards=156, quiet=17, writes=16,
                           attempted=1, stopped=1, restored=1, control_changed=0),
            'Complete successful provider cycle required')
    cleanup(text)
    require(re.findall(r'N71_DART_CYCLE_PROVIDER bound=(\d+) irq-hwirq=(\d+) mapping-new=([01]); no DMA attachment', text)
            in ([('1', '248', '0')], [('1', '248', '1')]), 'Bound Apple DART provider required')
    rows = re.findall(r'N71_DART_CYCLE_SNAPSHOT index=(\d+) command=([0-9a-f]{8}) tcr=([0-9a-f]{8}) error=([0-9a-f]{8}) valid=([0-9a-f]{4}); stable', text)
    require([int(row[0]) for row in rows] == [1, 2, 3, 4], 'Four ordered stable provider states required')
    states = [tuple(int(value, 16) for value in row[1:]) for row in rows]
    require(all(command != 0xffffffff and not command & 8 and tcr == 0 and not error & 0x80000000
                for command, tcr, error, valid in states), 'Faulted, busy or translated provider refused')
    require(len({state[:3] for state in states}) == 1 and states[1][3] == states[2][3] == 0,
            'Control changed or provider reset did not clear tables')
    words = re.findall(r'N71_DART_TTBR index=(\d{2}) value=([0-9a-f]{8}); stable', text)
    require([int(index) for index, _ in words] == list(range(16)), 'Complete private original table required')
    values = [int(value, 16) for _, value in words]
    require(all(value != 0xffffffff for value in values), 'Unavailable table refused')
    mask = sum(1 << index for index, value in enumerate(values) if value & 0x80000000)
    require(states[0][3] == states[3][3] == mask, 'Original/restored valid mask differs')
    result.update(provider_initialized=True, ttbr_words_restored=16,
                  ttbr_sha256=hashlib.sha256(struct.pack('<16I', *values)).hexdigest(),
                  command=states[0][0], fault_raw=states[0][2], dma_enabled=False)
    return result
