/* SPDX-License-Identifier: GPL-2.0-only */
/* Execute the real allocation policy with config I/O faults and no PCI core. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-resource-write.h"

struct backend {
	u32 config[2][64];
	unsigned int reads, writes, fail_read, fail_write, drop_write;
	int failure;
};

static unsigned int cases;
static const struct n71_resource_bar_layout layout = {.bytes = {0x8000, 0, 0x400000}};
static const struct n71_scan_request allocation[] = {
	{false, 4, 0x100, 2}, {false, 0x10, 0xc0800004, 4}, {false, 0x14, 0, 4},
	{false, 0x18, 0xc0000004, 4}, {false, 0x1c, 0, 4},
	{true, 0x30, 0xffff, 4}, {true, 0x1c, 0xf0, 2}, {true, 0x30, 0, 4},
	{true, 0x20, 0xc080c000, 4}, {true, 0x2c, 0, 4}, {true, 0x24, 0xfff0, 4},
	{true, 0x28, 0, 4}, {true, 0x2c, 0, 4}, {true, 0x3e, 0x20, 2}
};

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct backend *backend = context;
	u32 raw;
	assert(where < 256 && (size == 2 || size == 4));
	if (++backend->reads == backend->fail_read) {
		*value = 0xdeadbeef; /* A failed callback does not validate this value. */
		return backend->failure;
	}
	raw = backend->config[root ? 0 : 1][where / 4];
	*value = size == 4 ? raw : (raw >> ((where & 3) * 8)) & 0xffff;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct backend *backend = context;
	u32 *target = &backend->config[root ? 0 : 1][where / 4];
	unsigned int shift = (where & 3) * 8;
	/* Mutation captured: allowing allocation with either decode/master bit set. */
	assert(!(backend->config[0][1] & 7) && !(backend->config[1][1] & 7));
	assert(size != 4 || where != 4); /* Adjacent STATUS is W1C. */
	assert(!root || where != 0x1c || size == 2); /* Secondary STATUS stays intact. */
	if (++backend->writes == backend->fail_write)
		return backend->failure;
	if (backend->writes == backend->drop_write)
		return 0;
	if (size == 4)
		*target = value;
	else
		*target = (*target & ~(0xffffU << shift)) | (value << shift);
	return 0;
}

static void initialize(struct backend *backend)
{
	memset(backend, 0, sizeof(*backend));
	backend->failure = -EIO;
	backend->config[0][0] = 0x1004106b;
	backend->config[1][0] = 0x43a314e4;
	backend->config[0][1] = backend->config[1][1] = 0xa9000100;
	backend->config[0][2] = 0x06040001;
	backend->config[1][2] = 0x02800008;
	backend->config[0][3] = 0x10000;
	backend->config[0][6] = 0x010100;
	backend->config[0][7] = 0xa900ab12;
	backend->config[0][8] = 0x12301230;
	backend->config[0][9] = 0x98706543;
	backend->config[0][10] = 0x22334455;
	backend->config[0][11] = 0x55667788;
	backend->config[0][12] = 0xaabbccdd;
	backend->config[0][15] = 0x00201234;
	backend->config[1][4] = backend->config[1][6] = 4;
	cases++;
}

static int allocate(const struct n71_scan_io *io, struct n71_resource_write_state *state)
{
	unsigned int index;
	int error;
	for (index = 0; index < sizeof(allocation) / sizeof(allocation[0]); index++) {
		error = n71_resource_write(io, state, &allocation[index]);
		if (error)
			return error;
	}
	return 0;
}

static void restore_all(const struct n71_scan_io *io, struct n71_resource_write_state *state)
{
	state->active = false;
	assert(n71_resource_restore(io, state, true) == 0 && !state->pending);
	assert(n71_scan_restore(io, &state->reference) == 0);
}

