/* SPDX-License-Identifier: GPL-2.0-only */
/* Two stable, quiet S5L snapshots. No write operation is exposed. */
#ifndef N71_DART_OBSERVE_H
#define N71_DART_OBSERVE_H
#include "n71-pcie-contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

#define N71_DART_WORDS 19U
#define N71_DART_READS (2U * N71_DART_WORDS)

struct n71_dart_io {
	void *context;
	int (*quiet)(void *context);
	int (*read32)(void *context, u32 offset, u32 *value);
};

struct n71_dart_observation {
	u32 command, tcr, error, enabled, valid_ttbrs;
	u32 ttbr[16];
};

static inline u32 n71_dart_offset(unsigned int index)
{
	return index == 0 ? 0 : index == 1 ? 0xc : index == 2 ? 0x10 :
		0x40 + (index - 3) * 4;
}

static inline int n71_dart_observe(const struct n71_dart_io *io,
				  struct n71_dart_observation *out)
{
	struct n71_dart_observation result = {0};
	u32 first[N71_DART_WORDS], value;
	unsigned int sample, index;
	int error;

	if (!io || !io->quiet || !io->read32 || !out)
		return -EINVAL;
	for (sample = 0; sample < 2; sample++) {
		for (index = 0; index < N71_DART_WORDS; index++) {
			error = io->quiet(io->context);
			if (!error)
				error = io->read32(io->context, n71_dart_offset(index), &value);
			if (error)
				return error < 0 ? error : -EIO;
			if (value == 0xffffffffU)
				return -EIO;
			if (index == 0 && (value & 8))
				return -EBUSY;
			if (!sample)
				first[index] = value;
			else if (value != first[index])
				return -EAGAIN;
		}
	}
	error = io->quiet(io->context);
	if (error)
		return error < 0 ? error : -EIO;
	result.command = first[0];
	result.tcr = first[1];
	result.error = first[2];
	for (index = 0; index < 4; index++)
		if ((result.tcr >> (index * 8)) & 0x80)
			result.enabled |= 1U << index;
	for (index = 0; index < 16; index++) {
		result.ttbr[index] = first[index + 3];
		if (first[index + 3] & (1U << 31))
			result.valid_ttbrs |= 1U << index;
	}
	*out = result;
	return 0;
}
#endif /* N71_DART_OBSERVE_H */
