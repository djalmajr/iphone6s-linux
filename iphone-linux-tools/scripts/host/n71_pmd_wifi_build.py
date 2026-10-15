"""Bind the explicit PMD WCC stack to the compiled kernel and module inputs."""
from pathlib import Path
import n71_driver_modules as wlan
import n71_pmd_runtime_build as pmd

INPUTS_PIN = '9b8f8e789163e0d157dab31db058badfff63874f937eaf51e9f19dc334d52cba'
PATHS = ('rfkill/rfkill.ko', 'cfg80211/cfg80211.ko', 'brcm80211/brcmutil/brcmutil.ko',
         'brcm80211/brcmfmac/brcmfmac.ko', 'brcm80211/brcmfmac/wcc/brcmfmac-wcc.ko')
EXTRA = {'rfkill/rfkill-gpio.ko': ('rfkill_gpio', ['rfkill']),
         'brcm80211/brcmfmac/bca/brcmfmac-bca.ko': ('brcmfmac_bca', ['brcmfmac']),
         'brcm80211/brcmfmac/cyw/brcmfmac-cyw.ko': ('brcmfmac_cyw', ['brcmfmac', 'cfg80211'])}


def qualified(root):
    root = Path(root)
    kernel, _, hashes = pmd.snapshot(root, release=pmd.RELEASE)
    proof = pmd.evidence(root, 'n71-pmd-wifi-modules-qualified.json')
    pmd.require(type(proof.get('format')) is int and proof['format'] == 1
                and proof.get('qualified') is True
                and proof.get('status') == 'compiled_and_audited_not_loaded_on_phone'
                and proof.get('kernel_release') == pmd.RELEASE
                and proof.get('kernel_profile') == kernel['source']['bundle']
                and proof.get('source_commit') == kernel['source']['commit']
                and proof.get('kernel_record') == 'kernel-n71-pmd-build.json',
                'PMD WCC build selection differs')
    pmd.require(all(proof.get(name) is True for name in (
                'mac_bytes_elf_and_hash_audit', 'source_and_baseline_preserved',
                'legacy_source_and_kernel_preserved', 'all_imports_resolved',
                'pcie_msgbuf_symbols_linked', 'werror_modpost_passed', 'kernel_source_and_image_preserved'))
                and all(proof.get(name) is False for name in (
                    'installed', 'loaded_on_phone', 'firmware_selected', 'wifi_verified',
                    'telemetry_verified', 'linux_charging_validated')),
                'PMD WCC audit or physical proof scope differs')
    source = kernel['source']
    baseline = {'source_commit': source['commit'], 'bundle': source['bundle'],
                'patches': source['patches'], 'files': source['files'], 'kernel_sha256': hashes,
                'image_gzip_sha256': kernel['build']['outputs']['Image.gz']['sha256']}
    pmd.require(proof.get('preserved_kernel_sha256') == hashes
                and pmd.digest(proof.get('baseline')) == pmd.digest(baseline),
                'PMD WCC and kernel baseline differ')
    inputs = proof.get('input_qualification', {}).get('inputs')
    pmd.require(isinstance(inputs, dict) and len(inputs) == 16 and pmd.digest(inputs) == INPUTS_PIN,
                'PMD WCC compiled input manifest differs')
    for name, record in inputs.items():
        pmd.source_file(root, name, record)
    pmd.require(proof.get('variant_config_changes') == {'CONFIG_BRCMFMAC_PCIE': ['n', 'y'],
                'CONFIG_BRCMFMAC_PROTO_MSGBUF': ['n', 'y']}
                and proof.get('pci_alias_verified') == 'pci:v000014E4d000043A3sv*sd*bc02sc80i*',
                'PMD WCC PCIe configuration or endpoint alias differs')
    irq = proof.get('irq_correction', {})
    pmd.require(irq.get('applied_to_package_copy_only') is True
                and irq.get('target') == 'drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c'
                and irq.get('patch_sha256') == inputs['phone/kernel/patches/0008-brcmfmac-msi-error.patch']['sha256'],
                'PMD WCC MSI correction differs')
    modules = proof.get('modules')
    pmd.require(type(proof.get('module_count')) is int and proof['module_count'] == 8
                and isinstance(modules, dict) and set(modules) == set(PATHS) | set(EXTRA),
                'Eight compiled PMD Wi-Fi modules required')
    expected = dict(zip(PATHS, zip(wlan.NAMES, wlan.DEPENDS))) | EXTRA
    selected = []
    for path, (name, depends) in expected.items():
        row = modules[path]
        pmd.require(isinstance(row, dict) and row.get('name') == name and row.get('depends') == depends
                    and type(row.get('bytes')) is int and 0 < row['bytes'] <= 2 * 1024 * 1024
                    and pmd.sha(row.get('sha256')) and row.get('vermagic') == pmd.RELEASE + pmd.ABI
                    and row.get('imports_verified') is True and row.get('elf64_aarch64_relocatable') is True
                    and isinstance(row.get('imports'), list) and all(isinstance(item, str) for item in row['imports'])
                    and row['imports'] == sorted(set(row['imports']))
                    and (name != 'brcmfmac' or row.get('endpoint_pci_alias_verified') is True),
                    'PMD WCC module identity, imports or alias differs')
        if path in PATHS:
            selected.append({'name': name, 'module': path.rsplit('/', 1)[-1],
                             **{key: row[key] for key in ('bytes', 'sha256', 'vermagic', 'depends')}})
    return wlan.manifest(selected)
