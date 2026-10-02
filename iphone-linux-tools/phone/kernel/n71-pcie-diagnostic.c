// SPDX-License-Identifier: GPL-2.0-only
/* Opt-in clock/reset diagnostic; no PCI host registration, DMA or radio firmware. */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of_address.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include "n71-pcie-port.h"
#include "n71-pcie-link.h"
#include "n71-pcie-mmio.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Explicitly run one N71 clock/reset diagnostic at probe");
static bool enumerate;
module_param(enumerate, bool, 0400);
MODULE_PARM_DESC(enumerate, "Also train WLAN1 and read identity, without DMA or radio");

static int n71_table(struct device *dev, const char *name, u32 size,
		     struct n71_pcie_tunable **table, unsigned int *count)
{
	int cells = of_property_count_u32_elems(dev->of_node, name);
	unsigned int index;
	struct n71_pcie_tunable *result;
	u32 values[3];
	int error;

	if (cells <= 0 || cells % 3 || cells / 3 > N71_PCIE_MAX_TUNABLES)
		return -EINVAL;
	*count = cells / 3;
	result = devm_kcalloc(dev, *count, sizeof(*result), GFP_KERNEL);
	if (!result)
		return -ENOMEM;
	for (index = 0; index < *count; index++) {
		error = of_property_read_u32_index(dev->of_node, name, index * 3, &values[0]);
		if (!error)
			error = of_property_read_u32_index(dev->of_node, name, index * 3 + 1, &values[1]);
		if (!error)
			error = of_property_read_u32_index(dev->of_node, name, index * 3 + 2, &values[2]);
		if (error || values[2] & ~values[1])
			return error ? error : -EINVAL;
		result[index] = (struct n71_pcie_tunable){values[0], values[1], values[2]};
	}
	if (!n71_pcie_table_valid(result, *count, size))
		return -EINVAL;
	*table = result;
	return 0;
}

static int n71_validate_resources(struct platform_device *pdev)
{
	static const resource_size_t addresses[] = {0x610000000ULL, 0x601000000ULL,
		0x601004000ULL, 0x602000000ULL, 0x602004000ULL, 0x603000000ULL,
		0x603004000ULL, 0x604000000ULL, 0x604004000ULL, 0x600000000ULL, 0x600008000ULL};
	struct of_phandle_args gpio;
	struct resource *resource, controller;
	unsigned int index;
	int error;

	if (!of_machine_is_compatible("apple,n71") ||
	    platform_get_resource(pdev, IORESOURCE_MEM, 11))
		return -ENODEV;
	for (index = 0; index < ARRAY_SIZE(addresses); index++) {
		resource = platform_get_resource(pdev, IORESOURCE_MEM, index);
		if (!resource || resource->start != addresses[index] ||
		    resource_size(resource) != (index == 0 ? 0x1000000 : index == 9 ? 0x8000 : 0x4000))
			return -EINVAL;
	}
	error = of_parse_phandle_with_fixed_args(pdev->dev.of_node, "perst-gpios", 2, 0, &gpio);
	if (error)
		return error;
	error = of_address_to_resource(gpio.np, 0, &controller);
	if (!error && (controller.start != 0x20f100000ULL || gpio.args[0] != 161 || gpio.args[1] != 1))
		error = -EINVAL;
	of_node_put(gpio.np);
	return error;
}

static int n71_release_power(struct n71_diagnostic *state)
{
	int error, first = 0;
	while (state->powered) {
		error = pm_runtime_put_sync_suspend(state->domains[--state->powered]);
		if (error < 0 && !first)
			first = error;
	}
	while (state->attached)
		dev_pm_domain_detach(state->domains[--state->attached], true);
	return first;
}

static int n71_power(struct device *dev, struct n71_diagnostic *state)
{
	static const char * const names[] = {"pcie", "aux", "ref", "link1"};
	unsigned int index;
	int error;

	for (index = 0; index < ARRAY_SIZE(names); index++) {
		state->domains[index] = dev_pm_domain_attach_by_name(dev, names[index]);
		if (IS_ERR_OR_NULL(state->domains[index]))
			return state->domains[index] ? PTR_ERR(state->domains[index]) : -ENODEV;
		state->attached++;
		error = pm_runtime_resume_and_get(state->domains[index]);
		if (error < 0)
			return error;
		state->powered++;
	}
	return 0;
}

