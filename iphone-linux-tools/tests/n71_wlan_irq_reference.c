/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "n71-wlan-irq-reference.h"

static const struct n71_wlan_irq_request qualified = {
	.aic_cells = 3, .root_vector_count = 32, .root_vector_offset = 256,
	.port_index = 1, .port_vector_base = 8, .port_vector_count = 8,
};
static unsigned int cases;

static void refused(const struct n71_wlan_irq_request *request, int expected)
{
	struct n71_wlan_irq_reference output, before;
	memset(&before, 0xa5, sizeof(before));
	output = before;
	assert(n71_wlan_irq_reference(request, &output) == expected);
	assert(memcmp(&output, &before, sizeof(output)) == 0);
	cases++;
}

int main(void)
{
	const unsigned int aic[] = {264, 265, 266, 267, 268, 269, 270, 271};
	const unsigned int logical[] = {8, 9, 10, 11, 12, 13, 14, 15};
	const unsigned int invalid[] = {0, 1, 3, 7, 8, 9, 32, 256, UINT_MAX};
	struct n71_wlan_irq_request request;
	struct n71_wlan_irq_reference output;
	unsigned int index, field, value;

	/* Mutations: shifted vector, omitted AIC offset, FIQ or level trigger. */
	for (index = 0; index < 8; index++) {
		request = qualified;
		request.index = index;
		assert(n71_wlan_irq_reference(&request, &output) == 0);
		assert(output.aic_irq_number == aic[index]);
		assert(output.logical_vector == logical[index]);
		assert(output.fwspec[0] == 0 && output.fwspec[1] == aic[index]);
		assert(output.fwspec[2] == 1);
		cases++;
	}
	/* Mutations: each relaxed topology guard accepts an unqualified board. */
	for (field = 0; field < 6; field++) {
		for (value = 0; value < sizeof(invalid) / sizeof(invalid[0]); value++) {
			unsigned int *target;
			request = qualified;
			switch (field) {
			case 0: target = &request.aic_cells; break;
			case 1: target = &request.root_vector_count; break;
			case 2: target = &request.root_vector_offset; break;
			case 3: target = &request.port_index; break;
			case 4: target = &request.port_vector_base; break;
			default: target = &request.port_vector_count; break;
			}
			if (*target == invalid[value])
				continue;
			*target = invalid[value];
			refused(&request, -EINVAL);
		}
	}
	/* Mutations: >= to > admits the adjacent port; error class is preserved. */
	request = qualified;
	request.index = 8;
	refused(&request, -ERANGE);
	request.index = 9;
	refused(&request, -ERANGE);
	request.index = UINT_MAX;
	refused(&request, -ERANGE);
	refused(NULL, -EINVAL);
	assert(n71_wlan_irq_reference(&qualified, NULL) == -EINVAL);
	cases++;
	assert(cases == 61);
	puts("N71_WLAN_AIC_REFERENCE_OK cases=61; no IRQ allocation");
	return 0;
}
