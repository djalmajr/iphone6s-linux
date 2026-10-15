// SPDX-License-Identifier: GPL-2.0-only
/* Reserve N71 I2C1 GPIO descriptors without changing direction or mux. */
#include <linux/gpio/consumer.h>
#include <linux/gpio/driver.h>
#include <linux/gpio/machine.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/slab.h>
#include <linux/string.h>

#define N71_I2C_PATH "/soc/i2c@20a111000"
#define N71_GPIO_PATH "/soc/pinctrl@20f100000"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Reserve/release I2C1 descriptors twice; no direction, mux or I2C I/O");

static const unsigned int pins[] = {115, 114};

static int n71_pin_resource(struct device_node *node, u64 base, u64 size)
{
	struct resource resource;
	int error = of_address_to_resource(node, 0, &resource);

	if (error)
		return error;
	return resource.start == base && resource_size(&resource) == size &&
		resource_type(&resource) == IORESOURCE_MEM ? 0 : -ENODEV;
}

static int n71_pin_sample(struct regmap *map, unsigned int words[2])
{
	unsigned int pin, values[4];
	int error;

	for (pin = 0; pin < ARRAY_SIZE(pins); pin++) {
		unsigned int offset = pins[pin] * 4;

		error = regmap_read(map, offset, &values[0]);
		if (!error)
			error = regmap_read_bypassed(map, offset, &values[1]);
		if (!error)
			error = regmap_read_bypassed(map, offset, &values[2]);
		if (!error)
			error = regmap_read(map, offset, &values[3]);
		if (error)
			return error;
		if (values[0] != values[1] || values[1] != values[2] || values[2] != values[3] ||
		    (values[1] & 0x260) != 0x220)
			return -EUCLEAN;
		words[pin] = values[1];
	}
	return 0;
}

static int n71_pin_same(struct regmap *map, const unsigned int expected[2])
{
	unsigned int words[2];
	int error = n71_pin_sample(map, words);

	if (!error && (words[0] != expected[0] || words[1] != expected[1]))
		error = -EUCLEAN;
	return error;
}

static int n71_pin_cycle(struct device *consumer, struct gpio_device *gdev,
			 struct regmap *map, const unsigned int before[2])
{
	struct gpio_desc *descriptors[2] = {NULL, NULL};
	unsigned int index;
	int error = 0, cleanup_error;

	for (index = 0; index < ARRAY_SIZE(pins); index++) {
		struct gpio_desc *expected = gpio_device_get_desc(gdev, pins[index]);

		if (IS_ERR(expected)) {
			error = PTR_ERR(expected);
			break;
		}
		descriptors[index] = gpiod_get_index(consumer, "pins", index, GPIOD_ASIS);
		if (IS_ERR(descriptors[index])) {
			error = PTR_ERR(descriptors[index]);
			descriptors[index] = NULL;
			break;
		}
		if (descriptors[index] != expected || gpiod_hwgpio(descriptors[index]) != pins[index]) {
			error = -ENODEV;
			break;
		}
	}
	if (!error)
		error = n71_pin_same(map, before);
	for (index = ARRAY_SIZE(pins); index > 0; index--)
		if (descriptors[index - 1])
			gpiod_put(descriptors[index - 1]);
	cleanup_error = n71_pin_same(map, before);
	pr_info("N71_I2C_PIN_CYCLE error=%d cleanup-readback-error=%d descriptors-released=1\n",
		error, cleanup_error);
	return error ? error : cleanup_error;
}

