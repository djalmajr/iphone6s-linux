/* SPDX-License-Identifier: GPL-2.0-only */
/* Keep the original tables and recovery progress until restoration is proved. */
#ifndef N71_DART_LEASE_H
#define N71_DART_LEASE_H
#include "n71-dart-cycle.h"

struct n71_dart_lease {
	struct n71_dart_observation saved;
	unsigned int restore_index;
	bool captured, attempted, running, stopped, restored, control_changed;
	int operation_error, restore_error;
};

static inline bool n71_dart_lease_io_valid(const struct n71_dart_cycle_io *io)
{
	return io && io->snapshot && io->quiet && io->start && io->stop && io->write_ttbr;
}

static inline bool n71_dart_lease_pending(const struct n71_dart_lease *lease)
{
	return lease && lease->attempted && !lease->restored;
}

static inline int n71_dart_lease_acquire(const struct n71_dart_cycle_io *io,
				       struct n71_dart_lease *lease)
{
	struct n71_dart_observation observed;
	unsigned int index;
	int error;

	if (!n71_dart_lease_io_valid(io) || !lease)
		return -EINVAL;
	if (lease->captured || lease->attempted)
		return -EALREADY;
	error = n71_dart_error(io->snapshot(io->context, &observed));
	if (!error && !n71_dart_idle(&observed))
		error = -EACCES;
	if (error)
		goto done;
	lease->saved = observed;
	lease->captured = true;
	error = n71_dart_error(io->quiet(io->context));
	if (error)
		goto done;
	/* A failed start may still have registered a device or modified tables. */
	lease->attempted = true;
	error = n71_dart_error(io->start(io->context));
	if (!error) {
		error = n71_dart_error(io->snapshot(io->context, &observed));
		if (!error && !n71_dart_idle(&observed))
			error = -EACCES;
		for (index = 0; !error && index < 16; index++)
			if (observed.ttbr[index])
				error = -EIO;
	}
	lease->running = !error;
done:
	lease->operation_error = error;
	return error;
}

static inline int n71_dart_lease_cleanup(const struct n71_dart_cycle_io *io,
				       struct n71_dart_lease *lease)
{
	struct n71_dart_observation observed;
	unsigned int index;
	int error;

	if (!n71_dart_lease_io_valid(io) || !lease || lease->restore_index > 16 ||
	    (lease->attempted && !lease->captured))
		return -EINVAL;
	if (!n71_dart_lease_pending(lease))
		return 0;
	lease->restore_error = 0;
	/* Cleanup invalidates readiness even when stop only partially succeeds. */
	lease->running = false;
	if (!lease->stopped) {
		error = n71_dart_error(io->stop(io->context));
		if (error)
			goto failed;
		lease->stopped = true;
	}
	error = n71_dart_error(io->snapshot(io->context, &observed));
	if (!error && !n71_dart_idle(&observed))
		error = -EACCES;
	if (error)
		goto failed;
	/* A retry also verifies the words confirmed by an earlier attempt. */
	for (index = 0; index < lease->restore_index; index++)
		if (observed.ttbr[index] != lease->saved.ttbr[index]) {
			lease->restore_index = index;
			break;
		}
	while (lease->restore_index < 16) {
		index = lease->restore_index;
		error = n71_dart_error(io->quiet(io->context));
		if (!error)
			error = n71_dart_error(io->write_ttbr(io->context, index, lease->saved.ttbr[index]));
		if (error)
			goto failed;
		lease->restore_index++;
	}
	error = n71_dart_error(io->snapshot(io->context, &observed));
	if (!error && !n71_dart_idle(&observed))
		error = -EACCES;
	if (error)
		goto failed;
	for (index = 0; index < 16; index++)
		if (observed.ttbr[index] != lease->saved.ttbr[index]) {
			lease->restore_index = index;
			error = -EIO;
			goto failed;
		}
	lease->control_changed = observed.command != lease->saved.command ||
		observed.error != lease->saved.error;
	if (lease->control_changed && !lease->operation_error)
		lease->operation_error = -EIO;
	lease->restored = true;
	return 0;
failed:
	lease->restore_error = error;
	return error;
}
#endif /* N71_DART_LEASE_H */
