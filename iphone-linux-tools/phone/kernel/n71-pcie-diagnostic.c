// SPDX-License-Identifier: GPL-2.0-only
/* Opt-in clock/reset and temporary PCI sizing diagnostic; no DMA or radio. */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/string.h>
#include <linux/of_address.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include "n71-pcie-port.h"
#include "n71-pcie-link.h"
#include "n71-pcie-inventory.h"
#include "n71-pcie-mmio.h"
#include "n71-pcie-scan.h"
#include "n71-pcie-chip-mmio.h"
#include "n71-dart-mmio.h"
#include "n71-dart-provider.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Explicitly run one N71 clock/reset diagnostic at probe");
static bool enumerate;
module_param(enumerate, bool, 0400);
MODULE_PARM_DESC(enumerate, "Also train WLAN1 and read identity, without DMA or radio");
static bool config_inventory;
module_param(config_inventory, bool, 0400);
MODULE_PARM_DESC(config_inventory, "Read bounded endpoint config after enumeration; no BAR sizing");
static bool host_scan;
module_param(host_scan, bool, 0400);
MODULE_PARM_DESC(host_scan, "Temporarily scan with PCI core; size/restore BARs, no binding or DMA");
static bool scan_pme_disable;
module_param(scan_pme_disable, bool, 0400);
MODULE_PARM_DESC(scan_pme_disable, "Opt-in endpoint PME_ENABLE disable/restore for host_scan; no W1C");
static bool bar_sizing;
module_param(bar_sizing, bool, 0400);
MODULE_PARM_DESC(bar_sizing, "Size/restore endpoint BARs directly; no PCI devices, MMIO or DMA");
static bool chip_id;
module_param(chip_id, bool, 0400);
MODULE_PARM_DESC(chip_id, "Size BAR0 and read ChipCommon ID once; temporary route, no DMA or radio");
static bool dart_observe;
module_param(dart_observe, bool, 0400);
MODULE_PARM_DESC(dart_observe, "Read two stable DART snapshots; no provider, DART writes, DMA or IRQ");
static bool dart_cycle;
module_param(dart_cycle, bool, 0400);
MODULE_PARM_DESC(dart_cycle, "Test temporary DART provider and restore tables; no DMA attachment");
static DEFINE_MUTEX(session_lock);
static struct n71_diagnostic *session;
static struct device *session_device;

static int n71_inventory_read32(void *context, u32 offset, u32 *value)
{
	struct n71_diagnostic *state = context;
	u32 status;

	if (!value || offset % 4 || offset > 0xfc)
		return -EINVAL;
	status = readl(state->port + 0x88);
	if (status == 0xffffffff || !(status & 1))
		return -ENOLINK;
	*value = readl(state->ecam + 0x100000 + offset);
	return 0;
}

static int n71_inventory_report(struct device *dev, struct n71_diagnostic *state)
{
	struct n71_pcie_inventory_io io = {state, n71_inventory_read32};
	struct n71_pcie_inventory result;
	unsigned int index;
	int error;

	error = n71_pcie_inventory_collect(&io, &result);
	dev_info(dev, "N71_PCIE_INVENTORY_RESULT error=%d; no config writes\n", error);
	if (error)
		return error;
	dev_info(dev, "N71_PCIE_INVENTORY class-revision=%08x header=%08x subsystem=%08x\n",
		 result.class_revision, result.header, result.subsystem);
	dev_info(dev, "N71_PCIE_INVENTORY command-status=%08x interrupt=%08x reads=%u caps=%u\n",
		 result.command_status, result.interrupt, result.reads, result.capabilities);
	for (index = 0; index < ARRAY_SIZE(result.bars); index++)
		dev_info(dev, "N71_PCIE_BAR_RAW index=%u value=%08x; no sizing or MMIO access\n",
			 index, result.bars[index]);
	dev_info(dev, "N71_PCIE_CAP_RAW express=%02x/%08x msi=%02x/%08x msix=%02x/%08x\n",
		 result.express_offset, result.express_header,
		 result.msi_offset, result.msi_header, result.msix_offset, result.msix_header);
	return 0;
}

static int n71_table(struct device *dev, const char *name, u32 size,
		     struct n71_pcie_tunable **table, unsigned int *count)
{
	int cells = of_property_count_u32_elems(dev->of_node, name);
	unsigned int index;
	struct n71_pcie_tunable *result;
	u32 values[3];
	int error;

	if (cells <= 0 || cells % 3)
		return -EINVAL;
	*count = cells / 3;
	if (*count > N71_PCIE_MAX_TUNABLES)
		return -EINVAL;
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
	struct device *domain;
	int error;

