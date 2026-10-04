/* SPDX-License-Identifier: GPL-2.0-only */
/* Test a provider without DMA, then restore every saved table word. */
#ifndef N71_DART_CYCLE_H
#define N71_DART_CYCLE_H
#include "n71-dart-observe.h"

struct n71_dart_cycle_io {
	void *context;
	int (*snapshot)(void *context, struct n71_dart_observation *out);
	int (*quiet)(void *context);
	int (*start)(void *context);
	int (*stop)(void *context);
	int (*write_ttbr)(void *context, unsigned int index, u32 value);
};

struct n71_dart_cycle_result {
	unsigned int snapshots, writes;
	bool attempted, stopped, restored, control_changed;
	int operation_error, restore_error;
};

static inline int n71_dart_error(int error)
{
	return error > 0 ? -EIO : error;
}

static inline bool n71_dart_idle(const struct n71_dart_observation *state)
{
	return !state->tcr && !state->enabled && state->command != 0xffffffffU &&
		!(state->command & 8) && !(state->error & 0x80000000U);
}

static inline int n71_dart_cycle(const struct n71_dart_cycle_io *io,
				struct n71_dart_cycle_result *out)
{
	struct n71_dart_cycle_result result = {0};
	struct n71_dart_observation saved, observed;
	unsigned int index;
	int error;

	if (!io || !io->snapshot || !io->quiet || !io->start || !io->stop ||
	    !io->write_ttbr || !out)
		return -EINVAL;
	result.snapshots++;
	error = n71_dart_error(io->snapshot(io->context, &saved));
	if (!error && !n71_dart_idle(&saved))
		error = -EACCES;
	if (!error)
		error = n71_dart_error(io->quiet(io->context));
	if (error)
		goto done;
	result.attempted = true;
	error = n71_dart_error(io->start(io->context));
	if (!error) {
		result.snapshots++;
		error = n71_dart_error(io->snapshot(io->context, &observed));
		if (!error && !n71_dart_idle(&observed))
			error = -EACCES;
		for (index = 0; !error && index < 16; index++)
			if (observed.ttbr[index])
				error = -EIO;
	}
	result.operation_error = error;
	/* Start may have modified hardware even when probe failed. */
	error = n71_dart_error(io->stop(io->context));
	if (error)
		goto restore_failed;
	result.stopped = true;
	result.snapshots++;
	error = n71_dart_error(io->snapshot(io->context, &observed));
	if (!error && !n71_dart_idle(&observed))
		error = -EACCES;
	if (error)
		goto restore_failed;
	for (index = 0; index < 16; index++) {
		error = n71_dart_error(io->quiet(io->context));
		if (error)
			goto restore_failed;
		result.writes++;
		error = n71_dart_error(io->write_ttbr(io->context, index, saved.ttbr[index]));
		if (error && !result.restore_error)
			result.restore_error = error;
	}
	result.snapshots++;
	error = n71_dart_error(io->snapshot(io->context, &observed));
	if (!error && !n71_dart_idle(&observed))
		error = -EACCES;
	for (index = 0; !error && index < 16; index++)
		if (observed.ttbr[index] != saved.ttbr[index])
			error = -EIO;
	if (error)
		goto restore_failed;
	result.restored = !result.restore_error;
	result.control_changed = observed.command != saved.command || observed.error != saved.error;
	if (result.control_changed && !result.operation_error)
		result.operation_error = -EIO;
	goto done;
restore_failed:
	if (!result.restore_error)
		result.restore_error = error;
done:
	if (error && !result.operation_error && !result.restore_error)
		result.operation_error = error;
	*out = result;
	return result.restore_error ? result.restore_error : result.operation_error;
}
#endif /* N71_DART_CYCLE_H */
