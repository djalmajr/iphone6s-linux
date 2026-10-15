/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller serializes the lease with bus/provider teardown. No IRQ handler. */
#ifndef N71_PCIE_MSI_ALLOCATE_H
#define N71_PCIE_MSI_ALLOCATE_H
#include "n71-msi-allocation-lease.h"
#include "n71-pcie-resource-assign.h"

static inline int n71_msi_allocation_error(struct n71_scan_host *host)
{
	return host->msi_config.error ? host->msi_config.error :
		host->config.error ? host->config.error : host->io_error;
}

static inline int n71_msi_allocation_power(struct n71_scan_host *host, struct pci_dev *dev)
{
	struct n71_scan_io io = {host, n71_scan_raw_read, n71_scan_raw_write};
	u32 actual;
	int error;

	if (dev->pm_cap != 0x48 || dev->msi_cap != 0x58 || dev->msix_cap ||
	    dev->msi_enabled || dev->msix_enabled ||
	    (dev->current_state != PCI_UNKNOWN && dev->current_state != PCI_D0))
		return -EACCES;
	error = n71_scan_read(&io, false, 0x4c, 2, &actual);
	if (error || actual != 0x4008)
		return error ? error : -EACCES;
	/* Refresh the core's cache through the exported API; hardware is D0. */
	error = pci_set_power_state(dev, PCI_D0);
	if (error)
		return error > 0 ? -EIO : error;
	error = n71_msi_allocation_error(host);
	if (!error)
		error = n71_scan_read(&io, false, 0x4c, 2, &actual);
	if (!error && (actual != 0x4008 || dev->current_state != PCI_D0))
		error = -EIO;
	return error;
}

static inline int n71_msi_allocation_verify(struct n71_scan_host *host,
					   const struct n71_msi_allocation *lease)
{
	struct n71_wlan_msi *native = &host->msi.native;
	struct n71_scan_io io = {host, n71_scan_raw_read, n71_scan_raw_write};
	struct irq_data *own, *parent, *leaf;
	u32 control;
	int error = n71_msi_allocation_error(host);

	if (error)
		return error;
	if (!native->domain || !native->parent || !lease->vector ||
	    !lease->endpoint->msi_enabled || lease->endpoint->msix_enabled ||
	    lease->endpoint->irq != lease->vector || !n71_msi_config_grant(native->slots) ||
	    native->domain->mapcount != 1 || !native->child || native->child->mapcount != 1 ||
	    native->child->parent != native->domain || native->child_device != &lease->endpoint->dev)
		return -EACCES;
	own = irq_domain_get_irq_data(native->domain, lease->vector);
	parent = irq_domain_get_irq_data(native->parent, lease->vector);
	leaf = irq_get_irq_data(lease->vector);
	if (!own || !parent || !leaf || leaf->domain != native->child || leaf->parent_data != own ||
	    own->domain != native->domain || own->chip != &n71_wlan_msi_chip || own->chip_data != native ||
	    own->hwirq != n71_msi_config_vector(native->slots) - 8 || own->parent_data != parent ||
	    irqd_get_trigger_type(own) != IRQ_TYPE_EDGE_RISING || parent->domain != native->parent ||
	    parent->hwirq != 0x10100UL + n71_msi_config_vector(native->slots) ||
	    !parent->chip || !parent->chip->name || strcmp(parent->chip->name, "AIC"))
		return -EACCES;
	error = n71_msi_config_guard(&io, &host->msi_config);
	if (!error)
		error = n71_scan_read(&io, false, 0x5a, 2, &control);
	if (!error && control != 0x89)
		error = -EIO;
	if (!error)
		error = n71_msi_config_message(&io, native->slots);
	return error;
}

static inline int n71_pcie_msi_allocate(struct pci_host_bridge *bridge,
				       struct n71_scan_host *host, struct n71_msi_allocation *lease)
{
	struct n71_resource_devices devices = {0};
	struct n71_wlan_msi *native;
	struct n71_scan_io io;
	unsigned long flags;
	int error, vectors;

