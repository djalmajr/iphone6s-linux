"""Prove one held PCI assignment and its restoration without changing raw logs."""
import json
import re
import n71_resource_readback
import n71_resource_optional
import n71_resource_io16
import n71_resource_pref64
import n71_resource_build
import n71_scan_held_result

FIELDS = ('ready', 'attempted', 'assigned', 'pending', 'claimed', 'active', 'error')
RESULT = (r'N71_PCIE_RESOURCE_RESULT error=(-?\d+) assigned=([01]) pending=([01]) '
          r'claimed=([01]) attempts=(\d+) writes=(\d+); no decode, bind or DMA')
FALSE_LIMITS = ('profile_replaced_or_new_module_loaded_on_phone', 'real_kernel_pci_core_invoked',
                'new_image_built', 'physical_boot_attempted', 'irq_dma_iommu_verified',
                'wifi_verified', 'battery_or_charging_verified',
                'private_payload_dt_identity_keys_snapshot_ids_or_logs_published')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(text, marker, pattern):
    found = list(re.finditer(pattern + r'$', text, re.M))
    require(len(found) == text.count(marker), 'Incomplete ' + marker)
    return found


def live_status(text):
    found = rows(text, 'N71_PCIE_RESOURCES ',
                 r'^N71_PCIE_RESOURCES ready=([01]) attempted=([01]) assigned=([01]) '
                 r'pending=([01]) claimed=([01]) active=([01]) error=(-?\d+)')
    require(len(found) == 1, 'Unique resource getter required')
    state = dict(zip(FIELDS, map(int, found[0].groups())))
    require(-4095 <= state['error'] <= 0, 'Resource getter error differs')
    return state


def event(text, *, readback_required=False, optional_required=False, io16_required=False, pref64_required=False):
    found = rows(text, 'N71_PCIE_RESOURCE_RESULT ', RESULT)
    require(len(found) <= 1, 'Assignment must not repeat')
    if not found:
        n71_resource_readback.parse(text, None, required=readback_required)
        n71_resource_optional.parse(text, None, required=optional_required)
        n71_resource_io16.parse(text, None, required=io16_required)
        n71_resource_pref64.parse(text, None, required=pref64_required)
        return None
    values = tuple(map(int, found[0].groups()))
    error, assigned, pending, claimed, attempts, writes = values
    require(-4095 <= error <= 0 and 0 <= writes <= attempts <= 64, 'Assignment error/budget differs')
    require(not claimed or pending, 'Claimed window lacks captured rollback')
    require(claimed or attempts == 0, 'Allocation attempts require the claimed window')
    require((error == 0 and (assigned, pending, claimed) == (1, 1, 1) and writes > 0)
            or (error < 0 and assigned == 0), 'Assignment result state differs')
    require(text.index('N71_PCIE_SESSION_HELD ') < found[0].start(), 'Assignment precedes held acquisition')
    result = dict(zip(('error', 'assigned', 'pending', 'claimed', 'attempts', 'writes'), values))
    proof = dict(result)
    optional = n71_resource_optional.parse(text, result, required=optional_required)
    if optional is not None:
        proof['optional_windows'] = optional
    io16 = n71_resource_io16.parse(text, proof, required=io16_required)
    if io16 is not None:
        proof['io16_upper'] = io16
    pref64 = n71_resource_pref64.parse(text, proof, required=pref64_required)
    if pref64 is not None:
        proof['pref64_disable'] = pref64
    readback = n71_resource_readback.parse(text, proof, required=readback_required)
    if readback is not None:
        result['write_readback'] = readback
    if optional is not None:
        result['optional_windows'] = optional
    if io16 is not None:
        result['io16_upper'] = io16
    if pref64 is not None:
        result['pref64_disable'] = pref64
    return result


