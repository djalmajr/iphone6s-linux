/* SPDX-License-Identifier: GPL-2.0-only */
/* Temporary PCI-core sizing only; remove the bus before reset/power-off. */
#ifndef N71_PCIE_SCAN_H
#define N71_PCIE_SCAN_H
#include <linux/pci.h>
#include <linux/spinlock.h>
#include "n71-pcie-scan-config.h"
#include "n71-pcie-bar-sizing.h"
#include "n71-pcie-control-reference.h"
#include "n71-pcie-scan-link-target.h"
#include "n71-pcie-pme-control.h"

struct n71_scan_host {
	struct device *dev;
	void __iomem *ecam, *port;
	spinlock_t lock;
	struct n71_scan_config config;
	struct n71_link_target target;
	struct n71_pme_state pme;
	bool config_pending;
	struct resource windows[3];
	unsigned int reads, devices, endpoints;
	int io_error;
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
		error = n71_pme_scan_write(&io, &host->config, &host->pme, &request);
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

static int n71_pcie_scan_cleanup(struct n71_diagnostic *state)
{
	struct pci_host_bridge *bridge = state->scan_bridge;
	struct n71_scan_host *host;
	struct n71_scan_io io;
	struct n71_link_target_io target_io;
	int error;

	if (!bridge)
		return 0;
	host = pci_host_bridge_priv(bridge);
	if (bridge->bus)
		return -EBUSY;
	io = (struct n71_scan_io){host, n71_scan_raw_read, n71_scan_raw_write};
	target_io = (struct n71_link_target_io){host, n71_scan_target_read, n71_scan_target_write};
	if (host->config_pending) {
		/* Retry restoration only; no PCI callbacks or scan writes remain. */
		host->config.active = true;
		error = n71_scan_restore(&io, &host->config);
		dev_info(host->dev, "N71_PCIE_SCAN_CONFIG_RESTORED error=%d; decode/readback checked\n", error);
		if (error)
			return error;
		host->config_pending = false;
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
	return 0;
}

static int n71_pcie_scan_with_pme(struct device *dev, struct n71_diagnostic *state,
				 bool disable_pme)
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
	int error, restore;

	if (state->scan_bridge)
		return -EBUSY;
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
	error = pci_scan_root_bus_bridge(bridge);
	if (!error && !bridge->bus)
		error = -ENODEV;
	if (!error && bridge->bus)
		pci_walk_bus(bridge->bus, n71_scan_report_device, host);
	if (bridge->bus) {
		pci_stop_root_bus(bridge->bus);
		pci_remove_root_bus(bridge->bus);
		dev_info(dev, "N71_PCIE_SCAN_BUS_REMOVED bus-null=%u\n", !bridge->bus);
		if (!error && (host->config.error || host->io_error))
			error = host->config.error ? host->config.error : host->io_error;
		else if (!error && (host->devices != 2 || host->endpoints != 1))
			error = -ENODEV;
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

static int n71_pcie_scan(struct device *dev, struct n71_diagnostic *state)
{
	return n71_pcie_scan_with_pme(dev, state, false);
}
#endif /* N71_PCIE_SCAN_H */
