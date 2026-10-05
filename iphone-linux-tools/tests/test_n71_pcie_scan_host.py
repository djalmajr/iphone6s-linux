"""Fault-inject the real adapter's PCI API and MMIO backend without a device."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71PcieScanHost(unittest.TestCase):
    def compile_and_run(self, *, mutation=None):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; native gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-scan-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('pci.h', 'spinlock.h'):
                (folder / 'linux' / name).write_text('/* PCI API supplied by the harness. */\n')
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            source = (ROOT / 'phone/kernel/n71-pcie-scan.h').read_text()
            if mutation:
                before, after = mutation
                self.assertEqual(source.count(before), 1, 'Mutation requires a unique anchor')
                source = source.replace(before, after, 1)
            (folder / 'n71-pcie-scan.h').write_text(source)
            binary = folder / 'host'
            compiled = subprocess.run(
                [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                 '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                 str(ROOT / 'tests/n71_pcie_scan_host.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)

    def test_pci_scan_errors_and_removal_before_restore(self):
        result = self.compile_and_run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('N71_PCIE_SCAN_HOST_OK cases=21', result.stdout)

    def test_lifecycle_mutations_die_by_assertion(self):
        mutations = (
            ('missing-remove', 'pci_remove_root_bus(bridge->bus);', '(void)pci_remove_root_bus;'),
            ('early-restore', 'pci_stop_root_bus(bridge->bus);',
             'n71_scan_restore(&io, &host->config);\n\t\tpci_stop_root_bus(bridge->bus);'),
            ('ignored-refusal', 'host->config.error || host->io_error',
             'host->config.error && host->io_error'),
            ('restore-starved', '> 4096 && host->config.active', '> 4096'),
            ('enable-allowed', '(void)dev;\n\treturn -EPERM;', '(void)dev;\n\treturn 0;'),
            ('forgot-stop-error', 'if (!error && (host->config.error || host->io_error))',
             'if (!error && host->devices != 2 && (host->config.error || host->io_error))'),
            ('skip-target-prepare', 'error = n71_link_target_prepare(&target_io, &host->target);',
             'error = 0;'),
            ('skip-target-restore', 'if (host->target.pending) {', 'if (false) {'),
            ('release-after-config-failure', 'if (error)\n\t\t\treturn error;\n\t\thost->config_pending',
             'if (false)\n\t\t\treturn error;\n\t\thost->config_pending'),
            ('release-after-target-failure', 'if (error)\n\t\t\treturn error;\n\t}\n\tstate->scan_bridge',
             'if (false)\n\t\t\treturn error;\n\t}\n\tstate->scan_bridge'),
            ('lose-retained-bridge', 'state->scan_bridge = bridge;', 'state->scan_bridge = NULL;'),
            ('skip-partial-bus-removal', 'if (bridge->bus) {', 'if (!error && bridge->bus) {'),
            ('overwrite-pending-bridge', 'if (state->scan_bridge)\n\t\treturn -EBUSY;',
             'if (false)\n\t\treturn -EBUSY;'),
        )
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            for name, before, after in mutations:
                with self.subTest(mutation=name):
                    result = self.compile_and_run(mutation=(before, after))
                    self.assertEqual(result.returncode, -6, result.stderr)
                    self.assertIn('assert', result.stderr.lower())
                    print(f'N71_SCAN_HOST_ASSERTION_KILL {name}', flush=True)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)


if __name__ == '__main__':
    unittest.main()
