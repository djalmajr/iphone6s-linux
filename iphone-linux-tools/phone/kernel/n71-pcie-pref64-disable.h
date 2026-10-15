/* SPDX-License-Identifier: GPL-2.0-only */
/* Verify the complete disabled window, including its proved 64-bit types. */
#ifndef N71_PCIE_PREF64_DISABLE_H
#define N71_PCIE_PREF64_DISABLE_H
#include "n71-pcie-scan-config.h"

static inline int n71_pref64_disable_capture(u32 lower, u32 base_upper, u32 limit_upper)
{
	return lower != 0x00010001U || base_upper || limit_upper ? -EACCES : 0;
}

static inline bool n71_pref64_disable_request(const struct n71_scan_request *request)
{
	return request->root && request->where == 0x24 &&
		request->size == 4 && request->value == 0x0000fff0;
}

static inline int n71_pref64_disable_expected(const struct n71_scan_io *io,
					     const struct n71_scan_request *request,
					     u32 observed, u32 *expected)
{
	u32 actual;
	unsigned int index;
	int error;

	*expected = request->value;
	if (!n71_pref64_disable_request(request))
		return 0;
	if (observed != 0x00010001U && observed != 0x0001fff1U)
		return -EAGAIN;
	for (index = 0; index < 3; index++) {
		error = n71_scan_read(io, true, 0x24 + index * 4, 4, &actual);
		if (error)
			return error;
		if (actual != (index == 0 ? observed : 0U))
			return -EAGAIN;
	}
	*expected = 0x0001fff1U;
	return 0;
}
#endif /* N71_PCIE_PREF64_DISABLE_H */
