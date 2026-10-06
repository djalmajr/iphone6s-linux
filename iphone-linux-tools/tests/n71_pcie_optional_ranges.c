/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise absent optional windows using the real allocation policy. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-resource-write.h"

struct backend {
	u32 config[2][64];
	unsigned int reads, writes, fail_read, clear_read;
	int read_error;
	bool io_readonly, pref_readonly;
};
static unsigned int cases;
static const struct n71_scan_request io_upper = {true, 0x30, 0xffff, 4};
static const struct n71_scan_request io_lower = {true, 0x1c, 0xf0, 2};
static const struct n71_scan_request pref = {true, 0x24, 0xfff0, 4};

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct backend *b = context;
	u32 raw = b->config[root ? 0 : 1][where / 4];
	assert(where < 256 && (size == 2 || size == 4));
	assert(!root || where != 0x1c || size == 2);
	if (++b->reads == b->fail_read)
		return b->read_error;
	*value = size == 4 ? raw : (raw >> ((where & 3) * 8)) & 0xffff;
	if (b->reads == b->clear_read)
		b->config[root ? 0 : 1][where / 4] = 0;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct backend *b = context;
	u32 *target = &b->config[root ? 0 : 1][where / 4];
	assert(!(b->config[0][1] & 7) && !(b->config[1][1] & 7));
	assert(!root || where != 0x1c || size == 2);
	b->writes++;
	if (root && ((b->io_readonly && (where == 0x1c || where == 0x30)) ||
		     (b->pref_readonly && (where == 0x24 || where == 0x28 || where == 0x2c))))
		return 0;
	if (size == 4)
		*target = value;
	else
		*target = (*target & ~(0xffffU << ((where & 3) * 8))) | (value << ((where & 3) * 8));
	return 0;
}

static void initialize(struct backend *b)
{
	memset(b, 0, sizeof(*b));
	b->config[0][0] = 0x1004106b; b->config[1][0] = 0x43a314e4;
	b->config[0][2] = 0x06040001; b->config[1][2] = 0x02800008;
	b->config[0][3] = 0x10000; b->config[0][6] = 0x010100;
	b->config[0][7] = 0xa9000000; /* Secondary STATUS must remain unchanged. */
	b->config[1][4] = b->config[1][6] = 4;
	cases++;
}

static void absent_and_implemented(void)
{
	unsigned int flags;
	for (flags = 0; flags < 4; flags++) {
		struct backend b, before;
		struct n71_scan_io io = {&b, read_config, write_config};
		struct n71_resource_bar_layout layout = {.bytes = {0x8000, 0, 0x400000},
			.io_absent = !!(flags & 1), .pref_absent = !!(flags & 2)};
		struct n71_resource_write_state state = {0};
		unsigned int reads;
		const struct n71_scan_request memory = {true, 0x20, 0xc080c000, 4};
		initialize(&b); before = b; b.io_readonly = layout.io_absent; b.pref_readonly = layout.pref_absent;
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		assert(state.io_absent == layout.io_absent && state.pref_absent == layout.pref_absent);
		reads = b.reads;
		assert(n71_resource_write(&io, &state, &io_upper) == 0);
		assert(b.reads - reads == (layout.io_absent ? 7U : 6U));
		assert(n71_resource_write(&io, &state, &io_lower) == 0);
		assert(n71_resource_write(&io, &state, &pref) == 0);
		assert(state.io_noops == (layout.io_absent ? 2U : 0U));
		assert(state.pref_noops == (layout.pref_absent ? 1U : 0U));
		assert(b.writes == (layout.io_absent ? 0U : 2U) + (layout.pref_absent ? 0U : 1U));
		assert(b.config[0][12] == (layout.io_absent ? 0U : 0xffffU));
		assert(b.config[0][7] == (layout.io_absent ? 0xa9000000U : 0xa90000f0U));
		assert(b.config[0][9] == (layout.pref_absent ? 0U : 0xfff0U));
		assert(n71_resource_write(&io, &state, &memory) == 0);
		assert(state.writes == b.writes && !state.failure.valid);
		state.active = false;
		assert(n71_resource_restore(&io, &state, true) == 0);
		assert(n71_scan_restore(&io, &state.reference) == 0);
		assert(memcmp(b.config, before.config, sizeof(b.config)) == 0);
		assert(state.io_noops == (layout.io_absent ? 2U : 0U));
		assert(state.pref_noops == (layout.pref_absent ? 1U : 0U));
	}
}

static void contradictory_capture_and_live_drift(void)
{
	const u32 offsets[] = {0x1c, 0x30, 0x24, 0x28, 0x2c};
	unsigned int index;
	for (index = 0; index < 5; index++) {
		struct backend b;
		struct n71_scan_io io = {&b, read_config, write_config};
		struct n71_resource_bar_layout layout = {.bytes = {0x8000, 0, 0x400000},
			.io_absent = true, .pref_absent = true};
		struct n71_resource_write_state state = {0}, before;
		const struct n71_scan_request *request = index == 0 ? &io_upper : index == 1 ? &io_lower : &pref;
		unsigned int reads;
		initialize(&b); b.config[0][offsets[index] / 4] |= 1;
		before = state;
		assert(n71_resource_capture(&io, &layout, &state) == -EACCES);
		assert(memcmp(&state, &before, sizeof(state)) == 0 && b.writes == 0);
		initialize(&b); assert(n71_resource_capture(&io, &layout, &state) == 0);
		b.config[0][offsets[index] / 4] |= 1;
		assert(n71_resource_write(&io, &state, request) == -EAGAIN);
		assert(state.error == -EAGAIN && !state.failure.valid && !state.io_noops && !state.pref_noops);
		assert(b.writes == 0 && state.pending && state.active);
		reads = b.reads;
		assert(n71_resource_write(&io, &state, &io_upper) == -EAGAIN && b.reads == reads);
	}
}

static void errors_and_strict_fallback(void)
{
	unsigned int mode;
	for (mode = 0; mode < 7; mode++) {
		struct backend b;
		struct n71_scan_io io = {&b, read_config, write_config};
		struct n71_resource_bar_layout layout = {.bytes = {0x8000, 0, 0x400000},
			.io_absent = mode < 5, .pref_absent = mode < 5};
		struct n71_resource_write_state state = {0};
		const struct n71_scan_request *request = mode == 4 || mode == 6 ? &pref : &io_upper;
		int expected = mode == 4 ? -EAGAIN : mode == 0 || mode == 2 ? -ENOLINK : -EIO;
		initialize(&b); b.io_readonly = b.pref_readonly = true;
		assert(n71_resource_capture(&io, &layout, &state) == 0);
		if (mode < 4) {
			b.fail_read = b.reads + 6 + (mode >= 2); b.read_error = mode & 1 ? 7 : -ENOLINK;
		} else if (mode == 4) {
			b.config[0][9] = 1; b.clear_read = b.reads + 5;
		}
		assert(n71_resource_write(&io, &state, request) == expected);
		assert(state.error == expected && !state.writes && !state.io_noops && !state.pref_noops);
		assert(state.failure.valid == (mode >= 5));
		assert(b.writes == (mode >= 5 ? 1U : 0U));
		if (mode >= 5)
			assert(state.failure.after_valid && state.failure.after == 0);
	}
}

int main(void)
{
	absent_and_implemented(); contradictory_capture_and_live_drift(); errors_and_strict_fallback();
	printf("N71_PCIE_OPTIONAL_RANGES_OK cases=%u\n", cases);
	return 0;
}
