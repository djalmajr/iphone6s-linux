/* SPDX-License-Identifier: GPL-2.0-only */
/* Bounded, read-only standard/extended capability controls; never BAR/VPD data. */
#ifndef N71_PCIE_CONTROL_REFERENCE_H
#define N71_PCIE_CONTROL_REFERENCE_H
#include "n71-pcie-scan-config.h"

struct n71_control_word { u32 where, size, value, capability; };
struct n71_control_reference {
	struct n71_control_word words[32];
	u32 headers[16], offsets[16];
	unsigned int count, capabilities, reads;
};

static inline int n71_control_read(const struct n71_scan_io *io, bool root,
				 struct n71_control_reference *out,
				 u32 where, unsigned int size, u32 *value)
{
	if (++out->reads > 128)
		return -E2BIG;
	return n71_scan_read(io, root, where, size, value);
}

static inline int n71_control_add(const struct n71_scan_io *io, bool root,
				struct n71_control_reference *out,
				u32 base, u32 relative, unsigned int size, u32 id)
{
	struct n71_control_word word = {base + relative, size, 0, id};
	u32 limit = base < 0x100 ? 0x100 : 0x1000;
	int error;

	if (out->count == 32 || (size != 2 && size != 4) ||
	    word.where % size || word.where > limit - size)
		return -E2BIG;
	error = n71_control_read(io, root, out, word.where, size, &word.value);
	if (!error)
		out->words[out->count++] = word;
	return error;
}

static inline int n71_control_block(const struct n71_scan_io *io, bool root,
				  struct n71_control_reference *out, u32 base, u32 header)
{
	u32 id = base < 0x100 ? header & 0xff : header & 0xffff;
	static const u32 express[] = {8, 0xc, 0x10, 0x12, 0x28, 0x30};
	static const u32 aer[] = {4, 0xc, 0x10, 0x14, 0x18};
	unsigned int index;
	int error;

	if (base < 0x100 && (id == 1 || id == 5 || id == 0x11))
		return n71_control_add(io, root, out, base, id == 1 ? 4 : 2, 2, id);
	if (base < 0x100 && id == 0x10) {
		u32 version = (header >> 16) & 0xf;
		if (!version || version > 2)
			return -EINVAL;
		for (index = 0; index < (version == 2 ? 6U : 4U); index++) {
			error = n71_control_add(io, root, out, base, express[index], index == 1 ? 4 : 2, id);
			if (error)
				return error;
		}
	} else if (base >= 0x100 && id == 1) {
		for (index = 0; index < 5; index++) {
			error = n71_control_add(io, root, out, base, aer[index], 4, 0x10001);
			if (error)
				return error;
		}
	} else if (base >= 0x100 && id == 0x1f) {
		return n71_control_add(io, root, out, base, 8, 4, 0x1001f);
	}
	return 0;
}

static inline int n71_control_capture(const struct n71_scan_io *io, bool root,
				    struct n71_control_reference *out)
{
	struct n71_control_reference result = {0};
	u32 identity, command, status, next, header;
	unsigned int index;
	bool express = false, extended = false;
	int error;

	if (!io || !io->read || !out)
		return -EINVAL;
	error = n71_control_read(io, root, &result, 0, 4, &identity);
	if (error || identity != (root ? 0x1004106b : 0x43a314e4))
		return error ? error : -ENODEV;
	error = n71_control_read(io, root, &result, 4, 2, &command);
	if (error || command & 4)
		return error ? error : -EACCES;
	error = n71_control_read(io, root, &result, 6, 2, &status);
	if (error)
		return error;
	next = 0;
	if (status & 0x10) {
		error = n71_control_read(io, root, &result, 0x34, 1, &next);
		if (error)
			return error;
	}
	for (;;) {
		if (!next) {
			if (extended || !express)
				break;
			extended = true;
			next = 0x100;
		}
		if (next % 4 || next < (extended ? 0x100U : 0x40U) ||
		    next > (extended ? 0xffcU : 0xfcU))
			return -EINVAL;
		for (index = 0; index < result.capabilities; index++)
			if (result.offsets[index] == next)
				return -ELOOP;
		if (result.capabilities == 16)
			return -E2BIG;
		error = n71_control_read(io, root, &result, next, 4, &header);
		if (error)
			return error;
		if (extended && (!header || header == 0xffffffff))
			break;
		if (!extended && (!(header & 0xff) || (header & 0xff) == 0xff))
			return -EINVAL;
		result.headers[result.capabilities] = header;
		result.offsets[result.capabilities++] = next;
		if (!extended && (header & 0xff) == 0x10)
			express = true;
		error = n71_control_block(io, root, &result, next, header);
		if (error)
			return error;
		next = extended ? (header >> 20) & 0xfff : (header >> 8) & 0xff;
	}
	*out = result;
	return 0;
}
#endif
