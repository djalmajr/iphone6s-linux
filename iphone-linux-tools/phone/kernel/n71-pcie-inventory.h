/* SPDX-License-Identifier: GPL-2.0-only */
/* Bounded endpoint config reads. No BAR sizing, config writes or DMA. */
#ifndef N71_PCIE_INVENTORY_H
#define N71_PCIE_INVENTORY_H

#include "n71-pcie-contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

#define N71_PCIE_WLAN_ID 0x43a314e4U
#define N71_PCIE_INVENTORY_MAX_READS 63U

struct n71_pcie_inventory_io {
	void *context;
	int (*read32)(void *context, u32 offset, u32 *value);
};

struct n71_pcie_inventory {
	u32 identity, command_status, class_revision, header;
	u32 bars[6], subsystem, interrupt;
	u32 express_offset, express_header;
	u32 msi_offset, msi_header, msix_offset, msix_header;
	unsigned int reads, capabilities;
};

static inline int n71_pcie_inventory_read(const struct n71_pcie_inventory_io *io,
					  struct n71_pcie_inventory *result,
					  u32 offset, u32 *value)
{
	if (offset % 4 || offset > 0xfc ||
	    result->reads >= N71_PCIE_INVENTORY_MAX_READS)
		return -EINVAL;
	result->reads++;
	return io->read32(io->context, offset, value);
}

/* Caller must first prove link and hold its resources until this returns. */
static inline int n71_pcie_inventory_collect(const struct n71_pcie_inventory_io *io,
					     struct n71_pcie_inventory *out)
{
	struct n71_pcie_inventory result = {0};
	bool visited[64] = {false};
	u32 pointer, value, identity, command;
	unsigned int index;
	int error;

	if (!io || !io->read32 || !out)
		return -EINVAL;
	error = n71_pcie_inventory_read(io, &result, 0, &result.identity);
	if (error)
		return error;
	if (result.identity != N71_PCIE_WLAN_ID)
		return -ENODEV;
	error = n71_pcie_inventory_read(io, &result, 4, &result.command_status);
	if (error)
		return error;
	if (result.command_status == 0xffffffff || (result.command_status & 4))
		return -EACCES;
	error = n71_pcie_inventory_read(io, &result, 8, &result.class_revision);
	if (!error)
		error = n71_pcie_inventory_read(io, &result, 0xc, &result.header);
	if (error)
		return error;
	if (result.class_revision == 0xffffffff || ((result.header >> 16) & 0x7f))
		return -ENODEV;
	for (index = 0; index < 6; index++) {
		error = n71_pcie_inventory_read(io, &result, 0x10 + 4 * index,
						&result.bars[index]);
		if (error)
			return error;
	}
	error = n71_pcie_inventory_read(io, &result, 0x2c, &result.subsystem);
	if (!error)
		error = n71_pcie_inventory_read(io, &result, 0x3c, &result.interrupt);
	if (error)
		return error;
	if (!(result.command_status & (1U << 20)))
		return -ENODEV;
	error = n71_pcie_inventory_read(io, &result, 0x34, &pointer);
	if (error)
		return error;
	pointer &= 0xff;
	while (pointer) {
		if (pointer < 0x40 || pointer > 0xfc || pointer % 4 ||
		    visited[pointer / 4])
			return -EINVAL;
		visited[pointer / 4] = true;
		error = n71_pcie_inventory_read(io, &result, pointer, &value);
		if (error)
			return error;
		if (!(value & 0xff) || (value & 0xff) == 0xff)
			return -EIO;
		result.capabilities++;
		switch (value & 0xff) {
		case 0x10:
			if (result.express_offset || pointer > 0xcc ||
			    ((value >> 20) & 0xf) > 1)
				return -EINVAL;
			result.express_offset = pointer;
			result.express_header = value;
			break;
		case 5:
			if (result.msi_offset)
				return -EINVAL;
			result.msi_offset = pointer;
			result.msi_header = value;
			break;
		case 0x11:
			if (result.msix_offset)
				return -EINVAL;
			result.msix_offset = pointer;
			result.msix_header = value;
			break;
		}
		pointer = (value >> 8) & 0xff;
	}
	if (!result.express_offset)
		return -ENODEV;
	error = n71_pcie_inventory_read(io, &result, 0, &identity);
	if (!error)
		error = n71_pcie_inventory_read(io, &result, 4, &command);
	if (error)
		return error;
	if (command == 0xffffffff || (command & 4))
		return -EACCES;
	if (identity != result.identity || ((command ^ result.command_status) & 0xffff))
		return -EAGAIN;
	*out = result;
	return 0;
}

#endif /* N71_PCIE_INVENTORY_H */
