"""Validate held PCI ownership separately from completed removal/restoration."""
import json
import re
import n71_scan_pme_result
import n71_scan_result
import n71_scan_target_result

RELEASE = '7.2.0-iphone6s-dart-serdev-power2'
ACTIVE = {'ready': 1, 'retained': 1, 'scan_pending': 1, 'reset_pending': 1,
          'powered': 4, 'attached': 4, 'power_put_pending': 0,
          'primary_error': 0, 'cleanup_error': 0}
SESSION_PATTERN = (r'N71_PCIE_SESSION_HELD retained=([01]) scan_pending=([01]) '
                   r'reset_pending=([01]) powered=([0-4]) attached=([0-4]) '
                   r'power_put_pending=([01]) primary_error=(-?\d+) cleanup_error=(-?\d+); '
                   r'no bind, DMA or radio')
TARGET_PATTERN = (r'N71_PCIE_SCAN_TARGET_PREPARED error=(-?\d+) pending=([01]) '
                  r'prepared=([01]); no retrain')
CLEANUP_PATTERN = (r'N71_PCIE_SESSION_CLEANUP error=(-?\d+) retained=([01]) '
                   r'scan_pending=([01]) reset_pending=([01]) powered=([0-4]) '
                   r'attached=([0-4]) power_put_pending=([01]) primary_error=(-?\d+)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(text, marker, pattern):
    rows = list(re.finditer(pattern + r'$', text, re.M))
    require(len(rows) == text.count(marker) == 1, 'Unique complete ' + marker + ' required')
    return rows[0]


def live_held(text):
    row = unique(text, 'N71_PCIE_HELD ', r'^N71_PCIE_HELD held=([01])$')
    return int(row.group(1))


def acquisition(text):
    held = unique(text, 'N71_PCIE_SCAN_HELD ',
                  r'N71_PCIE_SCAN_HELD devices=2 endpoints=1; no bind, DMA or radio')
    session = unique(text, 'N71_PCIE_SESSION_HELD ', SESSION_PATTERN)
    require(tuple(map(int, session.groups())) == (1, 1, 1, 4, 4, 0, 0, 0),
            'Held caller must retain all acquired owners without errors')
    target = unique(text, 'N71_PCIE_SCAN_TARGET_PREPARED ', TARGET_PATTERN)
    prepared, _ = n71_scan_pme_result.records(text)
    require(target.groups() == ('0', '1', '1') and len(prepared) == 1
            and prepared[0].groups() == ('0', '1', '1'), 'Held TLS and PME preparation required')
    devices = n71_scan_result.device_resources(text)
    require(text.count('N71_PCIE_SCAN_DEVICE ') == 2 and text.count('N71_PCIE_SCAN_BAR ') == 6,
            'Complete held topology and BAR records required')
    require(all(row['command'] == 0 for row in devices['device_details']),
            'Held decode and bus-master must remain clear')
    require(all(row['start'] == 0 for row in devices['bars'])
            and [row['bytes'] for row in devices['bars']] == [0x8000, 0, 0x400000, 0, 0, 0],
            'Measured unassigned N71 BARs required')
    events = [target.start(), prepared[0].start()]
    events += [row.start() for row in re.finditer(r'N71_PCIE_SCAN_DEVICE ', text)]
    events += [row.start() for row in re.finditer(r'N71_PCIE_SCAN_BAR ', text)]
    events += [held.start(), session.start()]
    require(events == sorted(events) and len(events) == len(set(events)),
            'Held acquisition event order differs')
    return {'devices': 2, 'endpoints': 1, **devices}


def parse(text):
    result = acquisition(text)
    forbidden = ('N71_PCIE_SCAN_RESULT ', 'N71_PCIE_SCAN_WRITE_REFUSED ',
                 'N71_PCIE_SCAN_BUS_REMOVED ', 'N71_PCIE_SCAN_CONFIG_RESTORED ',
                 'N71_PCIE_SCAN_PME_RESTORED ', 'N71_PCIE_SCAN_TARGET_RESTORED ',
                 'N71_PCIE_SCAN_CLEANUP ', 'N71_PCIE_SESSION_CLEANUP ',
                 'N71_PCIE_RESET_RESTORED ', 'N71_PCIE_POWER_RELEASED ')
    require(not any(marker in text for marker in forbidden), 'Held acquisition already failed or cleaned up')
    require(live_held(text) == 1, 'Live held bus required')
    state = n71_scan_target_result.live_status(text)
    require(state == ACTIVE, 'Live held caller ownership differs')
    result.update(held_verified=True, caller_state=state,
                  target_prepare_verified=True, pme_prepare_verified=True)
    return result


def cleanup(text):
    require(live_held(text) == 0, 'Bus still held during cleanup')
    if 'N71_PCIE_SCAN_HELD ' not in text:
        n71_scan_pme_result.cleanup(text)
        failed = re.findall(r'N71_PCIE_(?:LINK|INVENTORY|SCAN)_RESULT error=(-?\d+)', text)
        sessions = re.findall(CLEANUP_PATTERN + r'$', text, re.M)
        require(len(sessions) == text.count('N71_PCIE_SESSION_CLEANUP '),
                'Incomplete caller failure before hold')
        caller_failed = (sessions and tuple(map(int, sessions[-1][:7])) == (0, 0, 0, 0, 0, 0, 0)
                         and int(sessions[-1][7]) < 0)
        require(any(int(error) < 0 for error in failed) or caller_failed,
                'Missing negative diagnostic proof before hold')
        return {'stop_error': 0, 'held_acquired': False}
    acquisition(text)
    state = n71_scan_target_result.live_status(text)
    require(state.get('ready') == 1 and state.get('primary_error') == 0
            and n71_scan_target_result.is_clean(state), 'Held caller cleanup incomplete')
    require('N71_PCIE_SCAN_RESULT ' not in text and 'N71_PCIE_SCAN_CLEANUP ' not in text,
            'Held and temporary scan protocols must not be mixed')
    removed = unique(text, 'N71_PCIE_SCAN_BUS_REMOVED ',
                     r'N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=(-?\d+)')
    stop_error = int(removed.group(1))
    require(stop_error <= 0, 'Invalid held stop error')
    configs = list(re.finditer(r'N71_PCIE_SCAN_CONFIG_RESTORED error=(-?\d+); decode/readback checked(?=\n|$)', text))
    require(len(configs) == text.count('N71_PCIE_SCAN_CONFIG_RESTORED ') and configs
            and configs[-1].group(1) == '0'
            and all(int(row.group(1)) < 0 for row in configs[:-1]), 'Final held config restore required')
    require(text.index('N71_PCIE_SESSION_HELD ') < removed.start() < configs[0].start(),
            'Remove the held bus before restoring config')
    prepared, restored = n71_scan_pme_result.records(text)
    n71_scan_pme_result.restore_owned(text, prepared, restored)
    targets = list(re.finditer(r'N71_PCIE_SCAN_TARGET_RESTORED error=(-?\d+) pending=([01]); no retrain(?=\n|$)', text))
    require(len(targets) == text.count('N71_PCIE_SCAN_TARGET_RESTORED ') and targets
            and targets[-1].groups() == ('0', '0')
            and all(int(row.group(1)) < 0 and row.group(2) == '1' for row in targets[:-1]),
            'Final held TLS restore required')
    reset = unique(text, 'N71_PCIE_RESET_RESTORED ',
                   r'N71_PCIE_RESET_RESTORED asserted=1 readback=1')
    power = unique(text, 'N71_PCIE_POWER_RELEASED ',
                   r'N71_PCIE_POWER_RELEASED powered=0 attached=0')
    sessions = list(re.finditer(CLEANUP_PATTERN + r'$', text, re.M))
    require(len(sessions) == text.count('N71_PCIE_SESSION_CLEANUP ') and sessions
            and tuple(map(int, sessions[-1].groups())) == (0, 0, 0, 0, 0, 0, 0, 0)
            and all(int(row.group(1)) < 0 and row.group(2) == '1' and row.group(8) == '0'
                    for row in sessions[:-1]), 'Final held caller cleanup required')
    require(targets[-1].start() < reset.start() < power.start() < sessions[-1].start(),
            'Held TLS, reset, power and caller cleanup order differs')
    refusals = list(re.finditer(r'N71_PCIE_SCAN_WRITE_REFUSED bus=\d+ devfn=[0-9a-f]{2} '
                                r'where=[0-9a-f]{3} size=[124] value=[0-9a-f]{8} error=(-\d+)(?=\n|$)', text))
    require(len(refusals) == text.count('N71_PCIE_SCAN_WRITE_REFUSED '), 'Complete stop refusals required')
    require((not refusals and stop_error == 0)
            or (refusals and stop_error < 0 and int(refusals[0].group(1)) == stop_error
                and all(text.index('N71_PCIE_SESSION_HELD ') < row.start() < removed.start()
                        for row in refusals)), 'Held stop refusal and error differ')
    return {'stop_error': stop_error, 'held_acquired': True}


def selected_records(root, *, release):
    require(release == RELEASE, 'Held scan requires the power2 ABI')
    path = root / 'docs/evidence/n71-pci-held-caller.json'
    evidence = json.loads(path.read_text())
    require(type(evidence.get('format')) is int and evidence.get('format') == 1
            and evidence.get('kernel_release') == release,
            'Held build identity differs')
    api = evidence['api']
    flags = ('requires_explicit_run_enumerate_inventory_host_scan_pme', 'requires_n71',
             'requires_complete_positive_scan_and_live_owned_bus',
             'retains_module_binding_mmio_reset_power', 'held_getter_reads_adapter_under_lock',
             'legacy_status_format_preserved', 'cleanup_action_releases_only_after_owners_finished',
             'negative_scan_not_reported_as_held', 'retry_does_not_scan_or_duplicate_power_put')
    require(api.get('parameter') == 'scan_hold' and api.get('default_enabled') is False
            and api.get('held_getter_mode') == '0400'
            and all(api.get(name) is True for name in flags), 'Held caller contract differs')
    build = evidence['kernel_build']
    require(build.get('werror') is True and build.get('modpost_passed') is True
            and build.get('elf_vermagic_verified') is True
            and build.get('source_config_image_exports_preserved') is True
            and build.get('reg_on_unchanged') is True, 'Qualified held module build required')
    limits = evidence['limits']
    require(limits.get('caller_exposes_hold') is True
            and all(limits.get(name) is False for name in
                    ('resources_assigned', 'pci_bus_add_devices_called', 'enable_device_allowed',
                     'dma_enabled', 'firmware_loaded')), 'Held build scope differs')
    records = [dict(build['modules'][name], module=name)
               for name in ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')]
    require(all(type(row.get('bytes')) is int and 64 <= row['bytes'] <= 256 * 1024
                and isinstance(row.get('sha256'), str)
                and re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                and row.get('vermagic') == release + ' SMP preempt mod_unload aarch64'
                for row in records), 'Held module bytes/hash/ABI differ')
    return records
