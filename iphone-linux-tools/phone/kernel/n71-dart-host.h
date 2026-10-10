/* SPDX-License-Identifier: GPL-2.0-only */
/* The caller serializes this lease with PCI removal and retains its module. */
#ifndef N71_DART_HOST_H
#define N71_DART_HOST_H
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/pci.h>
#include <linux/platform_device.h>

struct n71_dart_host {
	struct pci_host_bridge *bridge;
	struct device *master;
	struct platform_device *provider;
	struct device_node *master_node, *provider_node;
	struct of_changeset status_changes, map_changes;
	struct property *status_before, *status_property, *map_property;
	u32 phandle;
	bool status_queued, map_queued, populated, available, mapped;
};
struct n71_dart_host_request {
	struct pci_host_bridge *bridge;
	struct platform_device *provider;
};

static bool n71_dart_host_node_at(struct device_node *node, const char *path)
{
	struct device_node *found = of_find_node_by_path(path);
	bool matches = found && found == node;

	of_node_put(found);
	return matches;
}

static bool n71_dart_host_refs_valid(const struct n71_dart_host *owner)
{
	return owner->bridge->dev.parent == owner->master &&
		owner->provider->dev.parent == owner->master &&
		owner->master->of_node == owner->master_node &&
		owner->provider->dev.of_node == owner->provider_node &&
		owner->provider_node->phandle == owner->phandle &&
		(!owner->populated || of_node_check_flag(owner->provider_node, OF_POPULATED));
}

static int n71_dart_host_prepare(struct n71_dart_host *owner,
				 const struct n71_dart_host_request *request)
{
	struct device_node *master_node, *provider_node, *lookup;
	struct platform_device *provider, *found;
	struct device *master;
	struct property *status;
	u32 cells, map[8];
	int error;

	if (!owner || !request || !request->bridge || !request->provider)
		return -EINVAL;
	if (owner->bridge || request->bridge->bus)
		return -EBUSY;
	provider = request->provider;
	master = request->bridge->dev.parent;
	master_node = master ? master->of_node : NULL;
	provider_node = provider->dev.of_node;
	if (!of_machine_is_compatible("apple,n71") || !master_node || !provider_node ||
	    !n71_dart_host_node_at(master_node, "/soc/pcie@610000000") ||
	    !n71_dart_host_node_at(provider_node, "/soc/iommu@602008000") ||
	    !of_device_is_compatible(provider_node, "apple,s8000-dart") ||
	    provider->dev.parent != master || strcmp(provider->name, "n71-dart-cycle") ||
	    !provider->dev.driver || strcmp(provider->dev.driver->name, "apple-dart") ||
	    !platform_get_drvdata(provider))
		return -ENODEV;
	status = of_find_property(provider_node, "status", NULL);
	if (!status || status->length != sizeof("disabled") || !status->value ||
	    memcmp(status->value, "disabled", sizeof("disabled")) ||
	    !provider_node->phandle || provider_node->phandle == 0xffffffff ||
	    of_property_read_u32(provider_node, "#iommu-cells", &cells) || cells != 1)
		return -EINVAL;
	if (of_node_check_flag(provider_node, OF_POPULATED) ||
	    of_find_property(master_node, "iommu-map", NULL) ||
	    of_find_property(master_node, "iommu-map-mask", NULL) ||
	    of_find_property(master_node, "iommus", NULL))
		return -EBUSY;
	lookup = of_find_node_by_phandle(provider_node->phandle);
	error = lookup == provider_node ? 0 : -EINVAL;
	of_node_put(lookup);
	if (error)
		return error;
	found = of_find_device_by_node(provider_node);
	error = found == provider ? 0 : -EBUSY;
	if (found)
		put_device(&found->dev);
	if (error)
		return error;

	get_device(&request->bridge->dev);
	get_device(master);
	get_device(&provider->dev);
	owner->bridge = request->bridge;
	owner->master = master;
	owner->provider = provider;
	owner->master_node = of_node_get(master_node);
	owner->provider_node = of_node_get(provider_node);
	owner->status_before = status;
	owner->phandle = provider_node->phandle;
	of_changeset_init(&owner->status_changes);
	of_changeset_init(&owner->map_changes);
	error = of_changeset_update_prop_string(&owner->status_changes, provider_node, "status", "okay");
	if (error)
		return error;
	owner->status_queued = true;
	owner->status_property = list_last_entry(&owner->status_changes.entries,
					       struct of_changeset_entry, node)->prop;
	map[0] = 0x0008; map[1] = owner->phandle; map[2] = 0; map[3] = 1;
	map[4] = 0x0100; map[5] = owner->phandle; map[6] = 0; map[7] = 1;
	error = of_changeset_add_prop_u32_array(&owner->map_changes, master_node, "iommu-map", map, 8);
	if (error)
		return error;
	owner->map_queued = true;
	owner->map_property = list_last_entry(&owner->map_changes.entries,
					    struct of_changeset_entry, node)->prop;
	if (of_node_test_and_set_flag(provider_node, OF_POPULATED))
		return -EBUSY;
	owner->populated = true;
	error = of_changeset_apply(&owner->status_changes);
	owner->available = of_find_property(provider_node, "status", NULL) == owner->status_property;
	if (error)
		return error;
	if (!owner->available || !of_device_is_available(provider_node) || !n71_dart_host_refs_valid(owner))
		return -EIO;
	error = of_changeset_apply(&owner->map_changes);
	owner->mapped = of_find_property(master_node, "iommu-map", NULL) == owner->map_property;
	if (error)
		return error;
	return owner->mapped ? 0 : -EIO;
}

