/* SPDX-License-Identifier: GPL-2.0-only */
/* Reuse the config backend; exercise the actual IO16 policy and its rollback. */
#define main optional_ranges_entry
#include "n71_pcie_optional_ranges.c"
#undef main

struct io16_backend {
	struct backend raw;
	bool upper_readonly;
	unsigned int inject_after_read;
};

static int io16_read(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct io16_backend *b = context;
	int error = read_config(&b->raw, root, where, size, value);
	if (b->raw.reads == b->inject_after_read)
		b->raw.config[0][12] = 1;
	return error;
}

static int io16_write(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct io16_backend *b = context;
	if (root && where == 0x30 && b->upper_readonly) {
		b->raw.writes++;
		return 0;
	}
	return write_config(&b->raw, root, where, size, value);
}

static void io16_initialize(struct io16_backend *b)
{
	memset(b, 0, sizeof(*b));
	initialize(&b->raw);
	b->upper_readonly = true;
}

static struct n71_resource_bar_layout io16_layout(void)
{
	return (struct n71_resource_bar_layout){.bytes = {0x8000, 0, 0x400000},
		.io16_upper_unused = true};
}

static void sequence_and_default(void)
{
	unsigned int mode;
	for (mode = 0; mode < 3; mode++) {
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		struct n71_resource_bar_layout layout = io16_layout();
		struct n71_resource_write_state state = {0};
		const struct n71_scan_request clear_upper = {true, 0x30, 0, 4};
		struct backend before;
		unsigned int reads;
		io16_initialize(&b); before = b.raw;
		layout.io16_upper_unused = mode == 0;
		b.upper_readonly = mode != 2;
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		assert(state.io16_upper_unused == layout.io16_upper_unused);
		reads = b.raw.reads;
		assert(n71_resource_write(&io, &state, &io_upper) == (mode == 1 ? -EIO : 0));
		assert(b.raw.reads - reads == (mode == 0 ? 7U : 6U));
		assert(state.io16_noops == (mode == 0 ? 1U : 0U));
		assert(b.raw.writes == (mode == 0 ? 0U : 1U));
		assert(state.failure.valid == (mode == 1));
		if (mode == 1) {
			assert(state.failure.after_valid && state.failure.after == 0);
			continue;
		}
		assert(n71_resource_write(&io, &state, &io_lower) == 0);
		assert(b.raw.config[0][7] == 0xa90000f0);
		assert(n71_resource_write(&io, &state, &clear_upper) == 0);
		if (mode == 0) {
			assert(n71_resource_write(&io, &state, &io_upper) == 0);
			assert(state.io16_noops == 2 && state.writes == 1 && b.raw.writes == 1);
		}
		assert(!state.io_noops && !state.pref_noops);
		state.active = false;
		assert(n71_resource_restore(&io, &state, true) == 0);
		assert(n71_scan_restore(&io, &state.reference) == 0);
		assert(memcmp(b.raw.config, before.config, sizeof(before.config)) == 0);
	}
}

static void capture_and_live_conflicts(void)
{
	const u32 lower_values[] = {1, 0x100, 0x101, 2, 0x200, 0x202, 0xf0, 0x1000};
	unsigned int index;
	for (index = 0; index < 11; index++) {
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		struct n71_resource_bar_layout layout = io16_layout();
		struct n71_resource_write_state state = {0}, before;
		io16_initialize(&b);
		if (index < 8) b.raw.config[0][7] |= lower_values[index];
		else if (index < 10) b.raw.config[0][12] = index == 8 ? 1 : 0xffff;
		else layout.io_absent = true;
		before = state;
		assert(n71_resource_capture(&io, &layout, &state) == -EACCES);
		assert(memcmp(&state, &before, sizeof(state)) == 0 && !b.raw.writes);
	}
	for (index = 0; index < 10; index++) {
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		struct n71_resource_bar_layout layout = io16_layout();
		struct n71_resource_write_state state = {0};
		unsigned int reads;
		io16_initialize(&b);
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		if (index < 8) b.raw.config[0][7] |= lower_values[index] == 0xf0 ? 0xf1 : lower_values[index];
		else b.raw.config[0][12] = index == 8 ? 1 : 0xffff;
		assert(n71_resource_write(&io, &state, &io_upper) == -EAGAIN);
		assert(!b.raw.writes && !state.io16_noops && !state.failure.valid && state.pending);
		reads = b.raw.reads;
		assert(n71_resource_write(&io, &state, &io_lower) == -EAGAIN && b.raw.reads == reads);
	}
}

