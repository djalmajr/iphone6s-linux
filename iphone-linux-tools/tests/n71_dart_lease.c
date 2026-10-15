/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-dart-lease.h"

struct mock {
	struct n71_dart_observation original, state;
	unsigned int snapshots, quiet, starts, stops, writes, per_word[16];
	unsigned int fail_snapshot, fail_quiet, fail_write, corrupt_snapshot;
	int start_error, stop_error, snapshot_error;
	bool running, guard, write_after_store, leave_table, active_after_start;
};

static unsigned int cases;

static int snapshot(void *context, struct n71_dart_observation *out)
{
	struct mock *mock = context;
	if (++mock->snapshots == mock->fail_snapshot)
		return mock->snapshot_error;
	*out = mock->state;
	if (mock->snapshots == mock->corrupt_snapshot)
		out->ttbr[7] ^= 1;
	return 0;
}

static int quiet(void *context)
{
	struct mock *mock = context;
	mock->guard = ++mock->quiet != mock->fail_quiet;
	return mock->guard ? 0 : -ENOLINK;
}

static int start(void *context)
{
	struct mock *mock = context;
	mock->starts++;
	mock->running = true;
	if (!mock->leave_table)
		memset(mock->state.ttbr, 0, sizeof(mock->state.ttbr));
	if (mock->active_after_start)
		mock->state.tcr = 0x80;
	return mock->start_error;
}

static int stop(void *context)
{
	struct mock *mock = context;
	mock->stops++;
	if (mock->stop_error)
		return mock->stop_error;
	mock->running = false;
	return 0;
}

static int write_ttbr(void *context, unsigned int index, u32 value)
{
	struct mock *mock = context;
	assert(!mock->running && !mock->state.tcr && mock->guard && index < 16);
	assert(value == mock->original.ttbr[index]);
	mock->guard = false;
	mock->writes++;
	mock->per_word[index]++;
	if (mock->writes == mock->fail_write && !mock->write_after_store)
		return -EIO;
	mock->state.ttbr[index] = value;
	return mock->writes == mock->fail_write ? -EIO : 0;
}

static void initialize(struct mock *mock, struct n71_dart_lease *lease)
{
	unsigned int index;
	cases++;
	memset(mock, 0, sizeof(*mock));
	memset(lease, 0, sizeof(*lease));
	mock->snapshot_error = -EIO;
	mock->original.command = 0xf02;
	mock->original.error = 0x100;
	for (index = 0; index < 16; index++)
		mock->original.ttbr[index] = 0x80123400 + index;
	mock->state = mock->original;
}

static void restored(const struct mock *mock, const struct n71_dart_lease *lease)
{
	assert(lease->captured && lease->attempted && lease->stopped && lease->restored);
	assert(!lease->running && !n71_dart_lease_pending(lease) && !lease->restore_error);
	assert(lease->restore_index == 16 && !mock->running);
	assert(memcmp(mock->state.ttbr, mock->original.ttbr, sizeof(mock->state.ttbr)) == 0);
	assert(memcmp(lease->saved.ttbr, mock->original.ttbr, sizeof(lease->saved.ttbr)) == 0);
}

