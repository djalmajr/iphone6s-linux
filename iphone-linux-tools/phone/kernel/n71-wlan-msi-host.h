/* SPDX-License-Identifier: GPL-2.0-only */
/* The caller retains bridge/module and serializes scan, removal and cleanup. */
#ifndef N71_WLAN_MSI_HOST_H
#define N71_WLAN_MSI_HOST_H
#include <linux/pci.h>
#include "n71-wlan-msi-native.h"

struct n71_wlan_msi_host {
	struct pci_host_bridge *bridge;
	struct n71_wlan_msi native;
	bool associated, saved_msi_domain;
};
struct n71_wlan_msi_host_request {
	struct pci_host_bridge *bridge;
	const struct n71_wlan_msi_request *message;
	const struct irq_fwspec *spec;
};

static int n71_wlan_msi_host_acquire(struct n71_wlan_msi_host *owner,
				     const struct n71_wlan_msi_host_request *request)
{
	struct pci_host_bridge *bridge;
	int error;

	if (!owner || !request || !request->bridge || !request->message || !request->spec)
		return -EINVAL;
	if (owner->bridge || owner->associated)
		return -EBUSY;
	bridge = request->bridge;
	if (bridge->bus || dev_get_msi_domain(&bridge->dev))
		return -EBUSY;
	owner->bridge = bridge;
	owner->saved_msi_domain = bridge->msi_domain;
	error = n71_wlan_msi_acquire(&owner->native, request->spec, request->message);
	if (error)
		return error;
	dev_set_msi_domain(&bridge->dev, owner->native.domain);
	bridge->msi_domain = true;
	owner->associated = true;
	return 0;
}

static int n71_wlan_msi_host_release(struct n71_wlan_msi_host *owner)
{
	struct pci_host_bridge *bridge;
	int error;

	if (!owner)
		return -EINVAL;
	bridge = owner->bridge;
	if (!bridge)
		return 0;
	if (bridge->bus)
		return -EBUSY;
	if (owner->associated) {
		if (!owner->native.domain || dev_get_msi_domain(&bridge->dev) != owner->native.domain ||
		    !bridge->msi_domain)
			return -EINVAL;
		dev_set_msi_domain(&bridge->dev, NULL);
		bridge->msi_domain = owner->saved_msi_domain;
		owner->associated = false;
	} else if (dev_get_msi_domain(&bridge->dev)) {
		return -EBUSY;
	}
	error = n71_wlan_msi_release(&owner->native);
	if (error)
		return error;
	*owner = (struct n71_wlan_msi_host){0};
	return 0;
}
#endif /* N71_WLAN_MSI_HOST_H */
