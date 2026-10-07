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
            for name in ('pci.h', 'spinlock.h', 'ioport.h', 'iommu.h', 'bitmap.h', 'dma-mapping.h'):
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
        self.assertIn('N71_PCIE_RESOURCE_ASSIGN_OK cases=20', result.stdout)
        self.assertIn('N71_PCIE_MSI_SCAN_OK cases=14', result.stdout)
        self.assertIn('N71_PCIE_CONSUMER_REMOVAL_OK cases=7', result.stdout)
        self.assertIn('N71_PCIE_DART_SCAN_OK cases=39', result.stdout)
        self.assertIn('N71_PCIE_DMA_TOPOLOGY_OK cases=55', result.stdout)
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
             'pci_free_host_bridge(bridge);\n\t(void)stop_error;\n\treturn 0;'),
            ('forget-held-stop-refusal-on-retry', 'stop_error = host->held_stop_error;',
             'stop_error = 0;'),
            ('skip-consumer-phase', 'error = n71_pcie_scan_remove_consumers(state);',
             'error = false ? n71_pcie_scan_remove_consumers(state) : 0;'),
            ('forget-consumer-stop-error', 'host->held_stop_error = host->config.error ? host->config.error : host->io_error;',
             'host->held_stop_error = 0;'),
            ('restore-in-consumer-phase', 'return n71_dart_host_unmap(&host->dart);',
             'struct n71_scan_io early = {host, n71_scan_raw_read, n71_scan_raw_write};\n'
             '\tn71_scan_restore(&early, &host->config);\n\treturn n71_dart_host_unmap(&host->dart);'),
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

    def test_msi_scan_mutations_die_by_assertion(self):
        mutations = (
            ('skip-msi-prepare', 'error = n71_scan_msi_acquire(bridge, dev);',
             'error = false ? n71_scan_msi_acquire(bridge, dev) : 0;'),
            ('ignore-msi-prepare-error', 'error, host->msi.associated);\n\t\tif (error)',
             'error, host->msi.associated);\n\t\tif (false)'),
            ('msi-without-held-bus', 'if (options->msi_parent && !hold_bus)', 'if (false)'),
            ('skip-parent-put', 'of_node_put(parent);', '(void)parent;'),
            ('missing-pre-scan-opt-in', '.hold_bus = true, .msi_parent = true};',
             '.hold_bus = true, .msi_parent = false};'),
            ('msi-by-default', '.disable_pme = disable_pme, .hold_bus = hold_bus}',
             '.disable_pme = disable_pme, .hold_bus = hold_bus, .msi_parent = true}'),
            ('omit-bridge-inheritance', 'dev_get_msi_domain(&bridge->dev) != domain ||', 'false ||'),
            # Root reports reach the same bus through both pointers; remove both guards together.
            ('omit-root-bus-inheritance',
             'dev_get_msi_domain(&bridge->bus->dev) != domain ||\n\t\t    dev_get_msi_domain(&dev->bus->dev) != domain ||',
             'false || false ||'),
            ('omit-device-bus-inheritance', 'dev_get_msi_domain(&dev->bus->dev) != domain ||', 'false ||'),
            ('omit-device-inheritance', 'dev_get_msi_domain(&dev->dev) != domain)', 'false)'),
            ('skip-msi-cleanup', 'error = n71_wlan_msi_host_release(&host->msi);',
             'error = false ? n71_wlan_msi_host_release(&host->msi) : 0;'),
            ('ignore-msi-cleanup-error', 'error = n71_pcie_scan_remove_consumers(state);\n\tif (error)',
             'error = n71_pcie_scan_remove_consumers(state);\n\tif (false)'),
        )
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            for name, before, after in mutations:
                with self.subTest(mutation=name):
                    result = self.compile_and_run(mutation=(before, after))
                    self.assertEqual(result.returncode, -6, 'Compilation/timeout is not a kill: ' + name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_MSI_SCAN_ASSERTION_KILL ' + name, flush=True)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)

    def test_dart_scan_mutations_die_by_assertion(self):
        mutations = (
            ('dart-without-held-msi', 'if (options->provider && (!hold_bus || !options->msi_parent))', 'if (false)'),
            ('skip-dart-prepare', 'error = n71_dart_host_prepare(&host->dart, &request);',
             'error = false ? n71_dart_host_prepare(&host->dart, &request) : 0;'),
            ('ignore-dart-prepare-error', 'error, host->dart.available, host->dart.mapped);\n\t\tif (error)',
             'error, host->dart.available, host->dart.mapped);\n\t\tif (false)'),
            ('omit-provider-selection', '.msi_parent = true, .provider = provider,',
             '.msi_parent = true, .provider = NULL,'),
            ('accept-null-provider', 'if (!provider)\n\t\treturn -EINVAL;', 'if (false)\n\t\treturn -EINVAL;'),
            ('skip-iommu-readback', 'error = n71_scan_report_iommu(host, dev);',
             'error = false ? n71_scan_report_iommu(host, dev) : 0;'),
            ('ignore-provider-availability', '!host->dart.available ||', 'false ||'),
            ('ignore-map-state', '!host->dart.mapped ||', 'false ||'),
            ('ignore-owner-identity', '!n71_dart_host_refs_valid(&host->dart) ||', 'false ||'),
            ('ignore-fwspec-guards', '!spec || spec->iommu_fwnode != of_fwnode_handle(host->dart.provider_node) ||\n'
             '\t    spec->flags || spec->num_ids != 0 ||', '(false && spec) ||'),
            ('foreign-provider-fwnode', 'spec->iommu_fwnode != of_fwnode_handle(host->dart.provider_node) ||', 'false ||'),
            ('foreign-fwspec-flags', 'spec->flags ||', 'false ||'),
            ('wrong-fwspec-count', 'spec->num_ids != 0 ||', 'false ||'),
            ('foreign-map-identity', 'of_find_property(host->dart.master_node, "iommu-map", NULL) != host->dart.map_property ||', 'false ||'),
            ('foreign-status-identity', 'of_find_property(host->dart.provider_node, "status", NULL) != host->dart.status_property ||', 'false ||'),
            ('wrong-map-size', 'of_property_count_u32_elems(host->dart.master_node, "iommu-map") != 8 ||',
             '(false && of_property_count_u32_elems(host->dart.master_node, "iommu-map") != 8) ||'),
            ('ignore-map-read-error', 'of_property_read_u32_index(host->dart.master_node, "iommu-map", index, &value)',
             '(of_property_read_u32_index(host->dart.master_node, "iommu-map", index, &value), 0)'),
            ('wrong-map-cell', 'value != map[index]', '(false && value != map[index])'),
            ('ignore-domain-guards', '!domain || domain->type != IOMMU_DOMAIN_DMA ||\n'
             '\t    (host->iommu_domain && host->iommu_domain != domain)', 'false'),
            ('identity-domain-accepted', 'domain->type != IOMMU_DOMAIN_DMA ||', 'false ||'),
            ('different-domains-accepted', '(host->iommu_domain && host->iommu_domain != domain)', 'false'),
            ('lose-observed-domain', 'host->iommu_domain = domain;', 'host->iommu_domain = NULL;'),
            ('lose-observed-count', 'host->iommu_devices++;', '(void)host;'),
            ('accept-incomplete-readback', 'if (host->dart.bridge && host->iommu_devices != 2)', 'if (false)'),
            ('retain-stale-domain', 'host->iommu_domain = NULL;', '(void)host;'),
            ('retain-stale-count', 'host->iommu_devices = 0;', '(void)host;'),
            ('skip-dart-unmap', 'return n71_dart_host_unmap(&host->dart);',
             'return false ? n71_dart_host_unmap(&host->dart) : 0;'),
            ('ignore-dart-unmap-error', 'return n71_dart_host_unmap(&host->dart);',
             '(void)n71_dart_host_unmap(&host->dart);\n\treturn 0;'),
            ('skip-dart-release', 'error = n71_dart_host_release(&host->dart);',
             'error = false ? n71_dart_host_release(&host->dart) : 0;'),
            ('ignore-dart-release-error', 'error = n71_dart_host_release(&host->dart);\n\tif (error)',
             'error = n71_dart_host_release(&host->dart);\n\tif (false)'),
        )
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            for name, before, after in mutations:
                with self.subTest(mutation=name):
                    result = self.compile_and_run(mutation=(before, after))
                    self.assertEqual(result.returncode, -6, 'Compilation/timeout is not a kill: ' + name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_DART_SCAN_ASSERTION_KILL ' + name, flush=True)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)

    def test_dma_topology_mutations_die_by_assertion(self):
        mutations = (
            ('skip-dma-observation', 'if (n71_scan_report_dma(host, dev))',
             'if (false && n71_scan_report_dma(host, dev))'),
            ('multifunction-alias-accepted', 'dev->multifunction ||', 'false ||'),
            ('physical-function-accepted', 'dev->is_physfn ||', 'false ||'),
            ('virtual-function-accepted', 'dev->is_virtfn ||', 'false ||'),
            ('bridge-alias-flag-accepted', '(PCI_DEV_FLAG_PCIE_BRIDGE_ALIAS |', '(0 |'),
            ('translation-root-flag-accepted', 'PCI_DEV_FLAGS_BRIDGE_XLATE_ROOT |', '0 |'),
            ('bridge-no-alias-flag-accepted', '| PCI_DEV_FLAGS_PCI_BRIDGE_NO_ALIAS))', '| 0))'),
            ('local-alias-bitmap-accepted', '!bitmap_empty(dev->dma_alias_mask, PCI_DEVFN(31, 7) + 1)',
             '(false && !bitmap_empty(dev->dma_alias_mask, PCI_DEVFN(31, 7) + 1))'),
            ('foreign-dma-pointer-accepted', 'dev->dev.dma_mask != &dev->dma_mask ||', 'false ||'),
            ('streaming-mask-accepted', 'dev->dma_mask != DMA_BIT_MASK(32) ||', 'false ||'),
            ('coherent-mask-accepted', 'dev->dev.coherent_dma_mask != DMA_BIT_MASK(32))', 'false)'),
            ('root-header-accepted', 'dev->hdr_type == PCI_HEADER_TYPE_BRIDGE &&', 'true &&'),
            ('endpoint-header-accepted', 'dev->hdr_type == PCI_HEADER_TYPE_NORMAL &&', 'true &&'),
            ('root-pcie-type-accepted', 'pci_pcie_type(dev) == PCI_EXP_TYPE_ROOT_PORT)',
             '(pci_pcie_type(dev), true))'),
            ('endpoint-pcie-type-accepted', 'pci_pcie_type(dev) == PCI_EXP_TYPE_LEG_END)',
             '(pci_pcie_type(dev), true))'),
            ('endpoint-without-pcie', 'PCI_HEADER_TYPE_NORMAL && pci_is_pcie(dev) &&',
             'PCI_HEADER_TYPE_NORMAL && true &&'),
            ('legacy-root-refused', '!pci_is_pcie(dev) || pci_pcie_type(dev)',
             'pci_is_pcie(dev) && pci_pcie_type(dev)'),
            ('legacy-endpoint-refused', '|| pci_pcie_type(dev) == PCI_EXP_TYPE_LEG_END)', '|| false)'),
            ('root-bus-number-accepted', '!bus || bus->number ||', '!bus || false ||'),
            ('root-parent-accepted', 'bus->number || bus->parent ||', 'bus->number || false ||'),
            ('root-self-accepted', 'bus->parent || bus->self ||', 'bus->parent || false ||'),
            ('root-sysdata-accepted', 'bus->self || bus->sysdata != host ||', 'bus->self || false ||'),
            ('root-bus-owner-accepted', '!root || root->bus != bus ||', '!root || false ||'),
            ('endpoint-parent-accepted', 'dev->bus->parent != bus ||', 'false ||'),
            ('endpoint-sysdata-accepted', 'dev->bus->sysdata != host ||', 'false ||'),
            ('endpoint-bus-number-accepted', '(dev != root && (dev->bus->number != 1 ||',
             '(dev != root && (false ||'),
            ('root-subordinate-accepted', 'root->subordinate != dev->bus ||', 'false ||'),
            ('endpoint-subordinate-accepted', 'dev->class != 0x028000 || dev->subordinate ||',
             'dev->class != 0x028000 || false ||'),
            ('missing-group-accepted', 'if (!group)\n\t\treturn n71_scan_report_error(host, -EACCES);',
             'if (false)\n\t\treturn n71_scan_report_error(host, -EACCES);'),
            ('group-id-read-skipped', 'id = iommu_group_id(group);',
             'id = false ? iommu_group_id(group) : 7;'),
            ('group-ref-leaked', 'iommu_group_put(group);', '(void)iommu_group_put;'),
            ('group-ref-put-twice', 'iommu_group_put(group);', 'iommu_group_put(group); iommu_group_put(group);'),
            ('group-ref-put-before-read', 'id = iommu_group_id(group);\n\tiommu_group_put(group);',
             'iommu_group_put(group);\n\tid = iommu_group_id(group);'),
            ('negative-group-accepted', 'if (id < 0 ||', 'if (false ||'),
            ('zero-group-refused', 'if (id < 0 ||', 'if (id <= 0 ||'),
            ('foreign-group-accepted', '(host->iommu_devices && host->iommu_group_id != id)', 'false'),
            ('shared-id-lost', 'host->iommu_group_id = id;', 'host->iommu_group_id = -1;'),
            ('stale-group-after-removal', 'host->iommu_group_id = -1;', '(void)host;'),
            ('legacy-alias-inference-lost', 'if (dev != root && !pci_is_pcie(root))',
             'if (false && dev != root && !pci_is_pcie(root))'),
            ('requester-id-invented', '(dev->bus->number << 8) | dev->devfn, aliases, id,',
             '0, aliases, id,'),
        )
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            for name, before, after in mutations:
                with self.subTest(mutation=name):
                    result = self.compile_and_run(mutation=(before, after))
                    self.assertEqual(result.returncode, -6, 'Compilation/timeout is not a kill: ' + name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_DMA_TOPOLOGY_ASSERTION_KILL ' + name, flush=True)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)

    def test_resource_allocator_mutations_die_by_assertion(self):
        mutations = (
            ('readback-report-missing', 'assign', 'n71_resource_report_readback(host);', '(void)n71_resource_report_readback;'),
            ('readback-report-duplicate', 'assign', 'n71_resource_report_readback(host);',
             'n71_resource_report_readback(host); n71_resource_report_readback(host);'),
            ('readback-failure-lost', 'assign', 'failure->valid, failure->request.root', 'false, failure->request.root'),
            ('readback-root-lost', 'assign', 'failure->valid, failure->request.root', 'failure->valid, false'),
            ('readback-value-invented', 'assign', 'failure->after_valid, failure->after,', 'failure->after_valid, failure->request.value,'),
            ('readback-error-invented', 'assign', 'failure->write_error, failure->read_error, expected);',
             '1, failure->read_error, expected);'),
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