def outcome(text):
    state = live_status(text)
    action = rows(text, 'N71_PCIE_RESOURCE_ACTION ', r'^N71_PCIE_RESOURCE_ACTION exit=(\d+)')
    require(len(action) == 1 and 0 <= int(action[0].group(1)) <= 255, 'Complete action exit required')
    result = event(text)
    error = result['error'] if result else state['error']
    require(state == dict(ready=1, attempted=int(result is not None),
                          assigned=int(error == 0), pending=result['pending'] if result else 0,
                          claimed=result['claimed'] if result else 0, active=0, error=error),
            'Live assignment and kernel result differ')
    require((int(action[0].group(1)) == 0) == (error == 0), 'Action exit and assignment error differ')
    require(result is not None or error < 0, 'Missing assignment proof')
    require(text.count('N71_PCIE_RESOURCE_') == 1 + int(result is not None),
            'Assignment already restored or contains unknown events')
    n71_scan_held_result.parse(text, primary_error=error)
    refusals = rows(text, 'N71_PCIE_SCAN_WRITE_REFUSED ',
                    r'N71_PCIE_SCAN_WRITE_REFUSED bus=\d+ devfn=[0-9a-f]{2} where=[0-9a-f]{3} '
                    r'size=[124] value=[0-9a-f]{8} error=(-\d+)')
    require(not refusals or (result is not None and error < 0
                            and all(int(row.group(1)) == error
                                    and text.index('N71_PCIE_SESSION_HELD ') < row.start()
                                    < text.index('N71_PCIE_RESOURCE_RESULT ') for row in refusals)),
            'Assignment refusal and first error differ')
    return {'error': error, 'action_exit': int(action[0].group(1)), 'event': result,
            'assignment_verified': error == 0, 'early_refusal': result is None}


def cleanup(text, assignment=None):
    error = assignment['error'] if assignment else 0
    require(type(error) is int and -4095 <= error <= 0, 'Invalid assignment primary error')
    result = event(text)
    require(result == (assignment['event'] if assignment else None), 'Assignment history changed')
    state = live_status(text)
    require(state == dict.fromkeys(FIELDS, 0) | {'error': error}, 'Resource ownership still pending')
    base = n71_scan_held_result.cleanup(text, primary_error=error)
    restored = rows(text, 'N71_PCIE_RESOURCE_RESTORED ',
                    r'N71_PCIE_RESOURCE_RESTORED error=(-?\d+) pending=([01])')
    released = rows(text, 'N71_PCIE_RESOURCE_WINDOW_RELEASED ',
                    r'N71_PCIE_RESOURCE_WINDOW_RELEASED claimed=0')
    require(text.count('N71_PCIE_RESOURCE_') == int(result is not None) + len(restored) + len(released),
            'Unknown assignment cleanup event')
    removed = rows(text, 'N71_PCIE_SCAN_BUS_REMOVED ',
                   r'N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=(-?\d+)')
    configs = rows(text, 'N71_PCIE_SCAN_CONFIG_RESTORED ',
                   r'N71_PCIE_SCAN_CONFIG_RESTORED error=(-?\d+); decode/readback checked')
    pending = bool(result and result['pending'])
    claimed = bool(result and result['claimed'])
    if pending:
        require(restored and restored[-1].groups() == ('0', '0')
                and all(-4095 <= int(row.group(1)) < 0 and row.group(2) == '1' for row in restored[:-1]),
                'Final extra config restore required')
        require(len(removed) == 1 and configs
                and removed[0].start() < restored[0].start()
                and restored[-1].start() < configs[0].start(), 'Extra restore order differs')
    else:
        require(not restored, 'Unexpected extra rollback owner')
    if claimed:
        pme = rows(text, 'N71_PCIE_SCAN_PME_RESTORED ',
                   r'N71_PCIE_SCAN_PME_RESTORED error=(-?\d+) pending=([01]); no W1C')
        require(len(released) == 1 and configs and pme
                and configs[-1].start() < released[0].start() < pme[0].start(),
                'Release the window after generic config and before PME')
    else:
        require(not released, 'Unexpected window claim release')
    if assignment:
        require(base['held_acquired'] and len(removed) == 1 and -4095 <= base['stop_error'] <= 0,
                'Assignment cleanup lacks a held bus or valid stop error')
        if result and error:
            require(base['stop_error'] == error, 'Assignment stop error lost')
        elif result:
            refusals = rows(text, 'N71_PCIE_SCAN_WRITE_REFUSED ',
                            r'N71_PCIE_SCAN_WRITE_REFUSED bus=\d+ devfn=[0-9a-f]{2} where=[0-9a-f]{3} '
                            r'size=[124] value=[0-9a-f]{8} error=(-\d+)')
            require(all(row.start() > text.index('N71_PCIE_RESOURCE_RESULT ') for row in refusals),
                    'A successful assignment cannot follow a refused write')
    return dict(base, resource_cleanup_verified=True, assignment_error=error)


