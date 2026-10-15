/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller holds session_lock; device_lock also serializes endpoint bind/unbind. */
#ifndef N71_PCIE_DMA_LIVE_H
#define N71_PCIE_DMA_LIVE_H
#include <linux/ktime.h>
#include "n71-dma-observe.h"

struct n71_dma_live {
	struct n71_diagnostic *state;
	struct n71_scan_host *host;
	struct pci_dev *endpoint;
	struct iommu_domain *domain;
	unsigned int reads;
};

static int n71_dma_live_bound(struct pci_dev *endpoint)
{
	if (!endpoint->driver || !endpoint->dev.driver ||
	    endpoint->dev.driver != &endpoint->driver->driver ||
	    !endpoint->dev.driver->name || strcmp(endpoint->dev.driver->name, "brcmfmac") ||
	    endpoint->driver->driver_managed_dma || endpoint->vendor != 0x14e4 ||
	    endpoint->device != 0x43a3 || endpoint->class != 0x028000 ||
	    !endpoint->bus || endpoint->bus->number != 1 || endpoint->devfn)
		return -ENODEV;
	return 0;
}

static int n71_dma_live_guard(void *context)
{
	struct n71_dma_live *live = context;
	struct n71_diagnostic *state = live->state;
	struct n71_scan_host *host = live->host;

	if (!n71_session_has_held_bus(state) || state->attached != 4 || state->powered != 4 ||
	    state->power_put_pending || !state->reset_pending || !state->module_retained ||
	    !state->dart || !state->dart->lease.running || !state->dart->device ||
	    !state->dart->mmio.regs || state->dart->mmio.state != state ||
	    !host->brcmfmac.active || !host->driver_published || !host->driver_pm ||
	    host->driver_endpoint != live->endpoint || !host->dart.available || !host->dart.mapped ||
	    host->dart.provider != state->dart->device || !n71_dart_host_refs_valid(&host->dart) ||
	    !live->domain || host->iommu_domain != live->domain ||
	    live->domain->type != IOMMU_DOMAIN_DMA)
		return -EACCES;
	return n71_dma_live_bound(live->endpoint);
}

static int n71_dma_live_time(void *context, u64 *value)
{
	(void)context;
	*value = ktime_get_boottime_ns();
	return 0;
}

static int n71_dma_live_translate(void *context, u64 iova, u64 *physical)
{
	struct n71_dma_live *live = context;

	*physical = iommu_iova_to_phys(live->domain, iova);
	return 0;
}

static int n71_dma_live_read(void *context, u32 offset, u32 *value)
{
	struct n71_dma_live *live = context;

	if (live->reads >= 2 * N71_DMA_WORDS || offset != n71_dma_offset(live->reads % N71_DMA_WORDS))
		return -EINVAL;
	live->reads++;
	*value = readl(live->state->dart->mmio.regs + offset);
	return 0;
}

/* No new mapping, region claim, allocation, DMA operation or register write. */
static int n71_dma_capture_locked(struct n71_diagnostic *state, bool requested, u64 iova,
				  struct n71_dma_observation *out)
{
	struct n71_dma_live live = {.state = state};
	struct n71_dma_observation result = {.iova = iova};
	struct n71_dma_request request = {.requested = requested, .iova = iova};
	struct n71_dma_io io = {&live, n71_dma_live_guard, n71_dma_live_time,
			      n71_dma_live_translate, n71_dma_live_read};
	int error = -EACCES;

	if (!out)
		return -EINVAL;
	if (!requested || !n71_session_has_held_bus(state))
		goto done;
	live.host = pci_host_bridge_priv(state->scan_bridge);
	live.endpoint = live.host->driver_endpoint;
	if (!live.endpoint)
		goto done;
	device_lock(&live.endpoint->dev);
	error = n71_dma_live_bound(live.endpoint);
	if (error)
		goto unlock;
	/* The DMA domain API requires a bound, non-driver-managed DMA lifetime. */
	live.domain = iommu_get_domain_for_dev(&live.endpoint->dev);
	error = n71_dma_live_guard(&live);
	if (error)
		goto unlock;
	request.aperture_start = live.domain->geometry.aperture_start;
	request.aperture_end = live.domain->geometry.aperture_end;
	error = n71_dma_observe(&io, &request, &result);
unlock:
	device_unlock(&live.endpoint->dev);
done:
	result.error = error;
	*out = result;
	return error;
}
#endif /* N71_PCIE_DMA_LIVE_H */
