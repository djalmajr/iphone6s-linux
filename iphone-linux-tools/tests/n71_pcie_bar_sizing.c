/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-bar-sizing.h"

struct mock {
	u32 config[2][1024], masks[6];
	bool probing[6];
	unsigned int reads, writes, fail_read, fail_write;
};

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct mock *mock = context;
	u32 raw;
	if (++mock->reads == mock->fail_read)
		return -EIO;
	raw = mock->config[root ? 0 : 1][where / 4];
	if (!root && where >= 0x10 && where <= 0x24 && mock->probing[(where - 0x10) / 4])
		raw = mock->masks[(where - 0x10) / 4];
	*value = size == 4 ? raw : (raw >> ((where & 3) * 8)) & 0xffff;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct mock *mock = context;
	u32 *target = &mock->config[root ? 0 : 1][where / 4];
	bool window = root && (where == 0x1c || where == 0x24 || where == 0x28);
	assert(where == 4 || (root && where == 0x3e) ||
	       window ||
	       (where >= 0x10 && where <= (root ? 0x14U : 0x24U)) ||
	       where == (root ? 0x38U : 0x30U));
	if (++mock->writes == mock->fail_write)
		return -EIO;
	if (where == 4)
		assert(size == 2 && !(value & 4));
	else if (window) {
		/* These consumers restore windows; they must never probe or change them. */
		assert(!(mock->config[0][1] & 7));
		assert(size == (where == 0x1c ? 2U : 4U));
		assert(value == (*target & (size == 2 ? 0xffffU : 0xffffffffU)));
	}
	else if (!root && where >= 0x10 && where <= 0x24) {
		assert(!(mock->config[1][1] & 7));
		mock->probing[(where - 0x10) / 4] = value == 0xffffffff;
	}
	if (size == 4)
		*target = value;
	else {
		unsigned int shift = (where & 3) * 8;
		*target = (*target & ~(0xffffU << shift)) | (value << shift);
	}
	return 0;
}

static void initialize(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->config[0][0] = 0x1004106b;
	mock->config[1][0] = 0x43a314e4;
	mock->config[0][1] = mock->config[1][1] = 0xa9000103;
	mock->config[0][2] = 0x06040001;
	mock->config[1][2] = 0x02800008;
	mock->config[0][3] = 0x10000;
	mock->config[0][6] = 0x010100;
	mock->config[0][0x1c / 4] = 0xa900ab12;
	mock->config[0][0x24 / 4] = 0x98706543;
	mock->config[0][0x28 / 4] = 0x22334455;
	mock->config[1][4] = 4;
	mock->config[1][6] = 0xc0010004;
	mock->masks[0] = 0xffff8004;
	mock->masks[1] = 0xffffffff;
	mock->masks[2] = 0xffc00004;
	mock->masks[3] = 0xffffffff;
}

int main(void)
{
	struct mock mock, before;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_scan_config config;
	struct n71_bar_sizes sizes, sentinel;
	unsigned int reads, writes, index;
	int restore;

	initialize(&mock); before = mock;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == 0 && !restore);
	assert(sizes.bytes[0] == 0x8000 && sizes.bytes[1] == 0 &&
	       sizes.bytes[2] == 0x400000 && sizes.bytes[3] == 0 &&
	       sizes.bytes[4] == 0 && sizes.bytes[5] == 0);
	assert(memcmp(mock.config, before.config, sizeof(mock.config)) == 0 && !config.active);
	reads = mock.reads; writes = mock.writes;
	memset(&sentinel, 0xa5, sizeof(sentinel));
	/* Mutation proof: ignore a probe/restore fault or publish before restore. */
	for (index = 1; index <= reads; index++) {
		initialize(&mock); sizes = sentinel; mock.fail_read = index;
		assert(n71_bar_collect(&io, &config, &sizes, &restore) != 0);
		assert(memcmp(&sizes, &sentinel, sizeof(sizes)) == 0);
	}
	for (index = 1; index <= writes; index++) {
		initialize(&mock); sizes = sentinel; mock.fail_write = index;
		assert(n71_bar_collect(&io, &config, &sizes, &restore) != 0);
		assert(memcmp(&sizes, &sentinel, sizeof(sizes)) == 0);
	}
	initialize(&mock); before = mock; sizes = sentinel; mock.masks[0] = 0xffff7004;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == -EINVAL && !restore);
	assert(memcmp(mock.config, before.config, sizeof(mock.config)) == 0);
	assert(memcmp(&sizes, &sentinel, sizeof(sizes)) == 0);
	initialize(&mock); mock.masks[0] &= ~4U;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == -EINVAL && !restore);
	initialize(&mock); mock.config[1][8] = 1;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == -EINVAL && !restore);
	initialize(&mock); mock.config[1][9] = 4;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == -EINVAL && !restore);
	initialize(&mock); mock.masks[1] = 0xfffffffe;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == -EINVAL && !restore);
	initialize(&mock); mock.config[1][4] = 0; mock.masks[0] = 0xffff0000; mock.masks[1] = 0;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == 0 && sizes.bytes[0] == 0x10000);
	initialize(&mock); mock.config[1][1] |= 4;
	assert(n71_bar_collect(&io, &config, &sizes, &restore) == -EACCES && !mock.writes);
	puts("N71_PCIE_BAR_SIZING_OK");
	return 0;
}
