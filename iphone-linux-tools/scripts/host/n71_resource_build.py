"""Select an explicitly identified, qualified readback module beside the legacy build."""
import hashlib
import json
import re

FLAGS = ('same_write_permissions', 'existing_io_only', 'first_failure_retained', 'failed_callback_not_valid',
         'raw_callback_errors_preserved', 'verified_write_counter_only', 'one_record_before_result',
         'rollback_preserves_failure')
OPTIONAL_FLAGS = ('core_probe_flags_required', 'absent_resources_empty', 'capture_zero_baseline',
                 'live_zero_check', 'absent_requests_no_hardware_write', 'other_readback_strict',
                 'report_unique_before_readback', 'positive_disable_noops_required')
IO16_FLAGS = ('core_present_standard_window', 'both_type_fields_io16', 'coherent_optional_resource',
              'zero_capture_baseline', 'live_lower_zero_or_disabled', 'live_upper_zero',
              'temporary_upper_request_only', 'no_hardware_write', 'lower_readback_strict',
              'report_between_optional_and_readback', 'positive_noop_required',
              'combined_noop_budget', 'journal_preserves_event', 'legacy_defaults_preserved')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extended_evidence(root, original, request):
    path = root / 'docs/evidence' / request['filename']
    if not path.exists():
        return None
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024,
            'Optional build evidence missing or invalid')
    candidate = json.loads(path.read_text())
    digest = candidate.get('real_module_build', {}).get('modules', {}).get('n71-pcie-diagnostic.ko', {}).get('sha256')
    if digest != request['sha256']:
        return None
    require(candidate.get('base_readback_evidence_sha256') == hashlib.sha256(original.read_bytes()).hexdigest(),
            'Optional build readback base changed')
    if request['io16']:
        base = root / 'docs/evidence/n71-pci-optional-build.json'
        require(base.is_file() and not base.is_symlink() and base.stat().st_size <= 256 * 1024,
                'IO16 optional base missing or invalid')
        require(candidate.get('base_optional_evidence_sha256') == hashlib.sha256(base.read_bytes()).hexdigest(),
                'IO16 optional base changed')
    return candidate


def select(root, previous, *, release, pcie_sha256):
    require(isinstance(pcie_sha256, str) and re.fullmatch(r'[0-9a-f]{64}', pcie_sha256),
            'Explicit qualified PCI module hash required')
    path = root / 'docs/evidence/n71-pci-resource-readback.json'
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024,
            'Qualified readback module evidence missing or invalid')
    evidence = json.loads(path.read_text())
    optional = False
    io16 = False
    if pcie_sha256 != evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']:
        candidate = extended_evidence(root, path, {'filename': 'n71-pci-optional-build.json',
                                                  'sha256': pcie_sha256, 'io16': False})
        if candidate is None:
            candidate = extended_evidence(root, path, {'filename': 'n71-pci-io16-build.json',
                                                      'sha256': pcie_sha256, 'io16': True})
            io16 = candidate is not None
        if candidate is not None:
            evidence, optional = candidate, True
    require(type(evidence.get('format')) is int and evidence['format'] == 1, 'Readback build format differs')
    base = root / 'docs/evidence/n71-pci-resource-assignment.json'
    require(evidence.get('base_assignment_evidence_sha256') == hashlib.sha256(base.read_bytes()).hexdigest(),
            'Readback build assignment base changed')
    require(all(evidence.get('contract', {}).get(name) is True for name in FLAGS), 'Readback build contract differs')
    build = evidence['real_module_build']
    if optional:
        optional_contract = evidence.get('optional_contract', {})
        require(all(optional_contract.get(name) is True for name in OPTIONAL_FLAGS)
                and evidence.get('native_policy_adapter_qualified') is True
                and evidence.get('host_contract_qualified') is True,
                'Qualified optional policy, adapter and host contract required')
        require(build.get('optional_windows_report_compiled') is True
                and build.get('patched_source_files_verified') is True,
                'Optional report and patched source preservation not proved')
    if io16:
        io16_contract = evidence.get('io16_contract', {})
        require(all(io16_contract.get(name) is True for name in IO16_FLAGS),
                'Qualified IO16 policy, adapter and journal contract required')
        require(build.get('io16_upper_report_compiled') is True, 'Compiled IO16 report required')
    require(type(build.get('exit_code')) is int and build['exit_code'] == 0 and build.get('release') == release
            and all(build.get(name) is True for name in ('werror', 'modpost_passed', 'elf_vermagic_verified',
                    'source_config_image_exports_preserved', 'first_write_readback_report_compiled')),
            'Qualified readback build required')
    limits = evidence['limits']
    require(all(limits.get(name) is False for name in ('physical_loaded', 'new_image_built',
                'real_kernel_pci_core_invoked', 'wifi_functional', 'charging_proven', 'private_files_published')),
            'Readback build proof scope differs')
    interface = build['module_interface']
    require(interface.get('allocator_exports_linked') == ['pci_bus_size_bridges', 'pci_bus_assign_resources',
                                                        'request_resource', 'release_resource']
            and all(sum(row.startswith(name + ':') for row in interface['parameters']) == 1
                    for name in ('action', 'resources', 'held', 'status')), 'Readback module interface differs')
    records = [dict(build['modules'][name], module=name)
               for name in ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')]
    require(all(type(row.get('bytes')) is int and 64 <= row['bytes'] <= 256 * 1024
                and isinstance(row.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', row['sha256'])
                and row.get('vermagic') == release + ' SMP preempt mod_unload aarch64' for row in records),
            'Readback module bytes/hash/ABI differ')
    require(records[1] == previous[1], 'Readback build changed the held REG_ON module')
    require(records[0]['sha256'] == pcie_sha256 and records[0]['sha256'] != previous[0]['sha256'],
            'Requested PCI module is not the qualified readback build')
    records[0]['assignment_readback'] = True
    if optional:
        records[0]['assignment_optional_windows'] = True
    if io16:
        records[0]['assignment_io16_upper'] = True
    return records
