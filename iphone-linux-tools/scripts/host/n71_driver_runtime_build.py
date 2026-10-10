"""Select the qualified runtime caller and WCC stack against the same kernel base."""
import hashlib
import re
import n71_driver_modules as wlan
import n71_driver_runtime_stage as native
import n71_iommu_build as iommu
import n71_resource_result as resources

INPUT_PATHS_SHA256 = 'bea3f73047748edea1914cc070d6d04733304fefc8eb358ba09d8e62b298586e'
SCOPE = {
    'default_driver_runtime': False,
    'automatic_prepare_or_firmware_load': False,
    'actions': ['driver-' + name for name in native.ACTIONS],
    'cleanup_before': ['manual_msi', 'pci_consumers', 'dart_provider', 'reset', 'power'],
    'partial_owners': ['active', 'root_reference', 'endpoint_reference', 'pm_usage', 'root_override', 'endpoint_override'],
    'driver_status_fields': list(native.result.FIELDS),
    'publication_is_intent_only': True,
    'first_async_error_preserved': True,
    'getter_has_no_effects': True,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inputs(root, proof):
    records = proof.get('inputs')
    require(type(proof.get('input_count')) is int and proof['input_count'] == 69
        and isinstance(records, dict) and len(records) == 69 and all(isinstance(name, str) for name in records),
        'Runtime caller input set differs')
    require(hashlib.sha256('\n'.join(sorted(records)).encode()).hexdigest() == INPUT_PATHS_SHA256,
        'Runtime caller compiled input paths differ')
    pattern = r'(?:phone/kernel/n71-[a-z0-9-]+\.(?:c|h)|tests/(?:n71_[a-z0-9_]+\.(?:c|h)|test_n71_[a-z0-9_]+\.py))'
    for name, record in records.items():
        require(re.fullmatch(pattern, name) is not None and isinstance(record, dict)
            and set(record) == {'bytes', 'sha256'} and type(record['bytes']) is int and 0 < record['bytes'] <= 2 * 1024 * 1024
            and isinstance(record['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', record['sha256']),
            'Runtime caller input path or record differs')
        path = root / name
        require(path.resolve() == root.resolve() / name and path.is_file() and not path.is_symlink() and path.stat().st_size == record['bytes'],
            'Runtime caller input file or bytes changed')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], 'Runtime caller input content changed')


def qualified(root, request):
    require(isinstance(request, dict) and set(request) == {'release', 'pcie_sha256'} and request['release'] == wlan.RELEASE
        and isinstance(request['pcie_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', request['pcie_sha256']),
        'Runtime caller selection must be explicit')
    release = request['release']; parent = iommu.qualified(root, release=release)
    outputs = iommu.image_record(root, release=release)
    proof = iommu.evidence(root, 'n71-brcmfmac-caller-qualified.json')
    require(type(proof.get('format')) is int and proof['format'] == 1
        and proof.get('status') == 'runtime_caller_qualified_host_journal_firmware_energy_and_physical_activation_pending'
        and proof.get('input_hashes_verified_on_vm_and_mac') is True and proof.get('module_bytes_and_hash_verified_on_mac') is True,
        'Runtime caller is not qualified')
    scope = proof.get('scope')
    require(isinstance(scope, dict) and scope == SCOPE
        and all(type(scope[name]) is bool for name in SCOPE if type(SCOPE[name]) is bool), 'Runtime caller scope widened')
    gates = proof.get('gates')
    require(isinstance(gates, dict) and all(isinstance(gates.get(platform), dict)
        and type(gates[platform].get('total_cases')) is int and gates[platform]['total_cases'] == 575
        and type(gates[platform].get('total_assertion_mutations')) is int and gates[platform]['total_assertion_mutations'] == 455
        for platform in ('mac', 'ubuntu_arm64')), 'Runtime caller platform qualification differs')
    baseline = parent['baseline_sha256']
    preserved = {'source_commit': parent['source_commit'], 'tracked_patch_sha256': parent['original_tracked_patch_sha256'],
        'config_sha256': baseline['.config'], 'image_sha256': outputs['Image']['sha256'], 'exports_sha256': baseline['vmlinux.symvers']}
    require(proof.get('source_commit') == parent['source_commit'] and proof.get('preserved_kernel') == preserved,
        'Runtime caller and qualified kernel base differ')
    inputs(root, proof)
    record = proof.get('module')
    require(isinstance(record, dict) and record.get('elf64_aarch64') is True
        and type(record.get('bytes')) is int and 64 <= record['bytes'] <= 256 * 1024
        and record.get('sha256') == request['pcie_sha256']
        and record.get('vermagic') == release + ' SMP preempt mod_unload aarch64', 'Runtime caller module identity differs')
    imports, parameters = record.get('imports'), record.get('parameters')
    require(isinstance(imports, list) and len(imports) == 135 and all(isinstance(name, str) for name in imports)
        and imports == sorted(set(imports)) and isinstance(parameters, list) and all(isinstance(name, str) for name in parameters)
        and sum(name.startswith('driver_runtime:') for name in parameters) == 1
        and sum(name.startswith('driver_runtime_status:') for name in parameters) == 1,
        'Runtime caller imports or runtime getter are incomplete')
    drivers = wlan.qualified(root)
    wcc = iommu.evidence(root, 'n71-brcmfmac-pcie-modules-qualified.json').get('baseline')
    require(isinstance(wcc, dict) and wcc.get('source_head') == preserved['source_commit']
        and wcc.get('source_diff_sha256') == preserved['tracked_patch_sha256']
        and all(wcc.get(name) == baseline[name] for name in ('.config', 'vmlinux.symvers'))
        and wcc.get('arch/arm64/boot/Image') == outputs['Image']['sha256']
        and wcc.get('full-link-v1-20261005/Image.gz') == outputs['Image.gz']['sha256'],
        'WCC and runtime caller kernel base differ')
    return {'diagnostic': {key: record[key] for key in ('bytes', 'sha256', 'vermagic')},
        'drivers': drivers, 'kernel_outputs': outputs}


def select(root, request):
    selected = qualified(root, request)
    parent = iommu.qualified(root, release=request['release'])
    records = resources.selected_records(root, release=request['release'], pcie_sha256=parent['module_sha256'], iommu_parent=True)
    records[0].update(selected['diagnostic'], driver_runtime=True)
    return {'diagnostics': records, 'drivers': selected['drivers'], 'kernel_outputs': selected['kernel_outputs']}
