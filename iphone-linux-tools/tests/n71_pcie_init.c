/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-init.h"

struct mock {
	u32 registers[2][0x8000 / 4];
	unsigned int calls, fail_at, writes, polls, delays;
	u32 written_offset[8], written_value[8];
	enum n71_pcie_region written_region[8];
	bool never_ready, invalid_status;
};

static int read32(void *context, enum n71_pcie_region region, u32 offset, u32 *out)
{
	struct mock *mock = context;
	if (++mock->calls == mock->fail_at)
		return -EACCES;
	if (region == N71_PCIE_COMMON && offset == 0x2c) {
		mock->polls++;
		*out = mock->invalid_status ? 0xffffffff :
			(!mock->never_ready && mock->polls > 2 ? 1 : 0);
	} else {
		*out = mock->registers[region][offset / 4];
	}
	return 0;
}

static int write32(void *context, enum n71_pcie_region region, u32 offset, u32 value)
{
	struct mock *mock = context;
	if (++mock->calls == mock->fail_at)
		return -EACCES;
	assert(mock->writes < 8);
	mock->written_offset[mock->writes] = offset;
	mock->written_value[mock->writes] = value;
	mock->written_region[mock->writes++] = region;
	mock->registers[region][offset / 4] = value;
	return 0;
}

static void delay(void *context, unsigned int microseconds)
{
	struct mock *mock = context;
	assert(microseconds == 10);
	mock->delays++;
}

int main(void)
{
	const struct n71_pcie_tunable phy[] = {{0x100, 0xff, 0x123}, {0x100, 0xf0, 0x50}};
	const struct n71_pcie_tunable common[] = {{0x18, 0xff, 0x42}, {0x18, 0xff, 0x42}};
	struct n71_pcie_global_config config = {1, phy, 2, common, 2};
	struct mock mock;
	struct n71_pcie_io io = {&mock, read32, write32, delay};
	unsigned int calls, failure;
	struct n71_pcie_tunable invalid = {0x8000, 1, 1};

	memset(&mock, 0, sizeof(mock));
	mock.registers[N71_PCIE_PHY][0x100 / 4] = 0xa5a50000;
	mock.registers[N71_PCIE_COMMON][0x18 / 4] = 0x5a5a0000;
	assert(n71_pcie_initialize_global(&io, &config) == 0);
	assert(mock.writes == 5 && mock.polls == 3 && mock.delays == 2);
	assert(mock.written_region[0] == N71_PCIE_COMMON && mock.written_offset[0] == 4 && mock.written_value[0] == 0x11);
	assert(mock.written_offset[1] == 0x38 && mock.written_value[1] == 1);
	assert(mock.written_region[2] == N71_PCIE_PHY && mock.written_value[2] == 0xa5a50023);
	assert(mock.written_value[3] == 0xa5a50053); /* Repeated offset must retain order. */
	assert(mock.written_region[4] == N71_PCIE_COMMON && mock.written_value[4] == 0x5a5a0042);
	calls = mock.calls;
	for (failure = 1; failure <= calls; failure++) {
		memset(&mock, 0, sizeof(mock));
		mock.fail_at = failure;
		assert(n71_pcie_initialize_global(&io, &config) == -EACCES);
		assert(mock.calls == failure);
	}
	memset(&mock, 0, sizeof(mock));
	mock.never_ready = true;
	assert(n71_pcie_initialize_global(&io, &config) == -ETIMEDOUT);
	assert(mock.polls == 10000 && mock.delays == 9999 && mock.writes == 1);
	memset(&mock, 0, sizeof(mock));
	mock.invalid_status = true;
	assert(n71_pcie_initialize_global(&io, &config) == -EIO);
	assert(mock.polls == 1 && mock.writes == 1);
	memset(&mock, 0, sizeof(mock));
	config.common = &invalid;
	config.common_count = 1;
	assert(n71_pcie_initialize_global(&io, &config) == -EINVAL);
	assert(mock.calls == 0); /* Invalid later table must fail before global write. */
	config.common = common;
	config.lane_config = 3;
	assert(n71_pcie_initialize_global(&io, &config) == -EINVAL && mock.calls == 0);
	assert(!n71_pcie_table_valid(phy, 0, 0x4000));
	assert(!n71_pcie_table_valid(phy, 513, 0x4000));
	assert(n71_pcie_initialize_global(NULL, &config) == -EINVAL);
	assert(n71_pcie_apply_table(&io, N71_PCIE_PHY, &invalid, 1) == -EINVAL);
	assert(n71_pcie_apply_table(&io, (enum n71_pcie_region)2, phy, 2) == -EINVAL);
	assert(n71_pcie_apply_table(NULL, N71_PCIE_PHY, phy, 2) == -EINVAL);
	assert(mock.calls == 0);
	puts("N71_PCIE_GLOBAL_INIT_OK");
	return 0;
}