static void first_write_failure(void)
{
	const struct n71_scan_request request = {true, 0x30, 0xffff, 4};
	struct backend backend, before;
	struct n71_scan_io io = {&backend, read_config, write_config};
	unsigned int fault;

	/* Mutation captured: losing the first 0x30 readback, inventing validity, or adding I/O. */
	for (fault = 0; fault < 5; fault++) {
		struct n71_resource_write_state state = {0};
		struct n71_resource_write_failure failure;
		unsigned int reads, writes;
		int expected = fault == 1 || fault == 3 ? -ENOLINK : -EIO;

		initialize(&backend); backend.config[0][12] = 0; before = backend;
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		reads = backend.reads;
		if (fault == 0)
			backend.drop_write = 1;
		else if (fault < 3)
			backend.fail_write = 1;
		else
			backend.fail_read = reads + 6;
		backend.failure = fault == 2 || fault == 4 ? 7 : -ENOLINK;
		assert(n71_resource_write(&io, &state, &request) == expected);
		failure = state.failure;
		assert(state.error == expected && !state.writes && state.attempts == 1);
		assert(state.active && state.pending && failure.valid);
		assert(failure.request.root && failure.request.where == 0x30);
		assert(failure.request.size == 4 && failure.request.value == 0xffff);
		assert(failure.before == 0 && failure.after == 0);
		assert(failure.after_valid == (fault == 0));
		assert(failure.write_error == (fault == 1 || fault == 2 ? backend.failure : 0));
		assert(failure.read_error == (fault >= 3 ? backend.failure : 0));
		assert(backend.reads - reads == (fault == 1 || fault == 2 ? 5U : 6U));
		assert(backend.writes == 1 && backend.config[0][12] == (fault >= 3 ? 0xffffU : 0U));
		reads = backend.reads; writes = backend.writes;
		assert(n71_resource_write(&io, &state, &allocation[1]) == expected);
		assert(backend.reads == reads && backend.writes == writes);
		assert(memcmp(&state.failure, &failure, sizeof(failure)) == 0);
		backend.fail_read = backend.fail_write = backend.drop_write = 0;
		restore_all(&io, &state);
		assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
		assert(memcmp(&state.failure, &failure, sizeof(failure)) == 0);
		assert(state.error == expected && !state.writes);
	}
	/* Mutation captured: claiming a failure for success/no-op or losing the pre-write value. */
	{
		struct n71_resource_write_state state = {0};
		initialize(&backend); before = backend;
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		assert(n71_resource_write(&io, &state, &request) == 0 && !state.failure.valid && state.writes == 1);
		backend.drop_write = 2;
		assert(n71_resource_write(&io, &state, &allocation[7]) == -EIO);
		assert(state.failure.valid && state.failure.before == 0xffff && state.failure.after == 0xffff);
		assert(state.failure.request.value == 0 && state.failure.after_valid && state.writes == 1);
		backend.drop_write = 0; restore_all(&io, &state);
		assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
	}
}

