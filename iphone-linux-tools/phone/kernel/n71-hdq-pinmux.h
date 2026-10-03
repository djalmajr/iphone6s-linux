/* SPDX-License-Identifier: GPL-2.0-only */
/* Pinned N71 GPIO2 mode calculation only; no MMIO or ownership claim. */
#ifndef N71_HDQ_PINMUX_H
#define N71_HDQ_PINMUX_H
#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stdbool.h>
#endif

struct n71_hdq_pinmux_request {
	unsigned int flags;
	unsigned int glitchless;
	unsigned int pin;
};

struct n71_hdq_pinmux_plan {
	unsigned int offset;
	unsigned int mask;
	unsigned int value;
};

/* AppleS5L8960XGPIOIC mode2: glitchless selects bit4, otherwise bit5.
 * Both branches set input-enable and clear the other mux/direction bits.
 * This is a reference calculation, not a qualified hardware transaction.
 */
static inline bool n71_hdq_pinmux(const struct n71_hdq_pinmux_request *request,
				 struct n71_hdq_pinmux_plan *out)
{
	if (!request || !out || request->pin != 2 || request->flags != 0x102 ||
	    request->glitchless > 1)
		return false;
	out->offset = 0x08;
	out->mask = 0x270;
	out->value = request->glitchless ? 0x210 : 0x220;
	return true;
}
#endif
