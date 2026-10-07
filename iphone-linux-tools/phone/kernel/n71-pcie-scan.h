/* SPDX-License-Identifier: GPL-2.0-only */
/* PCI-core sizing; an explicitly held bus must be removed before power-off. */
#ifndef N71_PCIE_SCAN_H
#define N71_PCIE_SCAN_H
#include <linux/pci.h>
#include <linux/spinlock.h>
#include <linux/ioport.h>
#include <linux/iommu.h>
#include "n71-pcie-scan-config.h"
#include "n71-pcie-bar-sizing.h"
#include "n71-pcie-control-reference.h"
#include "n71-pcie-scan-link-target.h"
#include "n71-pcie-pme-control.h"
#include "n71-pcie-resource-write.h"
#include "n71-wlan-msi-host.h"
#include "n71-dart-host.h"

struct n71_scan_host {
	struct device *dev;
	void __iomem *ecam, *port;
	spinlock_t lock;
	struct n71_scan_config config;
	struct n71_link_target target;
	struct n71_pme_state pme;
	struct n71_resource_write_state resources;
	struct n71_wlan_msi_host msi;
	struct n71_dart_host dart;
	/* Borrowed while PCI consumers are alive; cleared after bus removal. */
	struct iommu_domain *iommu_domain;
	unsigned int iommu_devices;
	bool config_pending;
	bool bus_held;
	bool resource_attempted, resources_assigned, window_claimed;
	struct resource windows[3];
	unsigned int reads, devices, endpoints;
	int io_error, held_stop_error;
};

static int n71_scan_raw_read(void *context, bool root, u32 where,
			     unsigned int size, u32 *value)
{
	struct n71_scan_host *host = context;
	struct n71_pcie_ecam_location location;
	u32 status;
	int error;

	error = n71_pcie_ecam_locate(0x1000000, root ? 0 : 1, root ? 8 : 0,
				     where, size, &location);
	if (error || !value)
		return error ? error : -EINVAL;
	if (++host->reads > 4096 && host->config.active)
		return -E2BIG;
	if (!root) {
		status = readl(host->port + 0x88);
		if (status == 0xffffffff || !(status & 1))
			return -ENOLINK;
	}
	*value = (readl(host->ecam + location.dword_offset) >> location.shift) & location.mask;
	return 0;
}

static int n71_scan_raw_write(void *context, bool root, u32 where,
			      unsigned int size, u32 value)
{
	struct n71_scan_host *host = context;
	struct n71_pcie_ecam_location location;
	u32 status;
	void __iomem *address;
	int error;

	error = n71_pcie_ecam_locate(0x1000000, root ? 0 : 1, root ? 8 : 0,
				     where, size, &location);
	if (error || (size != 2 && size != 4))
		return error ? error : -EINVAL;
	if (!root) {
		status = readl(host->port + 0x88);
		if (status == 0xffffffff || !(status & 1))
			return -ENOLINK;
	}
	address = host->ecam + location.dword_offset + location.shift / 8;
	if (size == 2)
		writew(value, address); /* COMMAND never rewrites adjacent W1C STATUS. */
	else
		writel(value, address);
	return 0;
}

static inline int n71_pcie_size_bars(struct device *dev, struct n71_diagnostic *state,
				    struct n71_bar_sizes *out)
{
	struct n71_scan_host host = {.dev = dev, .ecam = state->ecam, .port = state->port};
	struct n71_scan_io io = {&host, n71_scan_raw_read, n71_scan_raw_write};
	struct n71_bar_sizes sizes;
	unsigned int bar;
	int error, restore;

	error = n71_bar_collect(&io, &host.config, &sizes, &restore);
	if (host.config.saved[0].identity)
		dev_info(dev, "N71_PCIE_SIZING_CONFIG_RESTORED error=%d; decode/readback checked\n", restore);
	if (!error)
		for (bar = 0; bar < 6; bar++)
			dev_info(dev, "N71_PCIE_SIZED_BAR index=%u raw=%08x mask=%08x bytes=%016llx; no MMIO\n",
				 bar, host.config.saved[1].bars[bar], sizes.masks[bar],
				 (unsigned long long)sizes.bytes[bar]);
	dev_info(dev, "N71_PCIE_SIZING_RESULT error=%d reads=%u attempts=%u writes=%u refusals=%u; no DMA or radio\n",
		 error, host.reads, host.config.attempts, host.config.writes, host.config.refusals);
	if (!error && out)
		*out = sizes;
	return error;
}

