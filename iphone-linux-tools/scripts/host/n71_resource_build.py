"""Select an explicitly identified, qualified readback module beside the legacy build."""
import hashlib
import json
import re

FLAGS = ('same_write_permissions', 'existing_io_only', 'first_failure_retained', 'failed_callback_not_valid',
         'raw_callback_errors_preserved', 'verified_write_counter_only', 'one_record_before_result',
         'rollback_preserves_failure')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def select(root, previous, *, release, pcie_sha256):
    require(isinstance(pcie_sha256, str) and re.fullmatch(r'[0-9a-f]{64}', pcie_sha256),
            'Explicit qualified PCI module hash required')
    path = root / 'docs/evidence/n71-pci-resource-readback.json'
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024,
            'Qualified readback module evidence missing or invalid')
    evidence = json.loads(path.read_text())
    require(type(evidence.get('format')) is int and evidence['format'] == 1, 'Readback build format differs')
    base = root / 'docs/evidence/n71-pci-resource-assignment.json'
    require(evidence.get('base_assignment_evidence_sha256') == hashlib.sha256(base.read_bytes()).hexdigest(),
            'Readback build assignment base changed')
    require(all(evidence.get('contract', {}).get(name) is True for name in FLAGS), 'Readback build contract differs')
    build = evidence['real_module_build']
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
    return records
