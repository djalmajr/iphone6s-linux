/* SPDX-License-Identifier: GPL-2.0-only */
/* Replay readonly types with writable addresses and the actual rollback. */
#define main optional_ranges_entry
#include "n71_pcie_optional_ranges.c"
#undef main

struct typed_backend {
	struct backend raw;
	bool preserve_types, drop_address, clear_types;
	int write_error;
};

static int typed_read(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct typed_backend *b = context;
	return read_config(&b->raw, root, where, size, value);
}

static int typed_write(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct typed_backend *b = context;
	if (root && where == 0x24) {
		if (b->write_error) { b->raw.writes++; return b->write_error; }
		if (b->drop_address) { b->raw.writes++; return 0; }
		if (b->preserve_types)
			value = (value & 0xfff0fff0U) | 0x00010001U;
		if (b->clear_types)
			value &= 0xfff0fff0U;
	}
	return write_config(&b->raw, root, where, size, value);
}

static void typed_initialize(struct typed_backend *b)
{
	memset(b, 0, sizeof(*b)); initialize(&b->raw);
	b->raw.config[0][9] = 0x00010001;
	b->preserve_types = true;
}

static struct n71_resource_bar_layout typed_layout(void)
{
	return (struct n71_resource_bar_layout){.bytes = {0x8000, 0, 0x400000}, .pref64_disable = true};
}

static void sequence_and_defaults(void)
{
	unsigned int mode;
	for (mode = 0; mode < 3; mode++) {
		struct typed_backend b;
		struct n71_scan_io io = {&b, typed_read, typed_write};
		struct n71_resource_bar_layout layout = typed_layout();
		struct n71_resource_write_state state = {0};
		struct backend before;
		typed_initialize(&b); before = b.raw;
		layout.pref64_disable = mode == 0; b.preserve_types = mode != 2;
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		assert(state.pref64_disable == layout.pref64_disable);
		assert(n71_resource_write(&io, &state, &pref) == (mode == 1 ? -EIO : 0));
		assert(b.raw.writes == 1 && state.writes == (mode == 1 ? 0U : 1U));
		assert(state.pref64_writes == (mode == 0 ? 1U : 0U));
		assert(b.raw.config[0][9] == (mode == 2 ? 0xfff0U : 0x1fff1U));
		assert(state.failure.valid == (mode == 1));
		if (mode == 1) {
			assert(state.failure.request.value == 0xfff0 && state.failure.expected == 0xfff0);
			assert(state.failure.before == 0x10001 && state.failure.after == 0x1fff1);
		} else {
			assert(n71_resource_write(&io, &state, &pref) == 0 && b.raw.writes == 1);
			assert(state.pref64_writes == (mode == 0 ? 1U : 0U));
			assert(n71_resource_write(&io, &state, &io_lower) == 0);
			assert(b.raw.config[0][7] == 0xa90000f0);
			assert(state.pref64_writes == (mode == 0 ? 1U : 0U));
			state.active = false;
			assert(n71_resource_restore(&io, &state, true) == 0);
			assert(n71_scan_restore(&io, &state.reference) == 0);
			assert(memcmp(b.raw.config, before.config, sizeof(before.config)) == 0);
		}
	}
}

static void contradictory_capture_and_live(void)
{
	unsigned int mode;
	for (mode = 0; mode < 6; mode++) {
		struct typed_backend b;
		struct n71_scan_io io = {&b, typed_read, typed_write};
		struct n71_resource_bar_layout layout = typed_layout();
		struct n71_resource_write_state state = {0}, before;
		typed_initialize(&b);
		if (mode < 3) b.raw.config[0][9] = mode == 0 ? 0 : mode == 1 ? 0x10002 : 0x1fff1;
		else if (mode < 5) b.raw.config[0][10 + mode - 3] = 1;
		else layout.pref_absent = true;
		before = state;
		assert(n71_resource_capture(&io, &layout, &state) == -EACCES);
		assert(memcmp(&state, &before, sizeof(state)) == 0 && !b.raw.writes);
	}
	for (mode = 0; mode < 5; mode++) {
		struct typed_backend b;
		struct n71_scan_io io = {&b, typed_read, typed_write};
		struct n71_resource_bar_layout layout = typed_layout();
		struct n71_resource_write_state state = {0};
		unsigned int reads;
		typed_initialize(&b); assert(n71_resource_capture(&io, &layout, &state) == 0);
		if (mode < 3) b.raw.config[0][9] = mode == 0 ? 0xfff0 : mode == 1 ? 0x10002 : 0x1ffe1;
		else b.raw.config[0][10 + mode - 3] = 1;
		assert(n71_resource_write(&io, &state, &pref) == -EAGAIN);
		assert(!b.raw.writes && !state.pref64_writes && !state.failure.valid && state.pending);
		reads = b.raw.reads;
		assert(n71_resource_write(&io, &state, &io_lower) == -EAGAIN && b.raw.reads == reads);
	}
}

static void strict_readback_and_errors(void)
{
	unsigned int mode;
	for (mode = 0; mode < 6; mode++) {
		struct typed_backend b;
		struct n71_scan_io io = {&b, typed_read, typed_write};
		struct n71_resource_bar_layout layout = typed_layout();
		struct n71_resource_write_state state = {0};
		unsigned int reads;
		typed_initialize(&b); assert(n71_resource_capture(&io, &layout, &state) == 0);
		if (mode == 0) b.drop_address = true;
		else if (mode == 1) b.clear_types = true;
		else if (mode < 4) b.write_error = mode == 2 ? -ENOLINK : 7;
		else { b.raw.fail_read = b.raw.reads + 9; b.raw.read_error = mode == 4 ? -ENOLINK : 7; }
		assert(n71_resource_write(&io, &state, &pref) == (mode == 2 || mode == 4 ? -ENOLINK : -EIO));
		assert(state.failure.valid && state.failure.request.value == 0xfff0);
		assert(state.failure.expected == 0x1fff1 && state.failure.before == 0x10001);
		assert(!state.writes && !state.pref64_writes && b.raw.writes == 1);
		assert(state.failure.after_valid == (mode < 2));
		if (mode < 2) assert(state.failure.after == (mode == 0 ? 0x10001U : 0xfff0U));
		reads = b.raw.reads;
		assert(n71_resource_write(&io, &state, &pref) == state.error && b.raw.reads == reads);
	}
}

int main(void)
{
	sequence_and_defaults(); contradictory_capture_and_live(); strict_readback_and_errors();
	printf("N71_PCIE_PREF64_POLICY_OK cases=%u\n", cases);
	return 0;
}
