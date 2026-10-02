/* SPDX-License-Identifier: GPL-2.0-only */
/* S8000 global initialization, using caller-owned I/O and private tunables. */
#ifndef N71_PCIE_INIT_H
#define N71_PCIE_INIT_H

#include "n71-pcie-contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

#define N71_PCIE_POLL_INTERVAL_US 10U
#define N71_PCIE_POLL_ATTEMPTS 10000U
#define N71_PCIE_MAX_TUNABLES 512U

enum n71_pcie_region {
	N71_PCIE_COMMON,
	N71_PCIE_PHY,
};

struct n71_pcie_tunable {
	u32 offset;
	u32 mask;
	u32 value;
};

struct n71_pcie_io {
	void *context;
	int (*read32)(void *context, enum n71_pcie_region region, u32 offset,
		      u32 *value);
	int (*write32)(void *context, enum n71_pcie_region region, u32 offset,
		       u32 value);
	void (*delay_us)(void *context, unsigned int microseconds);
};

struct n71_pcie_global_config {
	u32 lane_config;
	const struct n71_pcie_tunable *phy;
	unsigned int phy_count;
	const struct n71_pcie_tunable *common;
	unsigned int common_count;
};

static inline bool n71_pcie_table_valid(const struct n71_pcie_tunable *table,
				       unsigned int count, u32 aperture)
{
	unsigned int index;

	if (!table || !count || count > N71_PCIE_MAX_TUNABLES || aperture < 4)
		return false;
	for (index = 0; index < count; index++)
		if (table[index].offset % 4 || table[index].offset > aperture - 4)
			return false;
	return true;
}

static inline int n71_pcie_apply_table(const struct n71_pcie_io *io,
				      enum n71_pcie_region region,
				      const struct n71_pcie_tunable *table,
				      unsigned int count)
{
	unsigned int index;
	u32 old, value;
	int error;

	if (!io || !io->read32 || !io->write32 ||
	    (region != N71_PCIE_COMMON && region != N71_PCIE_PHY) ||
	    !n71_pcie_table_valid(table, count, region == N71_PCIE_PHY ? 0x4000 : 0x8000))
		return -EINVAL;
	for (index = 0; index < count; index++) {
		error = io->read32(io->context, region, table[index].offset, &old);
		if (error)
			return error;
		value = (old & ~table[index].mask) | (table[index].value & table[index].mask);
		if (value == old)
			continue;
		error = io->write32(io->context, region, table[index].offset, value);
		if (error)
			return error;
	}
	return 0;
}

/* Caller must validate/power/map the N71 resources and hold endpoint reset. */
static inline int n71_pcie_initialize_global(const struct n71_pcie_io *io,
					   const struct n71_pcie_global_config *config)
{
	unsigned int attempt;
	u32 status;
	int error;

	/* Check both complete tables before the first I/O; only N71 lane config1. */
	if (!io || !io->read32 || !io->write32 || !io->delay_us || !config ||
	    config->lane_config != 1 ||
	    !n71_pcie_table_valid(config->phy, config->phy_count, 0x4000) ||
	    !n71_pcie_table_valid(config->common, config->common_count, 0x8000))
		return -EINVAL;
	/* S8000 global function: common4, poll common2c bit0, common38, PHY/common. */
	error = io->write32(io->context, N71_PCIE_COMMON, 0x4, config->lane_config | 0x10);
	if (error)
		return error;
	for (attempt = 0; attempt < N71_PCIE_POLL_ATTEMPTS; attempt++) {
		error = io->read32(io->context, N71_PCIE_COMMON, 0x2c, &status);
		if (error)
			return error;
		if (status == 0xffffffff)
			return -EIO;
		if (status & 1)
			break;
		if (attempt + 1 < N71_PCIE_POLL_ATTEMPTS)
			io->delay_us(io->context, N71_PCIE_POLL_INTERVAL_US);
	}
	if (attempt == N71_PCIE_POLL_ATTEMPTS)
		return -ETIMEDOUT;
	error = io->write32(io->context, N71_PCIE_COMMON, 0x38, 1);
	if (error)
		return error;
	error = n71_pcie_apply_table(io, N71_PCIE_PHY, config->phy, config->phy_count);
	if (error)
		return error;
	return n71_pcie_apply_table(io, N71_PCIE_COMMON, config->common, config->common_count);
}

#endif /* N71_PCIE_INIT_H */
