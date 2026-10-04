// SPDX-License-Identifier: GPL-2.0-only
/* Observe the disabled I2C1 declaration and its existing GPIO provider. */
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of_address.h>
#include <linux/of_irq.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/string.h>

#define N71_I2C1_PATH "/soc/i2c@20a111000"
#define N71_GPIO_PATH "/soc/pinctrl@20f100000"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Observe N71 I2C1 DT and GPIO114/115; no activation or I2C I/O");

static bool n71_observe_path(struct device_node *node, const char *path)
{
	struct device_node *expected = of_find_node_by_path(path);
	bool matches = expected && node == expected;

	of_node_put(expected);
	return matches;
}

static int n71_observe_resource(struct device_node *node, u64 base, u64 size)
{
	struct resource resource;
	int error = of_address_to_resource(node, 0, &resource);

	if (error)
		return error;
	if (resource.start != base || resource_size(&resource) != size ||
	    resource_type(&resource) != IORESOURCE_MEM)
		return -ENODEV;
	return 0;
}

static int n71_observe_irq(struct device_node *node)
{
	struct of_phandle_args irq;
	int error;

	if (of_property_count_u32_elems(node, "interrupts") != 3)
		return -ENODEV;
	error = of_irq_parse_one(node, 0, &irq);
	if (error)
		return error;
	if (irq.args_count != 3 || irq.args[0] != 0 || irq.args[1] != 207 ||
	    irq.args[2] != 4 || !of_device_is_available(irq.np) ||
	    !of_device_is_compatible(irq.np, "apple,s8000-aic"))
		error = -ENODEV;
	else
		error = n71_observe_resource(irq.np, 0x20e100000ULL, 0x100000);
	of_node_put(irq.np);
	return error;
}

static int n71_observe_clock(struct device_node *node)
{
	struct of_phandle_args clock;
	u32 frequency;
	int error;

	if (of_count_phandle_with_args(node, "clocks", "#clock-cells") != 1)
		return -ENODEV;
	error = of_parse_phandle_with_args(node, "clocks", "#clock-cells", 0, &clock);
	if (error)
		return error;
	if (clock.args_count || !n71_observe_path(clock.np, "/clock-ref") ||
	    !of_device_is_available(clock.np) ||
	    !of_device_is_compatible(clock.np, "fixed-clock") ||
	    of_property_count_u32_elems(clock.np, "clock-frequency") != 1 ||
	    of_property_read_u32(clock.np, "clock-frequency", &frequency) ||
	    frequency != 24000000)
		error = -ENODEV;
	of_node_put(clock.np);
	return error;
}

static int n71_observe_domain(struct device_node *node)
{
	struct of_phandle_args domain;
	u32 reg[2];
	int error;

	if (of_count_phandle_with_args(node, "power-domains", "#power-domain-cells") != 1)
		return -ENODEV;
	error = of_parse_phandle_with_args(node, "power-domains", "#power-domain-cells", 0, &domain);
	if (error)
		return error;
	if (domain.args_count ||
	    !n71_observe_path(domain.np, "/soc/power-management@20e000000/power-controller@801a0") ||
	    !of_device_is_available(domain.np) ||
	    !of_device_is_compatible(domain.np, "apple,s8000-pmgr-pwrstate") ||
	    of_property_count_u32_elems(domain.np, "reg") != 2 ||
	    of_property_read_u32_array(domain.np, "reg", reg, 2) ||
	    reg[0] != 0x801a0 || reg[1] != 4)
		error = -ENODEV;
	of_node_put(domain.np);
	return error;
}

static int n71_observe_pins(struct device_node *node, struct device_node *gpio)
{
	struct of_phandle_args pins;
	struct device_node *parent;
	const char *name;
	u32 mux[2];
	int error;

	if (of_count_phandle_with_args(node, "pinctrl-0", NULL) != 1 ||
	    of_property_count_strings(node, "pinctrl-names") != 1 ||
	    of_property_read_string(node, "pinctrl-names", &name) ||
	    strcmp(name, "default"))
		return -ENODEV;
	error = of_parse_phandle_with_args(node, "pinctrl-0", NULL, 0, &pins);
	if (error)
		return error;
	parent = of_get_parent(pins.np);
	if (pins.args_count || parent != gpio ||
	    !n71_observe_path(pins.np, N71_GPIO_PATH "/i2c1-pins") ||
	    !of_device_is_available(pins.np) ||
	    of_property_count_u32_elems(pins.np, "pinmux") != 2 ||
	    of_property_read_u32_array(pins.np, "pinmux", mux, 2) ||
	    mux[0] != 0x10073 || mux[1] != 0x10072)
		error = -ENODEV;
	of_node_put(parent);
	of_node_put(pins.np);
	return error;
}

