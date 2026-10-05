/* SPDX-License-Identifier: GPL-2.0-only */
/* Temporary Gen2 target for an already active Gen1 root link; no retrain. */
#ifndef N71_PCIE_SCAN_LINK_TARGET_H
#define N71_PCIE_SCAN_LINK_TARGET_H
#include "n71-pcie-ecam.h"

struct n71_link_target_io {
	void *context;
	int (*read)(void *context, u32 where, unsigned int size, u32 *value);
	int (*write)(void *context, u32 where, unsigned int size, u32 value);
};

struct n71_link_target {
	u32 capability_header, link_capability, link_capability2, link_status, link_control, original;
	bool captured, pending, prepared;
};

static inline int n71_link_target_read(const struct n71_link_target_io *io,
				     u32 where, unsigned int size, u32 *value)
{
	int error = io->read(io->context, where, size, value);
	return error > 0 ? -EIO : error;
}

/* The caller supplies exclusively owned N71 root0:08 config access. */
static inline int n71_link_target_snapshot(const struct n71_link_target_io *io,
					 struct n71_link_target *out)
{
	struct n71_link_target result = {0};
	u32 value, next, visited[16];
	unsigned int count = 0, index;
	bool express = false;
	int error;

	if (!io || !io->read || !io->write || !out)
		return -EINVAL;
#define N71_LINK_READ(where, size, destination) do { \
	error = n71_link_target_read(io, where, size, destination); \
	if (error) return error; \
} while (0)
	N71_LINK_READ(0, 4, &value);
	if (value != 0x1004106b)
		return -ENODEV;
	N71_LINK_READ(8, 4, &value);
	if (value >> 8 != 0x060400)
		return -ENODEV;
	N71_LINK_READ(0xc, 4, &value);
	if ((value >> 16 & 0x7f) != 1)
		return -ENODEV;
	N71_LINK_READ(0x18, 4, &value);
	if ((value & 0xffffff) != 0x010100)
		return -ENODEV;
	N71_LINK_READ(4, 2, &value);
	if (value > 0xffff || value & 7)
		return -EACCES;
	N71_LINK_READ(6, 2, &value);
	if (value > 0xffff || !(value & 0x10))
		return -ENODEV;
	N71_LINK_READ(0x34, 1, &next);
	while (next) {
		if (next < 0x40 || next > 0xfc || next % 4)
			return -EINVAL;
		for (index = 0; index < count; index++)
			if (visited[index] == next)
				return -ELOOP;
		if (count == 16)
			return -E2BIG;
		visited[count++] = next;
		N71_LINK_READ(next, 4, &value);
		if (!(value & 0xff) || (value & 0xff) == 0xff)
			return -EINVAL;
		if ((value & 0xff) == 0x10) {
			if (express || next != 0x70 || ((value >> 16) & 0xff) != 0x42)
				return -ENODEV;
			express = true;
			result.capability_header = value;
		}
		next = (value >> 8) & 0xff;
	}
	if (!express)
		return -ENODEV;
	N71_LINK_READ(0x7c, 4, &result.link_capability);
	N71_LINK_READ(0x9c, 4, &result.link_capability2);
	N71_LINK_READ(0x80, 2, &result.link_control);
	N71_LINK_READ(0x82, 2, &result.link_status);
	N71_LINK_READ(0xa0, 2, &result.original);
#undef N71_LINK_READ
	if (result.link_capability == 0xffffffff ||
	    (result.link_capability & 0xf) != 2 || !(result.link_capability & 0x100000) ||
	    result.link_capability2 == 0xffffffff ||
	    ((result.link_capability2 & 0xfe) != 0 && (result.link_capability2 & 0xfe) != 6) ||
	    result.link_control != 0 || result.link_status > 0xffff ||
	    (result.link_status & 0xf) != 1 || !(result.link_status & 0x2000) ||
	    (result.link_status & 0x800) || (result.original != 1 && result.original != 2))
		return -EACCES;
	result.captured = true;
	*out = result;
	return 0;
}

static inline bool n71_link_target_same(const struct n71_link_target *saved,
					const struct n71_link_target *fresh)
{
	return saved->capability_header == fresh->capability_header &&
		saved->link_capability == fresh->link_capability &&
		saved->link_capability2 == fresh->link_capability2 &&
		saved->link_control == fresh->link_control &&
		saved->link_status == fresh->link_status;
}

static inline int n71_link_target_capture(const struct n71_link_target_io *io,
					struct n71_link_target *out)
{
	struct n71_link_target result;
	int error;

	/* Caller initializes the handle to zero; never replace pending ownership. */
	if (!out || out->pending || out->prepared)
		return -EINVAL;
	error = n71_link_target_snapshot(io, &result);
	if (!error && result.original != 1)
		error = -EACCES;
	if (!error)
		*out = result;
	return error;
}

static inline int n71_link_target_prepare(const struct n71_link_target_io *io,
					struct n71_link_target *saved)
{
	struct n71_link_target fresh;
	int error;

	if (!saved || !saved->captured || saved->original != 1 || saved->pending || saved->prepared)
		return -EINVAL;
	error = n71_link_target_snapshot(io, &fresh);
	if (error || fresh.original != 1 || !n71_link_target_same(saved, &fresh))
		return error ? error : -EIO;
	/* A failed write may still change hardware; retain restoration ownership. */
	saved->pending = true;
	error = io->write(io->context, 0xa0, 2, 2);
	if (error)
		return error < 0 ? error : -EIO;
	error = n71_link_target_snapshot(io, &fresh);
	if (error || fresh.original != 2 || !n71_link_target_same(saved, &fresh))
		return error ? error : -EIO;
	saved->prepared = true;
	return 0;
}

/* PCI callbacks/devices must be gone first; pending failure keeps ownership. */
static inline int n71_link_target_restore(const struct n71_link_target_io *io,
					struct n71_link_target *saved)
{
	struct n71_link_target fresh;
	int error;

	if (!saved || !saved->captured || saved->original != 1)
		return -EINVAL;
	if (!saved->pending)
		return saved->prepared ? -EINVAL : 0;
	saved->prepared = false;
	error = n71_link_target_snapshot(io, &fresh);
	if (error || !n71_link_target_same(saved, &fresh))
		return error ? error : -EIO;
	if (fresh.original != saved->original) {
		error = io->write(io->context, 0xa0, 2, saved->original);
		if (error)
			return error < 0 ? error : -EIO;
	}
	error = n71_link_target_snapshot(io, &fresh);
	if (error || fresh.original != saved->original || !n71_link_target_same(saved, &fresh))
		return error ? error : -EIO;
	saved->pending = false;
	return 0;
}
#endif
