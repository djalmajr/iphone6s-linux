/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-port.h"

struct mock {
	u32 common[0x8000 / 4], pending;
	unsigned int calls, fail_at, writes, delays, polls[2];
	u32 offsets[10], values[10], times[10002];
	bool port_writes[10];
	int timeout_poll;
	bool invalid_status;
};

static int record(struct mock *mock)
{
	return ++mock->calls == mock->fail_at ? -EACCES : 0;
}

static int read_common(void *context, enum n71_pcie_region region, u32 offset, u32 *out)
{
	struct mock *mock = context;
	int error = record(mock);
	assert(region == N71_PCIE_COMMON);
	if (error)
		return error;
	if (offset == 0x2c || offset == 0x1ac) {
		unsigned int index = offset == 0x2c ? 0 : 1;
		mock->polls[index]++;
		*out = mock->invalid_status ? 0xffffffff :
			(mock->timeout_poll == (int)index + 1 || mock->polls[index] < 3 ? 0 : index ? 1 : 16);
	} else {
		*out = mock->common[offset / 4];
	}
	return 0;
}

static int write_value(struct mock *mock, u32 offset, u32 value, bool port)
{
	int error = record(mock);
	if (error)
		return error;
	assert(mock->writes < 10);
	mock->offsets[mock->writes] = offset;
	mock->values[mock->writes] = value;
	mock->port_writes[mock->writes++] = port;
	if (!port)
		mock->common[offset / 4] = value;
	return 0;
}

static int write_common(void *context, enum n71_pcie_region region, u32 offset, u32 value)
{
	assert(region == N71_PCIE_COMMON);
	return write_value(context, offset, value, false);
}

static int read_port(void *context, u32 offset, u32 *out)
{
	struct mock *mock = context;
	int error = record(mock);
	assert(offset == 0x210);
	if (!error)
		*out = mock->pending;
	return error;
}

static int write_port(void *context, u32 offset, u32 value)
{
	assert(offset == 0x210);
	return write_value(context, offset, value, true);
}

static void delay(void *context, unsigned int time)
{
	struct mock *mock = context;
	assert(mock->delays < 10002 && (time == 10 || time == 100));
	mock->times[mock->delays++] = time;
}

static void reset(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->common[0x1a4 / 4] = 0xa5000001;
	mock->common[0x194 / 4] = 0xa5000100;
	mock->common[0x180 / 4] = 0xa5000100;
	mock->pending = 0x12;
}

int main(void)
{
	struct mock mock;
	struct n71_pcie_port_io io = {{&mock, read_common, write_common, delay}, read_port, write_port};
	const u32 offsets[] = {0x1a4, 0x194, 0x180, 0x180, 0x1a4, 0x4060, 0x210, 0x194};
	const u32 values[] = {0xa5000000, 0xa5000101, 0xa5000101, 0xa5000001, 0xa5000001, 3, 0x12, 0xa5000001};
	unsigned int calls, failure, index;

	reset(&mock);
	assert(n71_pcie_prepare_wlan(&io, false, false) == 0);
	assert(mock.writes == 8 && mock.polls[0] == 3 && mock.polls[1] == 3);
	assert(mock.delays == 6 && mock.times[2] == 100 && mock.times[5] == 100);
	for (index = 0; index < 8; index++) {
		assert(mock.offsets[index] == offsets[index] && mock.values[index] == values[index]);
		assert(mock.port_writes[index] == (index == 6));
	}
	calls = mock.calls;
	for (failure = 1; failure <= calls; failure++) {
		reset(&mock);
		mock.fail_at = failure;
		assert(n71_pcie_prepare_wlan(&io, false, false) == -EACCES);
		assert(mock.calls == failure);
	}
	for (index = 1; index <= 2; index++) {
		reset(&mock);
		mock.timeout_poll = (int)index;
		assert(n71_pcie_prepare_wlan(&io, false, false) == -ETIMEDOUT);
		assert(mock.polls[index - 1] == 10000 && mock.writes == (index == 1 ? 2 : 3));
	}
	reset(&mock);
	mock.invalid_status = true;
	assert(n71_pcie_prepare_wlan(&io, false, false) == -EIO && mock.writes == 2);
	reset(&mock);
	mock.pending = 0xffffffff;
	assert(n71_pcie_prepare_wlan(&io, false, false) == -EIO && mock.writes == 6);
	reset(&mock);
	mock.pending = 0;
	assert(n71_pcie_prepare_wlan(&io, false, false) == 0 && mock.writes == 7);
	reset(&mock);
	assert(n71_pcie_prepare_wlan(&io, true, false) == -EINVAL && mock.calls == 0);
	assert(n71_pcie_prepare_wlan(&io, false, true) == -EINVAL && mock.calls == 0);
	assert(n71_pcie_prepare_wlan(NULL, false, false) == -EINVAL);
	io.read_port = NULL;
	assert(n71_pcie_prepare_wlan(&io, false, false) == -EINVAL && mock.calls == 0);
	puts("N71_PCIE_PORT_PREPARE_OK");
	return 0;
}
