// SPDX-License-Identifier: GPL-2.0-only
/* Observe GPIO2 through its current provider; never request or configure it. */
#include <linux/module.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/string.h>

#define N71_GPIO2_OFFSET 0x08U
#define N71_GPIO2_CONFIG_MASK 0x270U

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "One read-only GPIO2 cache/hardware observation on N71");

static int __init n71_hdq_gpio_observe_init(void)
{
	struct device_node *node;
	struct platform_device *provider;
	struct resource resource;
	struct regmap *map;
	unsigned int cached_before, hardware_first, hardware_second, cached_after;
	int error;

	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	node = of_find_node_by_path("/soc/pinctrl@20f100000");
	if (!node)
		return -ENODEV;
	if (!of_device_is_available(node) ||
	    !of_device_is_compatible(node, "apple,pinctrl")) {
		error = -ENODEV;
		goto put_node;
	}
	error = of_address_to_resource(node, 0, &resource);
	if (error)
		goto put_node;
	if (resource.start != 0x20f100000ULL ||
	    resource_size(&resource) != 0x100000 ||
	    resource_type(&resource) != IORESOURCE_MEM) {
		error = -ENODEV;
		goto put_node;
	}
	provider = of_find_device_by_node(node);
	if (!provider) {
		error = -ENODEV;
		goto put_node;
	}
	/* A device reference alone does not preserve a devm regmap on unbind. */
	device_lock(&provider->dev);
	if (provider->dev.of_node != node || !provider->dev.driver ||
	    strcmp(provider->dev.driver->name, "apple-gpio-pinctrl")) {
		error = -ENODEV;
		goto unlock;
	}
	map = dev_get_regmap(&provider->dev, NULL);
	if (!map || regmap_get_val_bytes(map) != 4 ||
	    regmap_get_reg_stride(map) != 4) {
		error = -ENODEV;
		goto unlock;
	}
	error = regmap_read(map, N71_GPIO2_OFFSET, &cached_before);
	if (!error)
		error = regmap_read_bypassed(map, N71_GPIO2_OFFSET, &hardware_first);
	if (!error)
		error = regmap_read_bypassed(map, N71_GPIO2_OFFSET, &hardware_second);
	if (!error)
		error = regmap_read(map, N71_GPIO2_OFFSET, &cached_after);
	if (!error) {
		pr_info("N71_HDQ_GPIO2 cached-before=%08x hardware-first=%08x hardware-second=%08x cached-after=%08x; no writes\n",
			cached_before, hardware_first, hardware_second, cached_after);
		pr_info("N71_HDQ_GPIO2_CONFIG mask=270 hardware=%03x stable=%u cache-matches=%u; no ownership claim\n",
			hardware_second & N71_GPIO2_CONFIG_MASK,
			!((hardware_first ^ hardware_second) & N71_GPIO2_CONFIG_MASK),
			!((cached_after ^ hardware_second) & N71_GPIO2_CONFIG_MASK));
	}
unlock:
	device_unlock(&provider->dev);
	put_device(&provider->dev);
put_node:
	of_node_put(node);
	if (error)
		pr_info("N71_HDQ_GPIO2_REFUSED error=%d; no writes\n", error);
	return error;
}
module_init(n71_hdq_gpio_observe_init);

static void __exit n71_hdq_gpio_observe_exit(void)
{
	pr_info("N71_HDQ_GPIO2_UNLOADED; no writes or ownership changes\n");
}
module_exit(n71_hdq_gpio_observe_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 GPIO2 cached and bypassed observation through its existing provider");