	while (state->powered || state->power_put_pending) {
		if (state->power_put_pending) {
			domain = state->domains[state->powered];
			pm_runtime_barrier(domain);
			error = pm_runtime_suspend(domain); /* Never drop the same usage reference twice. */
		} else {
			domain = state->domains[--state->powered];
			state->power_put_pending = true;
			error = pm_runtime_put_sync_suspend(domain);
		}
		if (error < 0 || !pm_runtime_status_suspended(domain))
			return error < 0 ? error : -EBUSY;
		state->power_put_pending = false;
	}
	while (state->attached)
		dev_pm_domain_detach(state->domains[--state->attached], true);
	return 0;
}

static int n71_session_cleanup(struct n71_diagnostic *state)
{
	int error = n71_pcie_scan_cleanup(state);

	/* Pending rollback owns the link, GPIO, mappings and all power references. */
	if (error || state->scan_bridge)
		return error ? error : -EBUSY;
	if (state->reset_pending) {
		error = n71_reset(state, true);
		if (error)
			return error;
		state->reset_pending = false;
		dev_info(session_device, "N71_PCIE_RESET_RESTORED asserted=1 readback=1\n");
	}
	error = n71_release_power(state);
	if (!error)
		dev_info(session_device, "N71_PCIE_POWER_RELEASED powered=%u attached=%u\n",
			 state->powered, state->attached);
	return error;
}

static int n71_finish_cleanup(struct n71_diagnostic *state)
{
	state->cleanup_error = n71_session_cleanup(state);
	if (!state->cleanup_error && !state->scan_bridge && !state->reset_pending &&
	    !state->powered && !state->attached && !state->power_put_pending && state->module_retained) {
		state->module_retained = false;
		module_put(THIS_MODULE);
	}
	dev_info(session_device, "N71_PCIE_SESSION_CLEANUP error=%d retained=%u scan_pending=%u reset_pending=%u powered=%u attached=%u power_put_pending=%u primary_error=%d\n",
		 state->cleanup_error, state->module_retained, !!state->scan_bridge,
		 state->reset_pending, state->powered, state->attached,
		 state->power_put_pending, state->primary_error);
	return state->cleanup_error;
}

static int n71_cleanup_action(const char *text, const struct kernel_param *parameter)
{
	int error;

	(void)parameter;
	if (!sysfs_streq(text, "cleanup"))
		return -EINVAL;
	if (!try_module_get(THIS_MODULE))
		return -ENODEV;
	mutex_lock(&session_lock);
	error = session ? n71_finish_cleanup(session) : -ENODEV;
	mutex_unlock(&session_lock);
	module_put(THIS_MODULE);
	return error;
}

static int n71_session_status(char *buffer, const struct kernel_param *parameter)
{
	int length;

	(void)parameter;
	mutex_lock(&session_lock);
	if (session)
		length = scnprintf(buffer, PAGE_SIZE,
			"ready=1 retained=%u scan_pending=%u reset_pending=%u powered=%u attached=%u power_put_pending=%u primary_error=%d cleanup_error=%d\n",
			session->module_retained, !!session->scan_bridge, session->reset_pending,
			session->powered, session->attached, session->power_put_pending,
			session->primary_error, session->cleanup_error);
	else
		length = scnprintf(buffer, PAGE_SIZE, "ready=0 retained=0\n");
	mutex_unlock(&session_lock);
	return length;
}

static const struct kernel_param_ops cleanup_ops = {.set = n71_cleanup_action};
static const struct kernel_param_ops status_ops = {.get = n71_session_status};
module_param_cb(action, &cleanup_ops, NULL, 0200);
MODULE_PARM_DESC(action, "cleanup retries restoration only; never repeats enumeration or scan");
module_param_cb(status, &status_ops, NULL, 0400);
MODULE_PARM_DESC(status, "Inspect retained ownership and cleanup errors before normal unload");

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

