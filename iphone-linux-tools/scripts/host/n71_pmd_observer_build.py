"""Select the real observer modules only after qualification of their PMD base."""
import os
from pathlib import Path

ENV = 'IPHONE_LINUX_PMD_DIAGNOSTICS'
VARIANT = 'pmd-observers-v1'
SOURCE_HEAD = '8b62c9cd5c6bd1a1ef1144136ba7deadf94795da'
INPUTS_PIN = 'c5b5cd6307a6224496f35d975fe0141a933bcffc9330319d83a118b929391d6e'
MODULES_PIN = '81fbe4889446abde0eef330a5c142e8c8f75a9f0f2de082c06e1e633a5a7dcb5'
ARCHIVE = {'bytes': 399360, 'sha256': '4c83ad67d47cc1e31a0da53868ed22d6daee0c460606d6664f178d6cedb85681',
           'format': 'USTAR', 'mtime': 0, 'uid': 0, 'gid': 0, 'mode': '0644'}


def select(root, records, *, release, kernel_hashes, source_bundle):
    value = os.environ.get(ENV)
    if value is None:
        return records
    if value != VARIANT:
        raise ValueError('Explicit known PMD diagnostic variant required')
    # The caller has completed the legacy base check, including retained inputs.
    import n71_pmd_runtime_build as pmd
    pmd.require(isinstance(root, Path) and root.is_absolute() and root.resolve() == root
                and release == pmd.RELEASE, 'Canonical qualified PMD observer context required')
    proof = pmd.evidence(root, 'n71-pmd-observer-build.json')
    manifest = pmd.evidence(root, 'n71-pmd-observer-inputs.json')
    pmd.require(isinstance(proof, dict) and isinstance(manifest, dict), 'Observer records required')
    pmd.require(type(proof.get('format')) is int and proof['format'] == 1
                and proof.get('status') == 'compiled_verified_native_arm64_baselines_passed_not_phone_loaded'
                and proof.get('diagnostic_variant') == VARIANT
                and proof.get('source_head') == SOURCE_HEAD and proof.get('kernel_release') == release
                and proof.get('inputs_manifest_sha256') == INPUTS_PIN
                and proof.get('kernel_hashes') == kernel_hashes
                and proof.get('source_bundle') == source_bundle,
                'Observer build and qualified PMD kernel differ')
    pmd.require(all(proof.get(name) is True for name in (
                'w1_werror', 'modpost_passed', 'all_module_imports_resolved',
                'new_dma_parameters_and_i2c_report_verified_in_real_elf',
                'local_artifact_sha_size_and_elf_verified', 'base_kernel_source_and_outputs_preserved'))
                and all(proof.get(name) is False for name in (
                    'installed', 'loaded', 'physical_boot_tested', 'runtime_selection_integrated',
                    'wifi_verified', 'telemetry_verified', 'charging_verified', 'goal_complete')),
                'Observer compile audit or proof scope differs')
    for name, expected in (('input_count', 64), ('module_count', 7), ('module_bytes', 269312), ('jobs', 1)):
        pmd.require(type(proof.get(name)) is int and proof[name] == expected, 'Observer build counts differ')
    gates = proof.get('arm64_native')
    pmd.require(isinstance(gates, dict) and gates.get('modeled_kernel_pci_iommu_and_mmio_apis') is True,
                'Observer native proof scope differs')
    expected_gates = {'unittest_methods': 4, 'cases': 324, 'dma_helper_cases': 100,
                      'dma_backend_cases': 58, 'i2c_controller_cases': 81, 'i2c_caller_cases': 85,
                      'assertion_mutations_executed': 0, 'mac_assertion_mutations_reused': 108}
    for name, expected in expected_gates.items():
        pmd.require(type(gates.get(name)) is int and gates[name] == expected, 'Observer native gates differ')
    pmd.require(type(manifest.get('format')) is int and manifest['format'] == 1
                and manifest.get('source_head') == SOURCE_HEAD
                and type(manifest.get('input_count')) is int and manifest['input_count'] == 64
                and manifest.get('canonical_manifest_sha256') == INPUTS_PIN
                and pmd.digest(manifest.get('canonical_tar')) == pmd.digest(ARCHIVE)
                and pmd.digest(proof.get('input_archive')) == pmd.digest(ARCHIVE),
                'Observer sealed source identity differs')
    inputs = manifest.get('inputs')
    pmd.require(isinstance(inputs, dict) and len(inputs) == 64 and pmd.digest(inputs) == INPUTS_PIN,
                'Observer compiled source manifest differs')
    for name, row in inputs.items():
        pmd.source_file(root, name, row)
    modules = proof.get('modules')
    pmd.require(isinstance(modules, dict) and set(modules) == set(records)
                and pmd.digest(modules) == MODULES_PIN, 'Observer compiled module set differs')
    for row in modules.values():
        pmd.require(row.get('vermagic') == release + pmd.ABI
                    and row.get('elf64_aarch64_relocatable') is True,
                    'Observer diagnostic ABI differs')
    return {name: dict(row) for name, row in modules.items()}
