/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise the real adapter against the PCI API backend and a read-only upper register. */
#define main n71_existing_host_main
#include "n71_pcie_scan_host.c"
#undef main

int main(void)
{
	unsigned int mode;
	for (mode = 0; mode < 20; mode++) {
		struct device device = {0};
		struct n71_diagnostic state;
		struct n71_scan_host *host;
		struct resource *resource;
		const char *optional, *report, *readback;
		char expected_report[192];
		int expected = mode == 0 || mode == 1 || mode == 6 ? 0 :
			mode == 2 || mode == 3 || mode == 4 || mode == 5 || mode == 15 || mode == 17 || mode == 19 ? -EIO :
			mode == 16 ? -ENODEV : -EACCES;
		bool captured = mode < 7 || mode == 17 || mode == 19;
		bool enabled = mode == 0 || mode == 1 || mode == 17;
		initialize_case(PME_NONE, true); mock.resource_mode = true;
		iomem_resource = (struct resource){0};
		mock.ecam[0x100004 / 4] &= ~3U;
		mock.ecam[0x100010 / 4] = mock.ecam[0x100018 / 4] = 4;
		mock.ecam[0x8020 / 4] = 0x12301230;
		state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
		assert(n71_pcie_scan_hold(&device, &state) == 0);
		host = pci_host_bridge_priv(state.scan_bridge);
		mock.endpoint.resource[0] = (struct resource){.end = 0x7fff, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
		mock.endpoint.resource[2] = (struct resource){.end = 0x3fffff, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
		mock.root.resource[PCI_BRIDGE_MEM_WINDOW].flags = IORESOURCE_MEM;
		mock.root.io_window_1k = false;
		mock.resource_fault = READBACK_DROP;
		resource = &mock.root.resource[PCI_BRIDGE_IO_WINDOW];
		switch (mode) {
		case 1: *resource = (struct resource){.end = 0xfff, .flags = IORESOURCE_IO}; break;
		case 2: mock.root.io_window_1k = true; break;
		case 3: mock.ecam[0x801c / 4] = 0x101; break;
		case 4: mock.ecam[0x801c / 4] = 0x100; break;
		case 5: mock.ecam[0x801c / 4] = 2; break;
		case 6: mock.root.io_window = false; mock.io_readonly = true; break;
		case 7: *resource = (struct resource){.end = 0xfff, .flags = IORESOURCE_MEM}; break;
		case 8: *resource = (struct resource){.end = 0xfff, .flags = IORESOURCE_IO | IORESOURCE_MEM_64}; break;
		case 9: *resource = (struct resource){.start = 1, .end = 0xfff, .flags = IORESOURCE_IO}; break;
		case 10: *resource = (struct resource){.end = 0xffe, .flags = IORESOURCE_IO}; break;
		case 11: resource->start = 1; break;
		case 12: resource->end = 1; break;
		case 13: mock.ecam[0x8030 / 4] = 1; break;
		case 14: mock.ecam[0x801c / 4] = 0xf0; break;
		case 15: host->reads = 4096; break;
		case 16: mock.endpoint.driver = &mock; break;
		case 17: mock.resource_fault = BAD_BAR; break;
		case 18: mock.root.io_window = false; resource->flags = IORESOURCE_IO; break;
		case 19: mock.ecam[0x801c / 4] = 0x101; resource->flags = IORESOURCE_IO | 1; break;
		}
		assert(n71_pcie_assign_resources(&state) == expected);
		assert(host->resources.pending == captured && host->resources.io16_upper_unused == enabled);
		assert(host->resources.io16_noops == (enabled ? 1U : 0U));
		assert(host->resources.io_noops == (mode == 6 ? 2U : 0U));
		assert(host->resources_assigned == (expected == 0) && !host->resources.active);
		if (!captured) assert(!mock.claims && !mock.assigning && !mock.optional_attempts);
		if (enabled) assert(mock.optional_attempts == 2 && !host->resources.failure.valid);
		snprintf(expected_report, sizeof(expected_report),
			 "captured=%u enabled=%u noops=%u; temporary upper disable without hardware write\n",
			 captured, enabled, enabled ? 1U : 0U);
		optional = strstr(mock.log, "N71_PCIE_OPTIONAL_WINDOWS ");
		report = strstr(mock.log, "N71_PCIE_IO16_UPPER ");
		readback = strstr(mock.log, "N71_PCIE_ASSIGN_READBACK ");
		assert(optional && report && readback && optional < report && report < readback);
		assert(strstr(report, expected_report) && !strstr(report + 1, "N71_PCIE_IO16_UPPER "));
		assert(n71_pcie_assign_resources(&state) == (expected ? expected : -EALREADY));
		assert(!strstr(report + 1, "N71_PCIE_IO16_UPPER "));
		assert(n71_pcie_scan_cleanup(&state) == expected);
		assert(!state.scan_bridge && !iomem_resource.child && !mock.allocations && !mock.references);
		assert(mock.ecam[0x8020 / 4] == 0x12301230 && mock.ecam[0x100010 / 4] == 4);
		assert(mock.ecam[0x100018 / 4] == 4 && mock.scans == 1 && mock.removes == 1);
		free(mock.ecam);
	}
	printf("N71_PCIE_IO16_HOST_OK cases=%u; PCI allocator synthetic\n", mode);
	return 0;
}
