/* SPDX-License-Identifier: GPL-2.0-only */
/* Derive typed PREF eligibility through the actual PCI adapter, then restore. */
#define main n71_existing_host_main
#include "n71_pcie_scan_host.c"
#undef main

int main(void)
{
	unsigned int mode;
	for (mode = 0; mode < 35; mode++) {
		struct device device = {0};
		struct n71_diagnostic state;
		struct n71_scan_host *host;
		struct resource *resource;
		const char *io16, *report, *readback;
		char expected_report[160];
		int expected = mode == 0 || mode == 20 ? 0 :
			mode == 2 || mode == 14 || mode == 15 || mode == 27 || mode == 32 || mode == 33 ? -EIO :
			mode == 13 ? -E2BIG : mode == 24 || mode == 25 ? -EBUSY :
			(mode >= 17 && mode <= 19) || mode == 31 ? -EAGAIN : -EACCES;
		bool captured = mode == 0 || mode == 2 || mode == 14 || mode == 15 ||
			(mode >= 17 && mode <= 20) || mode == 27 || (mode >= 31 && mode <= 33);
		bool enabled = captured && mode != 2 && mode != 27;
		unsigned int writes = mode == 0 || (mode >= 17 && mode <= 20) || mode == 31 ? 1 : 0;
		int actual;
		initialize_case(PME_NONE, true); mock.resource_mode = true;
		iomem_resource = (struct resource){0};
		mock.ecam[0x100004 / 4] &= ~3U;
		mock.ecam[0x100010 / 4] = mock.ecam[0x100018 / 4] = 4;
		mock.ecam[0x8020 / 4] = 0x12301230;
		mock.ecam[0x8024 / 4] = 0x10001;
		mock.pref_types_readonly = true;
		state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
		assert(n71_pcie_scan_hold(&device, &state) == 0);
		host = pci_host_bridge_priv(state.scan_bridge);
		mock.endpoint.resource[0] = (struct resource){.end = 0x7fff, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
		mock.endpoint.resource[2] = (struct resource){.end = 0x3fffff, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
		mock.root.resource[PCI_BRIDGE_MEM_WINDOW].flags = IORESOURCE_MEM;
		mock.root.pref_64_window = true;
		resource = &mock.root.resource[PCI_BRIDGE_PREF_MEM_WINDOW];
		*resource = (struct resource){.end = 0xfffff,
			.flags = IORESOURCE_MEM | IORESOURCE_PREFETCH | IORESOURCE_MEM_64 | PCI_PREF_RANGE_TYPE_64};
		/* Regression: the physical bus has empty bridge resources before sizing. */
		if (mode >= 20)
			memset(mock.root.resource, 0, sizeof(mock.root.resource));
		switch (mode) {
		case 1: mock.root.pref_window = false; break;
		case 2: mock.root.pref_64_window = false; break;
		case 3: mock.ecam[0x8024 / 4] = 1; break;
		case 4: mock.ecam[0x8024 / 4] = 0x10000; break;
		case 5: mock.ecam[0x8024 / 4] = 0x20002; break;
		case 6: resource->flags ^= IORESOURCE_MEM_64; break;
		case 7: resource->flags ^= IORESOURCE_PREFETCH; break;
		case 8: resource->flags |= IORESOURCE_UNSET; break;
		case 9: resource->start = 1; break;
		case 10: resource->end--; break;
		case 11: mock.ecam[0x8024 / 4] = 0x1fff1; break;
		case 12: mock.ecam[0x8028 / 4] = 1; break;
		case 13: host->reads = 4096; break;
		case 14: mock.pref_drop_address = true; break;
		case 15: mock.pref_clear_types = true; break;
		case 16: mock.ecam[0x802c / 4] = 1; break;
		case 17: case 18: case 19: mock.pref_final_drift = mode - 16; break;
		case 21: resource->start = 1; break;
		case 22: resource->end = 1; break;
		case 23: resource->end = 0xfffff; break;
		case 24: resource->parent = &foreign_resource; break;
		case 25: resource->child = &foreign_resource; break;
		case 26: mock.root.pref_window = false; break;
		case 27: mock.root.pref_64_window = false; break;
		case 28: mock.ecam[0x8024 / 4] = 1; break;
		case 29: mock.ecam[0x8028 / 4] = 1; break;
		case 30: mock.ecam[0x802c / 4] = 1; break;
		case 31: mock.pref_final_drift = 1; break;
		case 32: mock.pref_drop_address = true; break;
		case 33: mock.pref_clear_types = true; break;
		case 34: mock.ecam[0x8024 / 4] = 0x1fff1; break;
		}
		if (mode == 1 || mode == 2 || mode == 26 || mode == 27) {
			struct n71_resource_bar_layout unsupported = {0};
			assert(n71_resource_pref64_layout(&mock.root, &unsupported) == 0 && !unsupported.pref64_disable);
		}
		actual = n71_pcie_assign_resources(&state);
		if (actual != expected)
			fprintf(stderr, "PREF64 mode=%u actual=%d expected=%d\n", mode, actual, expected);
		assert(actual == expected);
		assert(host->resources.pending == captured && host->resources.pref64_disable == enabled);
		assert(host->resources.pref64_writes == writes && host->resources_assigned == (expected == 0));
		assert(!host->resources.active);
		if (!captured) assert(!mock.claims && !mock.assigning);
		if (mode == 14 || mode == 15 || mode == 32 || mode == 33) {
			assert(host->resources.failure.valid && host->resources.failure.expected == 0x1fff1);
			assert(host->resources.failure.request.value == 0xfff0);
			assert(strstr(mock.log, "read_error=0 expected=0001fff1; no additional IO"));
		}
		snprintf(expected_report, sizeof(expected_report),
			 "captured=%u enabled=%u writes=%u; full disabled readback with preserved types\n",
			 captured, enabled, writes);
		io16 = strstr(mock.log, "N71_PCIE_IO16_UPPER ");
		report = strstr(mock.log, "N71_PCIE_PREF64_DISABLE ");
		readback = strstr(mock.log, "N71_PCIE_ASSIGN_READBACK ");
		assert(io16 && report && readback && io16 < report && report < readback);
		assert(strstr(report, expected_report) && !strstr(report + 1, "N71_PCIE_PREF64_DISABLE "));
		assert(n71_pcie_assign_resources(&state) == (expected ? expected : -EALREADY));
		assert(!strstr(report + 1, "N71_PCIE_PREF64_DISABLE "));
		assert(n71_pcie_scan_cleanup(&state) == expected);
		assert(!state.scan_bridge && !iomem_resource.child && !mock.allocations && !mock.references);
		assert(mock.ecam[0x8024 / 4] == 0x10001 && mock.ecam[0x8028 / 4] == 0);
		/* A refused capture never owns the externally injected upper limit. */
		assert(mock.ecam[0x802c / 4] == (mode == 16 || mode == 30 ? 1U : 0U));
		assert(mock.ecam[0x100010 / 4] == 4 && mock.ecam[0x100018 / 4] == 4);
		assert(mock.scans == 1 && mock.removes == 1);
		free(mock.ecam);
	}
	printf("N71_PCIE_PREF64_HOST_OK cases=%u; PCI allocator synthetic\n", mode);
	return 0;
}
