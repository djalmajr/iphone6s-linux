/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-scan-config.h"

struct mock {
	u32 config[2][1024];
	unsigned int reads, writes, fail_read, fail_write, bad_readback;
	u32 fail_read_where, failed_write_where;
	bool failed_write_root;
};

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct mock *mock = context;
	u32 mask = size == 4 ? 0xffffffff : (1U << (size * 8)) - 1;
	assert(where < 4096 && where % size == 0);
	if (++mock->reads == mock->fail_read || (root && where && where == mock->fail_read_where))
		return -EIO;
	*value = (mock->config[root ? 0 : 1][where / 4] >> ((where & 3) * 8)) & mask;
	if (mock->reads == mock->bad_readback)
		*value ^= 1;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct mock *mock = context;
	u32 *target = &mock->config[root ? 0 : 1][where / 4];
	u32 mask = size == 4 ? 0xffffffff : (1U << (size * 8)) - 1;
	unsigned int shift = (where & 3) * 8;
	assert(where < 4096 && where % size == 0);
	if (++mock->writes == mock->fail_write) {
		mock->failed_write_where = where;
		mock->failed_write_root = root;
		return -EIO;
	}
	if (where == 4)
		assert(size == 2 && !(value & 4)); /* No STATUS RMW or DMA. */
	else if (where >= 0x10 && where <= (root ? 0x14U : 0x24U))
		assert(!(mock->config[root ? 0 : 1][1] & 7));
	if (root && (where == 0x1c || where == 0x24 || where == 0x28)) {
		assert(size == (where == 0x1c ? 2U : 4U));
		assert(!(mock->config[0][1] & 7));
	}
	*target = (*target & ~(mask << shift)) | ((value & mask) << shift);
	return 0;
}

static void initialize(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->config[0][0] = 0x1004106b;
	mock->config[1][0] = 0x43a314e4;
	mock->config[0][1] = mock->config[1][1] = 0xa9000103;
	mock->config[0][2] = 0x06040001;
	mock->config[1][2] = 0x02800002;
	mock->config[0][3] = 0x00010000;
	mock->config[0][6] = 0x44010100;
	mock->config[0][0x3c / 4] = 0x00200100;
	mock->config[1][4] = 0xc0000004;
	mock->config[1][6] = 0xc0010000;
}

static int request(const struct n71_scan_io *io, struct n71_scan_config *config,
		   bool root, u32 where, unsigned int size, u32 value)
{
	struct n71_scan_request request = {root, where, value, size};
	return n71_scan_write(io, config, &request);
}

static void capture_rejected(struct mock *mock, int expected)
{
	struct n71_scan_io io = {mock, read_config, write_config};
	struct n71_scan_config config, sentinel;
	memset(&config, 0xa5, sizeof(config));
	memcpy(&sentinel, &config, sizeof(config));
	assert(n71_scan_capture(&io, &config) == expected);
	assert(memcmp(&config, &sentinel, sizeof(config)) == 0 && mock->writes == 0);
}

static void check_intx(void)
{
	static const u32 commands[] = {0, 0x400, 0x103, 0x503};
	struct mock mock, original;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_scan_config config;
	unsigned int function, index, bit;

	/* Mutation captured: refusing INTx probing blocks the core; widening its mask changes unrelated bits. */
	for (function = 0; function < 2; function++) {
		bool root = function == 0;
		for (index = 0; index < sizeof(commands) / sizeof(*commands); index++) {
			initialize(&mock);
			mock.config[function][1] = 0xa9000000 | commands[index];
			original = mock;
			assert(n71_scan_capture(&io, &config) == 0);
			assert(request(&io, &config, root, 4, 2, commands[index] ^ 0x400) == 0);
			assert(mock.config[function][1] == (0xa9000000 | (commands[index] ^ 0x400)));
			assert(request(&io, &config, root, 4, 2, (commands[index] & ~3U) ^ 0x400) == 0);
			assert(mock.config[function][1] == (0xa9000000 | ((commands[index] & ~3U) ^ 0x400)));
			assert(n71_scan_restore(&io, &config) == 0);
			assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
			for (bit = 8; bit <= 11; bit += 3) {
				mock = original;
				assert(n71_scan_capture(&io, &config) == 0);
				assert(request(&io, &config, root, 4, 2, commands[index] ^ (1U << bit)) < 0);
				assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
			}
		}
	}
	initialize(&mock); mock.config[1][1] = 0xa9000000;
	assert(n71_scan_capture(&io, &config) == 0);
	assert(request(&io, &config, false, 4, 2, 0x402) == -EPERM);
	assert(mock.config[1][1] == 0xa9000000); /* No new memory decode. */
}

