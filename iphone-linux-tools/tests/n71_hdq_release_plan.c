/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "n71-hdq-release-plan.h"

static void rejected(const struct n71_hdq_release_input *input)
{
	struct n71_hdq_release_plan plan = { N71_HDQ_RELEASE_ACK, 0xa5 };
	assert(n71_hdq_select_release(input, &plan) == -EINVAL);
	assert(plan.action == N71_HDQ_RELEASE_ACK && plan.disable_event_mask == 0xa5);
}

int main(void)
{
	struct n71_hdq_release_input input = { 0, 0, 0, 0, 1 };
	struct n71_hdq_release_plan plan;
	unsigned int mode, mask, alert, status;
	/* Kills unconditional06, status polarity/bit, mode and event-mask mutations. */
	for (mode = 0; mode < 2; mode++)
		for (mask = 0; mask <= 0xff; mask++)
			for (alert = 0; alert < 2; alert++)
				for (status = 0; status <= 0xff; status++) {
					enum n71_hdq_release_action expected;
					input = (struct n71_hdq_release_input){
						mode, mask, alert, status, 1 };
					if (mode)
						expected = mask == 0 ? N71_HDQ_RELEASE_NO_HANDSHAKE :
							N71_HDQ_RELEASE_ACK;
					else
						expected = alert == 1 && status < 128 ?
							N71_HDQ_RELEASE_ACK_FINAL : N71_HDQ_RELEASE_WRITE_ZERO;
					assert(n71_hdq_select_release(&input, &plan) == 0);
					assert(plan.action == expected);
					assert(plan.disable_event_mask ==
						(alert ? mask % 64 + (mask / 128) * 128 : mask));
				}
	/* Kills invalid-input acceptance and output writes before validation. */
	input = (struct n71_hdq_release_input){ 0, 0, 0, 0, 1 };
	rejected(NULL);
	assert(n71_hdq_select_release(&input, NULL) == -EINVAL);
	input.software_mode = 2; rejected(&input); input.software_mode = 0;
	input.cached_mask = 256; rejected(&input); input.cached_mask = 0;
	input.battery_alert_present = 2; rejected(&input); input.battery_alert_present = 0;
	input.status7 = 256; rejected(&input); input.status7 = 0;
	input.status_valid = 0; rejected(&input);
	input.status_valid = 2; rejected(&input);
	puts("N71_HDQ_RELEASE_PLAN_OK");
	return 0;
}
