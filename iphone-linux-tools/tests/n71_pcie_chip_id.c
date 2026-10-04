/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-chip-id.h"

struct mock {
	u32 config[2][1024], chip;
	unsigned int reads, writes, fail_read, fail_write, bad_readback, chip_reads;
	int chip_error;
};

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct mock *mock = context;
	u32 raw = mock->config[root ? 0 : 1][where / 4];
	if (++mock->reads == mock->fail_read)
		return -EIO;
	*value = size == 4 ? raw : (raw >> ((where & 3) * 8)) & 0xffff;
	if (mock->reads == mock->bad_readback)
		*value ^= 1;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct mock *mock = context;
	u32 *target = &mock->config[root ? 0 : 1][where / 4];
	assert(where == 4 || (root && (where == 0x20 || where == 0x3e)) ||
	       (!root && where == 0x80) ||
	       (where >= 0x10 && where <= (root ? 0x14U : 0x24U)) ||
	       where == (root ? 0x38U : 0x30U));
	if (++mock->writes == mock->fail_write)
		return -EIO;
	if (where == 4)
		assert(size == 2 && !(value & 5)); /* No DMA or I/O decode. */
	else
		assert(!(mock->config[root ? 0 : 1][1] & 7));
	if (size == 4)
		*target = value;
	else {
		unsigned int shift = (where & 3) * 8;
		*target = (*target & ~(0xffffU << shift)) | (value << shift);
	}
	return 0;
}

static int read_chip(void *context, u32 *value)
{
	struct mock *mock = context;
	assert((mock->config[0][1] & 7) == 2 && (mock->config[1][1] & 7) == 2);
	assert(mock->config[1][4] == 0xc0000004 && mock->config[1][5] == 0);
	assert(mock->config[0][8] == 0xc000c000 && mock->config[1][0x80 / 4] == 0x18000000);
	mock->chip_reads++;
	*value = mock->chip;
	return mock->chip_error;
}

static void initialize(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->config[0][0] = 0x1004106b;
	mock->config[1][0] = 0x43a314e4;
	mock->config[0][1] = mock->config[1][1] = 0xa9000100;
	mock->config[0][2] = 0x06040001;
	mock->config[1][2] = 0x02800008;
	mock->config[0][3] = 0x10000;
	mock->config[0][6] = 0x010100;
	mock->config[0][8] = 0x12301230;
	mock->config[1][4] = 4;
	mock->config[1][6] = 4;
	mock->config[1][0x80 / 4] = 0x18002000;
	mock->chip = 0x13324350;
}

int main(void)
{
	struct mock mock, before;
	struct n71_chip_io io = {{&mock, read_config, write_config}, read_chip};
	struct n71_bar_sizes measured = {.masks = {0xffff8004, 0xffffffff}, .bytes = {0x8000}};
	struct n71_scan_config config;
	struct n71_chip_identity result, sentinel;
	unsigned int reads, writes, index;
	int restore;

	initialize(&mock); before = mock;
	assert(n71_chip_collect(&io, &measured, &config, &result, &restore) == 0 && !restore);
	assert(result.raw == 0x13324350 && result.chip == 0x4350 && result.revision == 2);
	assert(mock.chip_reads == 1 && memcmp(mock.config, before.config, sizeof(mock.config)) == 0);
	reads = mock.reads; writes = mock.writes;
	memset(&sentinel, 0xa5, sizeof(sentinel));
	for (index = 1; index <= reads; index++) {
		initialize(&mock); before = mock; result = sentinel; mock.fail_read = index;
		assert(n71_chip_collect(&io, &measured, &config, &result, &restore) != 0);
		assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
		if (!restore)
			assert(memcmp(mock.config, before.config, sizeof(mock.config)) == 0);
	}
	for (index = 1; index <= writes; index++) {
		initialize(&mock); before = mock; result = sentinel; mock.fail_write = index;
		assert(n71_chip_collect(&io, &measured, &config, &result, &restore) != 0);
		assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
		if (!restore)
			assert(memcmp(mock.config, before.config, sizeof(mock.config)) == 0);
	}
	initialize(&mock); mock.chip = 0xffffffff;
	assert(n71_chip_collect(&io, &measured, &config, &result, &restore) == -ENODEV && !restore);
	initialize(&mock); mock.chip_error = 1;
	assert(n71_chip_collect(&io, &measured, &config, &result, &restore) == -EIO && !restore);
	initialize(&mock); mock.config[1][1] |= 4;
	assert(n71_chip_collect(&io, &measured, &config, &result, &restore) == -EACCES && !mock.writes);
	initialize(&mock); measured.bytes[0] = 0x4000;
	assert(n71_chip_collect(&io, &measured, &config, &result, &restore) == -EACCES && !mock.chip_reads);
	measured.bytes[0] = 0x8000;
	initialize(&mock); mock.bad_readback = 26;
	assert(n71_chip_collect(&io, &measured, &config, &result, &restore) != 0 && !mock.chip_reads);
	puts("N71_PCIE_CHIP_ID_OK");
	return 0;
}
