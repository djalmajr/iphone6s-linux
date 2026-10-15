/* SPDX-License-Identifier: GPL-2.0-only */
/* Independent N71 reference cases and preservation/refusal properties. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-contract.h"

static void resource_map(void)
{
	/* Cross-checked against the Apple ADT resource array, not the helpers. */
	const u32 expected[4][5] = {
		{0, 1, 2, 9, 10}, {0, 3, 4, 9, 10},
		{0, 5, 6, 9, 10}, {0, 7, 8, 9, 10},
	};
	u32 port;

	for (port = 0; port < 4; port++) {
		struct n71_pcie_resources result;
		assert(n71_pcie_resource_indices(port, &result));
		assert(result.ecam == expected[port][0]);
		assert(result.port == expected[port][1]);
		assert(result.nvmmu == expected[port][2]);
		assert(result.common == expected[port][3]);
		assert(result.phy == expected[port][4]);
	}
}

static void register_map(void)
{
	/* Values independently decoded from the S8000 selector jump table. */
	const u32 expected[4][6] = {
		{0x24, 0x2c, 0x100, 0x114, 0x124, 0x12c},
		{0x24, 0x2c, 0x180, 0x194, 0x1a4, 0x1ac},
		{0x24, 0x2c, 0x200, 0x214, 0x224, 0x22c},
		{0x24, 0x2c, 0x280, 0x294, 0x2a4, 0x2ac},
	};
	u32 port, id, offset;

	for (port = 0; port < 4; port++)
		for (id = 0; id < 6; id++) {
			assert(n71_pcie_common_offset(id, port, &offset));
			assert(offset == expected[port][id]);
			assert(offset % 4 == 0 && offset < 0x8000);
		}
}

static void preservation(void)
{
	const u32 offsets[] = {0x180, 0x180, 0x180, 0x194, 0x194, 0x1a4};
	const u32 masks[] = {1, 0x100, 0x100000, 1, 0x100, 1};
	const bool inverse[] = {false, false, false, false, true, true};
	u32 control, bit, setting;

	for (control = 0; control < 6; control++)
		for (bit = 0; bit < 32; bit++)
			for (setting = 0; setting < 2; setting++) {
				struct n71_pcie_update result;
				u32 old = 0xa5a55a5aU ^ (1U << bit);
				assert(n71_pcie_control_update(control, 1, setting, old, &result));
				assert(result.offset == offsets[control]);
				assert((result.value & ~masks[control]) == (old & ~masks[control]));
				assert(!!(result.value & masks[control]) == (setting != inverse[control]));
			}
}

static void refused_without_output(void)
{
	struct n71_pcie_resources resources = {17, 18, 19, 20, 21};
	struct n71_pcie_resources saved = resources;
	struct n71_pcie_update update = {0x1234, 0xabcdef};
	u32 offset = 0x1234;
	u32 invalid[] = {4, 5, 0xffffffffU};
	size_t index;

	for (index = 0; index < sizeof(invalid) / sizeof(invalid[0]); index++) {
		assert(!n71_pcie_resource_indices(invalid[index], &resources));
		assert(memcmp(&resources, &saved, sizeof(saved)) == 0);
		assert(!n71_pcie_common_offset(2, invalid[index], &offset));
		assert(offset == 0x1234);
		assert(!n71_pcie_control_update(N71_ID2_BIT0, invalid[index], true, 0, &update));
		assert(update.offset == 0x1234 && update.value == 0xabcdef);
	}
	assert(!n71_pcie_common_offset(6, 1, &offset));
	assert(offset == 0x1234);
	assert(!n71_pcie_control_update((enum n71_pcie_control)-1, 1, true, 0, &update));
	assert(!n71_pcie_control_update((enum n71_pcie_control)6, 1, true, 0, &update));
	assert(update.offset == 0x1234 && update.value == 0xabcdef);
	assert(!n71_pcie_resource_indices(1, NULL));
	assert(!n71_pcie_common_offset(2, 1, NULL));
	assert(!n71_pcie_control_update(N71_ID2_BIT0, 1, true, 0, NULL));
}

int main(void)
{
	resource_map();
	register_map();
	preservation();
	refused_without_output();
	puts("N71_PCIE_PRIMITIVES_OK; software contract only; no MMIO");
	return 0;
}
