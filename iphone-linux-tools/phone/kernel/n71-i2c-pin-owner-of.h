/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_I2C_PIN_OWNER_OF_H
#define N71_I2C_PIN_OWNER_OF_H
#include <linux/device.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/string.h>

static inline int n71_i2c_pin_owner_dt(struct device_node *node,
				       struct device_node *gpio)
{
	struct device_node *group, *expected, *parent;
	const char *name;
	u32 cells[2];
	int error;

	if (of_property_count_strings(node, "pinctrl-names") != 1 ||
	    of_property_read_string(node, "pinctrl-names", &name) || strcmp(name, "default") ||
	    of_find_property(node, "pinctrl-1", NULL) ||
	    of_find_property(node, "pins-gpios", NULL) ||
	    of_find_property(node, "pins-gpio", NULL) ||
	    of_count_phandle_with_args(node, "pinctrl-0", NULL) != 1)
		return -ENODEV;
	group = of_parse_phandle(node, "pinctrl-0", 0);
	expected = of_find_node_by_path("/soc/pinctrl@20f100000/i2c1-pins");
	parent = group ? of_get_parent(group) : NULL;
	error = !group || group != expected || parent != gpio ||
		of_property_count_u32_elems(group, "pinmux") != 2 ||
		of_property_read_u32_array(group, "pinmux", cells, 2) ||
		cells[0] != 0x10073 || cells[1] != 0x10072 ? -ENODEV : 0;
	of_node_put(parent);
	of_node_put(expected);
	of_node_put(group);
	return error;
}

/* Success owns one GPIO node reference; failure leaves no reference. */
static inline int n71_i2c_pin_owner_node(struct device *consumer,
					 struct device_node **gpio)
{
	struct device_node *expected;
	struct resource resource;
	u32 npins;
	int error;

	*gpio = NULL;
	if (!consumer || !consumer->of_node || consumer->bus || consumer->driver ||
	    consumer->pm_domain || !device_is_registered(consumer) ||
	    !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	expected = of_find_node_by_path("/soc/i2c@20a111000");
	error = !expected || expected != consumer->of_node ? -ENODEV : 0;
	of_node_put(expected);
	if (error)
		return error;
	*gpio = of_find_node_by_path("/soc/pinctrl@20f100000");
	if (!*gpio)
		return -ENODEV;
	error = n71_i2c_pin_owner_dt(consumer->of_node, *gpio);
	if (error)
		goto failed;
	if (!of_device_is_available(*gpio) ||
	    !of_device_is_compatible(*gpio, "apple,pinctrl") ||
	    of_property_read_u32(*gpio, "apple,npins", &npins) || npins != 208) {
		error = -ENODEV;
		goto failed;
	}
	error = of_address_to_resource(*gpio, 0, &resource);
	if (error)
		goto failed;
	if (resource.start != 0x20f100000ULL || resource_size(&resource) != 0x100000 ||
	    resource_type(&resource) != IORESOURCE_MEM) {
		error = -ENODEV;
		goto failed;
	}
	return 0;
failed:
	of_node_put(*gpio);
	*gpio = NULL;
	return error;
}
#endif /* N71_I2C_PIN_OWNER_OF_H */
