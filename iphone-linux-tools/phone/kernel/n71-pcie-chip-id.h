/* SPDX-License-Identifier: GPL-2.0-only */
/* One ChipCommon ID read through a temporary BAR0 route; never enable DMA. */
#ifndef N71_PCIE_CHIP_ID_H
#define N71_PCIE_CHIP_ID_H
#include "n71-pcie-bar-sizing.h"

#define N71_CHIP_BAR0_CPU 0x7c0000000ULL
#define N71_CHIP_BAR0_BYTES 0x8000U

struct n71_chip_io {
	struct n71_scan_io config;
	int (*read_chip)(void *context, u32 *value);
};

struct n71_chip_identity {
	u32 raw, chip, revision;
};

static inline int n71_chip_restore(const struct n71_scan_io *io,
				   struct n71_scan_config *config, u32 memory, u32 window)
{
	int error, first = 0;
	unsigned int function;

	for (function = 0; function < 2; function++) {
		error = n71_scan_restore_value(io, function == 0, 4, 2,
					       config->saved[function].command & ~3U);
		if (error && !first)
			first = error;
	}
	if (!first) {
		error = n71_scan_restore_value(io, false, 0x80, 4, window);
		if (error)
			first = error;
		error = n71_scan_restore_value(io, true, 0x20, 4, memory);
		if (error && !first)
			first = error;
	}
	/* Never reenable decode after a failed route/window restore. */
	if (first)
		for (function = 0; function < 2; function++)
			config->saved[function].command &= ~3U;
	error = n71_scan_restore(io, config);
	return first ? first : error;
}

static inline int n71_chip_collect(const struct n71_chip_io *io,
				   const struct n71_bar_sizes *measured,
				   struct n71_scan_config *config,
				   struct n71_chip_identity *out, int *restore_error)
{
	struct n71_chip_identity result;
	struct n71_scan_request steps[8];
	u32 memory = 0, window = 0, command;
	unsigned int step, function;
	bool attempted = false;
	int error, restore;

	if (!io || !io->read_chip || !measured || !config || !out || !restore_error)
		return -EINVAL;
	*restore_error = 0;
	error = n71_scan_capture(&io->config, config);
	if (error)
		return error;
	if (measured->bytes[0] != N71_CHIP_BAR0_BYTES || measured->bytes[1] ||
	    measured->masks[0] != 0xffff8004 || measured->masks[1] != 0xffffffff ||
	    config->saved[1].bars[0] != 4 || config->saved[1].bars[1] ||
	    (config->saved[0].command & 3) || (config->saved[1].command & 3)) {
		error = -EACCES;
		goto restore;
	}
	error = n71_scan_read(&io->config, true, 0x20, 4, &memory);
	if (!error)
		error = n71_scan_read(&io->config, false, 0x80, 4, &window);
	if (!error && (memory & 0x000f000f))
		error = -EINVAL;
	if (error)
		goto restore;
	steps[0] = (struct n71_scan_request){true, 4, config->saved[0].command & ~3U, 2};
	steps[1] = (struct n71_scan_request){false, 4, config->saved[1].command & ~3U, 2};
	steps[2] = (struct n71_scan_request){false, 0x14, 0, 4};
	steps[3] = (struct n71_scan_request){false, 0x10, 0xc0000004, 4};
	steps[4] = (struct n71_scan_request){true, 0x20, 0xc000c000, 4};
	steps[5] = (struct n71_scan_request){false, 0x80, 0x18000000, 4};
	steps[6] = (struct n71_scan_request){true, 4, (config->saved[0].command & ~3U) | 2, 2};
	steps[7] = (struct n71_scan_request){false, 4, (config->saved[1].command & ~3U) | 2, 2};
	attempted = true;
	for (step = 0; step < 8; step++) {
		error = n71_scan_restore_value(&io->config, steps[step].root,
					       steps[step].where, steps[step].size, steps[step].value);
		if (error)
			goto restore;
	}
	for (function = 0; function < 2; function++) {
		error = n71_scan_read(&io->config, function == 0, 4, 2, &command);
		if (!error && (command & 7) != 2)
			error = -EACCES;
		if (error)
			goto restore;
	}
	error = io->read_chip(io->config.context, &result.raw);
	if (error > 0)
		error = -EIO;
	if (!error) {
		result.chip = result.raw & 0xffff;
		result.revision = (result.raw >> 16) & 0xf;
		if (result.chip != 0x4350 || result.raw >> 28 != 1)
			error = -ENODEV;
	}
restore:
	restore = attempted ? n71_chip_restore(&io->config, config, memory, window) :
		n71_scan_restore(&io->config, config);
	*restore_error = restore;
	if (!error)
		error = restore;
	if (!error)
		*out = result;
	return error;
}
#endif /* N71_PCIE_CHIP_ID_H */