	if (!bridge || !host || !lease || !bridge->bus || bridge->bus->sysdata != host)
		return -ENODEV;
	if (n71_scan_driver_pending(host))
		return -EBUSY;
	if (lease->endpoint || lease->vector || host->msi_config.phase != N71_MSI_CONFIG_EMPTY)
		return -EBUSY;
	error = n71_msi_allocation_error(host);
	if (error)
		return error;
	if (host->msi_config.attempts || host->msi_config.cleanup_attempts)
		return -EALREADY;
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	native = &host->msi.native;
	if (!host->bus_held || !host->config_pending || !host->config.active ||
	    !host->resources_assigned || !host->resources.pending || host->resources.active ||
	    !host->window_claimed || !host->pme.prepared || !host->target.prepared ||
	    host->msi.bridge != bridge || !host->msi.associated || !native->domain ||
	    !native->parent || native->domain->parent != native->parent ||
	    native->slots || native->domain->mapcount || native->child ||
	    host->dart.bridge != bridge || !host->dart.available || !host->dart.mapped ||
	    !host->iommu_domain || host->iommu_devices != 2)
		return -EACCES;
	pci_lock_rescan_remove();
	devices.root = pci_get_slot(bridge->bus, 8);
	if (devices.root && devices.root->subordinate)
		devices.endpoint = pci_get_slot(devices.root->subordinate, 0);
	if (!devices.root || !devices.endpoint || devices.root->driver || devices.endpoint->driver ||
	    devices.root->vendor != 0x106b || devices.root->device != 0x1004 ||
	    devices.endpoint->vendor != 0x14e4 || devices.endpoint->device != 0x43a3 ||
	    devices.endpoint->bus->self != devices.root || devices.endpoint->bus->sysdata != host ||
	    devices.endpoint->bus->number != 1 || devices.endpoint->devfn ||
	    dev_get_msi_domain(&devices.root->dev) != native->domain ||
	    dev_get_msi_domain(&devices.endpoint->dev) != native->domain) {
		error = -ENODEV;
		goto put;
	}
#ifdef CONFIG_PCIEASPM
	/* pci_set_power_state also reconfigures a parent's existing ASPM link. */
	if (devices.root->link_state) {
		error = -EACCES;
		goto put;
	}
#endif
	pci_walk_bus(bridge->bus, n71_resource_visit, &devices);
	error = devices.error || devices.count != 2 ? -ENODEV : n71_resource_verify(host, &devices);
	if (!error)
		error = n71_msi_config_guard(&io, &host->msi_config);
	if (!error)
		error = n71_msi_allocation_power(host, devices.endpoint);
	if (!error) {
		spin_lock_irqsave(&host->lock, flags);
		error = n71_msi_config_capture(&io, &host->msi_config);
		spin_unlock_irqrestore(&host->lock, flags);
	}
	if (error)
		goto put;
	lease->endpoint = devices.endpoint;
	lease->default_irq = devices.endpoint->irq;
	devices.endpoint = NULL; /* Retain the reference until verified release. */
	vectors = pci_alloc_irq_vectors(lease->endpoint, 1, 1, PCI_IRQ_MSI);
	error = vectors == 1 ? 0 : vectors < 0 ? vectors : -EIO;
	if (!error) {
		error = pci_irq_vector(lease->endpoint, 0);
		if (error > 0) {
			lease->vector = error;
			error = n71_msi_allocation_verify(host, lease);
		} else if (!error) {
			error = -EIO;
		}
	}
	error = n71_msi_config_error(&host->msi_config, error);
put:
	pci_dev_put(devices.endpoint);
	pci_dev_put(devices.root);
	pci_unlock_rescan_remove();
	return error;
}

static inline int n71_pcie_msi_release(struct n71_scan_host *host, struct n71_msi_allocation *lease)
{
	struct n71_wlan_msi *native;
	struct n71_scan_io io;
	struct n71_msi_config_core core;
	unsigned long flags;
	int error;

	if (!host || !lease)
		return -EINVAL;
	if (n71_scan_driver_pending(host))
		return -EBUSY;
	if (!lease->endpoint)
		return host->msi_config.phase == N71_MSI_CONFIG_EMPTY && !lease->vector &&
			!lease->default_irq ? 0 : -EBUSY;
	if (host->msi_config.phase == N71_MSI_CONFIG_EMPTY)
		return -EBUSY;
	native = &host->msi.native;
	if (!host->bus_held || !host->msi.bridge || !host->msi.bridge->bus ||
	    !native->domain || lease->endpoint->driver || lease->endpoint->msix_enabled ||
	    (native->child && native->child_device != &lease->endpoint->dev))
		return -EBUSY;
	pci_lock_rescan_remove();
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	spin_lock_irqsave(&host->lock, flags);
	error = n71_msi_config_stop(&io, &host->msi_config);
	spin_unlock_irqrestore(&host->lock, flags);
	if (error)
		goto unlock;
	pci_free_irq_vectors(lease->endpoint);
	core = (struct n71_msi_config_core){
		.enabled = lease->endpoint->msi_enabled, .slots = native->slots,
		.mappings = native->domain->mapcount,
	};
	if (lease->endpoint->irq != lease->default_irq || (native->child && native->child->mapcount)) {
		error = n71_msi_config_error(&host->msi_config, -EIO);
		goto unlock;
	}
	spin_lock_irqsave(&host->lock, flags);
	error = n71_msi_config_restore(&io, &host->msi_config, &core);
	spin_unlock_irqrestore(&host->lock, flags);
	if (!error) {
		pci_dev_put(lease->endpoint);
		*lease = (struct n71_msi_allocation){0};
	}
unlock:
	pci_unlock_rescan_remove();
	return error;
}
#endif /* N71_PCIE_MSI_ALLOCATE_H */