static int n71_dart_host_unmap(struct n71_dart_host *owner)
{
	struct property *property;
	int error;

	if (!owner)
		return -EINVAL;
	if (!owner->bridge)
		return 0;
	if (owner->bridge->bus)
		return -EBUSY;
	if (!n71_dart_host_refs_valid(owner) ||
	    of_find_property(owner->master_node, "iommu-map-mask", NULL) ||
	    of_find_property(owner->master_node, "iommus", NULL))
		return -EACCES;
	property = of_find_property(owner->master_node, "iommu-map", NULL);
	if (property && property != owner->map_property)
		return -EACCES;
	if (property) {
		error = of_changeset_revert(&owner->map_changes);
		owner->mapped = of_find_property(owner->master_node, "iommu-map", NULL) == owner->map_property;
		if (error)
			return error;
		if (of_find_property(owner->master_node, "iommu-map", NULL))
			return -EIO;
	}
	owner->mapped = false;
	return 0;
}

static int n71_dart_host_release(struct n71_dart_host *owner)
{
	struct n71_dart_host released;
	struct platform_device *found;
	struct property *status;
	int error;

	if (!owner)
		return -EINVAL;
	if (!owner->bridge)
		return 0;
	error = n71_dart_host_unmap(owner);
	if (error)
		return error;
	found = of_find_device_by_node(owner->provider_node);
	if (found) {
		put_device(&found->dev);
		return -EBUSY;
	}
	status = of_find_property(owner->provider_node, "status", NULL);
	if (status != owner->status_before && status != owner->status_property)
		return -EACCES;
	if (status == owner->status_property && owner->status_queued) {
		error = of_changeset_revert(&owner->status_changes);
		owner->available = of_find_property(owner->provider_node, "status", NULL) == owner->status_property;
		if (error)
			return error;
	}
	if (of_find_property(owner->provider_node, "status", NULL) != owner->status_before ||
	    of_device_is_available(owner->provider_node))
		return -EIO;
	if (owner->populated)
		of_node_clear_flag(owner->provider_node, OF_POPULATED);
	of_changeset_destroy(&owner->map_changes);
	of_changeset_destroy(&owner->status_changes);
	released = *owner;
	*owner = (struct n71_dart_host){0};
	of_node_put(released.provider_node);
	of_node_put(released.master_node);
	put_device(&released.provider->dev);
	put_device(released.master);
	put_device(&released.bridge->dev);
	return 0;
}
#endif /* N71_DART_HOST_H */
