/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-dart-cycle.h"

struct mock {
	struct n71_dart_observation original, state;
	unsigned int snapshots, quiet, starts, stops, writes;
	unsigned int fail_snapshot, fail_quiet, fail_write;
	int start_error, stop_error;
	bool running, active_after_stop, corrupt_restore, changed_control, write_error_after_store;
};

static int snapshot(void *context, struct n71_dart_observation *out)
{
	struct mock *mock = context;
	if (++mock->snapshots == mock->fail_snapshot)
		return -EIO;
	*out = mock->state;
	if (mock->corrupt_restore && mock->snapshots == 4)
		out->ttbr[15] ^= 1;
	return 0;
}

static int quiet(void *context)
{
	struct mock *mock = context;
	return ++mock->quiet == mock->fail_quiet ? -ENOLINK : 0;
}

static int start(void *context)
{
	struct mock *mock = context;
	mock->starts++; mock->running = true;
	memset(mock->state.ttbr, 0, sizeof(mock->state.ttbr));
	mock->state.valid_ttbrs = 0;
	return mock->start_error;
}

static int stop(void *context)
{
	struct mock *mock = context;
	mock->stops++;
	if (mock->stop_error)
		return mock->stop_error;
	mock->running = false;
	if (mock->active_after_stop)
		mock->state.tcr = 0x80;
	if (mock->changed_control)
		mock->state.error = 0;
	return 0;
}

static int write_ttbr(void *context, unsigned int index, u32 value)
{
	struct mock *mock = context;
	assert(!mock->running && !mock->state.tcr && index == mock->writes && index < 16);
	assert(value == mock->original.ttbr[index]);
	if (++mock->writes == mock->fail_write && !mock->write_error_after_store)
		return -EIO;
	mock->state.ttbr[index] = value;
	return mock->writes == mock->fail_write ? -EIO : 0;
}

static void initialize(struct mock *mock)
{
	unsigned int index;
	memset(mock, 0, sizeof(*mock));
	mock->original.command = 0xf02;
	mock->original.error = 0x100;
	for (index = 0; index < 16; index++)
		mock->original.ttbr[index] = 0x80123400 + index;
	mock->state = mock->original;
}

int main(void)
{
	struct mock mock;
	struct n71_dart_cycle_io io = {&mock, snapshot, quiet, start, stop, write_ttbr};
	struct n71_dart_cycle_result result;
	unsigned int index;
	initialize(&mock);
	assert(n71_dart_cycle(&io, &result) == 0);
	assert(result.attempted && result.stopped && result.restored && !result.control_changed);
	assert(result.snapshots == 4 && result.writes == 16 && mock.quiet == 17 &&
	       mock.starts == 1 && mock.stops == 1);
	assert(memcmp(mock.state.ttbr, mock.original.ttbr, sizeof(mock.state.ttbr)) == 0);
	/* Mutation captured: failed start skips unregister or fails to restore original tables. */
	initialize(&mock); mock.start_error = -ENODEV;
	assert(n71_dart_cycle(&io, &result) == -ENODEV && result.restored && result.stopped);
	assert(mock.starts == 1 && mock.stops == 1 && mock.writes == 16);
	initialize(&mock); mock.stop_error = -EBUSY;
	assert(n71_dart_cycle(&io, &result) == -EBUSY && !result.restored && !result.stopped);
	assert(mock.writes == 0);
	initialize(&mock); mock.active_after_stop = true;
	assert(n71_dart_cycle(&io, &result) == -EACCES && mock.writes == 0);
	initialize(&mock); mock.corrupt_restore = true;
	assert(n71_dart_cycle(&io, &result) == -EIO && !result.restored);
	initialize(&mock); mock.changed_control = true;
	assert(n71_dart_cycle(&io, &result) == -EIO && result.restored && result.control_changed);
	for (index = 1; index <= 4; index++) {
		initialize(&mock); mock.fail_snapshot = index;
		assert(n71_dart_cycle(&io, &result) == -EIO && result.restored == (index == 2));
		assert(mock.stops == (index == 1 ? 0U : 1U));
	}
	for (index = 1; index <= 17; index++) {
		initialize(&mock); mock.fail_quiet = index;
		assert(n71_dart_cycle(&io, &result) == -ENOLINK && !result.restored);
		assert(mock.stops == (index == 1 ? 0U : 1U));
	}
	for (index = 1; index <= 16; index++) {
		initialize(&mock); mock.fail_write = index;
		assert(n71_dart_cycle(&io, &result) == -EIO && !result.restored && result.stopped);
		assert(mock.writes == 16);
	}
	initialize(&mock); mock.fail_write = 1; mock.write_error_after_store = true;
	assert(n71_dart_cycle(&io, &result) == -EIO && !result.restored && result.stopped);
	assert(memcmp(mock.state.ttbr, mock.original.ttbr, sizeof(mock.state.ttbr)) == 0);
	initialize(&mock); mock.state.tcr = 1;
	assert(n71_dart_cycle(&io, &result) == -EACCES && mock.starts == 0);
	initialize(&mock); mock.state.command |= 8;
	assert(n71_dart_cycle(&io, &result) == -EACCES && mock.starts == 0);
	initialize(&mock); mock.state.error |= 0x80000000;
	assert(n71_dart_cycle(&io, &result) == -EACCES && mock.starts == 0);
	assert(n71_dart_cycle(NULL, &result) == -EINVAL);
	assert(n71_dart_cycle(&io, NULL) == -EINVAL);
	puts("N71_DART_CYCLE_OK");
	return 0;
}