static int n71_probe_locked(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct n71_diagnostic *state;
	struct n71_pcie_global_config config = {.lane_config = 1};
	struct n71_pcie_tunable *phy, *common, *port, *ecam;
	unsigned int port_count, ecam_count;
	u32 root_id, port_status;
	struct n71_pcie_port_io io;
	struct n71_pcie_link_io link;
	u32 identity;
	const char *stage = "validate";
	int error, cleanup;

	state = devm_kzalloc(dev, sizeof(*state), GFP_KERNEL);
	if (!state)
		return -ENOMEM;
	io = (struct n71_pcie_port_io){{state, n71_read, n71_write, n71_delay}, n71_read_port, n71_write_port};
	link = (struct n71_pcie_link_io){state, n71_read_link, n71_write_link, n71_reset, n71_delay, n71_endpoint};

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
	state->common = devm_platform_ioremap_resource(pdev, 9);
	state->phy = devm_platform_ioremap_resource(pdev, 10);
	state->port = devm_platform_ioremap_resource(pdev, 3);
	state->ecam = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(state->common) || IS_ERR(state->phy) || IS_ERR(state->port) || IS_ERR(state->ecam))
		return -ENODEV;
	state->perst = devm_gpiod_get(dev, "perst", GPIOD_OUT_HIGH);
	if (IS_ERR(state->perst))
		return dev_err_probe(dev, PTR_ERR(state->perst), "N71_PCIE_DIAGNOSTIC PERST unavailable\n");
	platform_set_drvdata(pdev, state);
	session = state;
	session_device = dev;
	__module_get(THIS_MODULE);
	state->module_retained = true;
	stage = "power";
	error = n71_power(dev, state);
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
		root_id = readl(state->ecam + 0x8000);
		port_status = readl(state->port + 0x88);
		if (!root_id || root_id == 0xffffffff || port_status == 0xffffffff)
			error = -ENODEV;
		else
			dev_info(dev, "N71_PCIE_CLOCKS_READY root-id=%08x port88=%08x; PERST held; no DMA\n",
				 root_id, port_status);
	}
	if (!error && enumerate) {
		stage = "enumerate";
		state->reset_pending = true;
		error = n71_pcie_enumerate_wlan(&link, ecam, ecam_count, port, port_count, &identity);
		dev_info(dev, "N71_PCIE_LINK_RESULT error=%d port88=%08x reads=%u; no DMA\n",
			 error, state->last_link_status, state->link_status_reads);
		if (!error)
			dev_info(dev, "N71_PCIE_ENDPOINT_ID=%08x; bus-master clear; no radio\n", identity);
		if (!error && config_inventory) {
			stage = "inventory";
			error = n71_inventory_report(dev, state);
		}
		if (!error && host_scan) {
			stage = "host-scan";
			error = scan_pme_disable ? n71_pcie_scan_with_pme(dev, state, true) :
				n71_pcie_scan(dev, state);
		}
		if (!error && bar_sizing) {
			stage = "bar-sizing";
			error = n71_pcie_size_bars(dev, state, NULL);
		}
		if (!error && chip_id) {
			stage = "chip-id";
			error = n71_pcie_chip_id(dev, state);
		}
		if (!error && dart_observe) {
			stage = "dart-observe";
			error = n71_pcie_dart_observe(dev, state);
		}
		if (!error && dart_cycle) {
			stage = "dart-cycle";
			error = n71_pcie_dart_cycle(dev, state);
		}
	}
done:
	state->primary_error = error;
	cleanup = n71_finish_cleanup(state);
	if (cleanup && !error) {
		error = cleanup;
		stage = "cleanup";
	}
	if (state->module_retained) {
		/* Binding keeps devres alive; a module pin prevents normal unload. */
		dev_err(dev, "N71_PCIE_DIAGNOSTIC %s error=%d; cleanup retained, use action=cleanup\n", stage, error);
		return 0;
	}
	if (error) {
		session = NULL;
		session_device = NULL;
		platform_set_drvdata(pdev, NULL);
		return dev_err_probe(dev, error, "N71_PCIE_DIAGNOSTIC %s failed\n", stage);
	}
	return 0;
}

static int n71_probe(struct platform_device *pdev)
{
	int error;

	mutex_lock(&session_lock);
	error = session ? -EBUSY : n71_probe_locked(pdev);
	mutex_unlock(&session_lock);
	return error;
}

static void n71_remove(struct platform_device *pdev)
{
	mutex_lock(&session_lock);
	/* Suppressed bind attributes and the retained pin protect this lifetime. */
	WARN_ON(session && session->module_retained);
	if (platform_get_drvdata(pdev) == session) {
		session = NULL;
		session_device = NULL;
	}
	mutex_unlock(&session_lock);
}

static const struct of_device_id n71_match[] = {
	{.compatible = "apple,n71-pcie-diagnostic"}, {}
};
MODULE_DEVICE_TABLE(of, n71_match);
static struct platform_driver n71_driver = {
	.probe = n71_probe, .remove = n71_remove,
	.driver = {.name = "n71-pcie-diagnostic", .of_match_table = n71_match, .suppress_bind_attrs = true},
};

static int __init n71_init(void)
{
	if (!run || !of_machine_is_compatible("apple,n71"))
		return -ENODEV;
	if ((scan_pme_disable && !host_scan) || (config_inventory && !enumerate) ||
	    ((host_scan || bar_sizing || chip_id || dart_observe || dart_cycle) && !config_inventory) ||
	    (host_scan + bar_sizing + chip_id + dart_observe + dart_cycle > 1))
		return -EINVAL;
	return platform_driver_register(&n71_driver);
}
module_init(n71_init);
static void __exit n71_exit(void) { platform_driver_unregister(&n71_driver); }
module_exit(n71_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Opt-in N71 PCIe clocks and identification diagnostic; no DMA");