static int n71_scan_config_read(struct pci_bus *bus, unsigned int devfn,
				int where, int size, u32 *value)
{
	struct n71_scan_host *host = bus->sysdata;
	struct n71_pcie_ecam_location location;
	unsigned long flags;
	int error;

	*value = 0xffffffff;
	error = n71_pcie_ecam_locate(0x1000000, bus->number, devfn, where, size, &location);
	if (error)
		return error == -ENODEV ? PCIBIOS_DEVICE_NOT_FOUND : PCIBIOS_BAD_REGISTER_NUMBER;
	spin_lock_irqsave(&host->lock, flags);
	error = n71_scan_raw_read(host, location.root, where, size, value);
	if (error && !host->io_error)
		host->io_error = error;
	spin_unlock_irqrestore(&host->lock, flags);
	return error ? PCIBIOS_DEVICE_NOT_FOUND : PCIBIOS_SUCCESSFUL;
}

static int n71_scan_config_write(struct pci_bus *bus, unsigned int devfn,
				 int where, int size, u32 value)
{
	struct n71_scan_host *host = bus->sysdata;
	struct n71_pcie_ecam_location location;
	struct n71_scan_io io = {host, n71_scan_raw_read, n71_scan_raw_write};
	struct n71_scan_request request;
	unsigned long flags;
	int error;

	error = n71_pcie_ecam_locate(0x1000000, bus->number, devfn, where, size, &location);
	spin_lock_irqsave(&host->lock, flags);
	if (error) {
		n71_scan_refuse(&host->config, error);
	} else {
		request = (struct n71_scan_request){location.root, where, value, size};
		if (host->resources.active) {
			error = host->config.error ? host->config.error : n71_resource_write(&io, &host->resources, &request);
			if (error)
				n71_scan_refuse(&host->config, error);
		} else {
			error = n71_pme_scan_write(&io, &host->config, &host->pme, &request);
		}
	}
	spin_unlock_irqrestore(&host->lock, flags);
	if (error)
		dev_info(host->dev, "N71_PCIE_SCAN_WRITE_REFUSED bus=%u devfn=%02x where=%03x size=%d value=%08x error=%d\n",
			 bus->number, devfn, where, size, value, error);
	return error ? PCIBIOS_SET_FAILED : PCIBIOS_SUCCESSFUL;
}

static struct pci_ops n71_scan_ops = {
	.read = n71_scan_config_read, .write = n71_scan_config_write,
};

static int n71_scan_deny_enable(struct pci_host_bridge *bridge, struct pci_dev *dev)
{
	(void)bridge;
	(void)dev;
	return -EPERM;
}

static int n71_scan_report_error(struct n71_scan_host *host, int error)
{
	if (!host->io_error)
		host->io_error = error;
	return error;
}

static int n71_scan_report_iommu(struct n71_scan_host *host, struct pci_dev *dev)
{
	struct iommu_fwspec *spec = dev_iommu_fwspec_get(&dev->dev);
	struct iommu_domain *domain = iommu_get_domain_for_dev(&dev->dev);
	const u32 map[8] = {0x0008, host->dart.phandle, 0, 1, 0x0100, host->dart.phandle, 0, 1};
	u32 value;
	unsigned int index;

	if (!host->dart.available || !host->dart.mapped || !n71_dart_host_refs_valid(&host->dart) ||
	    of_find_property(host->dart.master_node, "iommu-map", NULL) != host->dart.map_property ||
	    of_find_property(host->dart.provider_node, "status", NULL) != host->dart.status_property ||
	    of_property_count_u32_elems(host->dart.master_node, "iommu-map") != 8 ||
	    !spec || spec->iommu_fwnode != of_fwnode_handle(host->dart.provider_node) ||
	    spec->flags || spec->num_ids != 0 ||
	    !domain || domain->type != IOMMU_DOMAIN_DMA ||
	    (host->iommu_domain && host->iommu_domain != domain))
		return n71_scan_report_error(host, -EACCES);
	/* apple-dart stores SIDs in private stream_maps; its fwspec IDs stay empty. */
	for (index = 0; index < 8; index++)
		if (of_property_read_u32_index(host->dart.master_node, "iommu-map", index, &value) || value != map[index])
			return n71_scan_report_error(host, -EACCES);
	host->iommu_domain = domain;
	host->iommu_devices++;
	dev_info(host->dev, "N71_PCIE_SCAN_IOMMU bus=%u devfn=%02x map_sid=0 translated=1; OF map and core domain, no private SID readback\n",
		 dev->bus->number, dev->devfn);
	return 0;
}

