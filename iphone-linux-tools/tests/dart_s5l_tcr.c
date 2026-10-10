/* SPDX-License-Identifier: GPL-2.0-only */
/* Compile the actual patch hunk with simulated MMIO, not a replacement writer. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define DART_S5L8960X_TCR_BITS_PER_STREAM 8
struct apple_dart_hw { unsigned int tcr; };
struct apple_dart { unsigned char *regs; const struct apple_dart_hw *hw; };
static bool warn_on(bool condition) { return condition; }
#define WARN_ON(condition) warn_on(condition)
static u32 readl(const void *address) { u32 value; memcpy(&value, address, 4); return value; }
static void writel(u32 value, void *address) { memcpy(address, &value, 4); }
#include "dart-write-under-test.h"

int main(void)
{
	u32 memory[4] = {0};
	const struct apple_dart_hw hw = {.tcr = 12};
	struct apple_dart dart = {(unsigned char *)memory, &hw};
	const u32 patterns[] = {0, UINT32_MAX, 0x01020304, 0xa5f00f5a, 0x80ff8000};
	unsigned int i, sid, value, shift;
	u32 expected, original;
	for (i = 0; i < sizeof(patterns) / sizeof(patterns[0]); i++) {
		for (sid = 0; sid < 4; sid++) {
			shift = sid * 8;
			for (value = 0; value <= 0xff; value++) {
				memory[3] = patterns[i];
				expected = (patterns[i] & ~(0xffU << shift)) | ((u32)value << shift);
				apple_dart_s5l8960x_write_tcr(&dart, sid, value);
				/* Original source, wrong mask or missing shift loses other streams. */
				assert(memory[3] == expected);
			}
		}
	}
	original = memory[3] = 0x01020304;
	apple_dart_s5l8960x_write_tcr(&dart, 4, 0);
	assert(memory[3] == original);
	apple_dart_s5l8960x_write_tcr(&dart, 32, 0);
	assert(memory[3] == original);
	apple_dart_s5l8960x_write_tcr(&dart, 1, 0x100);
	assert(memory[3] == original);
	puts("DART_S5L_STREAM_PRESERVATION_OK");
	return 0;
}
