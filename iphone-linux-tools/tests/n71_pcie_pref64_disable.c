/* SPDX-License-Identifier: GPL-2.0-only */
/* Replay the measured PREF64 values; prove scope, drift and raw errors. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-pref64-disable.h"

struct pref64_backend {
	u32 windows[3];
	unsigned int reads, fail_read;
	int read_error;
};
static unsigned int cases;
static const struct n71_scan_request disable_pref = {true, 0x24, 0x0000fff0, 4};

static int pref64_read(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct pref64_backend *b = context;
	assert(root && size == 4 && where >= 0x24 && where <= 0x2c && where % 4 == 0);
	if (++b->reads == b->fail_read)
		return b->read_error;
	*value = b->windows[(where - 0x24) / 4];
	return 0;
}

static int pref64_write(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	(void)context; (void)root; (void)where; (void)size; (void)value;
	assert(!"Expectation helper must never write hardware");
	return -EIO;
}

static void capture_baseline(void)
{
	const u32 bad_lower[] = {0, 1, 0x10000, 0x20002, 0x10002, 0x20001, 0x10011, 0x110001, 0x1fff1};
	unsigned int index;
	assert(n71_pref64_disable_capture(0x10001, 0, 0) == 0); cases++;
	for (index = 0; index < sizeof(bad_lower) / sizeof(bad_lower[0]); index++) {
		assert(n71_pref64_disable_capture(bad_lower[index], 0, 0) == -EACCES); cases++;
	}
	assert(n71_pref64_disable_capture(0x10001, 1, 0) == -EACCES); cases++;
	assert(n71_pref64_disable_capture(0x10001, 0, 1) == -EACCES); cases++;
}

static void live_values(void)
{
	const u32 values[] = {0x10001, 0x1fff1, 0, 0xfff0, 1, 0x10000, 0x10002, 0x20001, 0x1fff0, 0x1ffe1};
	unsigned int index;
	for (index = 0; index < sizeof(values) / sizeof(values[0]); index++) {
		struct pref64_backend b = {.windows = {values[index], 0, 0}};
		struct n71_scan_io io = {&b, pref64_read, pref64_write};
		u32 expected = 0xdeadbeef;
		int error = n71_pref64_disable_expected(&io, &disable_pref, values[index], &expected);
		assert(error == (index < 2 ? 0 : -EAGAIN));
		assert(expected == (index < 2 ? 0x1fff1U : 0xfff0U));
		assert(b.reads == (index < 2 ? 3U : 0U)); cases++;
	}
}

static void callback_errors_and_drift(void)
{
	unsigned int index, raw;
	for (index = 0; index < 3; index++) {
		for (raw = 0; raw < 2; raw++) {
			struct pref64_backend b = {.windows = {0x10001, 0, 0},
				.fail_read = index + 1, .read_error = raw ? 7 : -ENOLINK};
			struct n71_scan_io io = {&b, pref64_read, pref64_write};
			u32 expected;
			assert(n71_pref64_disable_expected(&io, &disable_pref, 0x10001, &expected)
				== (raw ? -EIO : -ENOLINK));
			assert(b.reads == index + 1 && expected == 0xfff0); cases++;
		}
		{
			struct pref64_backend b = {.windows = {0x10001, 0, 0}};
			struct n71_scan_io io = {&b, pref64_read, pref64_write};
			u32 expected;
			b.windows[index] ^= 1;
			assert(n71_pref64_disable_expected(&io, &disable_pref, 0x10001, &expected) == -EAGAIN);
			assert(b.reads == index + 1 && expected == 0xfff0); cases++;
		}
	}
}

static void request_scope(void)
{
	const struct n71_scan_request requests[] = {
		{false, 0x24, 0xfff0, 4}, {true, 0x20, 0xfff0, 4},
		{true, 0x24, 0xfff0, 2}, {true, 0x24, 0xffe0, 4},
	};
	unsigned int index;
	for (index = 0; index < sizeof(requests) / sizeof(requests[0]); index++) {
		struct pref64_backend b = {.windows = {0x10001, 0, 0}};
		struct n71_scan_io io = {&b, pref64_read, pref64_write};
		u32 expected = 0xdeadbeef;
		assert(n71_pref64_disable_expected(&io, &requests[index], 0x10001, &expected) == 0);
		assert(expected == requests[index].value && !b.reads); cases++;
	}
}

int main(void)
{
	capture_baseline(); live_values(); callback_errors_and_drift(); request_scope();
	printf("N71_PCIE_PREF64_HELPER_OK cases=%u\n", cases);
	return 0;
}
