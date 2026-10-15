/* SPDX-License-Identifier: GPL-2.0-only */
/* Endpoint BAR sizing with decode disabled and mandatory config restoration. */
#ifndef N71_PCIE_BAR_SIZING_H
#define N71_PCIE_BAR_SIZING_H
#include "n71-pcie-scan-config.h"
#ifndef __KERNEL__
typedef uint64_t u64;
#endif

struct n71_bar_sizes {
	u32 masks[6];
	u64 bytes[6];
};

static inline int n71_bar_decode(const u32 original[6], struct n71_bar_sizes *sizes)
{
	unsigned int bar;
	u64 mask, size, width;
	u32 type;

	for (bar = 0; bar < 6; bar++) {
		type = original[bar] & 0xf;
		if ((type & 1) || (type & 6) == 2 || (type & 6) == 6)
			return -EINVAL;
		mask = sizes->masks[bar] & ~0xfU;
		width = 0xffffffffULL;
		if ((type & 6) == 4) {
			if (bar == 5)
				return -EINVAL;
			mask |= (u64)sizes->masks[bar + 1] << 32;
			width = ~0ULL;
		} else if (!sizes->masks[bar] && !original[bar]) {
			continue; /* Unimplemented 32-bit word. */
		}
		if ((sizes->masks[bar] & 0xf) != type || !mask)
			return -EINVAL;
		size = ((~mask) & width) + 1;
		if (!size || (size & (size - 1)) || size < 16 ||
		    size > ((type & 6) == 4 ? 0x1a0000000ULL : 0x40000000ULL))
			return -EINVAL;
		sizes->bytes[bar] = size;
		if ((type & 6) == 4)
			bar++; /* The upper word is not a second resource. */
	}
	return 0;
}

static inline int n71_bar_probe(const struct n71_scan_io *io,
				struct n71_scan_config *config, struct n71_bar_sizes *sizes)
{
	struct n71_scan_request request = {false, 4, config->saved[1].command & ~3U, 2};
	unsigned int bar;
	int error = n71_scan_write(io, config, &request);

	for (bar = 0; !error && bar < 6; bar++) {
		request = (struct n71_scan_request){false, 0x10 + bar * 4, 0xffffffff, 4};
		error = n71_scan_write(io, config, &request);
		if (!error)
			error = n71_scan_read(io, false, request.where, 4, &sizes->masks[bar]);
		if (!error) {
			request.value = config->saved[1].bars[bar];
			error = n71_scan_write(io, config, &request);
		}
	}
	return error ? error : n71_bar_decode(config->saved[1].bars, sizes);
}

/* Never publish sizes after a partial probe or unverified restore. */
static inline int n71_bar_collect(const struct n71_scan_io *io,
				  struct n71_scan_config *config,
				  struct n71_bar_sizes *out, int *restore_error)
{
	struct n71_bar_sizes result = {0};
	int error, restore;

	if (!config || !out || !restore_error)
		return -EINVAL;
	*restore_error = 0;
	error = n71_scan_capture(io, config);
	if (error)
		return error;
	error = n71_bar_probe(io, config, &result);
	restore = n71_scan_restore(io, config);
	*restore_error = restore;
	if (!error)
		error = restore;
	if (!error)
		*out = result;
	return error;
}
#endif /* N71_PCIE_BAR_SIZING_H */
