/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-scan-link-target.h"

struct mock {
	u32 config[64];
	unsigned int reads, writes, fail_read, fail_write;
	bool write_took_effect, ignore_write, corrupt_link_after_write;
	int positive_error;
};

static int read_config(void *context, u32 where, unsigned int size, u32 *value)
{
	struct mock *mock = context;
	u32 mask = size == 4 ? 0xffffffff : (1U << (size * 8)) - 1;
	assert(where < 256 && (size == 1 || size == 2 || size == 4) && where % size == 0);
	if (++mock->reads == mock->fail_read)
		return mock->positive_error ? 1 : -EIO;
	*value = (mock->config[where / 4] >> ((where & 3) * 8)) & mask;
	return 0;
}

static int write_config(void *context, u32 where, unsigned int size, u32 value)
{
	struct mock *mock = context;
	assert(where == 0xa0 && size == 2 && (value == 1 || value == 2));
	mock->writes++;
	if (!mock->ignore_write && (mock->writes != mock->fail_write || mock->write_took_effect))
		mock->config[0xa0 / 4] = (mock->config[0xa0 / 4] & 0xffff0000) | value;
	if (mock->corrupt_link_after_write)
		mock->config[0x80 / 4] ^= 0x08000000;
	return mock->writes == mock->fail_write ? (mock->positive_error ? 1 : -EIO) : 0;
}

static void initialize(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->config[0] = 0x1004106b;
	mock->config[1] = 0x00100000;
	mock->config[2] = 0x06040001;
	mock->config[3] = 0x00010000;
	mock->config[0x18 / 4] = 0x00010100;
	mock->config[0x34 / 4] = 0x40;
	mock->config[0x40 / 4] = 0x00007001;
	mock->config[0x70 / 4] = 0x00420010;
	mock->config[0x7c / 4] = 0x00733812;
	mock->config[0x80 / 4] = 0x30110000;
	mock->config[0x9c / 4] = 6;
	mock->config[0xa0 / 4] = 0x5a5a0001;
}

static void rejected(struct mock *mock)
{
	struct n71_link_target_io io = {mock, read_config, write_config};
	struct n71_link_target state = {0}, before;
	state.original = 0xa5a5;
	before = state;
	assert(n71_link_target_capture(&io, &state) < 0);
	assert(memcmp(&state, &before, sizeof(state)) == 0 && mock->writes == 0);
}