def selected_records(root, *, release, pcie_sha256=None, iommu_parent=False):
    require(type(iommu_parent) is bool and (not iommu_parent or pcie_sha256 is not None),
            'IOMMU resources require explicit boolean and module hash')
    previous = n71_scan_held_result.selected_records(root, release=release)
    evidence = json.loads((root / 'docs/evidence/n71-pci-resource-assignment.json').read_text())
    require(type(evidence.get('format')) is int and evidence['format'] == 1, 'Assignment evidence format differs')
    contract = evidence['contract']
    flags = ('assignment_explicit_and_same_boot', 'scan_hold_and_live_bus_required',
             'module_reset_four_power_domains_retained', 'session_mutex_and_temporary_pin',
             'no_rescan_or_bind_enable_dma', 'mem32_claimed_in_iomem_before_allocator',
             'topology_layout_resource_parent_bounds_alignment_translation_and_readback_verified',
             'first_error_retained_and_ealready_nonfatal', 'removed_bus_never_assigned_even_with_pending_claim',
             'closed_phase_and_bus_removal_before_restore',
             'extra_then_generic_config_restore_before_empty_window_release',
             'cleanup_failure_retains_bridge_and_owners')
    require(all(contract.get(name) is True for name in flags)
            and contract.get('getter_fields') == list(FIELDS), 'Assignment contract differs')
    build = evidence['real_module_build']
    require(type(build.get('exit_code')) is int and build['exit_code'] == 0
            and build.get('release') == release
            and all(build.get(name) is True for name in ('werror', 'modpost_passed',
                    'elf_vermagic_verified', 'source_config_image_exports_preserved')),
            'Qualified assignment module build required')
    require(evidence['limits'].get('adapter_and_caller_integrated') is True
            and all(evidence['limits'].get(name) is False for name in FALSE_LIMITS), 'Assignment scope differs')
    interface = evidence['module_interface']
    require(interface.get('allocator_exports_linked') == ['pci_bus_size_bridges', 'pci_bus_assign_resources',
                                                        'request_resource', 'release_resource']
            and all(sum(row.startswith(name + ':') for row in interface['parameters']) == 1
                    for name in ('action', 'resources', 'held', 'status')), 'Assignment module interface differs')
    records = [dict(build['modules'][name], module=name)
               for name in ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')]
    require(all(type(row.get('bytes')) is int and 64 <= row['bytes'] <= 256 * 1024
                and isinstance(row.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                and row.get('vermagic') == release + ' SMP preempt mod_unload aarch64' for row in records),
            'Assignment module bytes/hash/ABI differ')
    require(records[1] == previous[1], 'Assignment REG_ON differs from qualified held profile')
    if iommu_parent:
        return n71_resource_build.select(root, records, release=release, pcie_sha256=pcie_sha256, iommu_parent=True)
    if pcie_sha256 is None or pcie_sha256 == records[0]['sha256']:
        return records
    return n71_resource_build.select(root, records, release=release, pcie_sha256=pcie_sha256)
