"""Qualify the explicit PMD ABI from real build facts; never operate hardware."""
import hashlib
import json
from pathlib import Path
import re
import n71_iommu_build as iommu
import n71_pmd_source_reference as source_reference

RELEASE = iommu.PMD_RELEASE
LEGACY = '7.2.0-iphone6s-dart-serdev-power2'
SOURCE_PIN = '2a0beffa904a3d440ec1d826ed8789b597f915ca0836df40430ff72c93117781'
INPUTS_PIN = '4e9221335b6f944f99a33fb3172307f612767ff21312b3616abc657b2c991e0f'
I2C = 'phone/kernel/n71-i2c-power-diagnostic.c'
NATIVE = 'n71-brcmfmac-caller-qualified.json'
ABI = ' SMP preempt mod_unload aarch64'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def evidence(root, name):
    path = root / 'docs/evidence' / name
    require(path.resolve() == path, 'PMD evidence aliases refused')
    return iommu.evidence(root, name)


def source_file(root, name, expected):
    path = root / name
    require(isinstance(expected, dict) and set(expected) == {'bytes', 'sha256'}
            and type(expected['bytes']) is int and 0 < expected['bytes'] <= 2 * 1024 * 1024
            and sha(expected['sha256']), 'PMD source record differs')
    require(path.resolve() == path and path.is_file() and not path.is_symlink()
            and path.stat().st_size == expected['bytes']
            and hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256'],
            'PMD compiled source bytes differ')


def native_reference(root, native, manifest, pcie, reuse, kernel, *, source_root):
    import n71_driver_runtime_build as caller
    require(reuse.get('reference_proof') == {'path': 'docs/evidence/' + NATIVE,
            'sha256': hashlib.sha256((root / 'docs/evidence' / NATIVE).read_bytes()).hexdigest()},
            'PMD native reference changed')
    require(native.get('status') == 'runtime_caller_qualified_host_journal_firmware_energy_and_physical_activation_pending'
            and native.get('input_hashes_verified_on_vm_and_mac') is True
            and native.get('module_bytes_and_hash_verified_on_mac') is True
            and native.get('scope') == caller.SCOPE
            and all(type(native['scope'][name]) is bool for name in caller.SCOPE
                    if type(caller.SCOPE[name]) is bool), 'PMD native caller scope differs')
    for platform in ('mac', 'ubuntu_arm64'):
        gate = native.get('gates', {}).get(platform, {})
        require(type(gate.get('total_cases')) is int and gate['total_cases'] == 575
                and type(gate.get('total_assertion_mutations')) is int
                and gate['total_assertion_mutations'] == 455, 'PMD native caller gates differ')
    inputs = native.get('inputs')
    require(type(native.get('input_count')) is int and native['input_count'] == 69
            and isinstance(inputs, dict) and len(inputs) == 69
            and hashlib.sha256('\n'.join(sorted(inputs)).encode()).hexdigest() == caller.INPUT_PATHS_SHA256,
            'PMD native input set differs')
    changed = []
    for name, expected in inputs.items():
        require(re.fullmatch(r'(?:phone/kernel/n71-[a-z0-9-]+\.(?:c|h)|tests/(?:n71_[a-z0-9_]+\.(?:c|h)|test_n71_[a-z0-9_]+\.py))', name),
                'PMD native input path differs')
        current = manifest['inputs'][name] if name == I2C else expected
        source_file(source_root, name, current)
        if current != expected:
            changed.append(name)
    require(changed == [I2C] and reuse.get('changed_previous_input_paths') == changed
            and all(reuse.get(name) is True for name in ('pcie_caller_c_and_all_recorded_headers_unchanged',
                    'pcie_imports_equal_to_previous', 'pcie_parameter_interface_equal_to_previous'))
            and reuse.get('physical_compatibility_proven') is False,
            'PMD caller input reuse scope differs')
    old = native['module']
    imports = pcie.get('imports')
    require(isinstance(imports, list) and len(imports) == 135 and imports == sorted(set(imports))
            and imports == old['imports'] and pcie.get('parameters') == old['parameters'],
            'PMD caller imports or interface changed')
    comparison = reuse['binary_comparison']
    require(comparison.get('old_module_sha256') == old['sha256']
            and comparison.get('new_module_sha256') == pcie['sha256']
            and comparison.get('all_executable_progbits_sections_identical') is True
            and comparison.get('modinfo_diff_is_only_selected_vermagic') is True
            and set(comparison.get('changed_progbits_or_rela_sections', {})) == {'.modinfo'},
            'PMD caller binary reuse differs')
    sections = comparison.get('executable_sections')
    require(isinstance(sections, dict) and len(sections) == 5 and all(
            type(row.get('bytes')) is int and row['bytes'] > 0 and row.get('type') == 1
            and row.get('flags') == 6 and sha(row.get('sha256')) for row in sections.values()),
            'PMD caller executable section proof differs')
    context = reuse['new_kernel_context']
    expected_symbols = dict.fromkeys(('iommu_group_get', 'iommu_group_id', 'iommu_group_put',
                                     'pci_for_each_dma_alias', 'serdev_device_set_stop_bits'), 'T')
    expected_symbols['pci_real_dma_dev'] = 'W'
    expected_exports = dict.fromkeys(('iommu_group_get', 'iommu_group_put', 'iommu_group_id',
                                     'serdev_device_set_stop_bits'), 'EXPORT_SYMBOL_GPL')
    require(context.get('symbols') == expected_symbols and context.get('exports') == expected_exports
            and context.get('release') == RELEASE
            and context.get('exports_sha256') == kernel['build']['vmlinux_symvers_sha256']
            and not ({'pci_for_each_dma_alias', 'pci_real_dma_dev'} & set(imports)),
            'PMD kernel DMA/group bindings differ')


