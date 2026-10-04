// SPDX-License-Identifier: GPL-2.0-only
/* Observe I2C1 PMGR states through the already initialized syscon provider. */
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/string.h>

#define N71_PMGR_PATH "/soc/power-management@20e000000"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Observe existing N71 I2C1/sio_p/sio_busif states; no activation");

static const struct n71_pmgr_domain {
	const char *path;
	const char *label;
	u32 offset;
} n71_domains[] = {
	{ N71_PMGR_PATH "/power-controller@801a0", "i2c1", 0x801a0 },
	{ N71_PMGR_PATH "/power-controller@80158", "sio_p", 0x80158 },
	{ N71_PMGR_PATH "/power-controller@80150", "sio_busif", 0x80150 },
};

static int n71_pmgr_metadata(struct device_node *node, struct device_node *pmgr,
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

static int n71_pmgr_sample(struct device_node *node, struct device_node *pmgr,
			  unsigned int index, unsigned int words[2])
{
	struct platform_device *provider;
	struct regmap *map;
	int error = n71_pmgr_metadata(node, pmgr, index);

	if (error)
		return error;
	provider = of_find_device_by_node(node);
	if (!provider)
		return -ENODEV;
	device_lock(&provider->dev);
	if (provider->dev.of_node != node || !provider->dev.driver ||
	    strcmp(provider->dev.driver->name, "apple-pmgr-pwrstate")) {
		error = -ENODEV;
		goto unlock;
	}
	/* This pinned driver's successful probe obtained this parent's syscon map.
	 * The device lock excludes probing/unbinding while checking its binding.
	 */
	map = syscon_node_to_regmap(pmgr);
	if (IS_ERR(map)) {
		error = PTR_ERR(map);
		goto unlock;
	}
	if (!map || regmap_get_val_bytes(map) != 4 || regmap_get_reg_stride(map) != 4) {
		error = -ENODEV;
		goto unlock;
	}
	error = regmap_read_bypassed(map, n71_domains[index].offset, &words[0]);
	if (!error)
		error = regmap_read_bypassed(map, n71_domains[index].offset, &words[1]);
unlock:
	device_unlock(&provider->dev);
	put_device(&provider->dev);
	return error;
}

static int __init n71_pmgr_power_observe_init(void)
{
	struct device_node *pmgr, *node;
	struct resource resource;
	unsigned int words[3][2], index;
	int error = -ENODEV;

	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	pmgr = of_find_node_by_path(N71_PMGR_PATH);
	if (!pmgr)
		return -ENODEV;
	if (!of_device_is_available(pmgr) ||
	    !of_device_is_compatible(pmgr, "apple,s8000-pmgr") ||
	    !of_device_is_compatible(pmgr, "syscon") ||
	    of_find_property(pmgr, "clocks", NULL) ||
	    of_find_property(pmgr, "resets", NULL))
		goto put_pmgr;
	error = of_address_to_resource(pmgr, 0, &resource);
	if (error)
		goto put_pmgr;
	if (resource.start != 0x20e000000ULL || resource_size(&resource) != 0x8c000 ||
	    resource_type(&resource) != IORESOURCE_MEM) {
		error = -ENODEV;
		goto put_pmgr;
	}
	for (index = 0; index < 3; index++) {
		node = of_find_node_by_path(n71_domains[index].path);
		if (!node) {
			error = -ENODEV;
			goto put_pmgr;
		}
		error = n71_pmgr_sample(node, pmgr, index, words[index]);
		of_node_put(node);
		if (error)
			goto put_pmgr;
	}
	for (index = 0; index < 3; index++)
		pr_info("N71_PMGR domain=%s offset=%05x sample0=%08x sample1=%08x stable=%u\n",
			n71_domains[index].label, n71_domains[index].offset,
			words[index][0], words[index][1], words[index][0] == words[index][1]);
	pr_info("N71_PMGR_OBSERVED writes=0 reads=6 atomic-chain=0 ownership=0\n");
put_pmgr:
	of_node_put(pmgr);
	return error;
}

static void __exit n71_pmgr_power_observe_exit(void)
{
	pr_info("N71_PMGR_UNLOADED hardware-changes=0\n");
}
module_init(n71_pmgr_power_observe_init);
module_exit(n71_pmgr_power_observe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 bounded PMGR observation without domain activation");
