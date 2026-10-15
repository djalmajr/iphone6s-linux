/* SPDX-License-Identifier: GPL-2.0-only */
/* N71 MSI parent request arithmetic; no IRQ/domain or message-data ownership. */
#ifndef N71_WLAN_IRQ_REFERENCE_H
#define N71_WLAN_IRQ_REFERENCE_H
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

struct n71_wlan_irq_request {
	unsigned int aic_cells;
	unsigned int root_vector_count;
	unsigned int root_vector_offset;
	unsigned int port_index;
	unsigned int port_vector_base;
	unsigned int port_vector_count;
	unsigned int index;
};

struct n71_wlan_irq_reference {
	unsigned int aic_irq_number;
	unsigned int logical_vector;
	unsigned int fwspec[3];
};

/* Apple N71: root32/offset256, WLAN port1/base8/count8. Linux uses three cells.
 * Caller must separately validate the parent OF node/domain and its lifetime.
 * AIC number, internal hwirq, Linux virq and MSI message data are distinct.
 */
static inline int n71_wlan_irq_reference(
		const struct n71_wlan_irq_request *request,
		struct n71_wlan_irq_reference *output)
{
	struct n71_wlan_irq_reference reference;

	if (!request || !output)
		return -EINVAL;
	if (request->aic_cells != 3 || request->root_vector_count != 32 ||
	    request->root_vector_offset != 256 || request->port_index != 1 ||
	    request->port_vector_base != 8 || request->port_vector_count != 8)
		return -EINVAL;
	if (request->index >= request->port_vector_count)
		return -ERANGE;
	reference.logical_vector = request->port_vector_base + request->index;
	reference.aic_irq_number = request->root_vector_offset + reference.logical_vector;
	reference.fwspec[0] = 0;
	reference.fwspec[1] = reference.aic_irq_number;
	reference.fwspec[2] = 1;
	*output = reference;
	return 0;
}
#endif /* N71_WLAN_IRQ_REFERENCE_H */
