// SPDX-License-Identifier: GPL-2.0-only
/* Share the existing simple-MFD regmap; never replace the PMIC owner. */
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of_address.h>
#include <linux/regmap.h>
#include <linux/string.h>
#include "n71-wlan-power.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Observe N71 REG_ON through the existing simple-MFD regmap");
static DEFINE_MUTEX(control_lock);
static struct i2c_client *owned_client;
static struct n71_wlan_power_state power_state;
static struct regmap *shared_map;

/* Hold the parent device lock until each regmap operation has finished.
 * devm can free the map on unbind: a retained client reference alone is not
 * sufficient. Revalidate both the exact driver and map on every operation.
 */
static bool n71_map_owned(struct i2c_client *client)
{
	return client->dev.driver &&
		!strcmp(client->dev.driver->name, "simple-mfd-i2c") &&
		shared_map && dev_get_regmap(&client->dev, NULL) == shared_map;
}

static int n71_reg_on_read(void *context, unsigned char *value)
{
	struct i2c_client *client = context;
	unsigned int raw = 0;
	int error = -ENODEV;

	device_lock(&client->dev);
	if (n71_map_owned(client)) {
		error = regmap_read(shared_map, N71_WLAN_REG_ON_REGISTER, &raw);
		if (!error && raw > 0xff)
			error = -ERANGE;
		if (!error)
			*value = raw;
	}
	pr_info("N71_REG_ON_READ error=%d value_valid=%u value=%02x\n",
		error, !error, raw);
	device_unlock(&client->dev);
	return error;
}

static int n71_reg_on_write(void *context, unsigned char value)
{
	struct i2c_client *client = context;
	unsigned int raw = 0;
	unsigned char bit;
	int error = -ENODEV;

	device_lock(&client->dev);
	if (n71_map_owned(client)) {
		/* Never write mode/drive bits, even if a concurrent reader exists. */
		error = regmap_read(shared_map, N71_WLAN_REG_ON_REGISTER, &raw);
		if (!error && !n71_wlan_shared_write_plan(raw, value, &bit))
			error = -EBUSY;
		if (!error)
			error = regmap_update_bits(shared_map, N71_WLAN_REG_ON_REGISTER,
					   1, bit);
	}
	pr_info("N71_REG_ON_WRITE requested=%02x prior=%02x error=%d; mask=01\n",
		(unsigned int)value, raw, error);
	device_unlock(&client->dev);
	return error;
}

static struct n71_wlan_power_io power_io = {
	.read = n71_reg_on_read,
	.write = n71_reg_on_write,
};

