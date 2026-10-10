"""Compile the native allocation adapter; API failures are not mutation kills."""
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('allocate-during-runtime', 'return -ENODEV;\n\tif (n71_scan_driver_pending(host))\n\t\treturn -EBUSY;', 'return -ENODEV;'),
    ('release-during-runtime', 'return -EINVAL;\n\tif (n71_scan_driver_pending(host))\n\t\treturn -EBUSY;', 'return -EINVAL;'),
    ('skip-power-api', 'error = pci_set_power_state(dev, PCI_D0);', 'error = 0;'),
    ('ignore-power-error', 'if (error)\n\t\treturn error > 0 ? -EIO : error;', 'if (false)\n\t\treturn error > 0 ? -EIO : error;'),
    ('skip-power-readback', 'actual != 0x4008 || dev->current_state != PCI_D0', 'false'),
    ('accept-pme-enabled', 'if (error || actual != 0x4008)', 'if (error)'),
    ('missing-held-bus', '!host->bus_held || !host->config_pending', '!host->config_pending'),
    ('missing-resource-assignment', '!host->resources_assigned || !host->resources.pending', '!host->resources.pending'),
    ('missing-msi-association', '!host->msi.associated || !native->domain', '!native->domain'),
    ('missing-iommu-count', 'host->iommu_devices != 2', 'false'),
    ('ignore-resource-verifier', 'devices.count != 2 ? -ENODEV : n71_resource_verify(host, &devices)', 'devices.count != 2 ? -ENODEV : 0'),
    ('wrong-vector-count', 'lease->endpoint, 1, 1, PCI_IRQ_MSI', 'lease->endpoint, 1, 2, PCI_IRQ_MSI'),
    ('allow-intx-fallback', 'lease->endpoint, 1, 1, PCI_IRQ_MSI', 'lease->endpoint, 1, 1, PCI_IRQ_MSI | 1U'),
    ('drop-endpoint-reference', 'devices.endpoint = NULL; /* Retain the reference until verified release. */', '/* Reference incorrectly released below. */'),
    ('skip-irq-verification', 'error = n71_msi_allocation_verify(host, lease);', 'error = 0;'),
    ('ignore-aic-hwirq', 'parent->hwirq != 0x10100UL + n71_msi_config_vector(native->slots)', 'false'),
    ('ignore-leaf-parent', 'leaf->parent_data != own', 'false'),
    ('ignore-core-mapcount', 'native->domain->mapcount != 1', 'false'),
    ('skip-message-readback', 'error = n71_msi_config_message(&io, native->slots);', 'error = 0;'),
    ('free-before-stop', 'error = n71_msi_config_stop(&io, &host->msi_config);', 'error = 0;'),
    ('ignore-stop-error', 'if (error)\n\t\tgoto unlock;\n\tpci_free_irq_vectors', 'if (false)\n\t\tgoto unlock;\n\tpci_free_irq_vectors'),
    ('ignore-restored-irq', 'lease->endpoint->irq != lease->default_irq', 'false'),
    ('forget-error-history', 'return host->msi_config.error ? host->msi_config.error :', 'return false ? host->msi_config.error :'),
    ('ignore-owned-hwirq', 'own->hwirq != n71_msi_config_vector(native->slots) - 8', 'false'),
    ('ignore-owned-chip-data', 'own->chip_data != native', 'false'),
    ('ignore-trigger-type', 'irqd_get_trigger_type(own) != IRQ_TYPE_EDGE_RISING', '(irqd_get_trigger_type(own) != IRQ_TYPE_EDGE_RISING && false)'),
    ('release-on-restore-error', 'if (!error) {\n\t\tpci_dev_put(lease->endpoint);', 'if (true) {\n\t\tpci_dev_put(lease->endpoint);'),
    ('accept-empty-lease-with-vector', '&& !lease->vector &&\n\t\t\t!lease->default_irq', '&& true'),
    ('power-before-identity-guard', 'if (!error)\n\t\terror = n71_msi_config_guard(&io, &host->msi_config);\n\tif (!error)\n\t\terror = n71_msi_allocation_power', 'if (!error)\n\t\terror = n71_msi_allocation_power'),
    ('free-without-config-owner', 'if (host->msi_config.phase == N71_MSI_CONFIG_EMPTY)\n\t\treturn -EBUSY;', 'if (false)\n\t\treturn -EBUSY;'),
    ('allow-aspm-side-effects', 'if (devices.root->link_state)', 'if (false)'),
)


class MsiAllocationTests(unittest.TestCase):
    def test_contract_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-msi-allocate.h').read_text()
        scan = (ROOT / 'phone/kernel/n71-pcie-scan.h').read_text()
        pending = re.search(r'static inline bool n71_scan_driver_pending\([^;]*?\n\{\n.*?\n\}', scan, re.S)
        self.assertIsNotNone(pending, 'Real runtime ownership predicate required')
        with tempfile.TemporaryDirectory(prefix='n71-msi-allocation-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h', 'n71-wlan-msi-config.h',
                         'n71-msi-allocation-lease.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            (folder / 'n71-pcie-resource-assign.h').write_text(pending.group(0) + '\n')
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertEqual(source.count(before), 1, name)
                    (folder / 'n71-pcie-msi-allocate.h').write_text(
                        source if before is None else source.replace(before, after, 1))
                    binary = folder / 'allocate'
                    built = subprocess.run(
                        [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                         '-I', str(folder), str(ROOT / 'tests/n71_pcie_msi_allocate.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(built.returncode, 0, name + ': compilation is not proof: ' + built.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                    if name == 'baseline':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('N71_PCIE_MSI_ALLOCATE_OK cases=', result.stdout)
                        print(result.stdout.strip(), flush=True)
                    else:
                        self.assertEqual(result.returncode, -6, name + result.stderr)
                        self.assertIn('assert', result.stderr.lower())
                        print('N71_MSI_ALLOCATE_ASSERTION_KILLED', name, flush=True)


if __name__ == '__main__':
    unittest.main()
