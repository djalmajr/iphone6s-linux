"""Require endpoint PME preparation/restoration in the selected retained scan."""
import re
import n71_scan_target_result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def records(text):
    prepared = list(re.finditer(r'N71_PCIE_SCAN_PME_PREPARED error=(-?\d+) pending=([01]) prepared=([01]); no W1C', text))
    restored = list(re.finditer(r'N71_PCIE_SCAN_PME_RESTORED error=(-?\d+) pending=([01]); no W1C', text))
    require(len(prepared) == text.count('N71_PCIE_SCAN_PME_PREPARED ')
            and len(restored) == text.count('N71_PCIE_SCAN_PME_RESTORED '), 'Complete PME records required')
    require(len(prepared) <= 1, 'Unique PME preparation required')
    return prepared, restored


def cleanup(text):
    n71_scan_target_result.cleanup(text)
    prepared, restored = records(text)
    if not prepared:
        require(not restored, 'PME restoration without preparation')
        result = n71_scan_target_result.n71_scan_result.summary(n71_scan_target_result.normalize(text)) if 'N71_PCIE_SCAN_RESULT ' in text else None
        require(result is None or result['error'] < 0, 'Successful scan requires PME preparation')
        return
    error, pending, ready = map(int, prepared[0].groups())
    require(error <= 0 and ((pending, ready) == (1, 1) if error == 0 else ready == 0),
            'PME preparation state differs')
    if not pending:
        require(not restored, 'Unowned PME restoration refused')
        return
    require(restored and restored[-1].groups() == ('0', '0'), 'Final PME restoration required')
    require(all(int(row.group(1)) < 0 and row.group(2) == '1' for row in restored[:-1]), 'PME retry state differs')
    config = list(re.finditer(r'N71_PCIE_SCAN_CONFIG_RESTORED error=0; decode/readback checked', text))
    require(config and config[-1].start() < restored[0].start(), 'Config must be restored before PME')
    removed = list(re.finditer(r'N71_PCIE_SCAN_BUS_REMOVED bus-null=1', text))
    require(not removed or removed[0].start() < restored[0].start(), 'PCI bus must be removed before PME')
    target = list(re.finditer(r'N71_PCIE_SCAN_TARGET_RESTORED ', text))
    require(target and restored[-1].start() < target[0].start(), 'PME must be restored before TLS')
    require(prepared[0].start() < restored[0].start(), 'PME restore precedes preparation')
    device = text.find('N71_PCIE_SCAN_DEVICE ')
    require(device < 0 or prepared[0].start() < device, 'PME must be prepared before PCI scan reports')


def parse(text):
    cleanup(text)
    prepared, _ = records(text)
    require(len(prepared) == 1 and prepared[0].groups() == ('0', '1', '1'),
            'Successful PME preparation required')
    result = n71_scan_target_result.parse(text)
    result['pme_prepare_verified'] = True
    result['pme_cleanup_verified'] = True
    return result