static int n71_validate_client(struct i2c_client *client)
{
	struct device_node *node = client->dev.of_node, *expected;
	struct resource bus;
	u32 address;
	int error;
	if (!run || !of_machine_is_compatible("apple,n71") || !node ||
	    client->addr != N71_WLAN_PMU_ADDRESS || client->flags & I2C_CLIENT_TEN ||
	    !i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -ENODEV;
	expected = of_find_node_by_path("/soc/i2c@20a110000/pmic@74");
	error = node == expected ? 0 : -ENODEV;
	of_node_put(expected);
	if (error || client->adapter->dev.of_node != node->parent ||
	    !of_device_is_compatible(node, "apple,antigua-pmic") ||
	    !of_device_is_compatible(node, "apple,i2c-pmic") || !of_device_is_available(node))
		return -ENODEV;
	error = of_address_to_resource(node->parent, 0, &bus);
	if (!error)
		error = of_property_read_u32(node, "reg", &address);
	if (!error && (bus.start != 0x20a110000ULL || address != N71_WLAN_PMU_ADDRESS))
		error = -ENODEV;
	return error;
}

static int n71_power_set(const char *text, const struct kernel_param *parameter)
{
	bool enabled;
	int error = kstrtobool(text, &enabled);
	if (error)
		return error;
	mutex_lock(&control_lock);
	/* Refuse insmod power arguments: inspect the bound client first. */
	if (!owned_client)
		error = -ENODEV;
	else
		error = enabled ? n71_wlan_power_acquire(&power_io, &power_state) :
			n71_wlan_power_release(&power_io, &power_state);
	pr_info("N71_REG_ON_CONTROL requested=%u error=%d active=%u restore_pending=%u\n",
		enabled, error, power_state.active, power_state.restore_pending);
	mutex_unlock(&control_lock);
	return error;
}

static int n71_power_get(char *buffer, const struct kernel_param *parameter)
{
	int length;
	mutex_lock(&control_lock);
	length = scnprintf(buffer, PAGE_SIZE, "%u\n", power_state.active);
	mutex_unlock(&control_lock);
	return length;
}

static int n71_state_get(char *buffer, const struct kernel_param *parameter)
{
	int length;
	mutex_lock(&control_lock);
	length = scnprintf(buffer, PAGE_SIZE, "bound=%u active=%u restore_pending=%u original=%02x\n",
		!!owned_client, power_state.active, power_state.restore_pending,
		(unsigned int)power_state.original);
	mutex_unlock(&control_lock);
	return length;
}

/* Apple's N71 GPIO read helper selects 0x180 + ((0x600 + pin*32)>>8),
 * bit(pin&7): GPIO10 uses register0x187/bit2. Read only; no set-mode call.
 */
static int n71_level_get(char *buffer, const struct kernel_param *parameter)
{
	unsigned int raw = 0;
	int error = -ENODEV;
	mutex_lock(&control_lock);
	if (owned_client) {
		device_lock(&owned_client->dev);
		if (n71_map_owned(owned_client)) {
			error = regmap_read(shared_map, 0x187, &raw);
			if (!error && raw > 0xff)
				error = -ERANGE;
		}
		device_unlock(&owned_client->dev);
	}
	if (!error)
		error = scnprintf(buffer, PAGE_SIZE, "N71_REG_ON_LEVEL raw=%02x bit2=%u\n",
			raw, !!(raw & 4));
	mutex_unlock(&control_lock);
	return error;
}

static const struct kernel_param_ops level_ops = {.get = n71_level_get};
module_param_cb(level, &level_ops, NULL, 0400);
MODULE_PARM_DESC(level, "Read only GPIO10 level from the pinned Apple status-bank mapping");

static const struct kernel_param_ops power_ops = {.set = n71_power_set, .get = n71_power_get};
static const struct kernel_param_ops state_ops = {.get = n71_state_get};
module_param_cb(power, &power_ops, NULL, 0600);
MODULE_PARM_DESC(power, "After observation: 1 asserts REG_ON; 0 verifies original restoration");
module_param_cb(state, &state_ops, NULL, 0400);
MODULE_PARM_DESC(state, "Check ownership, activation and pending restoration before unload");

static int __init n71_power_init(void)
{
	struct device_node *node;
	struct i2c_client *client;
	unsigned char value = 0, planned;
	int error;

	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	node = of_find_node_by_path("/soc/i2c@20a110000/pmic@74");
	client = node ? of_find_i2c_device_by_node(node) : NULL;
	of_node_put(node);
	if (!client)
		return -ENODEV;
	device_lock(&client->dev);
	error = n71_validate_client(client);
	if (!error && (!client->dev.driver ||
			strcmp(client->dev.driver->name, "simple-mfd-i2c")))
		error = -EBUSY;
	if (!error) {
		shared_map = dev_get_regmap(&client->dev, NULL);
		if (!shared_map || regmap_get_val_bytes(shared_map) != 1 ||
		    regmap_get_reg_stride(shared_map) != 1)
			error = -ENODEV;
	}
	device_unlock(&client->dev);
	if (!error)
		error = n71_reg_on_read(client, &value);
	if (error) {
		shared_map = NULL;
		put_device(&client->dev);
		return error;
	}
	owned_client = client; /* Keep the device reference until module exit. */
	power_io.context = client;
	pr_info("N71_REG_ON_PARENT simple-mfd-i2c shared-regmap; no rebind\n");
	pr_info("N71_REG_ON_OBSERVED control=%02x bit0=%u compatible-plan=%u; no value write\n",
		(unsigned int)value, (unsigned int)(value & 1),
		(unsigned int)n71_wlan_reg_on_plan(N71_WLAN_REG_ON_REGISTER,
			value, true, &planned));
	return 0;
}

module_init(n71_power_init);
static void __exit n71_power_exit(void)
{
	int error;
	mutex_lock(&control_lock);
	error = n71_wlan_power_release(&power_io, &power_state);
	pr_info("N71_REG_ON_REMOVE error=%d restore_pending=%u; parent retained\n",
		error, power_state.restore_pending);
	put_device(&owned_client->dev);
	owned_client = NULL;
	power_io.context = NULL;
	shared_map = NULL;
	mutex_unlock(&control_lock);
}
module_exit(n71_power_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 REG_ON observation and reversible bit0 via parent MFD regmap");