static int __init n71_i2c_topology_observe_init(void)
{
	struct device_node *node, *gpio;
	struct platform_device *provider, *controller;
	struct i2c_adapter *adapter;
	struct regmap *map;
	const char *status;
	unsigned int words[2][4], pin;
	int error = -ENODEV;

	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	node = of_find_node_by_path(N71_I2C1_PATH);
	if (!node)
		return -ENODEV;
	if (of_device_is_available(node) ||
	    of_property_read_string(node, "status", &status) || strcmp(status, "disabled") ||
	    !of_device_is_compatible(node, "apple,s8000-i2c") ||
	    !of_device_is_compatible(node, "apple,i2c") || of_get_child_count(node))
		goto put_node;
	controller = of_find_device_by_node(node);
	if (controller) {
		put_device(&controller->dev);
		error = -EBUSY;
		goto put_node;
	}
	adapter = of_find_i2c_adapter_by_node(node);
	if (adapter) {
		put_device(&adapter->dev);
		error = -EBUSY;
		goto put_node;
	}
	error = n71_observe_resource(node, 0x20a111000ULL, 0x1000);
	if (!error)
		error = n71_observe_irq(node);
	if (!error)
		error = n71_observe_clock(node);
	if (!error)
		error = n71_observe_domain(node);
	if (error)
		goto put_node;
	gpio = of_find_node_by_path(N71_GPIO_PATH);
	if (!gpio) {
		error = -ENODEV;
		goto put_node;
	}
	if (!of_device_is_available(gpio) || !of_device_is_compatible(gpio, "apple,pinctrl")) {
		error = -ENODEV;
		goto put_gpio;
	}
	error = n71_observe_resource(gpio, 0x20f100000ULL, 0x100000);
	if (!error)
		error = n71_observe_pins(node, gpio);
	if (error)
		goto put_gpio;
	provider = of_find_device_by_node(gpio);
	if (!provider) {
		error = -ENODEV;
		goto put_gpio;
	}
	/* Keep its devm regmap alive while an unbind would otherwise free it. */
	device_lock(&provider->dev);
	if (provider->dev.of_node != gpio || !provider->dev.driver ||
	    strcmp(provider->dev.driver->name, "apple-gpio-pinctrl")) {
		error = -ENODEV;
		goto unlock;
	}
	map = dev_get_regmap(&provider->dev, NULL);
	if (!map || regmap_get_val_bytes(map) != 4 || regmap_get_reg_stride(map) != 4) {
		error = -ENODEV;
		goto unlock;
	}
	for (pin = 0; pin < 2; pin++) {
		unsigned int offset = (114 + pin) * 4;

		error = regmap_read(map, offset, &words[pin][0]);
		if (!error)
			error = regmap_read_bypassed(map, offset, &words[pin][1]);
		if (!error)
			error = regmap_read_bypassed(map, offset, &words[pin][2]);
		if (!error)
			error = regmap_read(map, offset, &words[pin][3]);
		if (error)
			goto unlock;
	}
	for (pin = 0; pin < 2; pin++)
		pr_info("N71_I2C1_GPIO pin=%u cached-before=%08x hardware-first=%08x hardware-second=%08x cached-after=%08x stable=%u cache-matches=%u\n",
			114 + pin, words[pin][0], words[pin][1], words[pin][2], words[pin][3],
			words[pin][1] == words[pin][2], words[pin][3] == words[pin][2]);
	pr_info("N71_I2C1_OBSERVED disabled=1 children=0 platform=absent adapter=absent base=20a111000 size=1000 raw-irq=0,207,4 declared-clock-hz=24000000 domain-reg=801a0,4 declared-pinmux=10073,10072; no writes, activation or ownership claim\n");
unlock:
	device_unlock(&provider->dev);
	put_device(&provider->dev);
put_gpio:
	of_node_put(gpio);
put_node:
	of_node_put(node);
	if (error)
		pr_info("N71_I2C1_REFUSED error=%d; no writes or activation\n", error);
	return error;
}
module_init(n71_i2c_topology_observe_init);

static void __exit n71_i2c_topology_observe_exit(void)
{
	pr_info("N71_I2C1_UNLOADED; no writes or activation\n");
}
module_exit(n71_i2c_topology_observe_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 passive I2C1 DT and cached/bypassed GPIO114/115 observation");
