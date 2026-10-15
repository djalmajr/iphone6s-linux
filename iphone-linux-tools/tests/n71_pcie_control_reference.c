/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-control-reference.h"

struct mock { u32 config[1024]; unsigned int reads, fault; bool root, positive; };

static int read_reference(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct mock *mock = context;
	u32 mask = size == 4 ? 0xffffffff : (1U << (size * 8)) - 1;
	assert(root == mock->root && where < 4096 && where % size == 0);
	if (++mock->reads == mock->fault)
		return mock->positive ? 1 : -EIO;
	*value = (mock->config[where / 4] >> (8 * (where & 3))) & mask;
	return 0;
}

static int forbidden_write(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	(void)context; (void)root; (void)where; (void)size; (void)value;
	assert(0 && "Reference must never write configuration");
	return -EIO;
}

static void initialize(struct mock *mock, bool root)
{
	memset(mock, 0, sizeof(*mock)); mock->root = root;
	mock->config[0] = root ? 0x1004106b : 0x43a314e4;
	mock->config[1] = 0x00100000;
	mock->config[0x34 / 4] = 0x40;
	mock->config[0x40 / 4] = 0x00005001;
	mock->config[0x44 / 4] = 0x11228008;
	mock->config[0x50 / 4] = 0x00867005;
	mock->config[0x70 / 4] = root ? 0x00420010 : 0x00020010;
	mock->config[0x7c / 4] = 0x00100022;
	mock->config[0x80 / 4] = 0x20220002;
	mock->config[0xa0 / 4] = 0x33110001;
	mock->config[0x100 / 4] = 0x14010001;
	mock->config[0x140 / 4] = 0x0001001f;
}

static void rejected(struct mock *mock, int expected)
{
	struct n71_scan_io io = {mock, read_reference, forbidden_write};
	struct n71_control_reference out, original;
	memset(&out, 0xa5, sizeof(out)); original = out;
	assert(n71_control_capture(&io, mock->root, &out) == expected);
	assert(memcmp(&out, &original, sizeof(out)) == 0);
}

int main(void)
{
	struct mock mock, original;
	struct n71_scan_io io = {&mock, read_reference, forbidden_write};
	struct n71_control_reference out;
	unsigned int index, reads, function;

	for (function = 0; function < 2; function++) {
		initialize(&mock, function == 0); original = mock;
		assert(n71_control_capture(&io, mock.root, &out) == 0);
		assert(out.count == 14 && out.capabilities == 5 && out.reads <= 128);
		assert(out.words[0].where == 0x44 && out.words[0].size == 2 && out.words[0].value == 0x8008);
		assert(out.words[1].where == 0x52 && out.words[1].value == 0x86);
		assert(out.words[3].where == 0x7c && out.words[3].size == 4 && out.words[3].value == 0x00100022);
		assert(out.words[4].where == 0x80 && out.words[4].value == 2);
		assert(out.words[5].where == 0x82 && out.words[5].value == 0x2022);
		assert(out.words[7].where == 0xa0 && out.words[7].size == 2 && out.words[7].value == 1);
		assert(out.words[8].where == 0x104 && out.words[8].capability == 0x10001);
		assert(out.words[13].where == 0x148 && out.words[13].capability == 0x1001f);
		assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
		reads = mock.reads;
		for (index = 1; index <= reads; index++) {
			mock = original; mock.fault = index; rejected(&mock, -EIO);
		}
	}
	initialize(&mock, true); mock.fault = 1; mock.positive = true; rejected(&mock, -EIO);
	initialize(&mock, true); mock.config[0] ^= 1; rejected(&mock, -ENODEV);
	initialize(&mock, true); mock.config[1] |= 4; rejected(&mock, -EACCES);
	initialize(&mock, true); mock.config[0x34 / 4] = 0x41; rejected(&mock, -EINVAL);
	initialize(&mock, true); mock.config[0x34 / 4] = 0x42; rejected(&mock, -EINVAL);
	initialize(&mock, true); mock.config[0x40 / 4] = 0x4001; rejected(&mock, -ELOOP);
	initialize(&mock, true); mock.config[0x100 / 4] = 0x10010001; rejected(&mock, -ELOOP);
	initialize(&mock, true); mock.config[0x100 / 4] = 0x14110001; rejected(&mock, -EINVAL);
	initialize(&mock, true); mock.config[0x70 / 4] &= ~0xf0000U; rejected(&mock, -EINVAL);
	initialize(&mock, true); mock.config[0x40 / 4] = 0x00005009;
	assert(n71_control_capture(&io, true, &out) == 0 && out.count == 13); /* No vendor/VPD data. */
	initialize(&mock, true); mock.config[0x50 / 4] = 0x00867011;
	assert(n71_control_capture(&io, true, &out) == 0 && out.words[1].capability == 0x11);
	initialize(&mock, true); mock.config[1] = 0;
	assert(n71_control_capture(&io, true, &out) == 0 && out.count == 0 && out.capabilities == 0);
	initialize(&mock, true); mock.config[0x100 / 4] = 0xffffffff;
	assert(n71_control_capture(&io, true, &out) == 0 && out.count == 8);
	initialize(&mock, true);
	for (index = 0; index < 16; index++)
		mock.config[(0x40 + 8 * index) / 4] = ((index == 15 ? 0 : 0x48 + 8 * index) << 8) | 9;
	assert(n71_control_capture(&io, true, &out) == 0 && out.capabilities == 16 && out.count == 0);
	mock.config[0xb8 / 4] = 0xc009; mock.config[0xc0 / 4] = 9;
	rejected(&mock, -E2BIG);
	initialize(&mock, true);
	for (index = 0; index < 7; index++)
		mock.config[(0x40 + 4 * index) / 4] = 0x00420010 | ((index == 6 ? 0 : 0x44 + 4 * index) << 8);
	rejected(&mock, -E2BIG); /* Arbitrary capability data cannot overflow the control budget. */
	assert(n71_control_capture(NULL, true, &out) == -EINVAL);
	assert(n71_control_capture(&io, true, NULL) == -EINVAL);
	puts("N71_CONTROL_REFERENCE_OK");
	return 0;
}
