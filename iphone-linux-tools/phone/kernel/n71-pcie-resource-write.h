/* SPDX-License-Identifier: GPL-2.0-only */
/* Bound PCI allocator writes; the adapter owns bus removal and BAR rollback. */
#ifndef N71_PCIE_RESOURCE_WRITE_H
#define N71_PCIE_RESOURCE_WRITE_H
#include "n71-pcie-scan-config.h"
#include "n71-pcie-io16-upper.h"

#define N71_RESOURCE_MAX_ATTEMPTS 64U

static const u32 n71_resource_extra_offsets[] = {0x20, 0x2c, 0x30};

struct n71_resource_bar_layout {
	u32 bytes[6];
	bool io_absent, pref_absent, io16_upper_unused;
};

struct n71_resource_write_failure {
	struct n71_scan_request request;
	u32 before, after;
	int write_error, read_error;
	bool valid, after_valid;
};

struct n71_resource_write_state {
	struct n71_scan_config reference;
	struct n71_resource_write_failure failure;
	u32 extra[3];
	unsigned int attempts, writes, io_noops, pref_noops, io16_noops;
	int error;
	bool active, pending, io_absent, pref_absent, io16_upper_unused;
};

/* The adapter supplies PCI-core probe flags; zero config alone is insufficient. */
static inline int n71_resource_optional_capture(struct n71_resource_write_state *state,
					       const struct n71_resource_bar_layout *layout)
{
	const u32 *windows = state->reference.saved[0].bridge_windows;

	if ((layout->io_absent && (windows[0] || state->extra[2])) ||
	    (layout->pref_absent && (windows[1] || windows[2] || state->extra[1])))
		return -EACCES;
	if (layout->io16_upper_unused && (layout->io_absent ||
	    n71_io16_upper_capture(windows[0], state->extra[2])))
		return -EACCES;
	state->io_absent = layout->io_absent;
	state->pref_absent = layout->pref_absent;
	state->io16_upper_unused = layout->io16_upper_unused;
	return 0;
}

static inline int n71_resource_guard(const struct n71_scan_io *io)
{
	unsigned int function;
	u32 identity, command;
	int error;

	for (function = 0; function < 2; function++) {
		error = n71_scan_read(io, function == 0, 0, 4, &identity);
		if (!error)
			error = n71_scan_read(io, function == 0, 4, 2, &command);
		if (error)
			return error;
		if (identity != (function == 0 ? 0x1004106b : 0x43a314e4))
			return -ENODEV;
		if (command & 7)
			return -EACCES;
	}
	return 0;
}

static inline int n71_resource_capture(const struct n71_scan_io *io,
				      const struct n71_resource_bar_layout *layout,
				      struct n71_resource_write_state *out)
{
	struct n71_resource_write_state result = {0};
	unsigned int index;
	int error;

	if (!io || !io->read || !io->write || !layout || !out)
		return -EINVAL;
	if (out->pending || out->active)
		return -EBUSY;
	for (index = 0; index < 6; index++)
		if (layout->bytes[index] != (index == 0 ? 0x8000U : index == 2 ? 0x400000U : 0U))
			return -EINVAL;
	error = n71_scan_capture(io, &result.reference);
	if (!error)
		error = n71_resource_guard(io);
	if (error)
		return error;
	for (index = 0; index < 6; index++)
		if (result.reference.saved[1].bars[index] != (index == 0 || index == 2 ? 4U : 0U))
			return -EACCES;
	for (index = 0; index < 3; index++) {
		error = n71_scan_read(io, true, n71_resource_extra_offsets[index], 4, &result.extra[index]);
		if (!error && index == 2)
			error = n71_resource_optional_capture(&result, layout);
		if (error)
			return error;
	}
	result.active = result.pending = true;
	*out = result;
	return 0;
}

static inline bool n71_resource_bar_allowed(u32 value, u32 bytes)
{
	u32 address = value & ~0xfU;

	return (value & 0xf) == 4 && address >= 0xc0000000U &&
		!(address & (bytes - 1)) && address <= 0xffffffffU - (bytes - 1);
}

static inline bool n71_resource_request_allowed(const struct n71_resource_write_state *state,
					      const struct n71_scan_request *request)
{
	const struct n71_scan_function *saved = &state->reference.saved[request->root ? 0 : 1];
	u32 base, limit;

	if (request->where == 4 && request->size == 2)
		return request->value == saved->command && !(request->value & 7);
	if (request->root && request->where == 0x3e && request->size == 2)
		return request->value == saved->control;
	if (request->size != 4)
		return request->root && request->where == 0x1c &&
			request->size == 2 && request->value == 0x00f0;
	if (!request->root) {
		switch (request->where) {
		case 0x10:
			return n71_resource_bar_allowed(request->value, 0x8000U);
		case 0x18:
			return n71_resource_bar_allowed(request->value, 0x400000U);
		case 0x14:
		case 0x1c:
		case 0x20:
		case 0x24:
			return request->value == 0;
		default:
			return false;
		}
	}
	switch (request->where) {
	case 0x20:
		base = (request->value & 0xfff0U) << 16;
		limit = (request->value & 0xfff00000U) | 0xfffffU;
		return !(request->value & 0x000f000fU) &&
			(request->value == 0x0000fff0 || (base >= 0xc0000000U && base <= limit));
	case 0x24:
		return request->value == 0x0000fff0;
	case 0x28:
	case 0x2c:
		return request->value == 0;
	case 0x30:
		return request->value == 0 || request->value == 0x0000ffff;
	default:
		return false;
	}
}

