/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-inventory.h"

struct mock {
	u32 config[64];
	unsigned int calls, fail_at, identity_reads, command_reads;
	bool change_identity, change_command, late_master;
};

static int read32(void *context, u32 offset, u32 *value)
{
	struct mock *mock = context;

	assert(offset % 4 == 0 && offset <= 0xfc);
	assert(++mock->calls <= N71_PCIE_INVENTORY_MAX_READS);
	if (mock->calls == mock->fail_at)
		return -EIO;
	*value = mock->config[offset / 4];
	if (!offset && ++mock->identity_reads == 2 && mock->change_identity)
		*value ^= 1U << 16;
	if (offset == 4 && ++mock->command_reads == 2) {
		if (mock->change_command)
			*value ^= 1;
		if (mock->late_master)
			*value |= 4;
	}
	return 0;
}

static void initialize(struct mock *mock)
{
	unsigned int index;

	memset(mock, 0, sizeof(*mock));
	mock->config[0] = N71_PCIE_WLAN_ID;
	mock->config[1] = 1U << 20;
	mock->config[2] = 0x02800003; /* Synthetic class/revision. */
	mock->config[3] = 0x00800020;
	for (index = 0; index < 6; index++)
		mock->config[4 + index] = 0x10000000 + index * 0x1000;
	mock->config[0x2c / 4] = 0x1234106b;
	mock->config[0x3c / 4] = 0x1ff;
	mock->config[0x34 / 4] = 0x40;
	mock->config[0x40 / 4] = 0x5001;
	mock->config[0x50 / 4] = 0x00806005;
	mock->config[0x60 / 4] = 0x0002a010;
	mock->config[0xa0 / 4] = 0x00070011;
}

static void rejected(struct mock *mock, int expected)
{
	struct n71_pcie_inventory_io io = {mock, read32};
	struct n71_pcie_inventory out, sentinel;

	memset(&out, 0xa5, sizeof(out));
	memcpy(&sentinel, &out, sizeof(out));
	assert(n71_pcie_inventory_collect(&io, &out) == expected);
	assert(memcmp(&out, &sentinel, sizeof(out)) == 0);
}

int main(void)
{
	struct mock mock;
	struct n71_pcie_inventory_io io = {&mock, read32};
	struct n71_pcie_inventory out;
	unsigned int calls, index;
	const u32 bad_pointers[] = {0x3c, 0x41, 0xff};

	initialize(&mock);
	assert(n71_pcie_inventory_collect(&io, &out) == 0);
	assert(out.identity == 0x43a314e4 && out.class_revision == 0x02800003);
	assert(out.header == 0x00800020 && out.subsystem == 0x1234106b);
	assert(out.interrupt == 0x1ff && out.capabilities == 4);
	assert(out.express_offset == 0x60 && out.express_header == 0x0002a010);
	assert(out.msi_offset == 0x50 && out.msi_header == 0x00806005);
	assert(out.msix_offset == 0xa0 && out.msix_header == 0x00070011);
	assert(out.reads == 19 && mock.calls == 19);
	for (index = 0; index < 6; index++)
		assert(out.bars[index] == 0x10000000 + index * 0x1000);
	calls = mock.calls;
	for (index = 1; index <= calls; index++) {
		initialize(&mock);
		mock.fail_at = index;
		rejected(&mock, -EIO);
		assert(mock.calls == index);
	}
	initialize(&mock); mock.config[0] ^= 1U << 16; rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[0] = 0xffffffff; rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[1] |= 4; rejected(&mock, -EACCES);
	assert(mock.calls == 2); /* Refuse DMA before any other config read. */
	initialize(&mock); mock.config[1] = 0xffffffff; rejected(&mock, -EACCES);
	assert(mock.calls == 2);
	initialize(&mock); mock.config[1] = 0; rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[2] = 0xffffffff; rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[3] |= 1U << 16; rejected(&mock, -ENODEV);
	initialize(&mock); mock.change_identity = true; rejected(&mock, -EAGAIN);
	initialize(&mock); mock.change_command = true; rejected(&mock, -EAGAIN);
	initialize(&mock); mock.late_master = true; rejected(&mock, -EACCES);
	for (index = 0; index < sizeof(bad_pointers) / sizeof(*bad_pointers); index++) {
		initialize(&mock); mock.config[0x34 / 4] = bad_pointers[index];
		rejected(&mock, -EINVAL);
	}
	initialize(&mock); mock.config[0xa0 / 4] = 0x6001; rejected(&mock, -EINVAL);
	assert(mock.calls == 17); /* Detect the repeated pointer before re-reading. */
	initialize(&mock); mock.config[0x40 / 4] = 0; rejected(&mock, -EIO);
	initialize(&mock); mock.config[0x40 / 4] = 0xffffffff; rejected(&mock, -EIO);
	initialize(&mock); mock.config[0x60 / 4] = 0x0004a001; rejected(&mock, -ENODEV);
	initialize(&mock); mock.config[0x60 / 4] |= 4U << 20; rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[0xa0 / 4] = 0x0010; rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[0xa0 / 4] = 0x0005; rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[0xa0 / 4] = 0xb011;
	mock.config[0xb0 / 4] = 0x0011; rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[0x60 / 4] = 0xe001;
	mock.config[0xe0 / 4] = 0x0010; rejected(&mock, -EINVAL);
	initialize(&mock); mock.config[0x34 / 4] = 0; rejected(&mock, -ENODEV);
	initialize(&mock);
	for (index = 0x40; index <= 0xfc; index += 4)
		mock.config[index / 4] = ((index == 0xfc ? 0 : index + 4) << 8) |
			(index == 0x40 ? 0x10 : 1);
	assert(n71_pcie_inventory_collect(&io, &out) == 0);
	assert(out.reads == 63 && out.capabilities == 48 && out.express_offset == 0x40);
	initialize(&mock); mock.config[0x60 / 4] = 0x00010010;
	assert(n71_pcie_inventory_collect(&io, &out) == 0);
	assert(out.msi_offset == 0x50 && out.msix_offset == 0 && out.capabilities == 3);
	initialize(&mock); mock.config[4] = 0xffffffff;
	assert(n71_pcie_inventory_collect(&io, &out) == 0);
	assert(out.bars[0] == 0xffffffff); /* Raw value, no sizing/address claim. */
	initialize(&mock);
	assert(n71_pcie_inventory_collect(NULL, &out) == -EINVAL);
	assert(n71_pcie_inventory_collect(&io, NULL) == -EINVAL);
	io.read32 = NULL;
	assert(n71_pcie_inventory_collect(&io, &out) == -EINVAL && mock.calls == 0);
	puts("N71_PCIE_INVENTORY_READONLY_OK");
	return 0;
}
