/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller serializes a qualified genpd backend and retains objects on failure. */
#ifndef N71_I2C_POWER_LIFECYCLE_H
#define N71_I2C_POWER_LIFECYCLE_H
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/types.h>
#else
#include <errno.h>
#include <stdbool.h>
#endif

struct n71_i2c_power_io {
	void *context;
	/* Negative attach leaves no handle; successful attach does not power on. */
	int (*attach)(void *context);
	/* Nonnegative resume owns one usage reference; negative owns none. */
	int (*resume_and_get)(void *context);
	/* This consumes one usage reference even when suspend fails. */
	int (*put_and_suspend)(void *context);
	int (*suspend_zero_usage)(void *context);
	/* Verification and detach return zero only after the condition is proved. */
	int (*verify_active)(void *context);
	int (*verify_quiescent)(void *context);
	int (*detach_verified)(void *context);
};

struct n71_i2c_power_state {
	int cleanup_error;
	bool active;
	bool attached;
	bool cleanup_pending;
	bool usage_held;
};

static inline bool n71_i2c_power_io_valid(const struct n71_i2c_power_io *io)
{
	return io && io->attach && io->resume_and_get && io->put_and_suspend &&
		io->suspend_zero_usage && io->verify_active &&
		io->verify_quiescent && io->detach_verified;
}

static inline int n71_i2c_power_release(const struct n71_i2c_power_io *io,
				      struct n71_i2c_power_state *state)
{
	int error;

	if (!n71_i2c_power_io_valid(io) || !state)
		return -EINVAL;
	if (!state->attached) {
		if (state->active || state->cleanup_pending || state->usage_held)
			return -EINVAL;
		return 0;
	}
	if (!state->cleanup_pending)
		return -EINVAL;
	state->active = false;
	if (state->usage_held) {
		state->usage_held = false;
		error = io->put_and_suspend(io->context);
	} else {
		error = io->suspend_zero_usage(io->context);
	}
	if (error < 0)
		goto pending;
	error = io->verify_quiescent(io->context);
	if (error)
		goto pending;
	error = io->detach_verified(io->context);
	if (error)
		goto pending;
	state->attached = false;
	state->cleanup_pending = false;
	state->cleanup_error = 0;
	return 0;
pending:
	state->cleanup_error = error < 0 ? error : -EIO;
	return state->cleanup_error;
}

static inline int n71_i2c_power_acquire(const struct n71_i2c_power_io *io,
				      struct n71_i2c_power_state *state)
{
	int error;

	if (!n71_i2c_power_io_valid(io) || !state)
		return -EINVAL;
	if (state->active || state->attached || state->cleanup_pending || state->usage_held)
		return -EBUSY;
	state->cleanup_error = 0;
	error = io->attach(io->context);
	if (error < 0)
		return error;
	state->attached = true;
	state->cleanup_pending = true;
	error = io->resume_and_get(io->context);
	if (error < 0)
		goto failed;
	state->usage_held = true;
	error = io->verify_active(io->context);
	if (error) {
		if (error > 0)
			error = -EIO;
		goto failed;
	}
	state->active = true;
	return 0;
failed:
	n71_i2c_power_release(io, state);
	return error;
}
#endif /* N71_I2C_POWER_LIFECYCLE_H */