static int n71_scan_report_device(struct pci_dev *dev, void *context)
{
	struct n71_scan_host *host = context;
	unsigned int index;
	u16 command;
	bool root = dev->bus->number == 0 && dev->devfn == 8;
	int error;

	host->devices++;
	if ((root && (dev->vendor != 0x106b || dev->device != 0x1004 || dev->class != 0x060400)) ||
	    (!root && (dev->bus->number != 1 || dev->devfn || dev->vendor != 0x14e4 ||
		       dev->device != 0x43a3 || dev->class != 0x028000)))
		return n71_scan_report_error(host, -ENODEV);
	error = pci_read_config_word(dev, PCI_COMMAND, &command);
	if (error || (command & PCI_COMMAND_MASTER) || dev->driver)
		return n71_scan_report_error(host, -EACCES);
	if (host->msi.bridge) {
		struct irq_domain *domain = host->msi.native.domain;
		struct pci_host_bridge *bridge = host->msi.bridge;

		if (!host->msi.associated || !domain || !bridge->bus ||
		    dev_get_msi_domain(&bridge->dev) != domain ||
		    dev_get_msi_domain(&bridge->bus->dev) != domain ||
		    dev_get_msi_domain(&dev->bus->dev) != domain ||
		    dev_get_msi_domain(&dev->dev) != domain)
			return n71_scan_report_error(host, -EACCES);
		dev_info(host->dev, "N71_PCIE_SCAN_MSI bus=%u devfn=%02x inherited=1; no IRQ allocation\n",
			 dev->bus->number, dev->devfn);
	}
	if (host->dart.bridge) {
		error = n71_scan_report_iommu(host, dev);
		if (error)
			return error;
	}
	dev_info(host->dev, "N71_PCIE_SCAN_DEVICE bus=%u devfn=%02x id=%04x%04x class=%06x command=%04x driver=none\n",
		 dev->bus->number, dev->devfn, dev->device, dev->vendor, dev->class, command);
	if (root)
		return 0;
	host->endpoints++;
	for (index = 0; index < PCI_STD_NUM_BARS; index++) {
		struct resource *resource = &dev->resource[index];
		dev_info(host->dev, "N71_PCIE_SCAN_BAR index=%u start=%016llx end=%016llx flags=%08lx; no MMIO\n",
			 index, (unsigned long long)resource->start,
			 (unsigned long long)resource->end, resource->flags);
	}
	return 0;
}

static int n71_scan_validate_result(const struct n71_scan_host *host)
{
	if (host->config.error || host->io_error)
		return host->config.error ? host->config.error : host->io_error;
	if (host->dart.bridge && host->iommu_devices != 2)
		return -ENODEV;
	return host->devices == 2 && host->endpoints == 1 ? 0 : -ENODEV;
}

static int n71_scan_target_read(void *context, u32 where, unsigned int size, u32 *value)
{
	return n71_scan_raw_read(context, true, where, size, value);
}

static int n71_scan_target_write(void *context, u32 where, unsigned int size, u32 value)
{
	/* The target helper owns only this word, outside the generic PCI policy. */
	if (where != 0xa0 || size != 2 || (value != 1 && value != 2))
		return -EPERM;
	return n71_scan_raw_write(context, true, where, size, value);
}

/* Caller holds the rescan lock and retains all MMIO/power owners. */
static void n71_scan_remove_bus(struct pci_host_bridge *bridge)
{
	pci_stop_root_bus(bridge->bus);
	pci_remove_root_bus(bridge->bus);
}

