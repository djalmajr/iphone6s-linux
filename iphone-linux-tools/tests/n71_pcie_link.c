/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-link.h"

struct mock {
	u32 root[0x1000 / 4], port[0x4000 / 4];
	u32 endpoint, command, values[16], offsets[16];
	bool roots[16], reset, never_ready;
	unsigned int calls, fail_at, writes, polls, resets, delays;
};

static int call(struct mock *mock)
{
	return ++mock->calls == mock->fail_at ? -EACCES : 0;
}

static int read32(void *context, bool root, u32 offset, u32 *value)
{
	struct mock *mock = context;
	int error = call(mock);
	if (error)
		return error;
	if (!root && offset == 0x88) {
		mock->polls++;
		*value = mock->never_ready || mock->polls < 3 ? 0 : 1;
	} else {
		*value = root ? mock->root[offset / 4] : mock->port[offset / 4];
	}
	return 0;
}

static int write32(void *context, bool root, u32 offset, u32 value)
{
	struct mock *mock = context;
	int error = call(mock);
	if (error)
		return error;
	assert(mock->writes < 16 && !mock->reset);
	assert(!(root && offset == 4));
	mock->roots[mock->writes] = root;
	mock->offsets[mock->writes] = offset;
	mock->values[mock->writes++] = value;
	if (root)
		mock->root[offset / 4] = value;
	else
		mock->port[offset / 4] = value;
	return 0;
}

static int reset(void *context, bool asserted)
{
	struct mock *mock = context;
	int error = call(mock);
	if (error)
		return error;
	mock->reset = asserted;
	mock->resets++;
	return 0;
}

static void delay(void *context, unsigned int microseconds)
{
	struct mock *mock = context;
	assert(!mock->reset);
	assert(microseconds == (mock->delays ? 100 : 100000));
	mock->delays++;
}

static int endpoint(void *context, u32 offset, u32 *value)
{
	struct mock *mock = context;
	int error = call(mock);
	assert(!mock->reset && mock->polls >= 3 && !mock->never_ready);
	assert(offset == 0 || offset == 4);
	if (!error)
		*value = offset ? mock->command : mock->endpoint;
	return error;
}

static void initialize(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->reset = true;
	mock->root[4 / 4] = 1U << 20;
	mock->root[0x34 / 4] = 0x70;
	mock->root[0x70 / 4] = 0x10;
	mock->root[0xa0 / 4] = 0xabc00002;
	mock->root[0x98 / 4] = 0x12340000;
	mock->root[0x18 / 4] = 0x7e030200;
	mock->port[0x90 / 4] = 0xa5000000;
	mock->port[0x140 / 4] = 0x50500000;
	mock->endpoint = 0x123414e4; /* Synthetic identity, not a measured chipset. */
}

int main(void)
{
	struct mock mock;
	struct n71_pcie_link_io io = {&mock, read32, write32, reset, delay, endpoint};
	const struct n71_pcie_tunable root[] = {{0x98, 0xff, 0x125}};
	const struct n71_pcie_tunable port[] = {{0x90, 0xff, 0x125}};
	const u32 offsets[] = {0xa0, 0x98, 0x90, 0x18, 0x104, 0x140, 0x124, 0x128, 0x80};
	const u32 values[] = {0xabc00001, 0x12340025, 0xa5000025, 0x7e010100, 0, 0xd0500000, 0x31, 0x80008, 1};
	u32 identity = 0, sentinel = 0xdeadcafe;
	unsigned int index, calls;
	struct n71_pcie_tunable forbidden = {4, 4, 4};

	initialize(&mock);
	assert(n71_pcie_enumerate_wlan(&io, root, 1, port, 1, &identity) == 0);
	assert(identity == 0x123414e4 && mock.writes == 9 && mock.polls == 3 && mock.delays == 3);
	for (index = 0; index < 9; index++) {
		assert(mock.offsets[index] == offsets[index] && mock.values[index] == values[index]);
		assert(mock.roots[index] == (index == 0 || index == 1 || index == 3));
	}
	calls = mock.calls;
	for (index = 1; index <= calls; index++) {
		initialize(&mock);
		mock.fail_at = index;
		identity = sentinel;
		assert(n71_pcie_enumerate_wlan(&io, root, 1, port, 1, &identity) == -EACCES);
		assert(identity == sentinel && mock.reset);
		assert(mock.calls == index + (index >= 4 ? 1 : 0));
	}
	initialize(&mock);
	mock.never_ready = true;
	assert(n71_pcie_enumerate_wlan(&io, root, 1, port, 1, &identity) == -ETIMEDOUT);
	assert(mock.polls == 10000 && mock.reset && mock.resets == 2);
	for (index = 0; index < 3; index++) {
		initialize(&mock);
		mock.endpoint = index == 0 ? 0xffffffff : index == 1 ? 0x12340000 : 0x123414e4;
		mock.command = index == 2 ? 4 : 0;
		identity = sentinel;
		assert(n71_pcie_enumerate_wlan(&io, root, 1, port, 1, &identity) < 0);
		assert(identity == sentinel && mock.reset);
	}
	initialize(&mock);
	mock.root[0x70 / 4] = 0x7001; /* Capability cycle, no reset release. */
	assert(n71_pcie_enumerate_wlan(&io, root, 1, port, 1, &identity) == -EINVAL);
	assert(mock.reset && mock.resets == 0 && mock.writes == 0);
	initialize(&mock);
	assert(n71_pcie_enumerate_wlan(&io, &forbidden, 1, port, 1, &identity) == -EINVAL);
	assert(mock.calls == 0 && mock.reset);
	forbidden = (struct n71_pcie_tunable){0xa0, 0xf, 2};
	assert(n71_pcie_enumerate_wlan(&io, &forbidden, 1, port, 1, &identity) == -EINVAL);
	assert(mock.reset && mock.writes == 0);
	puts("N71_PCIE_LINK_SEQUENCE_OK");
	return 0;
}
