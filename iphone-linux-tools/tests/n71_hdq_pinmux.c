/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "n71-hdq-pinmux.h"

int main(void)
{
	struct n71_hdq_pinmux_plan plan = {0xdead, 0xbeef, 0xcafe};
	unsigned int variant, lower, upper;
	struct n71_hdq_pinmux_request request = {0x102, 0, 2};
	const struct n71_hdq_pinmux_request invalid[] = {
		{0x102, 0, 1}, {0x102, 0, 173}, {0x202, 0, 2},
		{0x1000102, 0, 2}, {0x102, 2, 2}, {0x102, ~0U, 2},
	};
	const unsigned int words[] = {0, 0xffffffffU, 0xa5a5a5a5U, 0x5a5a5a5aU};

	/* Kills wrong pin, packet, mux branch, offset, mask and input mutations. */
	for (variant = 0; variant < 2; variant++) {
		request.glitchless = variant;
		assert(n71_hdq_pinmux(&request, &plan));
		assert(plan.offset == 8 && plan.mask == 0x270);
		assert(plan.value == (variant ? 0x210U : 0x220U));
		for (upper = 0; upper < sizeof(words) / sizeof(words[0]); upper++) {
			for (lower = 0; lower < 1024; lower++) {
				unsigned int old = (words[upper] & ~0x3ffU) | lower;
				unsigned int next = (old & ~plan.mask) | (plan.value & plan.mask);
				assert((next & 0x270) == (variant ? 0x210U : 0x220U));
				assert((next & ~0x270U) == (old & ~0x270U));
			}
		}
	}
	plan.offset = 0xdead; plan.mask = 0xbeef; plan.value = 0xcafe;
	for (lower = 0; lower < sizeof(invalid) / sizeof(invalid[0]); lower++)
		assert(!n71_hdq_pinmux(&invalid[lower], &plan));
	assert(!n71_hdq_pinmux(NULL, &plan));
	assert(plan.offset == 0xdead && plan.mask == 0xbeef && plan.value == 0xcafe);
	assert(!n71_hdq_pinmux(&request, NULL));
	puts("N71_HDQ_PINMUX_CONTRACT_OK");
	return 0;
}
