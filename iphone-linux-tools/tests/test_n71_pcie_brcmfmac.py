"""Prove retained driver mode, real PCI callbacks and ordered recovery."""
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def functions(source, names):
    pattern = r'static (?:inline )?(?:int|bool) ({})\([^;]*?\n\{{\n.*?\n\}}'
    found = re.findall(pattern.format('|'.join(names)), source, re.S)
    if set(found) != set(names):
        raise AssertionError('Function extraction differs')
    return '\n\n'.join(match.group(0) for match in re.finditer(
        pattern.format('|'.join(names)), source, re.S)) + '\n'


MUTATIONS = (
    ('missing-iommu', 'adapter', 'host->iommu_devices != 2', 'false'),
    ('missing-resources', 'adapter', '!host->resources_assigned || !host->resources.pending', '!host->resources.pending'),
    ('missing-msi', 'adapter', '!host->msi.associated || !host->msi.native.domain', '!host->msi.native.domain'),
    ('ignore-registered-prepare', 'adapter', 'driver_find("brcmfmac", &pci_bus_type))\n\t\treturn -EACCES;', 'false)\n\t\treturn -EACCES;'),
    ('ignore-endpoint-id', 'adapter', 'devices.endpoint->vendor != 0x14e4', 'false'),
    ('ignore-dma-scope', 'adapter', '!n71_scan_dma_device_valid(devices.endpoint, false)', 'false'),
    ('ignore-publication-intent', 'adapter', 'host->driver_published || host->msi_allocation.endpoint', 'host->msi_allocation.endpoint'),
    ('steal-override', 'adapter', 'device_has_driver_override(&devices.root->dev) ||', 'false ||'),
    ('allow-aspm', 'adapter', 'if (devices.root->link_state)', 'if (false)'),
    ('forget-endpoint-ref', 'adapter', 'devices.endpoint = NULL;', '/* Incorrect put below. */'),
    ('missing-pm-ref', 'adapter', 'pm_runtime_get_noresume(&devices.endpoint->dev);', '/* Missing retained power reference. */'),
    ('discard-partial-error', 'adapter', 'n71_brcmfmac_error(&host->brcmfmac, error);\nunlock:', '(void)error;\nunlock:'),
    ('repeat-publish', 'adapter', 'if (host->driver_published)', 'if (false)'),
    ('omit-disable-root', 'adapter', 'if (pci_is_enabled(root))\n\t\tpci_disable_device(root);', '/* Missing root enable balance. */'),
    ('ignore-restore-error', 'adapter', 'if (error)\n\t\tgoto unlock;\n\tif (host->driver_root_override)', 'if (false)\n\t\tgoto unlock;\n\tif (host->driver_root_override)'),
    ('clear-foreign-override', 'adapter', 'device_match_driver_override(&device->dev, &expected) <= 0', '(device_match_driver_override(&device->dev, &expected) <= 0 && false)'),
    ('forget-pm-put', 'adapter', 'pm_runtime_put_noidle(&endpoint->dev);', '/* Missing power balance. */'),
    ('release-with-enable-two', 'adapter', 'atomic_read(&root->enable_cnt) > 1', 'false'),
    ('release-with-enable-negative', 'adapter', 'atomic_read(&endpoint->enable_cnt) < 0', 'false'),
    ('starve-scan-after-runtime', 'scan', 'host->driver_reads++;', 'host->reads++;'),
    ('deny-prepared-enable', 'scan', '(dev == host->driver_root || dev == host->driver_endpoint)', '(false)'),
    ('enable-other-device', 'scan', '(dev == host->driver_root || dev == host->driver_endpoint)', '(true)'),
    ('remove-active-driver', 'scan', 'host->brcmfmac.active || host->driver_root || host->driver_endpoint', 'false'),
)


class PcieBrcmfmacTests(unittest.TestCase):
    def test_retained_runtime_callbacks_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        scan = functions((ROOT / 'phone/kernel/n71-pcie-scan.h').read_text(), (
            'n71_scan_raw_read', 'n71_scan_raw_write', 'n71_scan_config_read',
            'n71_scan_config_write', 'n71_scan_deny_enable', 'n71_pcie_scan_remove_consumers'))
        power = functions((ROOT / 'phone/kernel/n71-pcie-msi-allocate.h').read_text(), (
            'n71_msi_allocation_error', 'n71_msi_allocation_power'))
        adapter = (ROOT / 'phone/kernel/n71-pcie-brcmfmac.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-pcie-brcmfmac-') as directory:
            folder = Path(directory)
            (folder / 'linux/device').mkdir(parents=True)
            for name in ('linux/device/driver.h', 'linux/pm_runtime.h'):
                (folder / name).write_text('/* Dependency API supplied by the harness. */\n')
            (folder / 'n71-pcie-msi-allocate.h').write_text(power)
            baseline_passed = False
            for name, target, before, after in (('baseline', None, None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    sources = {'scan': scan, 'adapter': adapter}
                    if target:
                        self.assertEqual(sources[target].count(before), 1, name)
                        sources[target] = sources[target].replace(before, after, 1)
                    (folder / 'n71-runtime-scan-extracted.h').write_text(sources['scan'])
                    (folder / 'n71-pcie-brcmfmac.h').write_text(sources['adapter'])
                    binary = folder / 'runtime'
                    compiled = subprocess.run(
                        [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                         '-I', str(ROOT / 'phone/kernel'), str(ROOT / 'tests/n71_pcie_brcmfmac.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, name + ': compilation is not proof: ' + compiled.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                    if name == 'baseline':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('N71_PCIE_BRCMFMAC_OK cases=', result.stdout)
                        baseline_passed = True
                        print(result.stdout.strip(), flush=True)
                    else:
                        self.assertEqual(result.returncode, -6, name + result.stderr)
                        self.assertIn('assert', result.stderr.lower())
                        print('N71_PCIE_BRCMFMAC_ASSERTION_KILLED', name, flush=True)
                if not baseline_passed:
                    return


if __name__ == '__main__':
    unittest.main()
