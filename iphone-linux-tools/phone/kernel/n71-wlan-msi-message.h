/* SPDX-License-Identifier: GPL-2.0-only */
/* Source-derived N71 MSI message reference; no IRQ allocation or MMIO. */
#ifndef N71_WLAN_MSI_MESSAGE_H
#define N71_WLAN_MSI_MESSAGE_H
#include "n71-wlan-irq-reference.h"

struct n71_wlan_msi_request {
	struct n71_wlan_irq_request irq;
	unsigned int address_lo, address_hi, vector_base;
};

struct n71_wlan_msi_reference {
	struct n71_wlan_irq_reference irq;
	unsigned int message[3];
};

/* Apple N71 stores offset256 separately from the zero controller vectorBase.
 * The bridge's message data is the logical vector8..15, not AIC264..271.
 * These are static reference values; parent ownership, delivery and hardware
 * configuration require separate native lifecycle and physical verification.
 */
static inline int n71_wlan_msi_message(
		const struct n71_wlan_msi_request *request,
		struct n71_wlan_msi_reference *output)
{
	struct n71_wlan_msi_reference reference = {0};
	int error;

	if (!request || !output)
		return -EINVAL;
	if (request->address_lo != 0xbffff000U || request->address_hi || request->vector_base)
		return -EINVAL;
	error = n71_wlan_irq_reference(&request->irq, &reference.irq);
	if (error)
		return error;
	reference.message[0] = request->address_lo;
	reference.message[1] = request->address_hi;
	reference.message[2] = reference.irq.logical_vector;
	*output = reference;
	return 0;
}
#endif /* N71_WLAN_MSI_MESSAGE_H */