def snapshot(root, *, release):
    require(release == RELEASE and isinstance(root, Path) and root.is_absolute()
            and root.resolve() == root, 'Explicit canonical PMD selection required')
    source_root = source_reference.resolve(root)
    kernel = evidence(root, 'kernel-n71-pmd-build.json')
    modules = evidence(root, 'n71-pmd-diagnostics-build.json')
    manifest = evidence(root, 'n71-pmd-diagnostic-inputs.json')
    reuse = evidence(root, 'n71-pmd-caller-reuse.json')
    native = evidence(root, NATIVE)
    build = kernel['build']
    require(type(kernel.get('format')) is int and kernel['format'] == 1
            and kernel.get('status') == 'compiled_verified' and type(build.get('exit_code')) is int
            and build['exit_code'] == 0 and build.get('kernel_release') == release
            and all(build.get(name) is True for name in ('full_image_linked', 'vmlinux_modpost_verified',
                    'serdev_stop_bits_export_verified', 'embedded_config_exact_match',
                    'source_before_equals_after', 'modules_prepare_executed'))
            and digest(kernel['source']) == SOURCE_PIN, 'PMD full kernel/source qualification differs')
    outputs = build['outputs']
    hashes = {'.config': outputs['config']['sha256'], 'arch/arm64/boot/Image': outputs['Image']['sha256'],
              'vmlinux.symvers': build['vmlinux_symvers_sha256']}
    require(all(sha(value) for value in hashes.values()), 'PMD kernel hashes differ')
    selected = dict(format=1, base_commit=kernel['source']['commit'], bundle=kernel['source']['bundle'],
                    required_localversion=kernel['source']['required_localversion'], stage='patched',
                    patches=kernel['source']['patches'], files=kernel['source']['files'],
                    physical_boot_tested=False, kernel_image_linked=False)
    require(type(modules.get('format')) is int and modules['format'] == 1
            and modules.get('status') == 'seven_modules_compiled_verified'
            and digest(modules.get('source_bundle')) == digest(selected) and modules.get('kernel_hashes') == hashes
            and modules.get('kernel_release') == release
            and all(modules.get(name) is True for name in ('w1_werror', 'modpost_passed',
                    'kernel_source_and_image_preserved', 'mac_module_hash_elf_abi_verified',
                    'real_preflight_no_output_verified', 'corrupt_archive_refusal_without_output_verified'))
            and modules.get('installed') is False and modules.get('loaded') is False,
            'PMD diagnostic build and kernel differ')
    require(type(manifest.get('input_count')) is int and manifest['input_count'] == 62
            and digest(manifest.get('inputs')) == INPUTS_PIN
            and modules.get('inputs_sha256') == {name: row['sha256'] for name, row in manifest['inputs'].items()},
            'PMD compiled input manifest differs')
    for name, row in manifest['inputs'].items():
        source_file(source_root, name, row)
    records = modules.get('modules')
    require(isinstance(records, dict) and len(records) == 7, 'Seven PMD diagnostics required')
    for name, filename in (('n71_pcie_diagnostic', 'n71-pcie-diagnostic.ko'),
                           ('n71_wlan_power_diagnostic', 'n71-wlan-power-diagnostic.ko')):
        row = records[name]
        require(type(row.get('bytes')) is int and 64 <= row['bytes'] <= 256 * 1024
                and sha(row.get('sha256')) and row.get('vermagic') == release + ABI
                and row.get('path') == 'sources/phone/kernel/' + filename
                and row.get('elf64_aarch64_relocatable') is True,
                'PMD diagnostic module identity differs')
    native_reference(root, native, manifest, records['n71_pcie_diagnostic'], reuse, kernel, source_root=source_root)
    import n71_pmd_observer_build as observers
    records = observers.select(root, records, release=release, kernel_hashes=hashes, source_bundle=selected)
    return kernel, records, hashes


def qualified(root, *, release):
    kernel, records, hashes = snapshot(root, release=release)
    pcie = records['n71_pcie_diagnostic']
    return {'source_commit': kernel['source']['commit'], 'baseline_sha256': hashes,
            'module_bytes': pcie['bytes'], 'module_sha256': pcie['sha256'], 'vermagic': pcie['vermagic']}


def records(root, *, release, pcie_sha256, iommu_parent):
    require(type(iommu_parent) is bool and iommu_parent is True and sha(pcie_sha256),
            'PMD resources require explicit IOMMU selection and module hash')
    _, modules, _ = snapshot(root, release=release)
    require(pcie_sha256 == modules['n71_pcie_diagnostic']['sha256'], 'PMD resource module hash differs')
    import n71_resource_result
    parent = iommu.qualified(root, release=LEGACY)
    previous = n71_resource_result.selected_records(root, release=LEGACY,
        pcie_sha256=parent['module_sha256'], iommu_parent=True)
    selected = [dict(record) for record in previous]
    for record, name in zip(selected, ('n71_pcie_diagnostic', 'n71_wlan_power_diagnostic')):
        record.update({key: modules[name][key] for key in ('bytes', 'sha256', 'vermagic')})
    return selected