static inline int n71_resource_refuse(struct n71_resource_write_state *state, int error)
{
	if (!state->error)
		state->error = error;
	return state->error;
}

/* Emulate only disable requests for ranges proved absent by the PCI core. */
static inline int n71_resource_optional_noop(const struct n71_scan_io *io,
					    struct n71_resource_write_state *state,
					    const struct n71_scan_request *request,
					    u32 observed, bool *handled)
{
	static const u32 offsets[] = {0x1c, 0x30, 0x24, 0x28, 0x2c};
	unsigned int start, end, index;
	u32 actual;
	bool io_range;
	int error;

	*handled = false;
	if (!request->root)
		return 0;
	io_range = state->io_absent &&
		((request->where == 0x1c && request->size == 2 && request->value == 0x00f0) ||
		 (request->where == 0x30 && request->size == 4 && request->value == 0x0000ffff));
	if (!io_range && !(state->pref_absent && request->where == 0x24 &&
			  request->size == 4 && request->value == 0x0000fff0))
		return 0;
	if (observed)
		return -EAGAIN;
	start = io_range ? 0 : 2;
	end = io_range ? 2 : 5;
	for (index = start; index < end; index++) {
		error = n71_scan_read(io, true, offsets[index], index == 0 ? 2 : 4, &actual);
		if (error)
			return error;
		if (actual)
			return -EAGAIN;
	}
	if (io_range)
		state->io_noops++;
	else
		state->pref_noops++;
	*handled = true;
	return 0;
}

/* Record the existing verification I/O; failed callbacks do not prove a value. */
static inline int n71_resource_write_value(const struct n71_scan_io *io,
					  struct n71_resource_write_state *state,
					  const struct n71_scan_request *request, u32 before)
{
	struct n71_resource_write_failure failure = {.request = *request, .before = before};
	u32 actual = 0;
	int error;

	failure.write_error = io->write(io->context, request->root, request->where,
					request->size, request->value);
	error = failure.write_error;
	if (!error) {
		failure.read_error = io->read(io->context, request->root, request->where,
					    request->size, &actual);
		error = failure.read_error;
		if (!error) {
			failure.after_valid = true;
			failure.after = actual;
			error = actual == request->value ? 0 : -EIO;
		}
	}
	if (error) {
		failure.valid = true;
		state->failure = failure;
	}
	return error > 0 ? -EIO : error;
}

static inline int n71_resource_write(const struct n71_scan_io *io,
				    struct n71_resource_write_state *state,
				    const struct n71_scan_request *request)
{
	u32 observed;
	bool handled;
	int error;

	if (!io || !io->read || !io->write || !state || !request)
		return -EINVAL;
	if (!state->active || !state->pending)
		return n71_resource_refuse(state, -EPERM);
	if (state->error)
		return state->error;
	if (++state->attempts > N71_RESOURCE_MAX_ATTEMPTS)
		return n71_resource_refuse(state, -E2BIG);
	if (!n71_resource_request_allowed(state, request))
		return n71_resource_refuse(state, -EPERM);
	error = n71_resource_guard(io);
	if (!error)
		error = n71_scan_read(io, request->root, request->where, request->size, &observed);
	if (error)
		return n71_resource_refuse(state, error);
	if (state->io16_upper_unused) {
		error = n71_io16_upper_noop(io, request, observed, &handled);
		if (error)
			return n71_resource_refuse(state, error);
		if (handled) {
			state->io16_noops++;
			return 0;
		}
	}
	if (observed == request->value)
		return 0;
	error = n71_resource_optional_noop(io, state, request, observed, &handled);
	if (error)
		return n71_resource_refuse(state, error);
	if (handled)
		return 0;
	error = n71_resource_write_value(io, state, request, observed);
	if (error)
		return n71_resource_refuse(state, error);
	state->writes++;
	return 0;
}

/* The adapter must remove the PCI bus before restoring additional windows. */
static inline int n71_resource_restore(const struct n71_scan_io *io,
				      struct n71_resource_write_state *state, bool bus_removed)
{
	unsigned int index;
	int error;

	if (!io || !io->read || !io->write || !state)
		return -EINVAL;
	if (!state->pending)
		return 0;
	if (!bus_removed || state->active)
		return -EBUSY;
	error = n71_resource_guard(io);
	if (error)
		return error;
	for (index = 0; index < 3; index++) {
		error = n71_scan_restore_value(io, true, n71_resource_extra_offsets[index], 4, state->extra[index]);
		if (error)
			return error;
	}
	state->pending = false;
	return 0;
}
#endif /* N71_PCIE_RESOURCE_WRITE_H */