static int __init n71_i2c_pin_cycle_init(void)
{
	struct device_node *node, *gpio;
	struct platform_device *provider, *controller;
	struct i2c_adapter *adapter;
	struct gpio_device *gdev, *label_device;
	struct gpiod_lookup_table *lookup;
	struct device *consumer;
	struct regmap *map;
	const char *status, *label;
	unsigned int before[2], cycle, index;
	u32 npins;
	int error = -ENODEV;

	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	node = of_find_node_by_path(N71_I2C_PATH);
	if (!node)
		return -ENODEV;
	if (of_device_is_available(node) || of_get_child_count(node) ||
	    of_property_read_string(node, "status", &status) || strcmp(status, "disabled") ||
	    !of_device_is_compatible(node, "apple,s8000-i2c") ||
	    !of_device_is_compatible(node, "apple,i2c"))
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
	error = n71_pin_resource(node, 0x20a111000ULL, 0x1000);
	if (error)
		goto put_node;
	gpio = of_find_node_by_path(N71_GPIO_PATH);
	if (!gpio) {
		error = -ENODEV;
		goto put_node;
	}
	if (!of_device_is_available(gpio) || !of_device_is_compatible(gpio, "apple,pinctrl") ||
	    of_property_read_u32(gpio, "apple,npins", &npins) || npins != 208) {
		error = -ENODEV;
		goto put_gpio;
	}
	error = n71_pin_resource(gpio, 0x20f100000ULL, 0x100000);
	if (error)
		goto put_gpio;
	provider = of_find_device_by_node(gpio);
	if (!provider) {
		error = -ENODEV;
		goto put_gpio;
	}
	/* All API requests and cleanup occur in this task while binding is locked. */
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
	gdev = gpio_device_find_by_fwnode(of_fwnode_handle(gpio));
	if (!gdev) {
		error = -ENODEV;
		goto unlock;
	}
	label = gpio_device_get_label(gdev);
	if (!label || strcmp(label, dev_name(&provider->dev))) {
		error = -ENODEV;
		goto put_gdev;
	}
	label_device = gpio_device_find_by_label(label);
	if (label_device != gdev) {
		if (label_device)
			gpio_device_put(label_device);
		error = -ENODEV;
		goto put_gdev;
	}
	gpio_device_put(label_device);
	error = n71_pin_sample(map, before);
	if (error)
		goto put_gdev;
	consumer = root_device_register("n71-i2c1-pin-cycle");
	if (IS_ERR(consumer)) {
		error = PTR_ERR(consumer);
		goto put_gdev;
	}
	lookup = kzalloc(struct_size(lookup, table, 3), GFP_KERNEL);
	if (!lookup) {
		error = -ENOMEM;
		goto unregister;
	}
	lookup->dev_id = dev_name(consumer);
	for (index = 0; index < ARRAY_SIZE(pins); index++)
		lookup->table[index] = GPIO_LOOKUP_IDX(label, pins[index], "pins", index,
						    GPIO_LOOKUP_FLAGS_DEFAULT);
	gpiod_add_lookup_table(lookup);
	for (cycle = 0; cycle < 2; cycle++) {
		error = n71_pin_cycle(consumer, gdev, map, before);
		if (error)
			break;
	}
	gpiod_remove_lookup_table(lookup);
	kfree(lookup);
	if (!error)
		pr_info("N71_I2C_PIN_CYCLES_OK cycles=2 pins=115,114 before=%08x,%08x unchanged=1; GPIO reservation only, no mux selection or I2C activation\n",
			before[0], before[1]);
unregister:
	root_device_unregister(consumer);
put_gdev:
	gpio_device_put(gdev);
unlock:
	device_unlock(&provider->dev);
	put_device(&provider->dev);
put_gpio:
	of_node_put(gpio);
put_node:
	of_node_put(node);
	if (error)
		pr_info("N71_I2C_PIN_REFUSED error=%d; no direction/value/mux or I2C programming\n", error);
	return error;
}
module_init(n71_i2c_pin_cycle_init);

static void __exit n71_i2c_pin_cycle_exit(void)
{
	pr_info("N71_I2C_PIN_UNLOADED; no retained descriptors or lookup\n");
}
module_exit(n71_i2c_pin_cycle_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 bounded I2C1 GPIO descriptor reservation and readback cycles");
