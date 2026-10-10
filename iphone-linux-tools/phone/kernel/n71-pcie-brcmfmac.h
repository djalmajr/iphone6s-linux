/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller serializes actions; normal driver unload must precede release. */
#ifndef N71_PCIE_BRCMFMAC_H
#define N71_PCIE_BRCMFMAC_H
#include <linux/device/driver.h>
#include <linux/pm_runtime.h>
#include "n71-pcie-msi-allocate.h"

static inline bool n71_brcmfmac_pending(const struct n71_scan_host *host)
{
	return n71_scan_driver_pending(host);
}

static inline int n71_pcie_brcmfmac_prepare(struct pci_host_bridge *bridge,
					  struct n71_scan_host *host)
{
	struct n71_resource_devices devices = {0};
	struct n71_scan_io io;
	unsigned long flags;
	int error;

	if (!bridge || !host || !bridge->bus || bridge->bus->sysdata != host)
		return -ENODEV;
	if (n71_brcmfmac_pending(host) || host->driver_published || host->msi_allocation.endpoint ||
	    host->msi_allocation.vector || host->msi_config.phase != N71_MSI_CONFIG_EMPTY)
		return -EBUSY;
	error = n71_msi_allocation_error(host);
	if (error)
		return error;
	if (!host->bus_held || !host->config_pending || !host->config.active ||
	    !host->resources_assigned || !host->resources.pending || host->resources.active ||
	    !host->window_claimed || !host->pme.prepared || !host->target.prepared ||
	    host->msi.bridge != bridge || !host->msi.associated || !host->msi.native.domain ||
	    !host->msi.native.parent || host->msi.native.slots || host->msi.native.domain->mapcount ||
	    host->msi.native.child || host->dart.bridge != bridge || !host->dart.available ||
	    !host->dart.mapped || !host->iommu_domain || host->iommu_devices != 2 ||
	    driver_find("brcmfmac", &pci_bus_type))
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
	    !n71_scan_dma_device_valid(devices.root, true) ||
	    !n71_scan_dma_device_valid(devices.endpoint, false)) {
		error = -ENODEV;
		goto put;
	}
#ifdef CONFIG_PCIEASPM
	if (devices.root->link_state) {
		error = -EACCES;
		goto put;
	}
#endif
	device_lock(&devices.root->dev);
	device_lock(&devices.endpoint->dev);
	if (device_has_driver_override(&devices.root->dev) ||
	    device_has_driver_override(&devices.endpoint->dev)) {
		error = -EBUSY;
		goto unlock;
	}
	pci_walk_bus(bridge->bus, n71_resource_visit, &devices);
	error = devices.error || devices.count != 2 ? -ENODEV : n71_resource_verify(host, &devices);
	if (!error)
		error = n71_msi_allocation_power(host, devices.endpoint);
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	if (!error) {
		spin_lock_irqsave(&host->lock, flags);
		error = n71_brcmfmac_capture(&io, &host->brcmfmac);
		spin_unlock_irqrestore(&host->lock, flags);
	}
	if (error)
		goto unlock;
	host->driver_root = devices.root;
	host->driver_endpoint = devices.endpoint;
	pm_runtime_get_noresume(&devices.root->dev);
	pm_runtime_get_noresume(&devices.endpoint->dev);
	host->driver_pm = true;
	error = device_set_driver_override(&devices.root->dev, "none");
	if (!error) {
		host->driver_root_override = true;
		error = device_set_driver_override(&devices.endpoint->dev, "brcmfmac");
		if (!error)
			host->driver_endpoint_override = true;
	}
	n71_brcmfmac_error(&host->brcmfmac, error);
unlock:
	device_unlock(&devices.endpoint->dev);
	device_unlock(&devices.root->dev);
	if (host->driver_root == devices.root) {
		devices.root = NULL;
		devices.endpoint = NULL;
	}
put:
	pci_dev_put(devices.endpoint);
	pci_dev_put(devices.root);
	pci_unlock_rescan_remove();
	return error;
}

static inline int n71_pcie_brcmfmac_publish(struct pci_host_bridge *bridge,
					  struct n71_scan_host *host)
{
	unsigned long flags;
	bool present;
	int error;

