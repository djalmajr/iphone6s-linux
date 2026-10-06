/* SPDX-License-Identifier: GPL-2.0-only */
/* Allocate the held N71 bus with PCI core; leave decode, bind and DMA off. */
#ifndef N71_PCIE_RESOURCE_ASSIGN_H
#define N71_PCIE_RESOURCE_ASSIGN_H
#include "n71-pcie-scan.h"

struct n71_resource_devices {
	struct pci_dev *root, *endpoint;
	unsigned int count;
	int error;
};

static int n71_resource_visit(struct pci_dev *dev, void *context)
{
	struct n71_resource_devices *devices = context;

	devices->count++;
	if (dev != devices->root && dev != devices->endpoint)
		devices->error = -ENODEV;
	return devices->error;
}

static int n71_resource_preflight(struct n71_scan_host *host,
				  struct n71_resource_devices *devices,
				  struct n71_resource_bar_layout *layout)
{
	struct pci_dev *root = devices->root, *endpoint = devices->endpoint;
	struct resource *resource;
	unsigned int index;
	unsigned long type_mask = IORESOURCE_TYPE_BITS | IORESOURCE_MEM_64 | IORESOURCE_PREFETCH;

	if (!root || !endpoint || root->bus->number || root->devfn != 8 ||
	    endpoint->bus->number != 1 || endpoint->devfn ||
	    root->vendor != 0x106b || root->device != 0x1004 || root->class != 0x060400 ||
	    endpoint->vendor != 0x14e4 || endpoint->device != 0x43a3 || endpoint->class != 0x028000 ||
	    root->driver || endpoint->driver || pci_is_enabled(root) || pci_is_enabled(endpoint) ||
	    root->subordinate != endpoint->bus || endpoint->bus->self != root ||
	    root->bus->sysdata != host || endpoint->bus->sysdata != host)
		return -ENODEV;
	pci_walk_bus(root->bus, n71_resource_visit, devices);
	if (devices->error || devices->count != 2)
		return -ENODEV;
	for (index = 0; index <= PCI_ROM_RESOURCE; index++) {
		resource = &root->resource[index];
		if (resource->flags || resource->start || resource->end || resource->parent || resource->child)
			return -EACCES;
		resource = &endpoint->resource[index];
		if (resource->parent || resource->child || resource->start)
			return -EACCES;
		if (index == 0 || index == 2) {
			u32 bytes = index == 0 ? 0x8000U : 0x400000U;
			if ((resource->flags & type_mask) != (IORESOURCE_MEM | IORESOURCE_MEM_64) ||
			    resource->flags & IORESOURCE_PCI_FIXED || resource_size(resource) != bytes)
				return -EINVAL;
			layout->bytes[index] = bytes;
		} else if (resource->flags || resource->end) {
			return -EINVAL;
		}
	}
	for (index = PCI_BRIDGE_IO_WINDOW; index <= PCI_BRIDGE_PREF_MEM_WINDOW; index++)
		if (root->resource[index].parent || root->resource[index].child)
			return -EBUSY;
	resource = &host->windows[1];
	if (resource->start != 0x7c0000000ULL || resource->end != 0x7ffffffffULL ||
	    resource->flags != IORESOURCE_MEM || resource->parent || resource->child)
		return -EINVAL;
	return 0;
}

static int n71_resource_verify_bar(struct n71_scan_host *host,
				   struct pci_dev *endpoint, unsigned int index)
{
	struct resource *resource = &endpoint->resource[index];
	struct resource *window = &endpoint->bus->self->resource[PCI_BRIDGE_MEM_WINDOW];
	struct pci_bus_region region;
	struct n71_scan_io io = {host, n71_scan_raw_read, n71_scan_raw_write};
	u32 low, high, bytes = index == 0 ? 0x8000U : 0x400000U;
	unsigned long type_mask = IORESOURCE_TYPE_BITS | IORESOURCE_MEM_64 | IORESOURCE_PREFETCH;
	int error;

	if (resource->parent != window || resource_size(resource) != bytes ||
	    (resource->flags & type_mask) != (IORESOURCE_MEM | IORESOURCE_MEM_64) ||
	    resource->flags & (IORESOURCE_UNSET | IORESOURCE_PCI_FIXED) ||
	    resource->start < window->start || resource->end > window->end ||
	    resource->start < 0x7c0000000ULL || resource->end > 0x7ffffffffULL ||
	    resource->start > resource->end || (resource->start & (bytes - 1)))
		return -EACCES;
	pcibios_resource_to_bus(endpoint->bus, &region, resource);
	if (region.start != resource->start - 0x700000000ULL ||
	    region.end != resource->end - 0x700000000ULL || region.end > 0xffffffffULL)
		return -ERANGE;
	error = n71_scan_read(&io, false, 0x10 + index * 4, 4, &low);
	if (!error)
		error = n71_scan_read(&io, false, 0x14 + index * 4, 4, &high);
	return error ? error : low == ((u32)region.start | 4U) && !high ? 0 : -EIO;
}

