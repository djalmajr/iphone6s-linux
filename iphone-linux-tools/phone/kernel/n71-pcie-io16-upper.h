/* SPDX-License-Identifier: GPL-2.0-only */
/* Ignore only the core's temporary upper disable request for a proved IO16 window. */
#ifndef N71_PCIE_IO16_UPPER_H
#define N71_PCIE_IO16_UPPER_H
#include "n71-pcie-scan-config.h"

static inline int n71_io16_upper_capture(u32 lower, u32 upper)
{
	/* Both type fields are IO16, with the measured unconfigured baseline. */
	return lower || upper ? -EACCES : 0;
}

static inline int n71_io16_upper_noop(const struct n71_scan_io *io,
				     const struct n71_scan_request *request,
				     u32 observed, bool *handled)
{
	u32 lower, upper;
	int error;

	*handled = false;
	if (!request->root || request->where != 0x30 ||
	    request->size != 4 || request->value != 0x0000ffff)
		return 0;
	if (observed)
		return -EAGAIN;
	error = n71_scan_read(io, true, 0x1c, 2, &lower);
	if (error)
		return error;
	/* Never read/write adjacent secondary STATUS or accept an enabled range. */
	if (lower != 0 && lower != 0x00f0)
		return -EAGAIN;
	error = n71_scan_read(io, true, 0x30, 4, &upper);
	if (error)
		return error;
	if (upper)
		return -EAGAIN;
	*handled = true;
	return 0;
}
#endif /* N71_PCIE_IO16_UPPER_H */
