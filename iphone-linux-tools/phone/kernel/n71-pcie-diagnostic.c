// SPDX-License-Identifier: GPL-2.0-only
/* Opt-in PCI diagnostic; driver runtime requires separate explicit actions. */
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
#include "n71-pcie-resource-assign.h"
#include "n71-pcie-msi-allocate.h"
#include "n71-pcie-brcmfmac.h"
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
static bool scan_hold;
module_param(scan_hold, bool, 0400);
MODULE_PARM_DESC(scan_hold, "Keep the PME host scan and its owners until action=cleanup; no bind or DMA");
static bool msi_parent;
module_param(msi_parent, bool, 0400);
MODULE_PARM_DESC(msi_parent, "Associate the private MSI parent before the held scan; allocation requires a separate action");
static bool iommu_parent;
module_param(iommu_parent, bool, 0400);
MODULE_PARM_DESC(iommu_parent, "Associate the retained DART provider before the held MSI scan; no driver or DMA");
static bool driver_runtime;
module_param(driver_runtime, bool, 0400);
MODULE_PARM_DESC(driver_runtime, "Permit explicit brcmfmac prepare/publish/release actions; probe never loads firmware");
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

static bool n71_msi_allocation_pending(const struct n71_scan_host *host)
{
	return host->msi_allocation.endpoint || host->msi_allocation.vector ||
		host->msi_allocation.default_irq || host->msi_config.phase != N71_MSI_CONFIG_EMPTY;
}

static void n71_msi_allocation_report(struct n71_scan_host *host, const char *action, int error)
{
	const struct n71_msi_allocation *lease = &host->msi_allocation;
	const struct n71_wlan_msi *native = &host->msi.native;

	dev_info(session_device, "N71_PCIE_MSI_ALLOCATION_RESULT action=%s error=%d owner=%u phase=%u vector=%u default_irq=%u software_enabled=%u slots=%u mappings=%u child=%u operation_error=%d; no IRQ delivery or DMA\n",
		 action, error, !!lease->endpoint, host->msi_config.phase, lease->vector, lease->default_irq,
		 lease->endpoint ? lease->endpoint->msi_enabled : 0, native->slots,
		 native->domain ? native->domain->mapcount : 0, !!native->child, n71_msi_allocation_error(host));
}

static bool n71_session_has_held_bus(const struct n71_diagnostic *state);
#include "n71-pcie-brcmfmac-caller.h"

