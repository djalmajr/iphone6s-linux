"""Validate temporary TLS rollback and live caller ownership, keeping raw logs intact."""
import re
import n71_scan_result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def live_status(text):
    rows = re.findall(r'^N71_PCIE_STATUS (.*)$', text, re.M)
    require(len(rows) == 1, 'Unique live PCIe caller status required')
    if rows[0] == 'ready=0 retained=0':
        return {'ready': 0, 'retained': 0}
    match = re.fullmatch(r'ready=1 retained=([01]) scan_pending=([01]) reset_pending=([01]) powered=([0-4]) attached=([0-4]) power_put_pending=([01]) primary_error=(-?\d+) cleanup_error=(-?\d+)', rows[0])
    require(match is not None, 'Complete live caller ownership required')
    result = dict(zip(('retained', 'scan_pending', 'reset_pending', 'powered', 'attached',
                       'power_put_pending', 'primary_error', 'cleanup_error'), map(int, match.groups())))
    result['ready'] = 1
    return result


def is_clean(status):
    return all(status.get(name, 0) == 0 for name in
               ('retained', 'scan_pending', 'reset_pending', 'powered', 'attached', 'power_put_pending', 'cleanup_error'))


def normalize(text):
    # Only translate the accounting annotation, never hardware values or error records.
    suffix = '; counts before cleanup, no DMA or radio'
    if 'N71_PCIE_SCAN_RESULT ' in text:
        require(text.count(suffix) == 1, 'Selected scan accounting annotation required')
    return text.replace(suffix, '; no DMA or radio')


def cleanup(text):
    status = live_status(text)
    require(is_clean(status), 'PCIe caller still owns pending cleanup')
    if not status['ready']:
        require('N71_PCIE_SCAN_RESULT ' not in text, 'Unbound caller cannot own a completed scan')
        return
    sessions = re.findall(r'N71_PCIE_SESSION_CLEANUP error=(-?\d+) retained=(\d+) scan_pending=(\d+) reset_pending=(\d+) powered=(\d+) attached=(\d+) power_put_pending=(\d+) primary_error=(-?\d+)', text)
    require(sessions and tuple(map(int, sessions[-1][:7])) == (0, 0, 0, 0, 0, 0, 0)
            and int(sessions[-1][7]) == status['primary_error'], 'Final caller cleanup proof required')
    if 'N71_PCIE_SCAN_RESULT ' not in text:
        n71_scan_result.cleanup(text)
        return
    result = n71_scan_result.summary(normalize(text))
    removed = re.findall(r'N71_PCIE_SCAN_BUS_REMOVED bus-null=(\d+)', text)
    require(removed in ([], ['1']), 'PCI bus removal differs')
    if result['devices'] or result['attempts'] or result['error'] == 0:
        require(removed == ['1'], 'Registered PCI bus removal required')
    config = re.findall(r'N71_PCIE_SCAN_CONFIG_RESTORED error=(-?\d+); decode/readback checked', text)
    require(config and config[-1] == '0' and all(int(e) <= 0 for e in config), 'Final config restoration required')
    prepared = re.findall(r'N71_PCIE_SCAN_TARGET_PREPARED error=(-?\d+) pending=([01]) prepared=([01]); no retrain', text)
    require(len(prepared) <= 1, 'Unique target prepare required')
    if prepared:
        error, pending, ready = map(int, prepared[0])
        require(error <= 0 and (error != 0 or (pending, ready) == (1, 1)), 'Target prepare state differs')
        if pending:
            restored = re.findall(r'N71_PCIE_SCAN_TARGET_RESTORED error=(-?\d+) pending=([01]); no retrain', text)
            require(restored and restored[-1] == ('0', '0'), 'Final TLS restoration required')
    elif result['error'] == 0:
        raise ValueError('Successful scan requires target preparation')


def parse(text):
    cleanup(text)
    require(live_status(text).get('primary_error') == 0, 'Successful caller result required')
    require(re.findall(r'N71_PCIE_SCAN_TARGET_PREPARED error=(-?\d+) pending=(\d+) prepared=(\d+); no retrain', text)
            == [('0', '1', '1')], 'Successful target prepare required')
    return n71_scan_result.parse(normalize(text))