static int n71_resource_verify(struct n71_scan_host *host, struct n71_resource_devices *devices)
{
	struct pci_dev *root = devices->root, *endpoint = devices->endpoint;
	struct resource *window = &root->resource[PCI_BRIDGE_MEM_WINDOW];
	struct n71_scan_io io = {host, n71_scan_raw_read, n71_scan_raw_write};
	struct pci_bus_region region;
	u32 actual, expected;
	unsigned int function, index;
	int error;

	if (host->config.error || host->io_error || host->resources.error)
		return host->config.error ? host->config.error : host->io_error ? host->io_error : host->resources.error;
	if (host->windows[1].parent != &iomem_resource || window->parent != &host->windows[1] ||
	    (window->flags & (IORESOURCE_TYPE_BITS | IORESOURCE_PREFETCH | IORESOURCE_MEM_64)) != IORESOURCE_MEM ||
	    window->flags & (IORESOURCE_UNSET | IORESOURCE_PCI_FIXED) ||
	    window->start < host->windows[1].start || window->end > host->windows[1].end ||
	    window->start > window->end || (window->start & 0xfffffU) ||
	    (window->end & 0xfffffU) != 0xfffffU || root->resource[PCI_BRIDGE_IO_WINDOW].parent ||
	    root->resource[PCI_BRIDGE_PREF_MEM_WINDOW].parent || root->driver || endpoint->driver ||
	    pci_is_enabled(root) || pci_is_enabled(endpoint))
		return -EACCES;
	for (index = 0; index <= PCI_ROM_RESOURCE; index++) {
		struct resource *resource = &root->resource[index];
		if (resource->flags || resource->start || resource->end || resource->parent)
			return -EACCES;
		if (index == 0 || index == 2)
			continue;
		resource = &endpoint->resource[index];
		if (resource->flags || resource->start || resource->end || resource->parent)
			return -EACCES;
	}
	if (!(endpoint->resource[0].end < endpoint->resource[2].start ||
	      endpoint->resource[2].end < endpoint->resource[0].start))
		return -EACCES;
	error = n71_resource_verify_bar(host, endpoint, 0);
	if (!error)
		error = n71_resource_verify_bar(host, endpoint, 2);
	if (error)
		return error;
	pcibios_resource_to_bus(root->bus, &region, window);
	if (region.start != window->start - 0x700000000ULL ||
	    region.end != window->end - 0x700000000ULL)
		return -ERANGE;
	expected = ((u32)(region.start >> 16) & 0xfff0U) | ((u32)region.end & 0xfff00000U);
	error = n71_scan_read(&io, true, 0x20, 4, &actual);
	if (!error && actual != expected)
		error = -EIO;
	for (function = 0; !error && function < 2; function++) {
		error = n71_scan_read(&io, function == 0, 4, 2, &actual);
		if (!error && (actual != host->resources.reference.saved[function].command || (actual & 7)))
			error = -EACCES;
	}
	if (!error)
		error = n71_scan_read(&io, true, 0x3e, 2, &actual);
	if (!error && actual != host->resources.reference.saved[0].control)
		error = -EACCES;
	return error;
}

static inline void n71_resource_report_readback(struct n71_scan_host *host)
{
	const struct n71_resource_write_failure *failure = &host->resources.failure;

	dev_info(host->dev, "N71_PCIE_ASSIGN_READBACK failed=%u root=%u where=%03x size=%u value=%08x before=%08x after_valid=%u after=%08x write_error=%d read_error=%d; no additional IO\n",
		 failure->valid, failure->request.root, failure->request.where, failure->request.size,
		 failure->request.value, failure->before, failure->after_valid, failure->after,
		 failure->write_error, failure->read_error);
}

/* Caller serializes this action with cleanup and retains MMIO/module/power. */
static inline int n71_pcie_assign_resources(struct n71_diagnostic *state)
{
	struct pci_host_bridge *bridge;
	struct n71_scan_host *host;
	struct n71_resource_devices devices = {0};
	struct n71_resource_bar_layout layout = {0};
	struct n71_scan_io io;
	int error;

	if (!state || !state->scan_bridge || !state->scan_bridge->bus)
		return -ENODEV;
	bridge = state->scan_bridge;
	host = pci_host_bridge_priv(bridge);
	if (!host->bus_held || !host->config_pending || !host->config.active ||
	    !host->pme.prepared || !host->target.prepared)
		return -EBUSY;
	if (host->resource_attempted)
		return host->config.error ? host->config.error : -EALREADY;
	if (host->config.error || host->io_error)
		return host->config.error ? host->config.error : host->io_error;
	host->resource_attempted = true;
	pci_lock_rescan_remove();
	devices.root = pci_get_slot(bridge->bus, 8);
	if (devices.root && devices.root->subordinate)
		devices.endpoint = pci_get_slot(devices.root->subordinate, 0);
	error = n71_resource_preflight(host, &devices, &layout);
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	if (!error)
		error = n71_resource_capture(&io, &layout, &host->resources);
	if (!error && devices.endpoint->bus->bridge_ctl != host->resources.reference.saved[0].control)
		error = -EACCES;
	if (!error) {
		error = request_resource(&iomem_resource, &host->windows[1]);
		if (!error)
			host->window_claimed = true;
	}
	if (!error) {
		pci_bus_size_bridges(bridge->bus);
		pci_bus_assign_resources(bridge->bus);
		error = n71_resource_verify(host, &devices);
	}
	host->resources.active = false;
	if (error)
		n71_scan_refuse(&host->config, error);
	else
		host->resources_assigned = true;
	pci_dev_put(devices.endpoint);
	pci_dev_put(devices.root);
	pci_unlock_rescan_remove();
	n71_resource_report_readback(host);
	dev_info(host->dev, "N71_PCIE_RESOURCE_RESULT error=%d assigned=%u pending=%u claimed=%u attempts=%u writes=%u; no decode, bind or DMA\n",
		 error, host->resources_assigned, host->resources.pending, host->window_claimed,
		 host->resources.attempts, host->resources.writes);
	return error;
}
#endif /* N71_PCIE_RESOURCE_ASSIGN_H */