int main(void)
{
	struct backend backend, before;
	struct n71_scan_io io = {&backend, read_config, write_config};
	struct n71_resource_write_state state = {0}, sentinel = {0};
	struct n71_resource_bar_layout invalid;
	const struct n71_scan_request refused[] = {
		{false, 0x10, 0xbfff8004, 4}, {false, 0x10, 0xc0000014, 4},
		{false, 0x10, 0xc0000005, 4}, {false, 0x18, 0xc0010004, 4},
		{false, 0x14, 1, 4}, {false, 0x1c, 1, 4}, {false, 0x20, 4, 4},
		{false, 0x24, 4, 4}, {true, 0x10, 0xc0000004, 4},
		{false, 0x10, 4, 2}, {true, 0x1c, 0xf0, 4},
		{true, 0x20, 0xc080c001, 4}, {true, 0x20, 0xbff0c000, 4},
		{true, 0x20, 0xc080bff0, 4}, {true, 0x24, 0xc080c000, 4},
		{true, 0x28, 1, 4}, {true, 0x2c, 1, 4}, {true, 0x30, 0x10000, 4},
		{true, 4, 0x104, 2}, {true, 4, 0x102, 2}, {true, 4, 0x100, 4},
		{true, 0x3e, 0x60, 2}, {false, 0x80, 0, 4}, {true, 0x44, 0, 2}
	};
	unsigned int index, reads, writes, capture_reads;
	int error;

	initialize(&backend); before = backend;
	assert(n71_resource_capture(&io, &layout, &state) == 0 && state.active && state.pending);
	assert(!backend.writes); capture_reads = backend.reads;
	assert(n71_resource_capture(&io, &layout, &state) == -EBUSY);
	assert(allocate(&io, &state) == 0);
	assert(!state.failure.valid);
	reads = backend.reads - capture_reads; writes = backend.writes;
	assert(backend.config[1][4] == 0xc0800004 && backend.config[1][6] == 0xc0000004);
	assert(backend.config[0][8] == 0xc080c000 && backend.config[0][7] == 0xa90000f0);
	assert(backend.config[0][1] == before.config[0][1] && backend.config[1][1] == before.config[1][1]);
	assert(n71_resource_restore(&io, &state, true) == -EBUSY && state.pending);
	state.active = false;
	assert(n71_resource_restore(&io, &state, false) == -EBUSY && state.pending);
	restore_all(&io, &state);
	assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
	index = backend.writes;
	assert(n71_resource_restore(&io, &state, true) == 0 && backend.writes == index);
	assert(n71_resource_write(&io, &state, &allocation[1]) == -EPERM && backend.writes == index);
	for (index = 0; index < 2; index++) {
		initialize(&backend); state = (struct n71_resource_write_state){0};
		state.active = index == 0; state.pending = index == 1;
		assert(n71_resource_capture(&io, &layout, &state) == -EBUSY && !backend.reads);
		state.error = 0;
		assert(n71_resource_write(&io, &state, &allocation[1]) == -EPERM && !backend.writes);
	}
	{
		const struct n71_scan_request edges[] = {
			{false, 0x10, 0xc0000004, 4}, {false, 0x10, 0xffff8004, 4},
			{false, 0x18, 0xffc00004, 4}, {true, 0x20, 0xfff0fff0, 4},
			{true, 0x20, 0xfff0, 4}
		};
		initialize(&backend); before = backend; state = (struct n71_resource_write_state){0};
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		for (index = 0; index < sizeof(edges) / sizeof(edges[0]); index++)
			assert(n71_resource_write(&io, &state, &edges[index]) == 0);
		restore_all(&io, &state);
		assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
	}

	for (index = 0; index < sizeof(refused) / sizeof(refused[0]); index++) {
		initialize(&backend); state = (struct n71_resource_write_state){0};
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		assert(n71_resource_write(&io, &state, &refused[index]) == -EPERM && state.error == -EPERM);
		assert(!state.failure.valid);
		assert(!backend.writes); error = backend.reads;
		assert(n71_resource_write(&io, &state, &allocation[1]) == -EPERM && backend.reads == (unsigned int)error);
	}
	/* Mutation captured: bypassing scope, alignment, capture atomicity or the first-error latch. */
	for (index = 0; index < 6; index++) {
		initialize(&backend); state = sentinel; invalid = layout; invalid.bytes[index]++;
		assert(n71_resource_capture(&io, &invalid, &state) == -EINVAL && !backend.reads);
		assert(memcmp(&state, &sentinel, sizeof(state)) == 0);
	}
	for (index = 1; index <= capture_reads; index++) {
		initialize(&backend); state = sentinel; backend.fail_read = index;
		assert(n71_resource_capture(&io, &layout, &state) == -EIO && !backend.writes);
		assert(memcmp(&state, &sentinel, sizeof(state)) == 0);
	}
	for (index = 0; index < 6; index++) {
		initialize(&backend); state = sentinel; backend.config[1][4 + index] ^= 8;
		assert(n71_resource_capture(&io, &layout, &state) == -EACCES && !backend.writes);
	}
	for (index = 0; index < 6; index++) {
		initialize(&backend); state = (struct n71_resource_write_state){0};
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		backend.config[index / 3][1] |= 1U << (index % 3);
		assert(n71_resource_write(&io, &state, &allocation[1]) == -EACCES && !backend.writes);
	}
	for (index = 0; index < 2; index++) {
		initialize(&backend); state = (struct n71_resource_write_state){0};
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		backend.config[index][0] ^= 0x10000;
		assert(n71_resource_write(&io, &state, &allocation[1]) == -ENODEV && !backend.writes);
	}
	initialize(&backend); state = (struct n71_resource_write_state){0};
	assert(n71_resource_capture(&io, &layout, &state) == 0);
	for (index = 0; index < N71_RESOURCE_MAX_ATTEMPTS; index++)
		assert(n71_resource_write(&io, &state, &allocation[0]) == 0);
	assert(n71_resource_write(&io, &state, &allocation[0]) == -E2BIG && !backend.writes);
	for (index = 1; index <= reads; index++) {
		initialize(&backend); before = backend; state = (struct n71_resource_write_state){0};
		assert(n71_resource_capture(&io, &layout, &state) == 0); backend.fail_read = backend.reads + index;
		assert(allocate(&io, &state) == -EIO && state.error == -EIO);
		backend.fail_read = 0; restore_all(&io, &state);
		assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
	}
	for (index = 1; index <= writes; index++) {
		unsigned int fault;
		for (fault = 0; fault < 3; fault++) {
			initialize(&backend); before = backend; state = (struct n71_resource_write_state){0};
			assert(n71_resource_capture(&io, &layout, &state) == 0);
			if (fault < 2) { backend.fail_write = index; backend.failure = fault ? 1 : -ENOLINK; }
			else backend.drop_write = index;
			assert(allocate(&io, &state) == (fault ? -EIO : -ENOLINK));
			backend.fail_write = backend.drop_write = 0; restore_all(&io, &state);
			assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
		}
	}
	/* Mutation captured: restoring a live bus, releasing a failed restore, or skipping an extra window. */
	for (index = 1; index <= 3; index++) {
		initialize(&backend); before = backend; state = (struct n71_resource_write_state){0};
		assert(n71_resource_capture(&io, &layout, &state) == 0 && allocate(&io, &state) == 0);
		state.active = false; backend.drop_write = backend.writes + index;
		assert(n71_resource_restore(&io, &state, true) == -EIO && state.pending);
		backend.drop_write = 0; restore_all(&io, &state);
		assert(memcmp(backend.config, before.config, sizeof(backend.config)) == 0);
	}
	first_write_failure();
	printf("N71_PCIE_RESOURCE_WRITE_OK cases=%u; no PCI core or hardware\n", cases);
	return 0;
}