/* Preserve the host for provider teardown between removal and restoration. */
static int n71_pcie_scan_remove_consumers(struct n71_diagnostic *state)
{
	struct pci_host_bridge *bridge = state->scan_bridge;
	struct n71_scan_host *host;
	int error;

	if (!bridge)
		return 0;
	host = pci_host_bridge_priv(bridge);
	if (host->resources.active)
		return -EBUSY;
	if (bridge->bus) {
		if (!host->bus_held)
			return -EBUSY;
		pci_lock_rescan_remove();
		n71_scan_remove_bus(bridge);
		pci_unlock_rescan_remove();
		if (bridge->bus)
			return -EBUSY;
		host->bus_held = false;
		host->held_stop_error = host->config.error ? host->config.error : host->io_error;
		dev_info(host->dev, "N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=%d\n", host->held_stop_error);
	}
	host->iommu_domain = NULL;
	host->iommu_devices = 0;
	error = n71_wlan_msi_host_release(&host->msi);
	if (error)
		return error;
	return n71_dart_host_unmap(&host->dart);
}

static int n71_pcie_scan_cleanup(struct n71_diagnostic *state)
{
	struct pci_host_bridge *bridge = state->scan_bridge;
	struct n71_scan_host *host;
	struct n71_scan_io io;
	struct n71_link_target_io target_io;
	int error, stop_error = 0;

	if (!bridge)
		return 0;
	error = n71_pcie_scan_remove_consumers(state);
	if (error)
		return error;
	host = pci_host_bridge_priv(bridge);
	stop_error = host->held_stop_error;
	error = n71_dart_host_release(&host->dart);
	if (error)
		return error;
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	target_io = (struct n71_link_target_io){host, n71_scan_target_read, n71_scan_target_write};
	if (host->resources.pending) {
		host->config.active = false; /* Removed bus: rollback is outside the scan budget. */
		error = n71_resource_restore(&io, &host->resources, !bridge->bus);
		dev_info(host->dev, "N71_PCIE_RESOURCE_RESTORED error=%d pending=%u\n", error, host->resources.pending);
		if (error)
			return error;
	}
	if (host->config_pending) {
		/* Retry restoration only; no PCI callbacks or scan writes remain. */
		host->config.active = true;
		error = n71_scan_restore(&io, &host->config);
		dev_info(host->dev, "N71_PCIE_SCAN_CONFIG_RESTORED error=%d; decode/readback checked\n", error);
		if (error)
			return error;
		host->config_pending = false;
	}
	if (host->window_claimed) {
		if (host->windows[1].parent != &iomem_resource || host->windows[1].child)
			return -EBUSY;
		error = release_resource(&host->windows[1]);
		if (error)
			return error;
		host->window_claimed = false;
		host->resources_assigned = false;
		dev_info(host->dev, "N71_PCIE_RESOURCE_WINDOW_RELEASED claimed=0\n");
	}
	if (host->pme.pending) {
		error = n71_pme_restore(&io, &host->pme);
		dev_info(host->dev, "N71_PCIE_SCAN_PME_RESTORED error=%d pending=%u; no W1C\n",
			 error, host->pme.pending);
		if (error)
			return error;
	}
	if (host->target.pending) {
		error = n71_link_target_restore(&target_io, &host->target);
		dev_info(host->dev, "N71_PCIE_SCAN_TARGET_RESTORED error=%d pending=%u; no retrain\n",
			 error, host->target.pending);
		if (error)
			return error;
	}
	state->scan_bridge = NULL;
	pci_free_host_bridge(bridge);
	return stop_error;
}

struct n71_scan_options {
	bool disable_pme, hold_bus, msi_parent;
	struct platform_device *provider;
};

static int n71_scan_msi_acquire(struct pci_host_bridge *bridge, struct device *dev)
{
	struct n71_scan_host *host = pci_host_bridge_priv(bridge);
	struct device_node *parent = of_irq_find_parent(dev->of_node);
	struct irq_fwspec spec = {.param_count = 3, .param = {0, 264, IRQ_TYPE_EDGE_RISING}};
	const struct n71_wlan_msi_request message = {
		.irq = {3, 32, 256, 1, 8, 8, 0}, .address_lo = 0xbffff000U,
	};
	struct n71_wlan_msi_host_request request = {.bridge = bridge, .message = &message, .spec = &spec};
	int error;

	if (!parent)
		return -ENODEV;
	spec.fwnode = of_fwnode_handle(parent);
	error = n71_wlan_msi_host_acquire(&host->msi, &request);
	of_node_put(parent);
	return error;
}