	if (!bridge || !host || !bridge->bus || bridge->bus->sysdata != host)
		return -ENODEV;
	if (host->driver_published)
		return -EALREADY;
	if (!host->brcmfmac.active || host->brcmfmac.error || !host->driver_pm ||
	    !host->driver_root || !host->driver_endpoint ||
	    !host->driver_root_override || !host->driver_endpoint_override)
		return -EACCES;
	pci_lock_rescan_remove();
	host->driver_published = true;
	pci_bus_add_devices(bridge->bus);
	pci_unlock_rescan_remove();
	present = pci_device_is_present(host->driver_root) && pci_device_is_present(host->driver_endpoint);
	spin_lock_irqsave(&host->lock, flags);
	if (!present)
		n71_brcmfmac_error(&host->brcmfmac, -EIO);
	error = host->brcmfmac.error ? host->brcmfmac.error : host->io_error;
	spin_unlock_irqrestore(&host->lock, flags);
	return error;
}

static inline int n71_brcmfmac_clear_override(struct pci_dev *device, const char *name)
{
	const struct device_driver expected = {.name = name};

	if (device_match_driver_override(&device->dev, &expected) <= 0)
		return -EAGAIN;
	return device_set_driver_override(&device->dev, "");
}

static inline int n71_pcie_brcmfmac_release(struct pci_host_bridge *bridge,
					  struct n71_scan_host *host)
{
	struct n71_brcmfmac_quiescent core;
	struct n71_scan_io io;
	struct pci_dev *root, *endpoint;
	unsigned long flags;
	int error;

	if (!bridge || !host || !bridge->bus || bridge->bus->sysdata != host)
		return -ENODEV;
	if (!n71_brcmfmac_pending(host))
		return 0;
	root = host->driver_root;
	endpoint = host->driver_endpoint;
	if (!root || !endpoint || !host->driver_pm || driver_find("brcmfmac", &pci_bus_type))
		return -EBUSY;
	pci_lock_rescan_remove();
	device_lock(&root->dev);
	device_lock(&endpoint->dev);
	core = (struct n71_brcmfmac_quiescent){
		.driver_registered = !!driver_find("brcmfmac", &pci_bus_type),
		.driver_bound = !!root->driver || !!endpoint->driver,
		.software_enabled = root->msi_enabled || root->msix_enabled ||
			endpoint->msi_enabled || endpoint->msix_enabled,
		.slots = host->msi.native.slots,
		.mappings = host->msi.native.domain ? host->msi.native.domain->mapcount : 1,
		.child_mappings = host->msi.native.child ? host->msi.native.child->mapcount : 0,
	};
	if (core.driver_registered || core.driver_bound || core.software_enabled ||
	    core.slots || core.mappings || core.child_mappings ||
	    atomic_read(&root->enable_cnt) < 0 || atomic_read(&endpoint->enable_cnt) < 0 ||
	    atomic_read(&root->enable_cnt) > 1 || atomic_read(&endpoint->enable_cnt) > 1) {
		error = -EBUSY;
		goto unlock;
	}
	if (pci_is_enabled(endpoint))
		pci_disable_device(endpoint);
	if (pci_is_enabled(root))
		pci_disable_device(root);
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	spin_lock_irqsave(&host->lock, flags);
	error = n71_brcmfmac_restore(&io, &host->brcmfmac, &core);
	spin_unlock_irqrestore(&host->lock, flags);
	if (error)
		goto unlock;
	if (host->driver_root_override) {
		error = n71_brcmfmac_clear_override(root, "none");
		if (error)
			goto unlock;
		host->driver_root_override = false;
	}
	if (host->driver_endpoint_override) {
		error = n71_brcmfmac_clear_override(endpoint, "brcmfmac");
		if (error)
			goto unlock;
		host->driver_endpoint_override = false;
	}
	pm_runtime_put_noidle(&endpoint->dev);
	pm_runtime_put_noidle(&root->dev);
	host->driver_pm = false;
	host->driver_root = NULL;
	host->driver_endpoint = NULL;
unlock:
	device_unlock(&endpoint->dev);
	device_unlock(&root->dev);
	if (!error) {
		pci_dev_put(endpoint);
		pci_dev_put(root);
	}
	pci_unlock_rescan_remove();
	return n71_brcmfmac_error(&host->brcmfmac, error);
}
#endif /* N71_PCIE_BRCMFMAC_H */
