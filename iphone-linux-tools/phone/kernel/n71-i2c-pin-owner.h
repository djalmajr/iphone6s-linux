/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller owns the qualified root consumer and serializes acquire/verify/release. */
#ifndef N71_I2C_PIN_OWNER_H
#define N71_I2C_PIN_OWNER_H
#include <linux/device.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/driver.h>
#include <linux/gpio/machine.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/pinctrl/consumer.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/slab.h>
#include <linux/string.h>
#include "n71-i2c-pin-owner-of.h"

struct n71_i2c_pin_owner {
	int cleanup_error;
	bool cleanup_pending;
	struct device *consumer;
	struct gpio_desc *descriptors[2];
	struct gpio_device *gdev;
	struct device_node *gpio;
	struct gpiod_lookup_table *lookup;
	struct pinctrl *pinctrl;
	struct platform_device *provider;
	u32 saved[2];
	bool selected;
};

static inline bool n71_i2c_pin_owner_clean(const struct n71_i2c_pin_owner *owner)
{
	return !owner->consumer && !owner->descriptors[0] && !owner->descriptors[1] &&
		!owner->gdev && !owner->gpio && !owner->lookup && !owner->pinctrl &&
		!owner->provider && !owner->cleanup_pending && !owner->selected;
}

/* Success leaves the device locked and the map valid only in this task. */
static inline int n71_i2c_pin_owner_map(struct n71_i2c_pin_owner *owner,
					struct regmap **map)
{
	struct device *device = &owner->provider->dev;
	struct gpio_device *registered_gdev;
	int error = -ENODEV;

	device_lock(device);
	if (device->of_node != owner->gpio || !device->driver ||
	    strcmp(device->driver->name, "apple-gpio-pinctrl") ||
	    !device->driver->suppress_bind_attrs)
		goto failed;
	*map = dev_get_regmap(device, NULL);
	if (!*map || regmap_get_val_bytes(*map) != 4 || regmap_get_reg_stride(*map) != 4)
		goto failed;
	if (owner->gdev) {
		registered_gdev = gpio_device_find_by_fwnode(of_fwnode_handle(owner->gpio));
		if (registered_gdev != owner->gdev) {
			if (registered_gdev)
				gpio_device_put(registered_gdev);
			goto failed;
		}
		gpio_device_put(registered_gdev);
	}
	return 0;
failed:
	device_unlock(device);
	return error;
}

static inline int n71_i2c_pin_owner_sample(struct regmap *map, u32 words[2])
{
	unsigned int pin, values[4];
	int error;

	for (pin = 0; pin < 2; pin++) {
		unsigned int offset = (115 - pin) * 4;

		error = regmap_read(map, offset, &values[0]);
		if (!error)
			error = regmap_read_bypassed(map, offset, &values[1]);
		if (!error)
			error = regmap_read_bypassed(map, offset, &values[2]);
		if (!error)
			error = regmap_read(map, offset, &values[3]);
		if (error)
			return error;
		if (values[0] != values[1] || values[1] != values[2] ||
		    values[2] != values[3] || (values[1] & 0x270) != 0x220)
			return -EUCLEAN;
		words[pin] = values[1];
	}
	return 0;
}

static inline int n71_i2c_pin_owner_same(struct n71_i2c_pin_owner *owner,
					 struct regmap *map)
{
	u32 words[2];
	int error = n71_i2c_pin_owner_sample(map, words);

	return error ? error : words[0] != owner->saved[0] || words[1] != owner->saved[1] ?
		-EUCLEAN : 0;
}

static inline void n71_i2c_pin_owner_drop_handles(struct n71_i2c_pin_owner *owner)
{
	unsigned int index;

	if (owner->pinctrl) {
		pinctrl_put(owner->pinctrl);
		owner->pinctrl = NULL;
		owner->selected = false;
	}
	for (index = 2; index > 0; index--) {
		if (owner->descriptors[index - 1]) {
			gpiod_put(owner->descriptors[index - 1]);
			owner->descriptors[index - 1] = NULL;
		}
	}
	if (owner->lookup) {
		gpiod_remove_lookup_table(owner->lookup);
		kfree(owner->lookup);
		owner->lookup = NULL;
	}
}

static inline int n71_i2c_pin_owner_release(struct n71_i2c_pin_owner *owner)
{
	struct regmap *map;
	int error;

	if (!owner)
		return -EINVAL;
	if (owner->cleanup_pending) {
		error = n71_i2c_pin_owner_map(owner, &map);
		if (error)
			goto pending;
		error = n71_i2c_pin_owner_same(owner, map);
		if (!error) {
			n71_i2c_pin_owner_drop_handles(owner);
			error = n71_i2c_pin_owner_same(owner, map);
		}
		device_unlock(&owner->provider->dev);
		if (error)
			goto pending;
		owner->cleanup_pending = false;
	} else {
		n71_i2c_pin_owner_drop_handles(owner);
	}
	if (owner->gdev) {
		gpio_device_put(owner->gdev);
		owner->gdev = NULL;
	}
	if (owner->provider) {
		put_device(&owner->provider->dev);
		owner->provider = NULL;
	}
	of_node_put(owner->gpio);
	owner->gpio = NULL;
	owner->consumer = NULL;
	owner->cleanup_error = 0;
	return 0;
pending:
	owner->cleanup_error = error;
	return error;
}

