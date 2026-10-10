/* SPDX-License-Identifier: GPL-2.0-only */
/* Reference selection only. No register, mask or charger state is changed. */
#ifndef N71_HDQ_RELEASE_PLAN_H
#define N71_HDQ_RELEASE_PLAN_H
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

enum n71_hdq_release_action {
	N71_HDQ_RELEASE_NO_HANDSHAKE,
	N71_HDQ_RELEASE_ACK,
	N71_HDQ_RELEASE_ACK_FINAL,
	N71_HDQ_RELEASE_WRITE_ZERO,
};

struct n71_hdq_release_input {
	unsigned int software_mode;
	unsigned int cached_mask;
	unsigned int battery_alert_present;
	unsigned int status7;
	unsigned int status_valid;
};

struct n71_hdq_release_plan {
	enum n71_hdq_release_action action;
	unsigned int disable_event_mask;
};

/* command0/request0 only. A known input is not proof that I/O is safe.
 * Caller owns status-read effects, event masks, mux and verified cleanup.
 */
static inline int n71_hdq_select_release(
		const struct n71_hdq_release_input *input,
		struct n71_hdq_release_plan *output)
{
	struct n71_hdq_release_plan plan;
	if (!input || !output || input->software_mode > 1 ||
	    input->cached_mask > 0xff || input->battery_alert_present > 1 ||
	    input->status7 > 0xff || input->status_valid != 1)
		return -EINVAL;
	if (input->software_mode == 1) {
		plan.action = input->cached_mask ? N71_HDQ_RELEASE_ACK :
			N71_HDQ_RELEASE_NO_HANDSHAKE;
	} else if (input->battery_alert_present && !(input->status7 & 0x80)) {
		plan.action = N71_HDQ_RELEASE_ACK_FINAL;
	} else {
		plan.action = N71_HDQ_RELEASE_WRITE_ZERO;
	}
	plan.disable_event_mask = input->cached_mask;
	if (input->battery_alert_present)
		plan.disable_event_mask &= ~0x40U;
	*output = plan;
	return 0;
}

#endif /* N71_HDQ_RELEASE_PLAN_H */