static int n71_pcie_scan_with_options(struct device *dev, struct n71_diagnostic *state,
				     const struct n71_scan_options *options)
{
	struct pci_host_bridge *bridge;
	struct n71_scan_host *host;
	struct n71_scan_host report;
	struct n71_scan_io io;
	struct n71_link_target_io target_io;
	struct resource_entry *entry;
	unsigned int windows = 0;
	struct n71_control_reference reference;
	unsigned int function, word;
	bool disable_pme = options->disable_pme, hold_bus = options->hold_bus;
	int error, restore;

	if (state->scan_bridge)
		return -EBUSY;
	if (hold_bus && !disable_pme)
		return -EINVAL;
	if (options->msi_parent && !hold_bus)
		return -EINVAL;
	if (options->provider && (!hold_bus || !options->msi_parent))
		return -EINVAL;
	bridge = pci_alloc_host_bridge(sizeof(*host));
	if (!bridge)
		return -ENOMEM;
	host = pci_host_bridge_priv(bridge);
	host->dev = dev;
	host->ecam = state->ecam;
	host->port = state->port;
	state->scan_bridge = bridge;
	spin_lock_init(&host->lock);
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	target_io = (struct n71_link_target_io){host, n71_scan_target_read, n71_scan_target_write};
	error = n71_scan_capture(&io, &host->config);
	if (error)
		goto restore;
	host->config_pending = true;
	error = n71_link_target_capture(&target_io, &host->target);
	if (error)
		goto restore;
	for (function = 0; function < 2; function++) {
		error = n71_control_capture(&io, function == 0, &reference);
		if (error)
			goto restore;
		dev_info(dev, "N71_PCIE_CONTROL_CAPTURE root=%u reads=%u capabilities=%u words=%u; read-only reference\n",
			 function == 0, reference.reads, reference.capabilities, reference.count);
		for (word = 0; word < reference.count; word++) {
			const struct n71_control_word *item = &reference.words[word];
			dev_info(dev, "N71_PCIE_CONTROL_REFERENCE root=%u where=%03x size=%u value=%08x capability=%05x\n",
				 function == 0, item->where, item->size, item->value, item->capability);
		}
	}
	/* Selected ADT ranges. This scan neither claims nor maps these windows. */
	host->windows[0] = (struct resource){.name = "N71 scan bus", .start = 0, .end = 1,
		.flags = IORESOURCE_BUS};
	host->windows[1] = (struct resource){.name = "N71 scan mem32", .start = 0x7c0000000ULL,
		.end = 0x7ffffffffULL, .flags = IORESOURCE_MEM};
	host->windows[2] = (struct resource){.name = "N71 scan mem64", .start = 0x620000000ULL,
		.end = 0x7bfffffffULL, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64 | IORESOURCE_PREFETCH};
	pci_add_resource(&bridge->windows, &host->windows[0]);
	pci_add_resource_offset(&bridge->windows, &host->windows[1], 0x700000000ULL);
	pci_add_resource_offset(&bridge->windows, &host->windows[2], 0);
	resource_list_for_each_entry(entry, &bridge->windows)
		windows++;
	if (windows != 3) {
		error = -ENOMEM;
		goto restore;
	}
	bridge->dev.parent = dev;
	bridge->ops = &n71_scan_ops;
	bridge->sysdata = host;
	bridge->enable_device = n71_scan_deny_enable;
	bridge->no_ext_tags = true;
	bridge->no_inc_mrrs = true;
	bridge->native_aer = bridge->native_pcie_hotplug = bridge->native_shpc_hotplug = 0;
	bridge->native_pme = bridge->native_ltr = bridge->native_dpc = bridge->native_cxl_error = 0;
	if (options->msi_parent) {
		error = n71_scan_msi_acquire(bridge, dev);
		dev_info(dev, "N71_PCIE_SCAN_MSI_PREPARED error=%d associated=%u; no IRQ allocation\n",
			 error, host->msi.associated);
		if (error)
			goto restore;
	}
	pci_lock_rescan_remove();
	error = n71_link_target_prepare(&target_io, &host->target);
	dev_info(dev, "N71_PCIE_SCAN_TARGET_PREPARED error=%d pending=%u prepared=%u; no retrain\n",
		 error, host->target.pending, host->target.prepared);
	if (error) {
		pci_unlock_rescan_remove();
		goto restore;
	}
	if (disable_pme) {
		error = n71_pme_disable(&io, &host->pme);
		dev_info(dev, "N71_PCIE_SCAN_PME_PREPARED error=%d pending=%u prepared=%u; no W1C\n",
			 error, host->pme.pending, host->pme.prepared);
		if (error) {
			pci_unlock_rescan_remove();
			goto restore;
		}
	}
	if (options->provider) {
		const struct n71_dart_host_request request = {.bridge = bridge, .provider = options->provider};

		error = n71_dart_host_prepare(&host->dart, &request);
		dev_info(dev, "N71_PCIE_SCAN_DART_PREPARED error=%d available=%u mapped=%u; before PCI publication\n",
			 error, host->dart.available, host->dart.mapped);
		if (error) {
			pci_unlock_rescan_remove();
			goto restore;
		}
	}
	error = pci_scan_root_bus_bridge(bridge);
	if (!error && !bridge->bus)
		error = -ENODEV;
	if (!error && bridge->bus)
		pci_walk_bus(bridge->bus, n71_scan_report_device, host);
	if (bridge->bus) {
		if (!error)
			error = n71_scan_validate_result(host);
		if (hold_bus && !error) {
			host->bus_held = true;
			pci_unlock_rescan_remove();
			dev_info(dev, "N71_PCIE_SCAN_HELD devices=%u endpoints=%u; no bind, DMA or radio\n",
				 host->devices, host->endpoints);
			return 0;
		}
		n71_scan_remove_bus(bridge);
		dev_info(dev, "N71_PCIE_SCAN_BUS_REMOVED bus-null=%u\n", !bridge->bus);
		if (!error)
			error = n71_scan_validate_result(host);
	}
	pci_unlock_rescan_remove();
restore:
	/* No registered bus remains; no PCI callbacks may outlive this cleanup. */
	report = *host;
	restore = n71_pcie_scan_cleanup(state);
	dev_info(dev, "N71_PCIE_SCAN_CLEANUP error=%d retained=%u\n", restore, !!state->scan_bridge);
	if (!error)
		error = restore;
	dev_info(dev, "N71_PCIE_SCAN_RESULT error=%d devices=%u endpoints=%u reads=%u attempts=%u writes=%u refusals=%u; counts before cleanup, no DMA or radio\n",
		 error, report.devices, report.endpoints, report.reads,
		 report.config.attempts, report.config.writes, report.config.refusals);
	return error;
}