static void check_bridge_windows(void)
{
	static const u32 offsets[] = {0x1c, 0x24, 0x28};
	static const u32 probes[] = {0xe0f0, 0xffe0fff0, 0xffffffff};
	struct mock mock, original;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_scan_config config;
	unsigned int index;

	initialize(&mock);
	mock.config[0][0x1c / 4] = 0xa9000021; /* Secondary STATUS must survive. */
	mock.config[0][0x24 / 4] = 0x11223344;
	mock.config[0][0x28 / 4] = 0x55667788;
	original = mock;
	assert(n71_scan_capture(&io, &config) == 0);
	assert(request(&io, &config, true, 4, 2, 0x100) == 0);
	for (index = 0; index < 3; index++) {
		assert(request(&io, &config, true, offsets[index], index ? 4 : 2, probes[index]) == 0);
		assert(mock.config[0][offsets[index] / 4] == (index ? probes[index] : (0xa9000000 | probes[index])));
	}
	assert(n71_scan_restore(&io, &config) == 0);
	assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
	for (index = 0; index < 3; index++) {
		mock = original;
		assert(n71_scan_capture(&io, &config) == 0);
		assert(request(&io, &config, true, offsets[index], index ? 4 : 2, probes[index]) == -EACCES);
		assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
		mock = original;
		assert(n71_scan_capture(&io, &config) == 0);
		assert(request(&io, &config, true, 4, 2, 0x100) == 0);
		assert(request(&io, &config, true, offsets[index], index ? 4 : 2, probes[index] ^ 0x10) == -EPERM);
		assert(n71_scan_restore(&io, &config) == 0);
		assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
		mock = original;
		assert(n71_scan_capture(&io, &config) == 0);
		mock.fail_read_where = offsets[index];
		assert(n71_scan_restore(&io, &config) == -EIO);
		assert(!(mock.config[0][1] & 3)); /* A failed window readback keeps decode off. */
	}
}

