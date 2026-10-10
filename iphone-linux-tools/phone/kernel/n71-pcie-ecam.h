/* SPDX-License-Identifier: GPL-2.0-only */
/* Read-only coordinates for the measured N71 root port1 and WLAN endpoint. */
#ifndef N71_PCIE_ECAM_H
#define N71_PCIE_ECAM_H

#include "n71-pcie-contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

struct n71_pcie_ecam_location {
	u32 dword_offset;
	unsigned int shift;
	u32 mask;
	bool root;
};

struct n71_pcie_ecam_io {
	void *context;
	int (*read32)(void *context, u32 dword_offset, u32 *value);
};

/* Exact N71 aperture; no remap, other port, downstream bus or function. */
static inline int n71_pcie_ecam_locate(u32 aperture, unsigned int bus,
				       unsigned int devfn, int where, unsigned int size,
				       struct n71_pcie_ecam_location *out)
{
	struct n71_pcie_ecam_location result;
	u32 base;

	if (!out || aperture != 0x1000000 ||
	    (size != 1 && size != 2 && size != 4) ||
	    where < 0 || where > (int)(0x1000 - size) || where % size)
		return -EINVAL;
	if (bus > 1 || (bus == 0 && devfn != 8) || (bus == 1 && devfn != 0))
		return -ENODEV;
	base = bus == 0 ? 0x8000 : 0x100000;
	result.dword_offset = base + ((u32)where & ~3U);
	result.shift = ((u32)where & 3) * 8;
	result.mask = size == 4 ? 0xffffffff : (1U << (size * 8)) - 1;
	result.root = bus == 0;
	*out = result;
	return 0;
}

/* Caller validates N71 resource ownership/clocks/link before invoking I/O. */
static inline int n71_pcie_ecam_read(const struct n71_pcie_ecam_io *io, u32 aperture,
				     unsigned int bus, unsigned int devfn,
				     int where, unsigned int size, u32 *out)
{
	struct n71_pcie_ecam_location location;
	u32 raw;
	int error;

	if (!io || !io->read32 || !out)
		return -EINVAL;
	error = n71_pcie_ecam_locate(aperture, bus, devfn, where, size, &location);
	if (error)
		return error;
	error = io->read32(io->context, location.dword_offset, &raw);
	if (error)
		return error < 0 ? error : -EIO;
	*out = (raw >> location.shift) & location.mask;
	return 0;
}

#endif /* N71_PCIE_ECAM_H */