int main(void)
{
	struct mock mock, original;
	struct n71_link_target_io io = {&mock, read_config, write_config};
	struct n71_link_target state = {0};
	unsigned int count, index, before;
	const struct {u32 where, mask;} bad[] = {
		{0, 1}, {8, 0x100}, {0xc, 0x10000}, {0x18, 0x10000},
		{4, 1}, {4, 2}, {4, 4}, {4, 0x100000}, {0x70, 0x10000},
		{0x70, 0x100000}, {0x7c, 1}, {0x7c, 0x100000},
		{0x80, 0x20}, {0x80, 0x08000000}, {0x80, 0x20000000},
		{0x80, 0x00020000}, {0xa0, 2}, {0xa0, 0x100},
		{0x9c, 2}, {0x9c, 4}, {0x9c, 8},
	};

	/* Mutation captured: a widened target/width or a retrain write changes other state. */
	initialize(&mock); original = mock;
	assert(n71_link_target_capture(&io, &state) == 0 && state.captured);
	count = mock.reads;
	assert(n71_link_target_prepare(&io, &state) == 0 && state.prepared && state.pending);
	assert(mock.writes == 1 && mock.config[0xa0 / 4] == 0x5a5a0002);
	assert(mock.config[0x80 / 4] == original.config[0x80 / 4]);
	assert(n71_link_target_prepare(&io, &state) == -EINVAL);
	assert(n71_link_target_capture(&io, &state) == -EINVAL && state.pending);
	assert(n71_link_target_restore(&io, &state) == 0 && !state.pending && !state.prepared);
	assert(mock.writes == 2 && memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
	assert(n71_link_target_restore(&io, &state) == 0 && mock.writes == 2);
	for (index = 0; index < sizeof(bad) / sizeof(*bad); index++) {
		initialize(&mock); mock.config[bad[index].where / 4] ^= bad[index].mask;
		rejected(&mock);
	}
	initialize(&mock); mock.config[0xa0 / 4] = 0x5a5a0002; rejected(&mock);
	initialize(&mock); mock.config[0x34 / 4] = 0x42; rejected(&mock);
	initialize(&mock); mock.config[0x34 / 4] = 0; rejected(&mock);
	initialize(&mock); mock.config[0x40 / 4] = 0x00004001; rejected(&mock);
	initialize(&mock); mock.config[0x70 / 4] = 0x0042fc10;
	mock.config[0xfc / 4] = 0x00420010; rejected(&mock);
	initialize(&mock); mock.config[0x70 / 4] |= 0x4000; rejected(&mock);
	initialize(&mock); mock.config[0x70 / 4] = 0xffffffff; rejected(&mock);
	initialize(&mock); mock.config[0x7c / 4] = 0xffffffff; rejected(&mock);
	initialize(&mock); mock.config[0x9c / 4] = 0xffffffff; rejected(&mock);
	initialize(&mock); mock.config[0x34 / 4] = 0xfc;
	mock.config[0xfc / 4] = 0x00420010; rejected(&mock);
	initialize(&mock); mock.config[0x34 / 4] = 0x80;
	for (index = 0x80; index <= 0xbc; index += 4)
		mock.config[index / 4] = ((index + 4) << 8) | 5;
	mock.config[0xc0 / 4] = 5; rejected(&mock);
	for (index = 1; index <= count; index++) {
		initialize(&mock); mock.fail_read = index; rejected(&mock);
	}
	initialize(&mock); mock.fail_read = 1; mock.positive_error = 1; rejected(&mock);

	/* Mutation captured: ignoring fresh ownership/link checks writes after a changed snapshot. */
	for (index = 0; index < sizeof(bad) / sizeof(*bad); index++) {
		initialize(&mock); memset(&state, 0, sizeof(state));
		assert(n71_link_target_capture(&io, &state) == 0);
		mock.config[bad[index].where / 4] ^= bad[index].mask;
		assert(n71_link_target_prepare(&io, &state) < 0 && !state.pending && mock.writes == 0);
	}
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	mock.config[0x7c / 4] ^= 0x10;
	assert(n71_link_target_prepare(&io, &state) == -EIO && !state.pending && mock.writes == 0);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	mock.config[0x9c / 4] ^= 0x100;
	assert(n71_link_target_prepare(&io, &state) == -EIO && !state.pending && mock.writes == 0);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	mock.config[0x80 / 4] ^= 0x10000000;
	assert(n71_link_target_prepare(&io, &state) == -EIO && !state.pending && mock.writes == 0);

	/* Mutation captured: write/readback failure loses cleanup, or retry duplicates a restored write. */
	for (index = 0; index < 2; index++) {
		initialize(&mock); memset(&state, 0, sizeof(state));
		assert(n71_link_target_capture(&io, &state) == 0);
		mock.fail_write = 1; mock.write_took_effect = index == 1;
		assert(n71_link_target_prepare(&io, &state) == -EIO && state.pending && !state.prepared);
		assert(n71_link_target_capture(&io, &state) == -EINVAL && state.pending);
		assert(n71_link_target_restore(&io, &state) == 0 && !state.pending);
		assert(mock.writes == 1 + index && (mock.config[0xa0 / 4] & 0xffff) == 1);
	}
	for (index = 1; index <= count * 2; index++) {
		initialize(&mock); memset(&state, 0, sizeof(state));
		assert(n71_link_target_capture(&io, &state) == 0);
		mock.fail_read = mock.reads + index;
		assert(n71_link_target_prepare(&io, &state) == -EIO);
		assert(state.pending == (index > count));
		mock.fail_read = 0;
		assert(n71_link_target_restore(&io, &state) == 0 && !state.pending);
	}
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	mock.ignore_write = true;
	assert(n71_link_target_prepare(&io, &state) == -EIO && state.pending);
	mock.ignore_write = false;
	assert(n71_link_target_restore(&io, &state) == 0 && mock.writes == 1);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	assert(n71_link_target_prepare(&io, &state) == 0);
	mock.fail_write = mock.writes + 1; mock.write_took_effect = true;
	assert(n71_link_target_restore(&io, &state) == -EIO && state.pending && !state.prepared);
	before = mock.writes;
	assert(n71_link_target_restore(&io, &state) == 0 && mock.writes == before);
	for (index = 1; index <= count * 2; index++) {
		initialize(&mock); memset(&state, 0, sizeof(state));
		assert(n71_link_target_capture(&io, &state) == 0);
		assert(n71_link_target_prepare(&io, &state) == 0);
		mock.fail_read = mock.reads + index;
		assert(n71_link_target_restore(&io, &state) == -EIO && state.pending && !state.prepared);
		mock.fail_read = 0; before = mock.writes;
		assert(n71_link_target_restore(&io, &state) == 0 && !state.pending);
		assert(mock.writes == before + (index <= count));
	}
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	assert(n71_link_target_prepare(&io, &state) == 0);
	mock.ignore_write = true;
	assert(n71_link_target_restore(&io, &state) == -EIO && state.pending);
	mock.ignore_write = false;
	assert(n71_link_target_restore(&io, &state) == 0 && !state.pending);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	assert(n71_link_target_prepare(&io, &state) == 0);
	mock.config[0] ^= 1; before = mock.writes;
	assert(n71_link_target_restore(&io, &state) == -ENODEV && state.pending && mock.writes == before);
	mock.config[0] ^= 1;
	assert(n71_link_target_restore(&io, &state) == 0 && !state.pending);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_link_target_capture(&io, &state) == 0);
	mock.corrupt_link_after_write = true;
	assert(n71_link_target_prepare(&io, &state) == -EACCES && state.pending);
	mock.corrupt_link_after_write = false; mock.config[0x80 / 4] ^= 0x08000000;
	assert(n71_link_target_restore(&io, &state) == 0);
	initialize(&mock); memset(&state, 0, sizeof(state));
	mock.config[0x9c / 4] = 0; /* Kernel's legacy SLS fallback, still exactly Gen2. */
	assert(n71_link_target_capture(&io, &state) == 0);
	assert(n71_link_target_prepare(&io, &state) == 0);
	assert(n71_link_target_restore(&io, &state) == 0);
	assert(n71_link_target_capture(NULL, &state) == -EINVAL);
	assert(n71_link_target_capture(&io, NULL) == -EINVAL);
	assert(n71_link_target_prepare(&io, NULL) == -EINVAL);
	assert(n71_link_target_restore(&io, NULL) == -EINVAL);
	puts("N71_PCIE_SCAN_LINK_TARGET_OK");
	return 0;
}
