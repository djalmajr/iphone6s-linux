/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71-wlan-msi-message.h"

static const struct n71_wlan_msi_request qualified = {
	.irq = {.aic_cells = 3, .root_vector_count = 32, .root_vector_offset = 256,
		.port_index = 1, .port_vector_base = 8, .port_vector_count = 8},
	.address_lo = 0xbffff000U,
};
static unsigned int cases;

static void refused(const struct n71_wlan_msi_request *request, int expected)
{
	struct n71_wlan_msi_reference output, saved;
	memset(&saved, 0xa5, sizeof(saved)); output = saved;
	assert(n71_wlan_msi_message(request, &output) == expected);
	assert(memcmp(&output, &saved, sizeof(output)) == 0);
	cases++;
}

int main(void)
{
	const unsigned int vectors[] = {8, 9, 10, 11, 12, 13, 14, 15};
	const unsigned int invalid[] = {0, 1, 256, UINT_MAX};
	struct n71_wlan_msi_request request;
	struct n71_wlan_msi_reference output;
	unsigned int index, field, value;
#ifdef __linux__
	/* Expected SIGABRT mutations must not invoke a piped machine crash handler. */
	assert(prctl(PR_SET_DUMPABLE, 0UL, 0UL, 0UL, 0UL) == 0);
#endif
	/* Mutations: AIC number as message data, shift, swapped address or missing output. */
	for (index = 0; index < 8; index++) {
		request = qualified; request.irq.index = index;
		output = (struct n71_wlan_msi_reference){0};
		assert(n71_wlan_msi_message(&request, &output) == 0);
		assert(output.message[0] == 0xbffff000U && output.message[1] == 0);
		assert(output.message[2] == vectors[index]);
		assert(output.irq.logical_vector == vectors[index]);
		assert(output.irq.aic_irq_number == 256 + vectors[index]);
		assert(output.irq.fwspec[0] == 0 && output.irq.fwspec[1] == 256 + vectors[index] &&
		       output.irq.fwspec[2] == 1);
		cases++;
	}
	/* Mutations: accept a different address/high word/vectorBase or overwrite on error. */
	for (field = 0; field < 3; field++) {
		for (value = 0; value < sizeof(invalid) / sizeof(invalid[0]); value++) {
			unsigned int *target;
			request = qualified;
			target = field == 0 ? &request.address_lo :
				field == 1 ? &request.address_hi : &request.vector_base;
			if (*target == invalid[value]) continue;
			*target = invalid[value]; refused(&request, -EINVAL);
		}
	}
	/* Mutation: ignore a failed parent reference and fabricate an MSI message. */
	for (field = 0; field < 6; field++) {
		request = qualified;
		switch (field) {
		case 0: request.irq.aic_cells = 2; break;
		case 1: request.irq.root_vector_count = 31; break;
		case 2: request.irq.root_vector_offset = 255; break;
		case 3: request.irq.port_index = 0; break;
		case 4: request.irq.port_vector_base = 7; break;
		default: request.irq.port_vector_count = 7; break;
		}
		refused(&request, -EINVAL);
	}
	request = qualified; request.irq.index = 8; refused(&request, -ERANGE);
	request.irq.index = 9; refused(&request, -ERANGE);
	request.irq.index = UINT_MAX; refused(&request, -ERANGE);
	refused(NULL, -EINVAL);
	assert(n71_wlan_msi_message(&qualified, NULL) == -EINVAL); cases++;
	request = qualified; request.address_hi = 1; request.irq.index = UINT_MAX;
	refused(&request, -EINVAL);
	assert(cases == 30);
	puts("N71_WLAN_MSI_MESSAGE_OK cases=30; no IRQ allocation or MMIO");
	return 0;
}
