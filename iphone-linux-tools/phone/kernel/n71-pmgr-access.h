/* SPDX-License-Identifier: GPL-2.0-only */
/* Qualified provider access; caller holds OF references and unlocks in the same task. */
#ifndef N71_PMGR_ACCESS_H
#define N71_PMGR_ACCESS_H
#include <linux/mfd/syscon.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/string.h>

#define N71_PMGR_PATH "/soc/power-management@20e000000"

struct n71_pmgr_reference {
	unsigned int index;
	struct device_node *node;
	struct device_node *pmgr;
};

struct n71_pmgr_access {
	struct platform_device *provider;
	struct regmap *map;
};

static const struct n71_pmgr_domain {
	const char *path;
	const char *label;
	u32 offset;
} n71_domains[] = {
	{ N71_PMGR_PATH "/power-controller@801a0", "i2c1", 0x801a0 },
	{ N71_PMGR_PATH "/power-controller@80158", "sio_p", 0x80158 },
	{ N71_PMGR_PATH "/power-controller@80150", "sio_busif", 0x80150 },
};

static inline int n71_pmgr_metadata(struct device_node *node, struct device_node *pmgr,
			     unsigned int index)
{
	struct device_node *parent = of_get_parent(node), *expected;
	struct of_phandle_args domain;
	const char *label;
	u32 reg[2];
	int error = -ENODEV;

	if (parent != pmgr || !of_device_is_available(node) ||
	    !of_device_is_compatible(node, "apple,s8000-pmgr-pwrstate") ||
	    !of_device_is_compatible(node, "apple,pmgr-pwrstate") ||
	    of_property_count_u32_elems(node, "reg") != 2 ||
	    of_property_read_u32_array(node, "reg", reg, 2) ||
	    reg[0] != n71_domains[index].offset || reg[1] != 4 ||
	    of_property_read_string(node, "label", &label) ||
	    strcmp(label, n71_domains[index].label))
		goto put_parent;
	if (index == 2) {
		error = of_find_property(node, "power-domains", NULL) ? -ENODEV : 0;
		goto put_parent;
	}
	if (of_count_phandle_with_args(node, "power-domains", "#power-domain-cells") != 1)
		goto put_parent;
	error = of_parse_phandle_with_args(node, "power-domains", "#power-domain-cells", 0, &domain);
	if (error)
		goto put_parent;
	expected = of_find_node_by_path(n71_domains[index + 1].path);
	if (!expected || domain.np != expected || domain.args_count)
		error = -ENODEV;
	of_node_put(expected);
	of_node_put(domain.np);
put_parent:
	of_node_put(parent);
	return error;
}


static inline int n71_pmgr_root_validate(struct device_node *pmgr)
{
	struct device_node *expected;
	struct resource resource;
	int error;

	if (!pmgr || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	expected = of_find_node_by_path(N71_PMGR_PATH);
	error = !expected || pmgr != expected ? -ENODEV : 0;
	of_node_put(expected);
	if (error)
		return error;
	if (!of_device_is_available(pmgr) ||
		!of_device_is_compatible(pmgr, "apple,s8000-pmgr") ||
		!of_device_is_compatible(pmgr, "syscon") ||
		of_find_property(pmgr, "clocks", NULL) ||
		of_find_property(pmgr, "resets", NULL))
		return -ENODEV;
	error = of_address_to_resource(pmgr, 0, &resource);
	if (error)
		return error;
	if (resource.start != 0x20e000000ULL || resource_size(&resource) != 0x8c000 ||
		resource_type(&resource) != IORESOURCE_MEM)
		return -ENODEV;
	return 0;
}

static inline void n71_pmgr_access_unlock(struct n71_pmgr_access *access)
{
	struct platform_device *provider;

	if (!access || !access->provider)
		return;
	provider = access->provider;
	access->map = NULL;
	access->provider = NULL;
	device_unlock(&provider->dev);
	put_device(&provider->dev);
}

static inline int n71_pmgr_access_lock(const struct n71_pmgr_reference *reference,
		struct n71_pmgr_access *access)
{
	struct device_node *node, *pmgr, *expected;
	struct platform_device *provider;
	struct regmap *map;
	unsigned int index;
	int error;

	if (!reference || !access || reference->index >= 3 ||
		!reference->node || !reference->pmgr)
		return -EINVAL;
	if (access->provider || access->map)
		return -EBUSY;
	node = reference->node;
	pmgr = reference->pmgr;
	index = reference->index;
	error = n71_pmgr_root_validate(pmgr);
	if (error)
		return error;
	expected = of_find_node_by_path(n71_domains[index].path);
	error = !expected || node != expected ? -ENODEV : 0;
	of_node_put(expected);
	if (error)
		return error;
	error = n71_pmgr_metadata(node, pmgr, index);
	if (error)
		return error;
	provider = of_find_device_by_node(node);
	if (!provider)
		return -ENODEV;
	device_lock(&provider->dev);
	access->provider = provider;
	if (provider->dev.of_node != node || !provider->dev.driver ||
		strcmp(provider->dev.driver->name, "apple-pmgr-pwrstate")) {
		error = -ENODEV;
		goto unlock;
	}
	/* The pinned bound provider obtained this syscon map during its probe. */
	map = syscon_node_to_regmap(pmgr);
	if (IS_ERR(map)) {
		error = PTR_ERR(map);
		goto unlock;
	}
	if (!map || regmap_get_val_bytes(map) != 4 || regmap_get_reg_stride(map) != 4) {
		error = -ENODEV;
		goto unlock;
	}
	access->map = map;
	return 0;
unlock:
	n71_pmgr_access_unlock(access);
	return error;
}

static inline int n71_pmgr_sample(const struct n71_pmgr_reference *reference,
		unsigned int words[2])
{
	struct n71_pmgr_access access = {0};
	struct regmap *map;
	unsigned int index;
	int error;

	if (!words)
		return -EINVAL;
	error = n71_pmgr_access_lock(reference, &access);
	if (error)
		return error;
	map = access.map;
	index = reference->index;
	error = regmap_read_bypassed(map, n71_domains[index].offset, &words[0]);
	if (!error)
		error = regmap_read_bypassed(map, n71_domains[index].offset, &words[1]);
	n71_pmgr_access_unlock(&access);
	return error;
}
#endif /* N71_PMGR_ACCESS_H */