static int n71_pcie_scan_with_mode(struct device *dev, struct n71_diagnostic *state,
				  bool disable_pme, bool hold_bus)
{
	const struct n71_scan_options options = {.disable_pme = disable_pme, .hold_bus = hold_bus};
	return n71_pcie_scan_with_options(dev, state, &options);
}

static inline int n71_pcie_scan_hold_msi(struct device *dev, struct n71_diagnostic *state)
{
	const struct n71_scan_options options = {.disable_pme = true, .hold_bus = true, .msi_parent = true};
	return n71_pcie_scan_with_options(dev, state, &options);
}

static inline int n71_pcie_scan_hold_iommu(struct device *dev, struct n71_diagnostic *state,
					struct platform_device *provider)
{
	const struct n71_scan_options options = {
		.disable_pme = true, .hold_bus = true, .msi_parent = true, .provider = provider,
	};

	if (!provider)
		return -EINVAL;
	return n71_pcie_scan_with_options(dev, state, &options);
}

static int n71_pcie_scan_with_pme(struct device *dev, struct n71_diagnostic *state,
				 bool disable_pme)
{
	return n71_pcie_scan_with_mode(dev, state, disable_pme, false);
}

/* Caller integration must retain its own module, MMIO and power references. */
static inline int n71_pcie_scan_hold(struct device *dev, struct n71_diagnostic *state)
{
	return n71_pcie_scan_with_mode(dev, state, true, true);
}

static int n71_pcie_scan(struct device *dev, struct n71_diagnostic *state)
{
	return n71_pcie_scan_with_pme(dev, state, false);
}
#endif /* N71_PCIE_SCAN_H */