int main(void)
{
	struct mock mock, original;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_scan_config config;
	unsigned int total, index, writes;
	const struct n71_scan_request bad[] = {
		{false, 4, 0x107, 2}, {false, 4, 0, 4}, {false, 5, 0, 2},
		{false, 0x10, 0xc1000000, 4}, {false, 0x30, 0xfffff801, 4},
		{true, 0x18, 0x020200, 4}, {true, 0x3e, 0x60, 2},
		{false, 0x80, 1, 4}, {false, 0x1000, 0, 4},
		{false, 0x80, 0x100, 1}, {false, 0x6, 0xffff, 2},
	};
	check_intx();
	check_bridge_windows();

	initialize(&mock);
	assert(n71_scan_capture(&io, &config) == 0 && config.active);
	assert(config.saved[0].identity == 0x1004106b && config.saved[1].identity == 0x43a314e4);
	total = mock.reads;
	for (index = 1; index <= total; index++) {
		initialize(&mock); mock.fail_read = index; capture_rejected(&mock, -EIO);
	}
	initialize(&mock); mock.config[0][0] ^= 1; capture_rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[1][0] ^= 1; capture_rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[0][1] |= 4; capture_rejected(&mock, -EACCES);
	initialize(&mock); mock.config[1][1] |= 4; capture_rejected(&mock, -EACCES);
	initialize(&mock); mock.config[1][2] = 0x02000001; capture_rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[1][3] = 0x00010000; capture_rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[0][6] ^= 0x10000; capture_rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[0][0x3c / 4] |= 0x400000; capture_rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[1][0x30 / 4] = 1; capture_rejected(&mock, -EACCES);
	for (index = 0; index < sizeof(bad) / sizeof(*bad); index++) {
		initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
		assert(n71_scan_write(&io, &config, &bad[index]) < 0);
		assert(mock.writes == 0 && config.refusals == 1 && config.error < 0);
		assert(request(&io, &config, false, 4, 2, 0x100) < 0 && mock.writes == 0);
	}
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.config[1][1] |= 4;
	assert(request(&io, &config, false, 4, 2, 0x107) == -EACCES && mock.writes == 0);
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	assert(request(&io, &config, false, 0x10, 4, 0xffffffff) == -EACCES);
	assert(mock.writes == 0); /* Sizing requires confirmed decode-off. */
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.config[0][0x1c / 4] = 0x02000000;
	assert(request(&io, &config, true, 0x1e, 2, 0xffff) == 0 && mock.writes == 0);
	mock.config[0][0x1c / 4] |= 0x08000000;
	assert(request(&io, &config, true, 0x1e, 2, 0xffff) == -EPERM && mock.writes == 0);
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	for (index = 0; index < N71_SCAN_MAX_WRITES; index++)
		assert(request(&io, &config, false, 0x80, 4, 0) == 0);
	assert(request(&io, &config, false, 0x80, 4, 0) == -E2BIG && mock.writes == 0);

	initialize(&mock); memcpy(&original, &mock, sizeof(mock));
	assert(n71_scan_capture(&io, &config) == 0);
	for (index = 0; index < 2; index++) {
		bool root = index == 0;
		unsigned int bar;
		assert(request(&io, &config, root, 4, 2, 0x100) == 0);
		for (bar = 0; bar < (root ? 2U : 6U); bar++) {
			assert(request(&io, &config, root, 0x10 + bar * 4, 4, 0xffffffff) == 0);
			assert(request(&io, &config, root, 0x10 + bar * 4, 4,
				       config.saved[index].bars[bar]) == 0);
		}
		assert(request(&io, &config, root, root ? 0x38 : 0x30, 4, 0xfffff800) == 0);
		assert(request(&io, &config, root, 4, 2, 0x103) == 0);
	}
	assert(request(&io, &config, true, 0x3e, 2, 0) == 0);
	config.error = -EPERM;
	assert(n71_scan_restore(&io, &config) == 0 && !config.active);
	assert(memcmp(mock.config, original.config, sizeof(mock.config)) == 0);
	assert(request(&io, &config, false, 4, 2, 0x100) == -EPERM);

	/* Exercise every raw restoration write failure; never reenable bad BARs. */
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.reads = mock.writes = 0;
	assert(n71_scan_restore(&io, &config) == 0);
	writes = mock.writes;
	for (index = 1; index <= writes; index++) {
		initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
		mock.reads = mock.writes = 0; mock.fail_write = index;
		mock.config[0][4] = mock.config[1][4] = 0xffffffff;
		assert(n71_scan_restore(&io, &config) == -EIO && !config.active);
		if (mock.failed_write_where != 4)
			assert((mock.config[mock.failed_write_root ? 0 : 1][1] & 3) == 0);
	}
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.reads = mock.writes = 0; mock.bad_readback = 2;
	assert(n71_scan_restore(&io, &config) == -EIO && mock.writes == 10);
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.config[1][0] ^= 1; mock.writes = 0;
	assert(n71_scan_restore(&io, &config) == -ENODEV && mock.writes == 9);
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.fail_write = 1;
	assert(request(&io, &config, false, 4, 2, 0x100) == -EIO && config.error == -EIO);
	initialize(&mock); assert(n71_scan_capture(&io, &config) == 0);
	mock.fail_read = mock.reads + 1;
	assert(request(&io, &config, false, 4, 2, 0x100) == -EIO && mock.writes == 0);
	assert(n71_scan_capture(NULL, &config) == -EINVAL);
	assert(n71_scan_restore(&io, NULL) == -EINVAL);
	puts("N71_PCIE_SCAN_CONFIG_OK");
	return 0;
}
