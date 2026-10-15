/* SPDX-License-Identifier: GPL-2.0-only */
/* Reuse the PCI API backend; keep new absent-range scenarios separately. */
#define main n71_existing_host_main
#include "n71_pcie_scan_host.c"
#undef main

int main(void)
{
	unsigned int mode;
	for (mode = 0; mode < 18; mode++) {
		struct device device = {0};
		struct n71_diagnostic state;
		struct n71_scan_host *host;
		char expected_report[256];
		const char *report, *readback;
		int expected = mode == 0 || mode == 1 || mode == 14 ? 0 :
			mode == 2 || mode == 15 || mode == 17 ? -EIO : mode == 16 ? -ENODEV : -EACCES;
		unsigned int io_noops = mode == 0 || mode == 1 || mode == 15 ? 2 : 0;
		unsigned int pref_noops = mode == 0 || mode == 15 ? 1 : 0;
		bool captured = mode == 0 || mode == 1 || mode == 2 || mode == 14 || mode == 15 || mode == 17;

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
		mock.root.io_window = mode == 2 || mode == 14 || mode == 17;
		mock.root.pref_window = mode == 1 || mode == 2 || mode == 14 || mode == 17;
		mock.io_readonly = !mock.root.io_window || mode == 2;
		mock.pref_readonly = !mock.root.pref_window || mode == 17;
		switch (mode) {
		case 3: mock.ecam[0x8030 / 4] = 1; break;
		case 4: mock.root.resource[PCI_BRIDGE_IO_WINDOW].flags = 1; break;
		case 5: mock.root.resource[PCI_BRIDGE_PREF_MEM_WINDOW].end = 1; break;
		case 6: mock.root.resource[PCI_BRIDGE_PREF_MEM_WINDOW].start = 1; break;
		case 7: mock.root.resource[PCI_BRIDGE_PREF_MEM_WINDOW].flags = 1; break;
		case 8: mock.root.resource[PCI_BRIDGE_IO_WINDOW].start = 1; break;
		case 9: mock.root.resource[PCI_BRIDGE_IO_WINDOW].end = 1; break;
		case 10: mock.ecam[0x801c / 4] = 1; break;
		case 11: mock.ecam[0x8024 / 4] = 1; break;
		case 12: mock.ecam[0x8028 / 4] = 1; break;
		case 13: mock.ecam[0x802c / 4] = 1; break;
		case 15: mock.resource_fault = BAD_BAR; break;
		case 16: mock.endpoint.driver = &mock; break;
		}
		assert(n71_pcie_assign_resources(&state) == expected);
		assert(host->resources.io_noops == io_noops && host->resources.pref_noops == pref_noops);
		assert(host->resources_assigned == (expected == 0) && !host->resources.active);
		if (mode == 0 || mode == 15) assert(mock.optional_attempts == 0);
		if (mode == 1) assert(mock.optional_attempts == 1);
		if (mode == 14) assert(mock.optional_attempts == 4);
		if (!captured) assert(mock.claims == 0 && mock.assigning == 0 && mock.optional_attempts == 0);
		snprintf(expected_report, sizeof(expected_report),
			 "captured=%u io_absent=%u pref_absent=%u io_noops=%u pref_noops=%u; absent ranges are emulated without hardware writes\n",
			 captured, captured && !mock.root.io_window, captured && !mock.root.pref_window, io_noops, pref_noops);
		report = strstr(mock.log, "N71_PCIE_OPTIONAL_WINDOWS ");
		readback = strstr(mock.log, "N71_PCIE_ASSIGN_READBACK ");
		assert(report && readback && report < readback && strstr(report, expected_report));
		assert(!strstr(report + 1, "N71_PCIE_OPTIONAL_WINDOWS "));
		assert(n71_pcie_assign_resources(&state) == (expected ? expected : -EALREADY));
		assert(!strstr(report + 1, "N71_PCIE_OPTIONAL_WINDOWS "));
		assert(n71_pcie_scan_cleanup(&state) == expected);
		assert(!state.scan_bridge && !iomem_resource.child && !mock.allocations && !mock.references);
		assert(mock.ecam[0x8020 / 4] == 0x12301230 && mock.ecam[0x100010 / 4] == 4);
		assert(mock.ecam[0x100018 / 4] == 4 && mock.scans == 1 && mock.removes == 1);
		free(mock.ecam);
	}
	printf("N71_PCIE_OPTIONAL_HOST_OK cases=%u; PCI allocator synthetic\n", mode);
	return 0;
}
