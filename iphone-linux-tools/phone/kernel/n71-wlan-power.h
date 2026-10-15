/* SPDX-License-Identifier: GPL-2.0-only */
/* Reversible REG_ON experiment. Caller validates board/client ownership. */
#ifndef N71_WLAN_POWER_H
#define N71_WLAN_POWER_H
#include "n71-wlan-power-contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

struct n71_wlan_power_io {
	void *context;
	int (*read)(void *context, unsigned char *value);
	int (*write)(void *context, unsigned char value);
};

struct n71_wlan_power_state {
	unsigned char original;
	bool active;
	bool restore_pending;
};

static inline bool n71_wlan_power_io_valid(const struct n71_wlan_power_io *io)
{
	return io && io->read && io->write;
}

/* Do not overwrite another owner's mode/drive bits if they changed. */
static inline int n71_wlan_power_release(const struct n71_wlan_power_io *io,
					 struct n71_wlan_power_state *state)
{
	unsigned char readback, restored;
	int error;
	if (!n71_wlan_power_io_valid(io) || !state)
		return -EINVAL;
	if (!state->restore_pending) {
		state->active = false;
		return 0;
	}
	error = io->read(io->context, &readback);
	if (error)
		return error;
	if ((readback & 0xfe) != (state->original & 0xfe) ||
	    !n71_wlan_reg_on_plan(N71_WLAN_REG_ON_REGISTER, readback,
				 state->original & 1, &restored))
		return -EBUSY;
	if (readback != restored) {
		error = io->write(io->context, restored);
		if (error)
			return error;
		error = io->read(io->context, &readback);
		if (error)
			return error;
		if (readback != state->original)
			return -EIO;
	}
	state->restore_pending = false;
	state->active = false;
	return 0;
}

/* A failed write may already have reached the chip: mark cleanup beforehand. */
static inline int n71_wlan_power_acquire(const struct n71_wlan_power_io *io,
					 struct n71_wlan_power_state *state)
{
	unsigned char original, requested, observed;
	int error, cleanup;
	if (!n71_wlan_power_io_valid(io) || !state)
		return -EINVAL;
	if (state->active || state->restore_pending)
		return -EBUSY;
	error = io->read(io->context, &original);
	if (error)
		return error;
	if (!n71_wlan_reg_on_plan(N71_WLAN_REG_ON_REGISTER, original, true, &requested))
		return -EINVAL;
	state->original = original;
	if (requested == original) {
		state->active = true;
		return 0;
	}
	state->restore_pending = true;
	error = io->write(io->context, requested);
	if (!error) {
		error = io->read(io->context, &observed);
		if (!error && observed != requested)
			error = -EIO;
	}
	if (error) {
		cleanup = n71_wlan_power_release(io, state);
		return cleanup ? cleanup : error;
	}
	state->active = true;
	return 0;
}

#endif /* N71_WLAN_POWER_H */
