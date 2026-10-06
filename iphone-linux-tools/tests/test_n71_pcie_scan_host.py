"""Fault-inject the real adapter's PCI API and MMIO backend without a device."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71PcieScanHost(unittest.TestCase):
    def compile_and_run(self, *, mutation=None, assignment_mutation=None):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; native gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-scan-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('pci.h', 'spinlock.h', 'ioport.h'):
                (folder / 'linux' / name).write_text('/* PCI API supplied by the harness. */\n')
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            source = (ROOT / 'phone/kernel/n71-pcie-scan.h').read_text()
            if mutation:
                before, after = mutation
                self.assertEqual(source.count(before), 1, 'Mutation requires a unique anchor')
                source = source.replace(before, after, 1)
            (folder / 'n71-pcie-scan.h').write_text(source)
            source = (ROOT / 'phone/kernel/n71-pcie-resource-assign.h').read_text()
            if assignment_mutation:
                before, after = assignment_mutation
                self.assertEqual(source.count(before), 1, 'Assignment mutation requires a unique anchor')
                source = source.replace(before, after, 1)
            (folder / 'n71-pcie-resource-assign.h').write_text(source)
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
        self.assertIn('N71_PCIE_SCAN_HOST_OK cases=29', result.stdout)
        self.assertIn('N71_PCIE_HELD_BUS_OK cases=16', result.stdout)
        self.assertIn('N71_PCIE_RESOURCE_ASSIGN_OK cases=19', result.stdout)
        print(result.stdout.strip(), flush=True)

    def test_lifecycle_mutations_die_by_assertion(self):
        mutations = (
            ('missing-remove', 'pci_remove_root_bus(bridge->bus);', '(void)pci_remove_root_bus;'),
            ('early-restore', '\t\tn71_scan_remove_bus(bridge);\n\t\tdev_info(dev,',
             '\t\tn71_scan_restore(&io, &host->config);\n\t\tn71_scan_remove_bus(bridge);\n\t\tdev_info(dev,'),
            ('ignored-refusal', 'host->config.error || host->io_error',
             'host->config.error && host->io_error'),
            ('restore-starved', '> 4096 && host->config.active', '> 4096'),
            ('enable-allowed', '(void)dev;\n\treturn -EPERM;', '(void)dev;\n\treturn 0;'),
            ('forgot-stop-error', ' !bridge->bus);\n\t\tif (!error)',
             ' !bridge->bus);\n\t\tif (!error && host->devices != 2)'),
            ('skip-target-prepare', 'error = n71_link_target_prepare(&target_io, &host->target);',
             'error = 0;'),
            ('skip-target-restore', 'if (host->target.pending) {', 'if (false) {'),
            ('release-after-config-failure', 'if (error)\n\t\t\treturn error;\n\t\thost->config_pending',
             'if (false)\n\t\t\treturn error;\n\t\thost->config_pending'),
            ('release-after-target-failure', 'if (error)\n\t\t\treturn error;\n\t}\n\tstate->scan_bridge',
             'if (false)\n\t\t\treturn error;\n\t}\n\tstate->scan_bridge'),
            ('lose-retained-bridge', 'state->scan_bridge = bridge;', 'state->scan_bridge = NULL;'),
            ('skip-partial-bus-removal',
             'pci_walk_bus(bridge->bus, n71_scan_report_device, host);\n\tif (bridge->bus) {',
             'pci_walk_bus(bridge->bus, n71_scan_report_device, host);\n\tif (!error && bridge->bus) {'),
            ('overwrite-pending-bridge', 'if (state->scan_bridge)\n\t\treturn -EBUSY;',
             'if (false)\n\t\treturn -EBUSY;'),
            ('skip-pme-prepare', 'error = n71_pme_disable(&io, &host->pme);', 'error = 0;'),
            ('skip-pme-restore', 'if (host->pme.pending) {', 'if (false) {'),
            ('release-after-pme-failure', 'if (error)\n\t\t\treturn error;\n\t}\n\tif (host->target.pending)',
             'if (false)\n\t\t\treturn error;\n\t}\n\tif (host->target.pending)'),
            ('generic-pme-callback', 'error = n71_pme_scan_write(&io, &host->config, &host->pme, &request);',
             'error = n71_scan_write(&io, &host->config, &request);'),
            ('lose-pme-ownership', 'error = n71_pme_restore(&io, &host->pme);',
             'error = n71_pme_restore(&io, &host->pme);\n\t\thost->pme.pending = false;'),
            ('hold-without-pme', 'if (hold_bus && !disable_pme)', 'if (false && !disable_pme)'),
            ('hold-negative-scan', 'if (hold_bus && !error)', 'if (hold_bus)'),
            ('hold-invalid-topology', 'host->devices == 2 && host->endpoints == 1',
             'host->devices >= 1 && host->endpoints <= 1'),
            ('lose-held-owner', 'host->bus_held = true;', 'host->bus_held = false;'),
            ('held-cleanup-without-lock',
             'pci_lock_rescan_remove();\n\t\tn71_scan_remove_bus(bridge);',
             'n71_scan_remove_bus(bridge);\n\t\tpci_lock_rescan_remove();'),
            ('held-cleanup-before-remove', 'if (bridge->bus) {\n\t\tif (!host->bus_held)',
             'if (false && bridge->bus) {\n\t\tif (!host->bus_held)'),
            ('ignore-held-stop-refusal', 'pci_free_host_bridge(bridge);\n\treturn stop_error;',
             'pci_free_host_bridge(bridge);\n\treturn 0;'),
            ('forget-held-stop-refusal-on-retry', 'stop_error = host->held_stop_error;',
             'stop_error = 0;'),
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

    def test_resource_allocator_mutations_die_by_assertion(self):
        mutations = (
            ('retry-assignment', 'assign', 'if (host->resource_attempted)', 'if (false)'),
            ('allocation-without-lock', 'assign', 'pci_lock_rescan_remove();', '(void)pci_lock_rescan_remove;'),
            ('extra-topology-accepted', 'assign', 'if (devices->error || devices->count != 2)', 'if (false)'),
            ('wrong-sized-bar', 'assign', '|| resource_size(resource) != bytes)', '|| false)'),
            ('capture-skipped', 'assign', 'error = n71_resource_capture(&io, &layout, &host->resources);', 'error = ((void)io, 0);'),
            ('claim-skipped', 'assign', 'error = request_resource(&iomem_resource, &host->windows[1]);', '(void)request_resource; error = 0;'),
            ('claim-owner-lost', 'assign', 'host->window_claimed = true;', 'host->window_claimed = false;'),
            ('sizing-skipped', 'assign', 'pci_bus_size_bridges(bridge->bus);', '(void)pci_bus_size_bridges;'),
            ('assignment-skipped', 'assign', 'pci_bus_assign_resources(bridge->bus);', '(void)pci_bus_assign_resources;'),
            ('verification-skipped', 'assign', 'error = n71_resource_verify(host, &devices);',
             '(void)n71_resource_verify; error = 0;'),
            ('bar-parent-widened', 'assign', 'resource->parent != window', 'resource->parent == NULL'),
            ('translation-lost', 'assign', 'region.start != resource->start - 0x700000000ULL', 'false'),
            ('bar-readback-lost', 'assign', 'low == ((u32)region.start | 4U)', 'low != 0'),
            ('overlap-accepted', 'assign', 'if (!(endpoint->resource[0].end', 'if (false && !(endpoint->resource[0].end'),
            ('extra-bar-accepted', 'assign',
             'resource = &endpoint->resource[index];\n\t\tif (resource->flags || resource->start || resource->end || resource->parent)',
             'resource = &endpoint->resource[index];\n\t\tif (false)'),
            ('post-driver-accepted', 'assign',
             'root->resource[PCI_BRIDGE_PREF_MEM_WINDOW].parent || root->driver || endpoint->driver ||',
             'root->resource[PCI_BRIDGE_PREF_MEM_WINDOW].parent ||'),
            ('phase-left-active', 'assign', 'host->resources.active = false;', 'host->resources.active = true;'),
            ('allocation-uses-probe-policy', 'scan',
             'n71_resource_write(&io, &host->resources, &request)',
             'n71_pme_scan_write(&io, &host->config, &host->pme, &request)'),
            ('remove-active-allocation', 'scan', 'if (host->resources.active)\n\t\treturn -EBUSY;',
             'if (false)\n\t\treturn -EBUSY;'),
            ('extra-restore-skipped', 'scan', 'if (host->resources.pending) {', 'if (false) {'),
            ('extra-restore-starved', 'scan', 'host->config.active = false; /* Removed bus:',
             'host->config.active = true; /* Removed bus:'),
            ('window-release-before-bars', 'scan', 'if (host->config_pending) {',
             'if (host->window_claimed) { release_resource(&host->windows[1]); host->window_claimed = false; }\n\tif (host->config_pending) {'),
            ('window-release-with-children', 'scan',
             'host->windows[1].parent != &iomem_resource || host->windows[1].child',
             'host->windows[1].parent != &iomem_resource'),
            ('failed-window-release-owner-lost', 'scan', 'error = release_resource(&host->windows[1]);',
             'error = release_resource(&host->windows[1]);\n\t\thost->window_claimed = false;'),
            ('window-release-error-ignored', 'scan',
             'if (error)\n\t\t\treturn error;\n\t\thost->window_claimed',
             'if (false)\n\t\t\treturn error;\n\t\thost->window_claimed'),
        )
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            for name, target, before, after in mutations:
                with self.subTest(mutation=name):
                    options = {'assignment_mutation' if target == 'assign' else 'mutation': (before, after)}
                    result = self.compile_and_run(**options)
                    self.assertEqual(result.returncode, -6, 'Compilation/timeout is not a kill: ' + name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_RESOURCE_ASSIGN_ASSERTION_KILL ' + name, flush=True)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)


if __name__ == '__main__':
    unittest.main()
