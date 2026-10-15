/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "n71-sn2400-input-reference.h"

static void check(unsigned int requested, unsigned int code, unsigned int nominal)
{
	struct n71_sn2400_input_request request = {requested, 0};
	struct n71_sn2400_input_setting setting;
	assert(n71_sn2400_input_reference(&request, &setting) == 0);
	assert(setting.register_value == code && setting.encoded_milliamps == nominal);
	assert(setting.suspend == (requested == 0));
}

int main(void)
{
	struct n71_sn2400_input_request request = {500, 0};
	struct n71_sn2400_input_setting result, before;
	unsigned int value, bounded, encoded;

	check(0, 0, 90); check(1, 0, 90); check(89, 0, 90);
	check(90, 0, 90); check(91, 0, 90); check(99, 0, 90);
	check(100, 1, 100); check(109, 1, 100); check(110, 2, 110);
	check(500, 41, 500); check(1999, 190, 1990); check(2000, 191, 2000);
	check(2001, 191, 2000); check(65535, 191, 2000);
	check(UINT_MAX, 191, 2000); check(0x80000000U, 191, 2000);
	/* Oracle follows the pinned instructions' multiply/shift, not C division. */
	for (value = 0; value <= 65535; value++) {
		bounded = value < 90 ? 90 : value > 2000 ? 2000 : value;
		encoded = (((bounded - 90) & 0xffffU) * 0xcccdU >> 19) & 0xffU;
		check(value, encoded, 90 + 10 * encoded);
	}
	memset(&before, 0xa5, sizeof(before));
	result = before;
	assert(n71_sn2400_input_reference(NULL, &result) == -EINVAL);
	assert(memcmp(&result, &before, sizeof(result)) == 0);
	assert(n71_sn2400_input_reference(&request, NULL) == -EINVAL);
	/* No board calibration table is available; all enabled/unknown values refuse. */
	for (value = 1; value <= 3; value++) {
		request.calibration_enabled = value;
		assert(n71_sn2400_input_reference(&request, &result) == -EINVAL);
		assert(memcmp(&result, &before, sizeof(result)) == 0);
	}
	request.calibration_enabled = UINT_MAX;
	assert(n71_sn2400_input_reference(&request, &result) == -EINVAL);
	assert(memcmp(&result, &before, sizeof(result)) == 0);
	puts("N71_SN2400_INPUT_REFERENCE_OK");
	return 0;
}
