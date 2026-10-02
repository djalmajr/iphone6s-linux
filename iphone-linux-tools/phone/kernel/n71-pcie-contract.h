/* SPDX-License-Identifier: GPL-2.0-only */
/* S8000 primitives derived from the N71 reference. No hardware access here. */
#ifndef N71_PCIE_CONTRACT_H
#define N71_PCIE_CONTRACT_H

#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stdbool.h>
#include <stdint.h>
typedef uint32_t u32;
#endif

#define N71_PCIE_PORT_COUNT 4U
#define N71_PCIE_WLAN_PORT 1U

struct n71_pcie_resources {
	u32 ecam;
	u32 port;
	u32 nvmmu;
	u32 common;
	u32 phy;
};

/* Apple resource numbering, not Linux PCI function or stream numbering. */
static inline bool n71_pcie_resource_indices(u32 port,
					    struct n71_pcie_resources *out)
{
	if (!out || port >= N71_PCIE_PORT_COUNT)
		return false;
	out->ecam = 0;
	out->port = 2 * port + 1;
	out->nvmmu = 2 * port + 2;
	out->common = 2 * N71_PCIE_PORT_COUNT + 1;
	out->phy = 2 * N71_PCIE_PORT_COUNT + 2;
	return true;
}

/* IDs in the S8000 virtual register selector; semantic names are unproven. */
static inline bool n71_pcie_common_offset(u32 id, u32 port, u32 *out)
{
	u32 value;

	if (!out || port >= N71_PCIE_PORT_COUNT || id > 5)
		return false;
	switch (id) {
	case 0:
		value = 0x24;
		break;
	case 1:
		value = 0x2c;
		break;
	case 2:
		value = 0x100 + port * 0x80;
		break;
	case 3:
		value = 0x114 + port * 0x80;
		break;
	case 4:
		value = 0x124 + port * 0x80;
		break;
	default:
		value = 0x12c + port * 0x80;
		break;
	}
	*out = value;
	return true;
}

enum n71_pcie_control {
	N71_ID2_BIT0,
	N71_ID2_BIT8,
	N71_ID2_BIT20,
	N71_ID3_BIT0,
	N71_ID3_BIT8_INVERTED,
	N71_ID4_BIT0_INVERTED,
};

struct n71_pcie_update {
	u32 offset;
	u32 value;
};

/* Compute one RMW without clearing unrelated bits or touching MMIO. */
static inline bool n71_pcie_control_update(enum n71_pcie_control control,
					  u32 port, bool enabled, u32 old,
					  struct n71_pcie_update *out)
{
	u32 id, mask, offset;
	bool inverted = false;

	if (!out)
		return false;
	switch (control) {
	case N71_ID2_BIT0:
		id = 2;
		mask = 1;
		break;
	case N71_ID2_BIT8:
		id = 2;
		mask = 1U << 8;
		break;
	case N71_ID2_BIT20:
		id = 2;
		mask = 1U << 20;
		break;
	case N71_ID3_BIT0:
		id = 3;
		mask = 1;
		break;
	case N71_ID3_BIT8_INVERTED:
		id = 3;
		mask = 1U << 8;
		inverted = true;
		break;
	case N71_ID4_BIT0_INVERTED:
		id = 4;
		mask = 1;
		inverted = true;
		break;
	default:
		return false;
	}
	if (!n71_pcie_common_offset(id, port, &offset))
		return false;
	out->offset = offset;
	out->value = (old & ~mask) | ((enabled != inverted) ? mask : 0);
	return true;
}

#endif /* N71_PCIE_CONTRACT_H */