int main(void)
{
	struct mock mock;
	struct n71_dart_lease lease;
	struct n71_dart_cycle_io io = {&mock, snapshot, quiet, start, stop, write_ttbr}, bad;
	unsigned int index, after, count;

	/* Mutations: duplicate start, premature stop, replacing the original baseline. */
	initialize(&mock, &lease);
	assert(n71_dart_lease_acquire(&io, &lease) == 0);
	assert(lease.running && n71_dart_lease_pending(&lease) && mock.running);
	assert(mock.stops == 0 && mock.writes == 0 && mock.snapshots == 2);
	assert(n71_dart_lease_acquire(&io, &lease) == -EALREADY && mock.starts == 1);
	assert(n71_dart_lease_cleanup(&io, &lease) == 0);
	restored(&mock, &lease);
	assert(mock.stops == 1 && mock.writes == 16 && mock.quiet == 17);
	count = mock.snapshots;
	assert(n71_dart_lease_cleanup(&io, &lease) == 0 && mock.snapshots == count);
	assert(n71_dart_lease_acquire(&io, &lease) == -EALREADY && mock.starts == 1);

	/* Mutations: forget partial start, ignore stop error, unregister twice on retry. */
	for (index = 0; index < 2; index++) {
		initialize(&mock, &lease);
		mock.start_error = index ? 1 : -ENODEV;
		assert(n71_dart_lease_acquire(&io, &lease) == (index ? -EIO : -ENODEV));
		assert(n71_dart_lease_pending(&lease));
		mock.stop_error = -EBUSY;
		assert(n71_dart_lease_cleanup(&io, &lease) == -EBUSY);
		assert(mock.running && !lease.running && lease.restore_index == 0 && mock.writes == 0);
		mock.stop_error = 0;
		assert(n71_dart_lease_cleanup(&io, &lease) == 0);
		restored(&mock, &lease);
		assert(lease.operation_error == (index ? -EIO : -ENODEV) && mock.stops == 2);
	}
	for (index = 1; index <= 4; index++) {
		initialize(&mock, &lease);
		mock.fail_snapshot = index;
		assert(n71_dart_lease_acquire(&io, &lease) == (index <= 2 ? -EIO : 0));
		if (index == 1) {
			assert(!lease.attempted && mock.starts == 0);
			assert(n71_dart_lease_cleanup(&io, &lease) == 0 && mock.writes == 0);
			continue;
		}
		assert(n71_dart_lease_cleanup(&io, &lease) == (index >= 3 ? -EIO : 0));
		if (index >= 3) {
			assert(n71_dart_lease_pending(&lease) && lease.restore_index == (index == 3 ? 0U : 16U));
			mock.fail_snapshot = 0;
			assert(n71_dart_lease_cleanup(&io, &lease) == 0);
		}
		restored(&mock, &lease);
		assert(mock.writes == 16 && mock.stops == 1);
	}

	/* Mutations: skip quiet, advance on failure, rewrite an already confirmed prefix. */
	for (index = 1; index <= 17; index++) {
		initialize(&mock, &lease);
		mock.fail_quiet = index;
		assert(n71_dart_lease_acquire(&io, &lease) == (index == 1 ? -ENOLINK : 0));
		if (index == 1) {
			assert(!lease.attempted && mock.starts == 0);
			assert(n71_dart_lease_cleanup(&io, &lease) == 0 && mock.writes == 0);
			continue;
		}
		assert(n71_dart_lease_cleanup(&io, &lease) == -ENOLINK);
		assert(lease.restore_index == index - 2 && n71_dart_lease_pending(&lease));
		mock.fail_quiet = 0;
		assert(n71_dart_lease_cleanup(&io, &lease) == 0);
		restored(&mock, &lease);
		assert(mock.writes == 16 && mock.stops == 1);
		for (count = 0; count < 16; count++)
			assert(mock.per_word[count] == 1);
	}
	for (after = 0; after < 2; after++)
		for (index = 1; index <= 16; index++) {
			initialize(&mock, &lease);
			mock.fail_write = index;
			mock.write_after_store = after;
			assert(n71_dart_lease_acquire(&io, &lease) == 0);
			assert(n71_dart_lease_cleanup(&io, &lease) == -EIO);
			assert(lease.restore_index == index - 1 && n71_dart_lease_pending(&lease));
			mock.fail_write = 0;
			assert(n71_dart_lease_cleanup(&io, &lease) == 0);
			restored(&mock, &lease);
			assert(mock.writes == 17 && mock.stops == 1);
			for (count = 0; count < 16; count++)
				assert(mock.per_word[count] == (count == index - 1 ? 2U : 1U));
		}

	/* Mutations: ignore readback or ignore drift in words confirmed before a retry. */
	initialize(&mock, &lease);
	mock.fail_quiet = 8;
	assert(n71_dart_lease_acquire(&io, &lease) == 0);
	assert(n71_dart_lease_cleanup(&io, &lease) == -ENOLINK && lease.restore_index == 6);
	mock.state.ttbr[2] ^= 1;
	mock.fail_quiet = 0;
	assert(n71_dart_lease_cleanup(&io, &lease) == 0);
	restored(&mock, &lease);
	assert(mock.writes == 20 && mock.per_word[0] == 1 && mock.per_word[2] == 2);
	initialize(&mock, &lease);
	mock.corrupt_snapshot = 4;
	assert(n71_dart_lease_acquire(&io, &lease) == 0);
	assert(n71_dart_lease_cleanup(&io, &lease) == -EIO && lease.restore_index == 7);
	assert(n71_dart_lease_cleanup(&io, &lease) == 0);
	restored(&mock, &lease);
	assert(mock.writes == 25);

	initialize(&mock, &lease);
	assert(n71_dart_lease_acquire(&io, &lease) == 0);
	mock.state.tcr = 0x80;
	assert(n71_dart_lease_cleanup(&io, &lease) == -EACCES && mock.writes == 0);
	mock.state.tcr = 0;
	assert(n71_dart_lease_cleanup(&io, &lease) == 0);
	restored(&mock, &lease);
	initialize(&mock, &lease);
	assert(n71_dart_lease_acquire(&io, &lease) == 0);
	mock.state.error = 0;
	assert(n71_dart_lease_cleanup(&io, &lease) == 0);
	restored(&mock, &lease);
	assert(lease.control_changed && lease.operation_error == -EIO);
	for (index = 0; index < 3; index++) {
		initialize(&mock, &lease);
		if (!index) mock.state.tcr = 1;
		if (index == 1) mock.state.command |= 8;
		if (index == 2) mock.state.error |= 0x80000000;
		assert(n71_dart_lease_acquire(&io, &lease) == -EACCES && !lease.attempted && mock.starts == 0);
	}
	for (index = 0; index < 2; index++) {
		initialize(&mock, &lease);
		mock.leave_table = !index;
		mock.active_after_start = index;
		assert(n71_dart_lease_acquire(&io, &lease) == (index ? -EACCES : -EIO));
		mock.state.tcr = 0;
		assert(n71_dart_lease_cleanup(&io, &lease) == 0);
		restored(&mock, &lease);
	}
	initialize(&mock, &lease);
	mock.fail_snapshot = 1; mock.snapshot_error = 1;
	assert(n71_dart_lease_acquire(&io, &lease) == -EIO && !lease.attempted);
	initialize(&mock, &lease);
	lease.restore_index = 17;
	assert(n71_dart_lease_cleanup(&io, &lease) == -EINVAL && mock.stops == 0);
	initialize(&mock, &lease);
	lease.attempted = true;
	assert(n71_dart_lease_cleanup(&io, &lease) == -EINVAL && mock.stops == 0);
	for (index = 0; index < 5; index++) {
		initialize(&mock, &lease);
		bad = io;
		if (!index) bad.snapshot = NULL;
		if (index == 1) bad.quiet = NULL;
		if (index == 2) bad.start = NULL;
		if (index == 3) bad.stop = NULL;
		if (index == 4) bad.write_ttbr = NULL;
		assert(n71_dart_lease_acquire(&bad, &lease) == -EINVAL);
		assert(n71_dart_lease_cleanup(&bad, &lease) == -EINVAL && mock.starts == 0);
	}
	assert(n71_dart_lease_acquire(NULL, &lease) == -EINVAL);
	assert(n71_dart_lease_acquire(&io, NULL) == -EINVAL);
	assert(n71_dart_lease_cleanup(NULL, &lease) == -EINVAL);
	assert(n71_dart_lease_cleanup(&io, NULL) == -EINVAL);
	assert(!n71_dart_lease_pending(NULL));
	printf("N71_DART_LEASE_OK cases=%u\n", cases);
	return 0;
}
