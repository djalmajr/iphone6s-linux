// SPDX-License-Identifier: GPL-2.0-only
/* One explicit REG_ON observation. No PMIC value, mode or charger writes. */
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of_address.h>
#include "n71-wlan-power-contract.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Explicitly read the N71 WLAN PMIC GPIO10 control byte");

static int n71_observe_reg_on(struct i2c_client *client, unsigned char *value)
{
	unsigned char address[2];
	struct i2c_msg messages[] = {
		{.addr = N71_WLAN_PMU_ADDRESS, .len = 2, .buf = address},
		{.addr = N71_WLAN_PMU_ADDRESS, .flags = I2C_M_RD, .len = 1, .buf = value},
	};
	int result;

	if (client->addr != N71_WLAN_PMU_ADDRESS || client->flags & I2C_CLIENT_TEN ||
	    !i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -ENODEV;
	n71_wlan_reg_on_address(address);
	/* The first message selects address08fc; it contains no value byte. */
	result = i2c_transfer(client->adapter, messages, ARRAY_SIZE(messages));
	return result == ARRAY_SIZE(messages) ? 0 : result < 0 ? result : -EIO;
}

static int __init n71_power_init(void)
{
	struct device_node *node;
	struct i2c_client *client;
	struct resource bus;
	unsigned char value = 0, planned;
	u32 address;
	int error;

	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	node = of_find_node_by_path("/soc/i2c@20a110000/pmic@74");
	if (!node)
		return -ENODEV;
	error = of_address_to_resource(node->parent, 0, &bus);
	if (!error)
		error = of_property_read_u32(node, "reg", &address);
	if (!error && (!of_device_is_compatible(node, "apple,antigua-pmic") ||
		      !of_device_is_available(node) || bus.start != 0x20a110000ULL ||
		      address != N71_WLAN_PMU_ADDRESS))
		error = -ENODEV;
	client = error ? NULL : of_find_i2c_device_by_node(node);
	if (!error && (!client || client->adapter->dev.of_node != node->parent))
		error = -ENODEV;
	of_node_put(node);
	if (!error) {
		device_lock(&client->dev);
		/* Do not take over a bound PMIC driver or its register ownership. */
		error = client->dev.driver ? -EBUSY : n71_observe_reg_on(client, &value);
		device_unlock(&client->dev);
	}
	if (client)
		put_device(&client->dev);
	if (error) {
		pr_err("N71_REG_ON_OBSERVATION_FAILED error=%d; no value write\n", error);
		return error;
	}
	pr_info("N71_REG_ON_OBSERVED control=%02x bit0=%u compatible-plan=%u; no value write\n",
		(unsigned int)value, (unsigned int)(value & 1),
		(unsigned int)n71_wlan_reg_on_plan(N71_WLAN_REG_ON_REGISTER, value, true, &planned));
	return 0;
}

module_init(n71_power_init);
static void __exit n71_power_exit(void) { }
module_exit(n71_power_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Explicit N71 PMIC WLAN REG_ON observation; no value writes");
