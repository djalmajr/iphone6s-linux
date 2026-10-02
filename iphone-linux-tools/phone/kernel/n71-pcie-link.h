/* SPDX-License-Identifier: GPL-2.0-only */
/* Minimal N71 enumeration experiment, after global/port preparation. No DMA. */
#ifndef N71_PCIE_LINK_H
#define N71_PCIE_LINK_H
#include "n71-pcie-init.h"

struct n71_pcie_link_io {
	void *context;
	int (*read32)(void *context, bool root, u32 offset, u32 *value);
	int (*write32)(void *context, bool root, u32 offset, u32 value);
	int (*reset)(void *context, bool asserted);
	void (*delay_us)(void *context, unsigned int microseconds);
	int (*read_endpoint)(void *context, u32 offset, u32 *value);
};

static inline int n71_pcie_find_express(const struct n71_pcie_link_io *io, u32 *out)
{
	bool visited[64] = {false};
	u32 status, pointer, value;
	int error;

	error = io->read32(io->context, true, 4, &status);
	if (error)
		return error;
	if (status == 0xffffffff || !(status & (1U << 20)))
		return -ENODEV;
	error = io->read32(io->context, true, 0x34, &pointer);
	if (error)
		return error;
	pointer &= 0xff;
	while (pointer) {
		if (pointer < 0x40 || pointer > 0xfc || pointer % 4 || visited[pointer / 4])
			return -EINVAL;
		visited[pointer / 4] = true;
		error = io->read32(io->context, true, pointer, &value);
		if (error)
			return error;
		if (value == 0xffffffff)
			return -EIO;
		if ((value & 0xff) == 0x10) {
			if (pointer > 0xcc)
				return -EINVAL;
			*out = pointer;
			return 0;
		}
		pointer = (value >> 8) & 0xff;
	}
	return -ENODEV;
}

static inline bool n71_pcie_link_table_valid(const struct n71_pcie_tunable *table,
					    unsigned int count, bool root)
{
	unsigned int index;
	if (!n71_pcie_table_valid(table, count, root ? 0x1000 : 0x4000))
		return false;
	/* Do not write COMMAND/status, bus windows, IRQ mask, or LTSSM via tables. */
	for (index = 0; index < count; index++)
		if ((root && (table[index].offset < 0x40)) ||
		    (!root && (table[index].offset == 0x80 || table[index].offset == 0x104)))
			return false;
	return true;
}

static inline int n71_pcie_link_rmw(const struct n71_pcie_link_io *io, bool root,
				   u32 offset, u32 mask, u32 requested)
{
	u32 old, value;
	int error = io->read32(io->context, root, offset, &old);
	if (error)
		return error;
	if (old == 0xffffffff)
		return -EIO;
	value = (old & ~mask) | (requested & mask);
	return value == old ? 0 : io->write32(io->context, root, offset, value);
}

static inline int n71_pcie_apply_link_table(const struct n71_pcie_link_io *io,
					   bool root,
					   const struct n71_pcie_tunable *table,
					   unsigned int count)
{
	unsigned int index;
	int error;
	for (index = 0; index < count; index++) {
		error = n71_pcie_link_rmw(io, root, table[index].offset,
					 table[index].mask, table[index].value);
		if (error)
			return error;
	}
	return 0;
}

/* Returns endpoint identity only after link/COMMAND checks; never enables DMA.
 * Caller holds PERST at entry and owns power/map validation and final cleanup.
 */
static inline int n71_pcie_enumerate_wlan(const struct n71_pcie_link_io *io,
					 const struct n71_pcie_tunable *root,
					 unsigned int root_count,
					 const struct n71_pcie_tunable *port,
					 unsigned int port_count, u32 *identity)
{
	u32 cap, value, endpoint;
	unsigned int attempt;
	int error, cleanup;

	if (!io || !io->read32 || !io->write32 || !io->reset || !io->delay_us ||
	    !io->read_endpoint || !identity ||
	    !n71_pcie_link_table_valid(root, root_count, true) ||
	    !n71_pcie_link_table_valid(port, port_count, false))
		return -EINVAL;
	error = n71_pcie_find_express(io, &cap);
	if (error)
		return error;
	for (attempt = 0; attempt < root_count; attempt++)
		if (root[attempt].offset == cap + 0x30 &&
		    ((root[attempt].value ^ 1) & root[attempt].mask & 0xf))
			return -EINVAL;
	error = io->reset(io->context, false);
	if (error)
		goto fail;
	io->delay_us(io->context, 100000);
	error = n71_pcie_link_rmw(io, true, cap + 0x30, 0xf, 1);
	if (error)
		goto fail;
	error = n71_pcie_apply_link_table(io, true, root, root_count);
	if (error)
		goto fail;
	error = n71_pcie_apply_link_table(io, false, port, port_count);
	if (error)
		goto fail;
	/* Root bus0, secondary/subordinate1; preserve secondary latency byte. */
	error = n71_pcie_link_rmw(io, true, 0x18, 0xffffff, 0x010100);
	if (error)
		goto fail;
	error = io->write32(io->context, false, 0x104, 0);
	if (error)
		goto fail;
	error = n71_pcie_link_rmw(io, false, 0x140, 1U << 31, 1U << 31);
	if (error)
		goto fail;
	error = io->write32(io->context, false, 0x124, 0x31);
	if (error)
		goto fail;
	error = io->write32(io->context, false, 0x128, 0x80008);
	if (error)
		goto fail;
	error = n71_pcie_link_rmw(io, false, 0x80, 1, 1);
	if (error)
		goto fail;
	for (attempt = 0; attempt < 10000; attempt++) {
		error = io->read32(io->context, false, 0x88, &value);
		if (error || value == 0xffffffff) {
			error = error ? error : -EIO;
			goto fail;
		}
		if (value & 1)
			break;
		if (attempt + 1 < 10000)
			io->delay_us(io->context, 100);
	}
	if (attempt == 10000) {
		error = -ETIMEDOUT;
		goto fail;
	}
	error = io->read_endpoint(io->context, 0, &endpoint);
	if (error || !(endpoint & 0xffff) || (endpoint & 0xffff) == 0xffff) {
		error = error ? error : -ENODEV;
		goto fail;
	}
	error = io->read_endpoint(io->context, 4, &value);
	if (error || value == 0xffffffff || value & 4) {
		error = error ? error : -EACCES;
		goto fail;
	}
	*identity = endpoint;
	return 0;
fail:
	cleanup = io->reset(io->context, true);
	return cleanup ? cleanup : error;
}

#endif /* N71_PCIE_LINK_H */