static inline int n71_i2c_pin_owner_verify(void *context)
{
	struct n71_i2c_pin_owner *owner = context;
	struct regmap *map;
	unsigned int index;
	int error;

	if (!owner || !owner->cleanup_pending || !owner->selected || !owner->pinctrl ||
	    !owner->descriptors[0] || !owner->descriptors[1])
		return -EINVAL;
	error = n71_i2c_pin_owner_map(owner, &map);
	if (error)
		return error;
	for (index = 0; index < 2; index++) {
		if (gpio_device_get_desc(owner->gdev, 115 - index) != owner->descriptors[index] ||
		    gpiod_hwgpio(owner->descriptors[index]) != 115 - index) {
			error = -ENODEV;
			goto unlock;
		}
	}
	error = n71_i2c_pin_owner_same(owner, map);
unlock:
	device_unlock(&owner->provider->dev);
	return error;
}

static inline int n71_i2c_pin_owner_acquire(struct device *consumer,
					    struct n71_i2c_pin_owner *owner)
{
	struct gpio_device *label_device;
	struct pinctrl_state *state;
	struct regmap *map;
	const char *label;
	unsigned int index;
	int error;

	if (!owner)
		return -EINVAL;
	if (!n71_i2c_pin_owner_clean(owner))
		return -EBUSY;
	owner->consumer = consumer;
	error = n71_i2c_pin_owner_node(consumer, &owner->gpio);
	if (error)
		goto failed;
	owner->provider = of_find_device_by_node(owner->gpio);
	if (!owner->provider) {
		error = -ENODEV;
		goto failed;
	}
	error = n71_i2c_pin_owner_map(owner, &map);
	if (error)
		goto failed;
	owner->gdev = gpio_device_find_by_fwnode(of_fwnode_handle(owner->gpio));
	if (!owner->gdev) {
		error = -ENODEV;
		goto unlock;
	}
	label = gpio_device_get_label(owner->gdev);
	if (!label || strcmp(label, dev_name(&owner->provider->dev))) {
		error = -ENODEV;
		goto unlock;
	}
	label_device = gpio_device_find_by_label(label);
	error = label_device != owner->gdev ? -ENODEV : 0;
	if (label_device)
		gpio_device_put(label_device);
	if (error)
		goto unlock;
	error = n71_i2c_pin_owner_sample(map, owner->saved);
	if (error)
		goto unlock;
	owner->cleanup_pending = true;
	owner->lookup = kzalloc(struct_size(owner->lookup, table, 3), GFP_KERNEL);
	if (!owner->lookup) {
		error = -ENOMEM;
		goto unlock;
	}
	owner->lookup->dev_id = dev_name(consumer);
	for (index = 0; index < 2; index++)
		owner->lookup->table[index] = GPIO_LOOKUP_IDX(label, 115 - index, "pins", index,
							      GPIO_LOOKUP_FLAGS_DEFAULT);
	gpiod_add_lookup_table(owner->lookup);
	for (index = 0; index < 2; index++) {
		struct gpio_desc *expected = gpio_device_get_desc(owner->gdev, 115 - index);
		struct gpio_desc *descriptor;

		if (IS_ERR(expected)) {
			error = PTR_ERR(expected);
			goto unlock;
		}
		descriptor = gpiod_get_index(consumer, "pins", index, GPIOD_ASIS);
		if (IS_ERR(descriptor)) {
			error = PTR_ERR(descriptor);
			goto unlock;
		}
		owner->descriptors[index] = descriptor;
		if (descriptor != expected || gpiod_hwgpio(descriptor) != 115 - index) {
			error = -ENODEV;
			goto unlock;
		}
	}
	owner->pinctrl = pinctrl_get(consumer);
	if (IS_ERR(owner->pinctrl)) {
		error = PTR_ERR(owner->pinctrl);
		owner->pinctrl = NULL;
		goto unlock;
	}
	state = pinctrl_lookup_state(owner->pinctrl, "default");
	if (IS_ERR(state)) {
		error = PTR_ERR(state);
		goto unlock;
	}
	error = pinctrl_select_state(owner->pinctrl, state);
	if (!error)
		error = n71_i2c_pin_owner_same(owner, map);
	if (!error)
		owner->selected = true;
unlock:
	device_unlock(&owner->provider->dev);
	if (!error)
		return 0;
failed:
	n71_i2c_pin_owner_release(owner);
	return error;
}
#endif /* N71_I2C_PIN_OWNER_H */