static void read_failures_and_races(void)
{
	unsigned int mode;
	for (mode = 0; mode < 6; mode++) {
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		struct n71_resource_bar_layout layout = io16_layout();
		struct n71_resource_write_state state = {0};
		int expected = mode >= 4 ? -EAGAIN : mode & 1 ? -EIO : -ENOLINK;
		io16_initialize(&b);
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		if (mode < 4) {
			b.raw.fail_read = b.raw.reads + 6 + (mode >= 2);
			b.raw.read_error = mode & 1 ? 7 : -ENOLINK;
		} else if (mode == 4) {
			b.raw.config[0][12] = 0xffff;
			b.raw.clear_read = b.raw.reads + 5;
		} else {
			b.inject_after_read = b.raw.reads + 5;
		}
		assert(n71_resource_write(&io, &state, &io_upper) == expected);
		assert(state.error == expected && !state.io16_noops && !state.failure.valid && !b.raw.writes);
	}
}

static void helper_scope(void)
{
	const struct n71_scan_request requests[] = {
		{false, 0x30, 0xffff, 4}, {true, 0x2c, 0xffff, 4},
		{true, 0x30, 0xffff, 2}, {true, 0x30, 0xfffe, 4},
	};
	unsigned int index;
	for (index = 0; index < 4; index++) {
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		bool handled = true;
		io16_initialize(&b);
		assert(n71_io16_upper_noop(&io, &requests[index], 0, &handled) == 0);
		assert(!handled && !b.raw.reads && !b.raw.writes);
	}
}

static void guard_scope_and_budget(void)
{
	const struct n71_scan_request requests[] = {
		{false, 0x30, 0xffff, 4}, {true, 0x30, 0xffff, 2}, {true, 0x30, 1, 4},
		{true, 0x1c, 0xf0, 4}, {true, 0x1c, 0x101, 2}, {true, 4, 4, 2},
	};
	unsigned int index;
	for (index = 0; index < 14; index++) {
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		struct n71_resource_bar_layout layout = io16_layout();
		struct n71_resource_write_state state = {0};
		const struct n71_scan_request *request = &io_upper;
		int expected = -EACCES;
		io16_initialize(&b);
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		if (index < 6) { request = &requests[index]; expected = -EPERM; }
		else if (index < 12) b.raw.config[index < 9 ? 0 : 1][1] = 1U << ((index - 6) % 3);
		else if (index == 12) { b.raw.config[1][0] ^= 1; expected = -ENODEV; }
		else { state.attempts = N71_RESOURCE_MAX_ATTEMPTS; expected = -E2BIG; }
		assert(n71_resource_write(&io, &state, request) == expected);
		assert(state.error == expected && !state.io16_noops && !state.failure.valid && !b.raw.writes);
	}
	{
		struct io16_backend b;
		struct n71_scan_io io = {&b, io16_read, io16_write};
		struct n71_resource_bar_layout layout = io16_layout();
		struct n71_resource_write_state state = {0};
		io16_initialize(&b);
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		state.attempts = N71_RESOURCE_MAX_ATTEMPTS - 1;
		assert(n71_resource_write(&io, &state, &io_upper) == 0);
		assert(state.attempts == N71_RESOURCE_MAX_ATTEMPTS && state.io16_noops == 1);
	}
}

int main(void)
{
	sequence_and_default(); capture_and_live_conflicts(); read_failures_and_races(); guard_scope_and_budget(); helper_scope();
	printf("N71_PCIE_IO16_UPPER_OK cases=%u\n", cases);
	return 0;
}