static int n71_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct n71_diagnostic state = {};
	struct n71_pcie_global_config config = {.lane_config = 1};
	struct n71_pcie_tunable *phy, *common, *port, *ecam;
	unsigned int port_count, ecam_count;
	u32 root_id, port_status;
	struct n71_pcie_port_io io = {{&state, n71_read, n71_write, n71_delay}, n71_read_port, n71_write_port};
	struct n71_pcie_link_io link = {&state, n71_read_link, n71_write_link, n71_reset, n71_delay, n71_endpoint};
	u32 identity;
	const char *stage = "validate";
	int error, cleanup;

	error = n71_validate_resources(pdev);
	if (!error)
		error = n71_table(dev, "n71,phy-tunables", 0x4000, &phy, &config.phy_count);
	if (!error)
		error = n71_table(dev, "n71,common-tunables", 0x8000, &common, &config.common_count);
	if (!error)
		error = n71_table(dev, "n71,port1-tunables", 0x4000, &port, &port_count);
	if (!error)
		error = n71_table(dev, "n71,config1-tunables", 0x1000, &ecam, &ecam_count);
	if (!error && (!n71_pcie_link_table_valid(ecam, ecam_count, true) ||
		       !n71_pcie_link_table_valid(port, port_count, false)))
		error = -EINVAL;
	if (error)
		return dev_err_probe(dev, error, "N71_PCIE_DIAGNOSTIC validate failed\n");
	config.phy = phy;
	config.common = common;
	state.common = devm_platform_ioremap_resource(pdev, 9);
	state.phy = devm_platform_ioremap_resource(pdev, 10);
	state.port = devm_platform_ioremap_resource(pdev, 3);
	state.ecam = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(state.common) || IS_ERR(state.phy) || IS_ERR(state.port) || IS_ERR(state.ecam))
		return -ENODEV;
	state.perst = devm_gpiod_get(dev, "perst", GPIOD_OUT_HIGH);
	if (IS_ERR(state.perst))
		return dev_err_probe(dev, PTR_ERR(state.perst), "N71_PCIE_DIAGNOSTIC PERST unavailable\n");
	stage = "power";
	error = n71_power(dev, &state);
	if (error)
		goto done;
	stage = "global";
	error = n71_pcie_initialize_global(&io.common, &config);
	if (error)
		goto done;
	stage = "port1";
	error = n71_pcie_prepare_wlan(&io, false, false);
	if (!error) {
		stage = "root-read";
		root_id = readl(state.ecam + 0x8000);
		port_status = readl(state.port + 0x88);
		if (!root_id || root_id == 0xffffffff || port_status == 0xffffffff)
			error = -ENODEV;
		else
			dev_info(dev, "N71_PCIE_CLOCKS_READY root-id=%08x port88=%08x; PERST held; no DMA\n",
				 root_id, port_status);
	}
	if (!error && enumerate) {
		stage = "enumerate";
		error = n71_pcie_enumerate_wlan(&link, ecam, ecam_count, port, port_count, &identity);
		dev_info(dev, "N71_PCIE_LINK_RESULT error=%d port88=%08x reads=%u; no DMA\n",
			 error, state.last_link_status, state.link_status_reads);
		if (!error)
			dev_info(dev, "N71_PCIE_ENDPOINT_ID=%08x; bus-master clear; no radio\n", identity);
		cleanup = n71_reset(&state, true);
		if (cleanup) {
			dev_err(dev, "N71_PCIE_DIAGNOSTIC reset cleanup failed: %d\n", cleanup);
			if (!error)
				error = cleanup;
		}
	}
done:
	/* Reassert reset after enumeration and balance every power reference. */
	cleanup = n71_release_power(&state);
	if (cleanup < 0) {
		dev_err(dev, "N71_PCIE_DIAGNOSTIC power cleanup failed: %d\n", cleanup);
		if (!error) {
			error = cleanup;
			stage = "cleanup";
		}
	}
	if (error)
		return dev_err_probe(dev, error, "N71_PCIE_DIAGNOSTIC %s failed\n", stage);
	return 0;
}

static const struct of_device_id n71_match[] = {
	{.compatible = "apple,n71-pcie-diagnostic"}, {}
};
MODULE_DEVICE_TABLE(of, n71_match);
static struct platform_driver n71_driver = {
	.probe = n71_probe,
	.driver = {.name = "n71-pcie-diagnostic", .of_match_table = n71_match},
};

static int __init n71_init(void)
{
	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	return platform_driver_register(&n71_driver);
}
module_init(n71_init);
static void __exit n71_exit(void) { platform_driver_unregister(&n71_driver); }
module_exit(n71_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Opt-in N71 PCIe clocks and identification diagnostic; no DMA");
