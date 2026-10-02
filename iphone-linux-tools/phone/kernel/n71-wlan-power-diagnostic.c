// SPDX-License-Identifier: GPL-2.0-only
/* Explicit observation, then optional reversible GPIO10 bit0 experiment. */
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of_address.h>
#include "n71-wlan-power.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Claim the unbound N71 PMIC client and observe REG_ON");
static DEFINE_MUTEX(control_lock);
static struct i2c_client *owned_client;
static struct n71_wlan_power_state power_state;
static int probe_error = -ENODEV;

static int n71_reg_on_read(void *context, unsigned char *value)
{
	struct i2c_client *client = context;
	unsigned char address[2];
	struct i2c_msg messages[] = {
		{.addr = N71_WLAN_PMU_ADDRESS, .len = 2, .buf = address},
		{.addr = N71_WLAN_PMU_ADDRESS, .flags = I2C_M_RD, .len = 1, .buf = value},
	};
	int result;
	n71_wlan_reg_on_address(address);
	result = i2c_transfer(client->adapter, messages, ARRAY_SIZE(messages));
	return result == ARRAY_SIZE(messages) ? 0 : result < 0 ? result : -EIO;
}

static int n71_reg_on_write(void *context, unsigned char value)
{
	struct i2c_client *client = context;
	unsigned char packet[3];
	struct i2c_msg message = {.addr = N71_WLAN_PMU_ADDRESS, .len = 3, .buf = packet};
	int result;
	n71_wlan_reg_on_address(packet);
	packet[2] = value;
	result = i2c_transfer(client->adapter, &message, 1);
	return result == 1 ? 0 : result < 0 ? result : -EIO;
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
	    !of_device_is_compatible(node, "apple,antigua-pmic") || !of_device_is_available(node))
		return -ENODEV;
	error = of_address_to_resource(node->parent, 0, &bus);
	if (!error)
		error = of_property_read_u32(node, "reg", &address);
	if (!error && (bus.start != 0x20a110000ULL || address != N71_WLAN_PMU_ADDRESS))
		error = -ENODEV;
	return error;
}

static int n71_power_probe(struct i2c_client *client)
{
	unsigned char value = 0, planned;
	int error = n71_validate_client(client);
	if (error)
		return error;
	mutex_lock(&control_lock);
	error = owned_client ? -EBUSY : n71_reg_on_read(client, &value);
	probe_error = error;
	if (!error) {
		owned_client = client;
		power_io.context = client;
		pr_info("N71_REG_ON_OBSERVED control=%02x bit0=%u compatible-plan=%u; no value write\n",
			(unsigned int)value, (unsigned int)(value & 1),
			(unsigned int)n71_wlan_reg_on_plan(N71_WLAN_REG_ON_REGISTER, value, true, &planned));
	}
	mutex_unlock(&control_lock);
	return error;
}

/* Request/verify power=0 before unloading. Removal failure remains visible. */
static void n71_power_remove(struct i2c_client *client)
{
	int error;
	mutex_lock(&control_lock);
	if (owned_client == client) {
		error = n71_wlan_power_release(&power_io, &power_state);
		pr_info("N71_REG_ON_REMOVE error=%d restore_pending=%u\n",
			error, power_state.restore_pending);
		owned_client = NULL;
		power_io.context = NULL;
	}
	mutex_unlock(&control_lock);
}

static const struct of_device_id n71_power_match[] = {
	{.compatible = "apple,antigua-pmic"},
	{},
};
/* No MODULE_DEVICE_TABLE: this experiment must not autoload. */
static struct i2c_driver n71_power_driver = {
	.driver = {.name = "n71-wlan-power-diagnostic", .of_match_table = n71_power_match},
	.probe = n71_power_probe,
	.remove = n71_power_remove,
};

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
	int error;
	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	node = of_find_node_by_path("/soc/i2c@20a110000/pmic@74");
	client = node ? of_find_i2c_device_by_node(node) : NULL;
	of_node_put(node);
	if (!client)
		return -ENODEV;
	device_lock(&client->dev);
	error = client->dev.driver ? -EBUSY : n71_validate_client(client);
	device_unlock(&client->dev);
	put_device(&client->dev);
	if (error)
		return error;
	/* Driver core arbitrates binding; never replace another driver. */
	error = i2c_add_driver(&n71_power_driver);
	if (error)
		return error;
	if (!owned_client) {
		i2c_del_driver(&n71_power_driver);
		pr_err("N71_REG_ON_OBSERVATION_FAILED error=%d; no value write\n", probe_error);
		return probe_error;
	}
	return 0;
}

module_init(n71_power_init);
static void __exit n71_power_exit(void) { i2c_del_driver(&n71_power_driver); }
module_exit(n71_power_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 PMIC REG_ON observation and explicit reversible bit0 control");
