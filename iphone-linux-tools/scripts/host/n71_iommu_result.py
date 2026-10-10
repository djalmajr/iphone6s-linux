"""Collect software MSI/OF/core association without claiming IRQ or DMA delivery."""
import re
import n71_dart_cycle_result
import n71_driver_runtime_result
import n71_driver_runtime_stage
import n71_iommu_build
import n71_msi_allocation_result
import n71_resource_result
import n71_scan_held_result
import n71_scan_target_result

PCIE = '/sys/module/n71_pcie_diagnostic/parameters/'
MSI_FIELDS = ('requested', 'ready', 'held', 'associated', 'owner', 'domain', 'mappings', 'child', 'session_error')
IOMMU_FIELDS = ('requested', 'ready', 'held', 'owner', 'available', 'mapped', 'observed', 'map_checked', 'session_error')
MSI_ACTIVE = dict(zip(MSI_FIELDS, (1, 1, 1, 1, 1, 1, 0, 0, 0)))
IOMMU_ACTIVE = dict(zip(IOMMU_FIELDS, (1, 1, 1, 1, 1, 1, 2, 1, 0)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def capable(session):
    value = getattr(session, 'iommu_parent', False)
    require(type(value) is bool, 'IOMMU selection must be an exact boolean')
    return value


def selected(session, root):
    if not capable(session):
        return
    require(session.scan_hold and session.resource_capable
            and session.release == n71_scan_held_result.RELEASE, 'IOMMU requires the held resource power2 session')
    build = n71_iommu_build.qualified(root, release=session.release)
    records = [record for record, _ in session.modules if record['module'] == 'n71-pcie-diagnostic.ko']
    require(len(records) == 1 and records[0]['sha256'] == build['module_sha256']
            and type(records[0]['bytes']) is int and records[0]['bytes'] == build['module_bytes']
            and records[0]['vermagic'] == build['vermagic']
            == session.release + ' SMP preempt mod_unload aarch64', 'Selected IOMMU module identity differs')


def getter(session):
    if not capable(session):
        return ''
    return ('printf "N71_PCIE_MSI "; cat ' + PCIE + 'msi; '
            'printf "N71_PCIE_IOMMU "; cat ' + PCIE + 'iommu; '
            'printf "N71_HELD_PARAM msi_parent="; cat ' + PCIE + 'msi_parent; '
            'printf "N71_HELD_PARAM iommu_parent="; cat ' + PCIE + 'iommu_parent; '
            + n71_msi_allocation_result.getter() + n71_driver_runtime_result.getter())


def live(text):
    states = []
    for marker, fields in (('N71_PCIE_MSI ', MSI_FIELDS), ('N71_PCIE_IOMMU ', IOMMU_FIELDS)):
        pattern = '^' + marker + ' '.join(name + r'=(-?\d+)' for name in fields)
        row = n71_scan_held_result.unique(text, marker, pattern)
        state = dict(zip(fields, map(int, row.groups())))
        require(all(value in (0, 1) for name, value in state.items()
                    if name not in ('mappings', 'observed', 'session_error'))
                and -4095 <= state['session_error'] <= 0, 'IOMMU getter values differ')
        states.append(state)
    msi, iommu = states
    require(0 <= msi['mappings'] <= 8 and 0 <= iommu['observed'] <= 2,
            'Association getter budget differs')
    require(all(msi[key] == iommu[key] for key in ('requested', 'ready', 'held', 'session_error')),
            'MSI and IOMMU live state disagree')
    require(not iommu['map_checked'] or all(iommu[key] for key in ('held', 'owner', 'available', 'mapped'))
            and iommu['observed'] == 2, 'Checked map lacks its retained owners')
    require(not iommu['mapped'] or (iommu['available'] and iommu['owner']), 'Map lacks an available owner')
    return {'msi': msi, 'iommu': iommu}


def snapshot(session, text, present):
    if not capable(session) or not present:
        return
    state = live(text)
    for name in ('msi_parent', 'iommu_parent'):
        row = n71_scan_held_result.unique(text, 'N71_HELD_PARAM ' + name + '=',
                                        '^N71_HELD_PARAM ' + name + r'=([YN])')
        require(row.group(1) == 'Y', 'Held IOMMU immutable selection changed')
    require(state['iommu']['requested'] == 1
            and state['iommu']['held'] == n71_scan_held_result.live_held(text), 'IOMMU bus selection differs')
    caller = n71_scan_target_result.live_status(text)
    require(state['iommu']['ready'] == caller['ready']
            and state['iommu']['session_error'] == caller.get('cleanup_error', 0), 'IOMMU and caller state disagree')
    n71_msi_allocation_result.snapshot(text, caller, state['iommu']['held'])
    n71_driver_runtime_result.snapshot(session, text, {'caller': caller, 'held': state['iommu']['held']})


def dma_topology(text):
    marker = 'N71_PCIE_SCAN_DMA '
    suffix = '; public topology/source, read-only, no DMA'
    rows = list(re.finditer(marker + r'bus=(\d+) devfn=([0-9a-f]{2}) rid=([0-9a-f]{4}) '
                          r'aliases-inferred=(\d+) group=(\d+) streaming=([0-9a-f]{16}) '
                          r'coherent=([0-9a-f]{16})' + re.escape(suffix) + r'$', text, re.M))
    require(len(rows) == text.count(marker) == 2
            and [row.groups()[:3] for row in rows] == [('0', '08', '0008'), ('1', '00', '0100')],
            'Exact ordered DMA topology required')
    root, endpoint = [row.groups() for row in rows]
    require(root[3] == '1' and endpoint[3] in ('1', '2'), 'Inferred alias set differs')
    require(root[4] == endpoint[4] and 0 <= int(root[4]) <= 2147483647, 'Shared IOMMU group differs')
    require(all(row[5:] == ('00000000ffffffff', '00000000ffffffff') for row in (root, endpoint)),
            'Observed streaming/coherent DMA masks differ')
    return {'requester_ids': [8, 256], 'group_id': int(root[4]), 'mask_bits': 32,
            'root_aliases_inferred': 1, 'endpoint_aliases_inferred': int(endpoint[3]),
            'aliases_inferred_from_fixed_source': True, 'physical_translation_verified': False}, rows


def acquisition(text):
    n71_scan_held_result.acquisition(text)
    dma, dma_rows = dma_topology(text)
    provider = n71_scan_held_result.unique(text, 'N71_DART_CYCLE_PROVIDER ',
        r'N71_DART_CYCLE_PROVIDER bound=1 irq-hwirq=248 mapping-new=([01]); no DMA attachment')
    lease = n71_scan_held_result.unique(text, 'N71_DART_LEASE_ACQUIRE ',
        r'N71_DART_LEASE_ACQUIRE error=0 running=1 pending=1; no DMA attachment')
    scans = []
    for marker, suffix in (('N71_PCIE_SCAN_MSI ', ' inherited=1; no IRQ allocation'),
                          ('N71_PCIE_SCAN_IOMMU ', ' map_sid=0 translated=1; OF map and core domain, no private SID readback')):
        rows = list(re.finditer(marker + r'bus=(\d+) devfn=([0-9a-f]{2})' + re.escape(suffix) + r'$', text, re.M))
        require(len(rows) == text.count(marker) == 2
                and [row.groups() for row in rows] == [('0', '08'), ('1', '00')],
                'Exact ordered root/endpoint association required')
        scans.append(rows)
    devices = list(re.finditer(r'N71_PCIE_SCAN_DEVICE bus=(\d+) devfn=([0-9a-f]{2}) .*$', text, re.M))
    require(len(devices) == 2 and [row.groups() for row in devices] == [('0', '08'), ('1', '00')],
            'Association device records differ')
    held = n71_scan_held_result.unique(text, 'N71_PCIE_SESSION_HELD ', n71_scan_held_result.SESSION_PATTERN)
    positions = [provider.start(), lease.start()]
    for index in range(2):
        positions += [scans[0][index].start(), dma_rows[index].start(),
                      scans[1][index].start(), devices[index].start()]
    positions.append(held.start())
    require(positions == sorted(set(positions)), 'Provider/association publication order differs')
    return {'observed_devices': len(scans[1]), 'software_association_observed': True, 'dma_topology': dma,
            'irq_delivery_verified': False, 'dma_translation_verified': False,
            'wifi_verified': False, 'battery_or_charging_verified': False}


def retained(session, text):
    if not capable(session):
        return
    snapshot(session, text, True)
    initial = {'msi': MSI_ACTIVE, 'iommu': IOMMU_ACTIVE}
    exposed = n71_driver_runtime_result.capable(session) and n71_driver_runtime_result.association(
        session, text, {'published': driver_published(session), 'actual': live(text), 'initial': initial})
    require(exposed or live(text) == initial, 'Retained MSI/IOMMU association incomplete')
    require('N71_DART_CYCLE_RELEASED ' not in text and 'N71_DART_LEASE_CLEANUP ' not in text,
            'Retained provider already released or cleanup attempted')
    result = acquisition(text)
    saved = session.result.get('iommu_association')
    require(saved is None or saved == result, 'Saved IOMMU summary differs')
    session.result['iommu_association'] = result


def driver_published(session):
    entries = n71_driver_runtime_stage.fields(session)['driver_runtime_journal']
    return any(entry['action'] == 'publish' and entry['completion'] is not None
               and entry['completion']['native']['published'] == 1 for entry in entries)


def resume(session, live_text, prior):
    if not capable(session):
        return
    if n71_driver_runtime_result.capable(session):
        boot = session.result.get('boot_id', '')
        require(re.fullmatch(n71_driver_runtime_stage.BOOT, boot), 'Runtime continuation lacks its boot identity')
        for text in (prior, live_text):
            row = n71_scan_held_result.unique(text, 'N71_BOOT_ID ', '^N71_BOOT_ID (' + n71_driver_runtime_stage.BOOT + ')$')
            require(row.group(1) == boot, 'Driver continuation belongs to another boot')
            snapshot(session, text, True)
        n71_driver_runtime_result.association_resume(session, {
            'published': driver_published(session), 'current': live_text, 'prior': prior,
            'before': live(prior), 'after': live(live_text), 'initial': {'msi': MSI_ACTIVE, 'iommu': IOMMU_ACTIVE}})
        return
    if 'N71_PCIE_IOMMU ' in live_text or 'N71_PCIE_IOMMU ' in prior:
        require(live(live_text) == live(prior), 'Live IOMMU ownership changed; no cleanup attempted')
    n71_msi_allocation_result.resume(live_text, prior)
    n71_driver_runtime_result.resume(session, live_text, prior)


def saved(session, data, text):
    require(data.get('iommu_parent', False) is capable(session), 'Saved IOMMU mode changed')
    if capable(session):
        snapshot(session, text, 'N71_PCIE_IOMMU ' in text)
        expected = acquisition(text) if 'N71_PCIE_SESSION_HELD ' in text else None
        require(data['result'].get('iommu_association') == expected, 'Saved association differs from checkpoint')


def pre_scan_cleanup(session, text):
    if not capable(session) or 'N71_PCIE_SCAN_' in text:
        return None
    caller = n71_scan_target_result.live_status(text)
    primary = caller.get('primary_error', 0)
    if caller['ready'] != 1 or primary >= 0 or 'N71_DART_LEASE_ACQUIRE ' not in text:
        return None
    cleanup(session, text)
    acquired = n71_scan_held_result.unique(text, 'N71_DART_LEASE_ACQUIRE ',
        r'N71_DART_LEASE_ACQUIRE error=(-?\d+) running=0 pending=([01]); no DMA attachment')
    require(int(acquired.group(1)) == primary, 'Pre-scan provider and caller failure differ')
    require(session.resource_attempted is False and session.resource_assignment is None
            and 'N71_PCIE_RESOURCE_' not in text, 'Pre-scan failure cannot own an assignment')
    import n71_resource_stage
    n71_resource_stage.verify_readback(session, text)
    require(n71_resource_stage.n71_resource_result.live_status(text)
            == dict.fromkeys(n71_resource_stage.n71_resource_result.FIELDS, 0) | {'error': primary},
            'Pre-scan resources still owned')
    finished = list(re.finditer(n71_scan_held_result.CLEANUP_PATTERN + r'$', text, re.M))
    require(len(finished) == text.count('N71_PCIE_SESSION_CLEANUP ') and finished
            and tuple(map(int, finished[-1].groups())) == (0, 0, 0, 0, 0, 0, 0, primary)
            and all(int(row.group(1)) < 0 and row.group(2) == '1' and int(row.group(8)) == primary
                    for row in finished[:-1]), 'Pre-scan caller release incomplete')
    reset = n71_scan_held_result.unique(text, 'N71_PCIE_RESET_RESTORED ',
        r'N71_PCIE_RESET_RESTORED asserted=1 readback=1')
    power = n71_scan_held_result.unique(text, 'N71_PCIE_POWER_RELEASED ',
        r'N71_PCIE_POWER_RELEASED powered=0 attached=0')
    require(text.index('N71_DART_CYCLE_RELEASED ') < reset.start() < power.start() < finished[-1].start(),
            'Pre-scan provider/reset/power release order differs')
    return {'stop_error': 0, 'held_acquired': False, 'resource_cleanup_verified': True, 'assignment_error': 0}


def unbound_prepare_failure(text, caller):
    if caller['ready'] or 'N71_PCIE_SCAN_DART_PREPARED ' not in text:
        return None
    n71_scan_target_result.cleanup(text)
    prepared = n71_scan_held_result.unique(text, 'N71_PCIE_SCAN_DART_PREPARED ',
        r'N71_PCIE_SCAN_DART_PREPARED error=(-?\d+) available=0 mapped=0; before PCI publication')
    primary = int(prepared.group(1))
    scan = n71_scan_target_result.n71_scan_result.summary(n71_scan_target_result.normalize(text))
    require(-4095 <= primary < 0 and scan['error'] == primary
            and all(scan[name] == 0 for name in ('devices', 'endpoints', 'attempts', 'writes', 'refusals')),
            'Unbound DART prepare requires a matching negative unpublished scan')
    require('N71_PCIE_SESSION_HELD ' not in text and 'N71_PCIE_SCAN_BUS_REMOVED ' not in text,
            'Unbound DART prepare cannot own a published bus')
    require('N71_DART_LEASE_ACQUIRE ' in text, 'Unbound DART prepare lacks its provider lease')
    finished = list(re.finditer(n71_scan_held_result.CLEANUP_PATTERN + r'$', text, re.M))
    require(len(finished) == text.count('N71_PCIE_SESSION_CLEANUP ') == 1
            and tuple(map(int, finished[0].groups())) == (0, 0, 0, 0, 0, 0, 0, primary),
            'Unbound DART prepare requires matching complete caller cleanup')
    return prepared


def cleanup(session, text):
    if not capable(session):
        return None
    snapshot(session, text, True)
    caller = n71_scan_target_result.live_status(text)
    require(live(text) == {'msi': dict.fromkeys(MSI_FIELDS, 0) | {'requested': 1, 'ready': caller['ready']},
                           'iommu': dict.fromkeys(IOMMU_FIELDS, 0) | {'requested': 1, 'ready': caller['ready']}},
            'MSI/IOMMU ownership still pending')
    require(n71_scan_target_result.is_clean(caller), 'IOMMU caller cleanup incomplete')
    unbound = unbound_prepare_failure(text, caller)
    if 'N71_PCIE_SESSION_HELD ' in text:
        result = acquisition(text)
        require(session.result.get('iommu_association') in (None, result), 'Cleanup association history changed')
    proof = {'software_ownership_released': True, 'physical_of_unmap_readback_verified': False,
             'irq_delivery_verified': False, 'dma_translation_verified': False}
    if 'N71_DART_LEASE_ACQUIRE ' in text:
        acquired = n71_scan_held_result.unique(text, 'N71_DART_LEASE_ACQUIRE ',
            r'N71_DART_LEASE_ACQUIRE error=(-?\d+) running=([01]) pending=([01]); no DMA attachment')
        error, running, pending = map(int, acquired.groups())
        require((error == 0 and running == pending == 1) or (-4095 <= error < 0 and running == 0),
                'DART acquisition error/readiness differs')
        require(unbound is None or (error, running, pending) == (0, 1, 1),
                'Unbound DART prepare requires a running provider lease')
        require('N71_PCIE_SESSION_HELD ' in text or error < 0 or caller.get('primary_error', 0) < 0 or unbound is not None,
                'Incomplete association lacks a negative caller/provider proof')
        released = n71_scan_held_result.unique(text, 'N71_DART_CYCLE_RELEASED ',
            r'N71_DART_CYCLE_RELEASED device=0 mapping-new=0 claimed=0 mapped=0')
        lease = list(re.finditer(r'N71_DART_LEASE_CLEANUP error=(-?\d+) pending=([01]) index=(\d+) '
            r'device=([01]) mapping-new=([01]) claimed=([01]) mapped=([01]); ownership retained until restore$', text, re.M))
        final = lease[-1].groups() if lease else None
        require(len(lease) == text.count('N71_DART_LEASE_CLEANUP ') and final
                and final[:5] == ('0', '0', '16' if pending else '0', '0', '0')
                and (not pending or final[5:] == ('1', '1'))
                and all(-4095 <= int(row.group(1)) < 0 for row in lease[:-1]), 'Final DART lease restore required')
        configs = list(re.finditer(r'N71_PCIE_SCAN_CONFIG_RESTORED error=(-?\d+); decode/readback checked$', text, re.M))
        if 'N71_PCIE_SCAN_BUS_REMOVED ' in text:
            removed = n71_scan_held_result.unique(text, 'N71_PCIE_SCAN_BUS_REMOVED ',
                r'N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=(-?\d+)')
            require(removed.start() < lease[0].start(), 'DART stop precedes consumer removal')
        require(lease[-1].start() < released.start(), 'Provider release precedes lease restoration')
        if unbound is not None:
            reset = n71_scan_held_result.unique(text, 'N71_PCIE_RESET_RESTORED ',
                r'N71_PCIE_RESET_RESTORED asserted=1 readback=1')
            power = n71_scan_held_result.unique(text, 'N71_PCIE_POWER_RELEASED ',
                r'N71_PCIE_POWER_RELEASED powered=0 attached=0')
            require(len(configs) == text.count('N71_PCIE_SCAN_CONFIG_RESTORED ') == 1
                    and unbound.start() < configs[0].start()
                    and configs[-1].start() < lease[0].start()
                    and released.start() < reset.start() < power.start() < text.index('N71_PCIE_SESSION_CLEANUP '),
                    'Unpublished scan config/provider/reset/power release order differs')
        else:
            require(not configs or released.start() < configs[0].start(),
                    'Provider release and host restore order differs')
        if 'N71_DART_CYCLE_RESULT ' in text:
            cycle = n71_dart_cycle_result.summary(text)
            require(text.count('N71_DART_CYCLE_RESULT ') == 1, 'Unique complete DART cycle required')
            if cycle['control_changed']:
                assignment = n71_resource_result.event(text)
                first_error = (assignment['error'] if assignment else 0) or cycle['error']
                require(cycle == dict(error=-5, snapshots=4, reads=152, guards=156, quiet=17, writes=16,
                                      attempted=1, stopped=1, restored=1, control_changed=1)
                        and (error, running, pending) == (0, 1, 1)
                        and 'N71_PCIE_SESSION_HELD ' in text
                        and caller.get('primary_error', 0) == first_error,
                        'Changed DART control requires complete restored negative operation proof')
                n71_dart_cycle_result.cleanup(text)
                require(lease[-1].start() < text.index('N71_DART_CYCLE_RESULT ') < released.start(),
                        'DART operation result must follow restore and precede provider release')
                proof['provider_operation_error'] = cycle['error']
    return proof
