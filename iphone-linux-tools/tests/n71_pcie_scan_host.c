/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise the unchanged adapter against a fault-injected PCI API/backend. */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "n71-pcie-contract.h"
typedef uint16_t u16;
#define __iomem
#define PCI_COMMAND 4
#define PCI_COMMAND_MASTER 4
#define PCI_STD_NUM_BARS 6
#define PCIBIOS_DEVICE_NOT_FOUND 0x86
#define PCIBIOS_BAD_REGISTER_NUMBER 0x87
#define PCIBIOS_SET_FAILED 0x88
#define PCIBIOS_SUCCESSFUL 0
#define IORESOURCE_BUS 0x1000
#define IORESOURCE_MEM 0x200
#define IORESOURCE_MEM_64 0x100000
#define IORESOURCE_PREFETCH 0x2000
typedef int spinlock_t;
#define spin_lock_init(lock) (*(lock) = 0)
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock) = 1; (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { assert(*(lock)); *(lock) = 0; (void)(flags); } while (0)

struct device { struct device *parent; };
struct resource { const char *name; uint64_t start, end; unsigned long flags; };
struct resource_entry { struct resource_entry *next; struct resource *res; uint64_t offset; };
struct resource_list { struct resource_entry *first; };
struct pci_bus { void *sysdata; unsigned int number; };
struct pci_dev {
	struct pci_bus *bus;
	unsigned int devfn, vendor, device, class;
	void *driver;
	struct resource resource[6];
};
struct pci_ops {
	int (*read)(struct pci_bus *, unsigned int, int, int, u32 *);
	int (*write)(struct pci_bus *, unsigned int, int, int, u32);
};
struct pci_host_bridge {
	struct device dev;
	struct pci_bus *bus;
	struct pci_ops *ops;
	void *sysdata;
	int (*enable_device)(struct pci_host_bridge *, struct pci_dev *);
	bool no_ext_tags, no_inc_mrrs;
	unsigned int native_aer, native_pcie_hotplug, native_shpc_hotplug, native_pme;
	unsigned int native_ltr, native_dpc, native_cxl_error;
	struct resource_list windows;
	unsigned char private[];
};
struct n71_diagnostic { void *ecam, *port; };
#define resource_list_for_each_entry(entry, list) \
	for ((entry) = (list)->first; (entry); (entry) = (entry)->next)

enum fault { NONE, CAP_WRITE, STOP_WRITE, SCAN_FAIL, MISSING_ENDPOINT, MASTER,
	WINDOW_ALLOC, LINK_DOWN, RESTORE_DROP, READ_BUDGET, WRONG_FUNCTION };
static struct {
	enum fault fault;
	u32 *ecam, port[4096];
	struct pci_host_bridge *bridge;
	struct pci_dev root, endpoint;
	struct pci_bus endpoint_bus;
	unsigned int allocations, scans, stops, removes, writes, bars_after_scan;
	bool locked, returned;
	char log[16384];
	size_t used;
} mock;

static u32 readl(const void *address)
{
	u32 value;
	memcpy(&value, address, sizeof(value));
	return value;
}
static void writel(u32 value, void *address)
{
	if (mock.returned) {
		assert(!mock.scans || mock.removes == 1);
		mock.bars_after_scan++;
	}
	memcpy(address, &value, sizeof(value));
	mock.writes++;
}
static void writew(u16 value, void *address)
{
	if (mock.returned) {
		assert(!mock.scans || mock.removes == 1);
		if (mock.fault == RESTORE_DROP && address == (void *)&mock.ecam[0x100004 / 4] && value == 0x100)
			return;
	}
	memcpy(address, &value, sizeof(value));
	mock.writes++;
}
static void dev_info(struct device *dev, const char *format, ...)
{
	va_list args;
	int length;
	(void)dev;
	va_start(args, format);
	length = vsnprintf(mock.log + mock.used, sizeof(mock.log) - mock.used, format, args);
	va_end(args);
	assert(length >= 0 && (size_t)length < sizeof(mock.log) - mock.used);
	mock.used += length;
}
static struct pci_host_bridge *pci_alloc_host_bridge(size_t size)
{
	struct pci_host_bridge *bridge = calloc(1, sizeof(*bridge) + size);
	assert(bridge);
	mock.allocations++;
	return bridge;
}
static void *pci_host_bridge_priv(struct pci_host_bridge *bridge) { return bridge->private; }
static void pci_free_host_bridge(struct pci_host_bridge *bridge)
{
	struct resource_entry *entry = bridge->windows.first;
	while (entry) { struct resource_entry *next = entry->next; free(entry); entry = next; }
	assert(mock.allocations == 1 && (!mock.scans || mock.removes == 1));
	free(bridge); mock.allocations--;
}
static void pci_add_resource_offset(struct resource_list *list, struct resource *res, uint64_t offset)
{
	struct resource_entry *entry;
	if (mock.fault == WINDOW_ALLOC && res->start == 0x7c0000000ULL)
		return;
	entry = calloc(1, sizeof(*entry)); assert(entry);
	entry->next = list->first; entry->res = res; entry->offset = offset; list->first = entry;
}
static void pci_add_resource(struct resource_list *list, struct resource *res)
{
	pci_add_resource_offset(list, res, 0);
}
static void pci_lock_rescan_remove(void) { assert(!mock.locked); mock.locked = true; }
static void pci_unlock_rescan_remove(void) { assert(mock.locked); mock.locked = false; }
static int pci_scan_root_bus_bridge(struct pci_host_bridge *bridge)
{
	u32 value;
	unsigned int function, index;
	assert(mock.locked && bridge->enable_device(bridge, NULL) == -EPERM);
	assert(bridge->no_ext_tags && !bridge->native_aer && !bridge->native_pme);
	if (mock.fault == SCAN_FAIL)
		return -ENOMEM;
	mock.bridge = bridge; mock.scans++;
	bridge->bus = calloc(1, sizeof(*bridge->bus)); assert(bridge->bus);
	bridge->bus->sysdata = bridge->sysdata;
	mock.endpoint_bus = (struct pci_bus){bridge->sysdata, 1};
	mock.root = (struct pci_dev){.bus = bridge->bus, .devfn = 8, .vendor = 0x106b,
		.device = 0x1004, .class = 0x060400};
	mock.endpoint = (struct pci_dev){.bus = &mock.endpoint_bus, .vendor = 0x14e4,
		.device = 0x43a3, .class = 0x028000};
	mock.endpoint.resource[0] = (struct resource){.start = 0x7c0000000ULL,
		.end = 0x7c0003fffULL, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
	assert(bridge->ops->read(bridge->bus, 0, 0, 4, &value) == PCIBIOS_DEVICE_NOT_FOUND);
	assert(value == 0xffffffff);
	for (function = 0; function < 2; function++) {
		struct pci_bus *bus = function ? &mock.endpoint_bus : bridge->bus;
		unsigned int devfn = function ? 0 : 8;
		assert(bridge->ops->write(bus, devfn, 4, 2, 0x100) == 0);
		for (index = 0; index < (function ? 6U : 2U); index++) {
			u32 original;
			assert(bridge->ops->read(bus, devfn, 0x10 + index * 4, 4, &original) == 0);
			assert(bridge->ops->write(bus, devfn, 0x10 + index * 4, 4, 0xffffffff) == 0);
			assert(bridge->ops->write(bus, devfn, 0x10 + index * 4, 4, original) == 0);
		}
		assert(bridge->ops->write(bus, devfn, 4, 2, 0x103) == 0);
	}
	if (mock.fault == CAP_WRITE)
		assert(bridge->ops->write(&mock.endpoint_bus, 0, 0x80, 4, 1) == PCIBIOS_SET_FAILED);
	if (mock.fault == WRONG_FUNCTION)
		assert(bridge->ops->write(&mock.endpoint_bus, 8, 0x10, 4, 0xffffffff) == PCIBIOS_SET_FAILED);
	if (mock.fault == MASTER)
		mock.ecam[0x100004 / 4] |= 4;
	if (mock.fault == READ_BUDGET)
		for (index = 0; index < 4100; index++)
			bridge->ops->read(&mock.endpoint_bus, 0, 0, 4, &value);
	if (mock.fault == READ_BUDGET)
		mock.ecam[0x100010 / 4] = 0xffffffff;
	mock.returned = true;
	return 0; /* Like PCI core, ignored config errors need the adapter latch. */
}
static int pci_read_config_word(struct pci_dev *dev, unsigned int where, u16 *value)
{
	u32 result;
	int error = mock.bridge->ops->read(dev->bus, dev->devfn, where, 2, &result);
	*value = result;
	return error;
}
static void pci_walk_bus(struct pci_bus *bus, int (*callback)(struct pci_dev *, void *), void *context)
{
	assert(bus && mock.locked);
	if (callback(&mock.root, context) || mock.fault == MISSING_ENDPOINT)
		return;
	callback(&mock.endpoint, context);
}
static void pci_stop_root_bus(struct pci_bus *bus)
{
	assert(bus && mock.locked && !mock.removes); mock.stops++;
	if (mock.fault == STOP_WRITE)
		assert(mock.bridge->ops->write(bus, 8, 0x80, 4, 1) == PCIBIOS_SET_FAILED);
}
static void pci_remove_root_bus(struct pci_bus *bus)
{
	assert(mock.stops == 1 && mock.locked); mock.removes++;
	free(bus); mock.bridge->bus = NULL;
}
#include "n71-pcie-scan.h"

int main(void)
{
	const int expected[] = {0, -EPERM, -EPERM, -ENOMEM, -ENODEV, -EACCES,
		-ENOMEM, -ENOLINK, -EIO, -E2BIG, -ENODEV};
	unsigned int index;
	for (index = 0; index < sizeof(expected) / sizeof(*expected); index++) {
		struct n71_diagnostic state;
		struct device device = {0};
		memset(&mock, 0, sizeof(mock)); mock.fault = index;
		mock.ecam = calloc(0x1000000 / 4, sizeof(u32)); assert(mock.ecam);
		mock.ecam[0x8000 / 4] = 0x1004106b; mock.ecam[0x100000 / 4] = 0x43a314e4;
		mock.ecam[0x8004 / 4] = mock.ecam[0x100004 / 4] = 0xa9000103;
		mock.ecam[0x8008 / 4] = 0x06040001; mock.ecam[0x100008 / 4] = 0x02800002;
		mock.ecam[0x800c / 4] = 0x00010000; mock.ecam[0x8018 / 4] = 0x44010100;
		mock.ecam[0x100010 / 4] = 0xc0000004;
		mock.port[0x88 / 4] = index == LINK_DOWN ? 0 : 5;
		state = (struct n71_diagnostic){mock.ecam, mock.port};
		{
			int result = n71_pcie_scan(&device, &state);
			if (result != expected[index])
				fprintf(stderr, "case=%u actual=%d expected=%d\n%s", index, result, expected[index], mock.log);
			assert(result == expected[index]);
		}
		assert(!mock.allocations && !mock.locked);
		if (mock.scans)
			assert(mock.stops == 1 && mock.removes == 1);
		assert(mock.ecam[0x100010 / 4] == 0xc0000004);
		assert((mock.ecam[0x8004 / 4] & 0xffff0000) == 0xa9000000);
		assert((mock.ecam[0x100004 / 4] & 0xffff0000) == 0xa9000000);
		assert(strstr(mock.log, "N71_PCIE_SCAN_RESULT error="));
		if (!index) {
			assert(strstr(mock.log, "N71_PCIE_SCAN_BUS_REMOVED bus-null=1"));
			assert(strstr(mock.log, "N71_PCIE_SCAN_CONFIG_RESTORED error=0"));
			assert(strstr(mock.log, "index=0 start=00000007c0000000 end=00000007c0003fff"));
		}
		free(mock.ecam);
	}
	puts("N71_PCIE_SCAN_HOST_OK cases=11");
	return 0;
}