static int n71_session_cleanup(struct n71_diagnostic *state)
{
	struct n71_scan_host *host;
	int error;

	if (state->scan_bridge) {
		host = pci_host_bridge_priv(state->scan_bridge);
		error = n71_driver_cleanup(state, host);
		if (error)
			return error;
		if (n71_msi_allocation_pending(host)) {
			error = n71_pcie_msi_release(host, &host->msi_allocation);
			if (!error && n71_msi_allocation_pending(host))
				error = -EBUSY;
			n71_msi_allocation_report(host, "cleanup", error);
			if (error)
				return error;
		}
		if (host->dart.bridge) {
			error = n71_pcie_scan_remove_consumers(state);
			if (error)
				return error;
		}
	}
	error = n71_pcie_dart_cleanup(session_device, state);

	if (error || state->dart)
		return error ? error : -EBUSY;
	error = n71_pcie_scan_cleanup(state);

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
	if (!state->cleanup_error && !state->dart && !state->scan_bridge && !state->reset_pending &&
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

static int n71_assign_action(void);
static int n71_dart_action(bool release);
static int n71_msi_action(bool release);

static int n71_cleanup_action(const char *text, const struct kernel_param *parameter)
{
	int error;

	(void)parameter;
	if (sysfs_streq(text, "driver-prepare"))
		return n71_driver_action(N71_DRIVER_PREPARE);
	if (sysfs_streq(text, "driver-publish"))
		return n71_driver_action(N71_DRIVER_PUBLISH);
	if (sysfs_streq(text, "driver-release"))
		return n71_driver_action(N71_DRIVER_RELEASE);
	if (sysfs_streq(text, "assign"))
		return n71_assign_action();
	if (sysfs_streq(text, "msi-hold"))
		return n71_msi_action(false);
	if (sysfs_streq(text, "msi-release"))
		return n71_msi_action(true);
	if (sysfs_streq(text, "dart-hold"))
		return n71_dart_action(false);
	if (sysfs_streq(text, "dart-release"))
		return n71_dart_action(true);
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

static bool n71_session_has_held_bus(const struct n71_diagnostic *state)
{
	struct n71_scan_host *host;

	if (!state || !state->scan_bridge || !state->scan_bridge->bus)
		return false;
	host = pci_host_bridge_priv(state->scan_bridge);
	return host->bus_held;
}

static int n71_assign_action(void)
{
	bool pinned;
	int error;

	if (!scan_hold)
		return -EINVAL;
	pinned = try_module_get(THIS_MODULE);
	if (!pinned)
		return -ENODEV;
	mutex_lock(&session_lock);
	if (!session || !n71_session_has_held_bus(session)) {
		error = -ENODEV;
	} else if (!session->module_retained || !session->reset_pending ||
		   session->powered != 4 || session->attached != 4 || session->power_put_pending ||
		   session->primary_error || session->cleanup_error) {
		error = -EBUSY;
	} else {
		error = n71_pcie_assign_resources(session);
		if (error && error != -EALREADY && !session->primary_error)
			session->primary_error = error;
	}
	mutex_unlock(&session_lock);
	module_put(THIS_MODULE);
	return error;
}

static int n71_msi_action(bool release)
{
	struct n71_scan_host *host = NULL;
	int error;

	if (!scan_hold || !msi_parent || !iommu_parent)
		return -EINVAL;
	if (!try_module_get(THIS_MODULE))
		return -ENODEV;
	mutex_lock(&session_lock);
	if (!session || !n71_session_has_held_bus(session)) {
		error = -ENODEV;
	} else if (session->attached != 4 || session->powered != 4 || session->power_put_pending ||
		   !session->reset_pending || !session->module_retained) {
		error = -EBUSY;
	} else {
		host = pci_host_bridge_priv(session->scan_bridge);
		if (n71_scan_driver_pending(host)) {
			error = -EBUSY;
			goto unlock;
		}
		if (release) {
			error = n71_pcie_msi_release(host, &host->msi_allocation);
			if (!error && n71_msi_allocation_pending(host))
				error = -EBUSY;
		} else if (session->primary_error || session->cleanup_error) {
			error = -EBUSY;
		} else if (!session->dart || !session->dart->lease.running || !session->dart->device) {
			error = -EACCES;
		} else if (n71_msi_allocation_pending(host)) {
			error = -EBUSY;
		} else {
			error = n71_pcie_msi_allocate(session->scan_bridge, host, &host->msi_allocation);
			if (error && error != -EALREADY && !session->primary_error)
				session->primary_error = error;
		}
		n71_msi_allocation_report(host, release ? "release" : "hold", error);
	}
unlock:
	mutex_unlock(&session_lock);
	module_put(THIS_MODULE);
	return error;
}

static int n71_resource_status(char *buffer, const struct kernel_param *parameter)
{
	struct n71_scan_host *host;
	bool assigned;
	int length, error;

	(void)parameter;
	mutex_lock(&session_lock);
	if (session && session->scan_bridge) {
		host = pci_host_bridge_priv(session->scan_bridge);
		error = session->primary_error ? session->primary_error :
			host->config.error ? host->config.error :
			host->io_error ? host->io_error : host->resources.error;
		assigned = session->scan_bridge->bus && host->bus_held && host->resources_assigned &&
			host->window_claimed && host->windows[1].parent == &iomem_resource &&
			!host->resources.active && !error;
		length = scnprintf(buffer, PAGE_SIZE,
			"ready=1 attempted=%u assigned=%u pending=%u claimed=%u active=%u error=%d\n",
			host->resource_attempted, assigned, host->resources.pending,
			host->window_claimed, host->resources.active, error);
	} else {
		length = scnprintf(buffer, PAGE_SIZE,
			"ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=%d\n",
			session ? session->primary_error : 0);
	}
	mutex_unlock(&session_lock);
	return length;
}

static int n71_dart_action(bool release)
{
	struct n71_scan_host *host;
	int error;

	if (!scan_hold)
		return -EINVAL;
	if (!try_module_get(THIS_MODULE))
		return -ENODEV;
	mutex_lock(&session_lock);
	if (!session || !session->module_retained || !session->reset_pending ||
	    session->powered != 4 || session->attached != 4 || session->power_put_pending) {
		error = -ENODEV;
	} else if (release) {
		host = session->scan_bridge ? pci_host_bridge_priv(session->scan_bridge) : NULL;
		if (host && host->dart.bridge) {
			dev_info(session_device, "N71_DART_RELEASE_REFUSED association-owned; use action=cleanup\n");
			error = -EBUSY;
		} else {
			error = n71_pcie_dart_cleanup(session_device, session);
		}
	} else if (!n71_session_has_held_bus(session) || session->primary_error || session->cleanup_error) {
		error = -EBUSY;
	} else {
		host = pci_host_bridge_priv(session->scan_bridge);
		if (!host->resources_assigned || !host->window_claimed || host->resources.active ||
		    host->windows[1].parent != &iomem_resource || host->resources.error ||
		    host->config.error || host->io_error) {
			error = -EACCES;
		} else {
			error = n71_pcie_dart_acquire(session_device, session);
			if (error && error != -EALREADY && !session->primary_error)
				session->primary_error = error;
		}
	}
	mutex_unlock(&session_lock);
	module_put(THIS_MODULE);
	return error;
}

static int n71_dart_status(char *buffer, const struct kernel_param *parameter)
{
	struct n71_dart_provider *provider;
	int length;

	(void)parameter;
	mutex_lock(&session_lock);
	provider = session ? session->dart : NULL;
	length = scnprintf(buffer, PAGE_SIZE,
		"ready=%u acquired=%u running=%u pending=%u stopped=%u restored=%u index=%u device=%u mapping_new=%u claimed=%u mapped=%u operation_error=%d restore_error=%d irq_domain=%u irq_fwnode=%u\n",
		!!session, !!provider, provider ? provider->lease.running : 0,
		provider ? n71_dart_lease_pending(&provider->lease) : 0,
		provider ? provider->lease.stopped : 0, provider ? provider->lease.restored : 0,
		provider ? provider->lease.restore_index : 0, provider ? !!provider->device : 0,
		provider ? !!provider->interrupt.irq : 0, provider ? !!provider->claimed : 0,
		provider ? !!provider->mmio.regs : 0, provider ? provider->lease.operation_error : 0,
		provider ? provider->lease.restore_error : 0,
		provider ? !!provider->interrupt.domain : 0, provider ? !!provider->interrupt.fwnode : 0);
	mutex_unlock(&session_lock);
	return length;
}

static int n71_held_status(char *buffer, const struct kernel_param *parameter)
{
	int length;

	(void)parameter;
	mutex_lock(&session_lock);
	length = scnprintf(buffer, PAGE_SIZE, "held=%u\n", n71_session_has_held_bus(session));
	mutex_unlock(&session_lock);
	return length;
}

static int n71_msi_status(char *buffer, const struct kernel_param *parameter)
{
	struct n71_wlan_msi_host *owner = NULL;
	struct n71_scan_host *host;
	int length;

	(void)parameter;
	mutex_lock(&session_lock);
	if (session && session->scan_bridge) {
		host = pci_host_bridge_priv(session->scan_bridge);
		owner = &host->msi;
	}
	length = scnprintf(buffer, PAGE_SIZE,
		"requested=%u ready=%u held=%u associated=%u owner=%u domain=%u mappings=%u child=%u session_error=%d\n",
		msi_parent, !!session, n71_session_has_held_bus(session),
		owner ? owner->associated : 0, owner ? !!owner->bridge : 0,
		owner ? !!owner->native.domain : 0,
		owner && owner->native.domain ? owner->native.domain->mapcount : 0,
		owner ? !!owner->native.child : 0, session ? session->cleanup_error : 0);
	mutex_unlock(&session_lock);
	return length;
}

static int n71_msi_allocation_status(char *buffer, const struct kernel_param *parameter)
{
	struct n71_scan_host *host = NULL;
	const struct n71_msi_allocation *lease;
	const struct n71_wlan_msi *native;
	int error, length;

	(void)parameter;
	mutex_lock(&session_lock);
	if (session && session->scan_bridge)
		host = pci_host_bridge_priv(session->scan_bridge);
	lease = host ? &host->msi_allocation : NULL;
	native = host ? &host->msi.native : NULL;
	error = session && session->primary_error ? session->primary_error :
		host ? n71_msi_allocation_error(host) : 0;
	length = scnprintf(buffer, PAGE_SIZE,
		"ready=%u held=%u owner=%u phase=%u vector=%u default_irq=%u software_enabled=%u slots=%u mappings=%u child=%u error=%d session_error=%d\n",
		!!host, n71_session_has_held_bus(session), lease ? !!lease->endpoint : 0,
		host ? host->msi_config.phase : 0, lease ? lease->vector : 0, lease ? lease->default_irq : 0,
		lease && lease->endpoint ? lease->endpoint->msi_enabled : 0, native ? native->slots : 0,
		native && native->domain ? native->domain->mapcount : 0, native ? !!native->child : 0,
		error, session ? session->cleanup_error : 0);
	mutex_unlock(&session_lock);
	return length;
}

static int n71_iommu_status(char *buffer, const struct kernel_param *parameter)
{
	struct n71_scan_host *host = NULL;
	bool checked;
	int length;

	(void)parameter;
	mutex_lock(&session_lock);
	if (session && session->scan_bridge)
		host = pci_host_bridge_priv(session->scan_bridge);
	/* Last OF/core observation; no private SID, translation or IRQ readback. */
	checked = n71_session_has_held_bus(session) && host && host->dart.bridge && host->dart.available && host->dart.mapped &&
		host->iommu_domain && host->iommu_devices == 2 && !host->config.error && !host->io_error;
	length = scnprintf(buffer, PAGE_SIZE,
		"requested=%u ready=%u held=%u owner=%u available=%u mapped=%u observed=%u map_checked=%u session_error=%d\n",
		iommu_parent, !!session, n71_session_has_held_bus(session),
		host ? !!host->dart.bridge : 0, host ? host->dart.available : 0,
		host ? host->dart.mapped : 0, host ? host->iommu_devices : 0,
		checked, session ? session->cleanup_error : 0);
	mutex_unlock(&session_lock);
	return length;
}

static const struct kernel_param_ops cleanup_ops = {.set = n71_cleanup_action};
static const struct kernel_param_ops status_ops = {.get = n71_session_status};
static const struct kernel_param_ops held_ops = {.get = n71_held_status};
static const struct kernel_param_ops resource_ops = {.get = n71_resource_status};
static const struct kernel_param_ops dart_ops = {.get = n71_dart_status};
static const struct kernel_param_ops msi_ops = {.get = n71_msi_status};
static const struct kernel_param_ops msi_allocation_ops = {.get = n71_msi_allocation_status};
static const struct kernel_param_ops iommu_ops = {.get = n71_iommu_status};
static const struct kernel_param_ops driver_ops = {.get = n71_driver_status};
module_param_cb(action, &cleanup_ops, NULL, 0200);
MODULE_PARM_DESC(action, "assign, dart-hold/release, msi-hold/release, driver-prepare/publish/release, cleanup operate on the retained session; no rescan");
module_param_cb(status, &status_ops, NULL, 0400);
MODULE_PARM_DESC(status, "Inspect retained ownership and cleanup errors before normal unload");
module_param_cb(held, &held_ops, NULL, 0400);
MODULE_PARM_DESC(held, "Read live bus ownership; distinct from pending restoration");
module_param_cb(resources, &resource_ops, NULL, 0400);
MODULE_PARM_DESC(resources, "Read assignment and pending ownership; a removed bus is never assigned");
module_param_cb(dart, &dart_ops, NULL, 0400);
MODULE_PARM_DESC(dart, "Read DART ownership and recovery progress independently of PCI resources");
module_param_cb(msi, &msi_ops, NULL, 0400);
MODULE_PARM_DESC(msi, "Read MSI association ownership and pending session cleanup; not IRQ delivery proof");
module_param_cb(msi_allocation, &msi_allocation_ops, NULL, 0400);
MODULE_PARM_DESC(msi_allocation, "Read allocation ownership and last validation; no new IO or IRQ delivery proof");
module_param_cb(iommu, &iommu_ops, NULL, 0400);
MODULE_PARM_DESC(iommu, "Read OF/core DART association and pending cleanup; not DMA translation proof");
module_param_cb(driver_runtime_status, &driver_ops, NULL, 0400);
MODULE_PARM_DESC(driver_runtime_status, "Read driver runtime ownership and errors; publication is not firmware or radio readiness");

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
		if (!error && iommu_parent) {
			stage = "iommu-provider";
			error = n71_pcie_dart_acquire(dev, state);
			if (!error && (!state->dart || !state->dart->lease.running || !state->dart->device))
				error = -ENODEV;
		}
		if (!error && host_scan) {
			stage = scan_hold ? "host-scan-hold" : "host-scan";
			if (iommu_parent)
				error = n71_pcie_scan_hold_iommu(dev, state, state->dart->device);
			else if (scan_hold)
				error = msi_parent ? n71_pcie_scan_hold_msi(dev, state) :
					n71_pcie_scan_hold(dev, state);
			else
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
	if (scan_hold && !error) {
		if (n71_session_has_held_bus(state)) {
			dev_info(dev, "N71_PCIE_SESSION_HELD retained=%u scan_pending=%u reset_pending=%u powered=%u attached=%u power_put_pending=%u primary_error=%d cleanup_error=%d; no bind, DMA or radio\n",
				 state->module_retained, !!state->scan_bridge, state->reset_pending,
				 state->powered, state->attached, state->power_put_pending,
				 state->primary_error, state->cleanup_error);
			return 0;
		}
		error = -ENODEV;
		stage = "host-scan-hold-proof";
	}
done:
	if (!state->primary_error)
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
	if ((driver_runtime && !iommu_parent) || (iommu_parent && (!msi_parent || !scan_hold)) ||
	    (msi_parent && !scan_hold) || (scan_hold && (!host_scan || !scan_pme_disable)) ||
	    (scan_pme_disable && !host_scan) || (config_inventory && !enumerate) ||
	    ((host_scan || bar_sizing || chip_id || dart_observe || dart_cycle) && !config_inventory) ||
	    (host_scan + bar_sizing + chip_id + dart_observe + dart_cycle > 1))
		return -EINVAL;
	return platform_driver_register(&n71_driver);
}
module_init(n71_init);
static void __exit n71_exit(void) { platform_driver_unregister(&n71_driver); }
module_exit(n71_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Opt-in N71 PCIe diagnostic with explicit brcmfmac runtime actions");
