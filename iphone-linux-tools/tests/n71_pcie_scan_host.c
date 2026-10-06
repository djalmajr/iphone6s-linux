/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise scan/held-bus callbacks against a fault-injected PCI API/backend. */
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
#define PCI_IO_BASE 0x1c
#define PCI_COMMAND_MASTER 4
#define PCI_STD_NUM_BARS 6
#define PCIBIOS_DEVICE_NOT_FOUND 0x86
#define PCIBIOS_BAD_REGISTER_NUMBER 0x87
#define PCIBIOS_SET_FAILED 0x88
#define PCIBIOS_SUCCESSFUL 0
#define IORESOURCE_BUS 0x1000
#define IORESOURCE_IO 0x100
#define IORESOURCE_MEM 0x200
#define IORESOURCE_MEM_64 0x100000
#define IORESOURCE_PREFETCH 0x2000
#define IORESOURCE_TYPE_BITS 0x1f00
#define IORESOURCE_PCI_FIXED 0x10
#define IORESOURCE_UNSET 0x20000000
#define PCI_ROM_RESOURCE 6
#define PCI_BRIDGE_IO_WINDOW 7
#define PCI_BRIDGE_MEM_WINDOW 8
#define PCI_BRIDGE_PREF_MEM_WINDOW 9
typedef int spinlock_t;
#define spin_lock_init(lock) (*(lock) = 0)
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock) = 1; (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { assert(*(lock)); *(lock) = 0; (void)(flags); } while (0)

struct device { struct device *parent; };
struct resource { const char *name; uint64_t start, end; unsigned long flags; struct resource *parent, *child; };
static struct resource iomem_resource, foreign_resource;
static uint64_t resource_size(const struct resource *res) { return res->end - res->start + 1; }
struct resource_entry { struct resource_entry *next; struct resource *res; uint64_t offset; };
struct resource_list { struct resource_entry *first; };
struct pci_bus { void *sysdata; unsigned int number; struct pci_dev *self; unsigned int bridge_ctl; };
struct pci_dev {
	struct pci_bus *bus;
	unsigned int devfn, vendor, device, class;
	void *driver;
	struct resource resource[10];
	struct pci_bus *subordinate;
	bool enabled, io_window, pref_window, io_window_1k;
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
struct n71_diagnostic { void *ecam, *port; struct pci_host_bridge *scan_bridge; };
#define resource_list_for_each_entry(entry, list) \
	for ((entry) = (list)->first; (entry); (entry) = (entry)->next)

enum fault { NONE, CAP_WRITE, STOP_WRITE, SCAN_FAIL, MISSING_ENDPOINT, MASTER,
	WINDOW_ALLOC, LINK_DOWN, RESTORE_DROP, READ_BUDGET, WRONG_FUNCTION,
	TARGET_PREPARE_DROP, TARGET_RESTORE_DROP, TARGET_OWNER_CHANGED,
	TARGET_LINK_CHANGED, ROOT_DECODE, SCAN_PARTIAL_FAIL, TARGET_VERIFY_CHANGED,
	REFUSAL_AND_RESTORE_DROP, BRIDGE_ALLOC_FAIL, SCAN_NO_BUS,
	PME_NONE, PME_PREPARE_DROP, PME_RESTORE_DROP, PME_CORE_EVENT,
	PME_DISABLE_EVENT, PME_CAP_BAD, PME_CORE_LATCHED, PME_LINK_LOST,
	STOP_AND_RESTORE };
enum resource_fault { RESOURCE_OK, CLAIM_CONFLICT, BAD_LAYOUT, BAD_PARENT,
	OVERLAP, BAD_TRANSLATION, BAD_BAR, MISSING_ASSIGNMENT, CORE_REFUSAL,
	RESTORE_EXTRA_DROP, RELEASE_FAIL, CHILD_LEFT, ACTIVE_PHASE, WRONG_TOPOLOGY,
	BRIDGE_CONTROL_MISMATCH, ROOT_WINDOW_BAD, EXTRA_BAR, AFTER_ASSIGN_DRIVER, ROLLBACK_BUDGET, READBACK_DROP };
static struct {
	enum fault fault;
	u32 *ecam, port[4096];
	struct pci_host_bridge *bridge;
	struct pci_dev root, endpoint;
	struct pci_bus endpoint_bus;
	unsigned int allocations, scans, stops, removes, writes, bars_after_scan;
	unsigned int target_prepares, target_restores;
	unsigned int pme_prepares, pme_restores, pme_reads;
	bool locked, returned, pme;
	bool resource_mode, allocating, io_readonly, pref_readonly;
	unsigned int optional_attempts;
	enum resource_fault resource_fault;
	unsigned int claims, releases, sizing, assigning, references;
	char log[16384];
	size_t used;
} mock;

static u32 readl(const void *address)
{
	u32 value;
	if (mock.ecam && address == &mock.ecam[0x10004c / 4])
		mock.pme_reads++;
	memcpy(&value, address, sizeof(value));
	return value;
}
static void writel(u32 value, void *address)
{
	if (mock.allocating && (address == &mock.ecam[0x8030 / 4] ||
	    address == &mock.ecam[0x8024 / 4] || address == &mock.ecam[0x8028 / 4] ||
	    address == &mock.ecam[0x802c / 4])) {
		mock.optional_attempts++;
		if ((address == &mock.ecam[0x8030 / 4] && mock.io_readonly) ||
		    (address != &mock.ecam[0x8030 / 4] && mock.pref_readonly))
			return;
	}
	if (mock.allocating && mock.resource_fault == READBACK_DROP &&
	    address == &mock.ecam[0x8030 / 4] && value == 0xffff)
		return;
	if (mock.returned && !mock.allocating) {
		assert(!mock.scans || mock.removes == 1);
		mock.bars_after_scan++;
		if (mock.resource_fault == RESTORE_EXTRA_DROP && address == &mock.ecam[0x8020 / 4])
			return;
	}
	memcpy(address, &value, sizeof(value));
	mock.writes++;
}
static void writew(u16 value, void *address)
{
	if (mock.allocating && address == &mock.ecam[0x801c / 4]) {
		mock.optional_attempts++;
		if (mock.io_readonly)
			return;
	}
	if (mock.returned && !mock.allocating) {
		assert(!mock.scans || mock.removes == 1);
		if ((mock.fault == RESTORE_DROP || mock.fault == STOP_AND_RESTORE) &&
		    address == (void *)&mock.ecam[0x100004 / 4] && value == 0x100)
			return;
	}
	if (address == (void *)&mock.ecam[0x10004c / 4]) {
		u16 original;
		memcpy(&original, address, sizeof(original));
		assert(mock.pme && !(value & 0x8000));
		assert((value & ~0x8100U) == (original & ~0x8100U));
		if (value & 0x100) {
			assert(!mock.scans || mock.removes == 1);
			mock.pme_restores++;
			if (mock.fault == PME_RESTORE_DROP)
				return;
		} else {
			assert(!mock.scans);
			mock.pme_prepares++;
			if (mock.fault == PME_PREPARE_DROP)
				return;
		}
		value = (value & ~0x8000U) | (original & 0x8000U);
		if (mock.fault == PME_DISABLE_EVENT)
			value |= 0x8000;
	}
	if (address == (void *)mock.ecam + 0x80a0) {
		if (value == 2) {
			assert(!mock.scans);
			mock.target_prepares++;
			if (mock.fault == TARGET_PREPARE_DROP)
				return;
			if (mock.fault == TARGET_LINK_CHANGED)
				mock.ecam[0x8080 / 4] = 0x20020000;
		} else {
			assert(value == 1 && (!mock.scans || mock.removes == 1));
			mock.target_restores++;
			if (mock.fault == TARGET_RESTORE_DROP || mock.fault == REFUSAL_AND_RESTORE_DROP)
				return;
			if (mock.fault == TARGET_VERIFY_CHANGED)
				mock.ecam[0x8080 / 4] = 0x20020000;
		}
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
	if (mock.fault == BRIDGE_ALLOC_FAIL) {
		free(bridge);
		return NULL;
	}
	mock.allocations++;
	return bridge;
}
static void *pci_host_bridge_priv(struct pci_host_bridge *bridge) { return bridge->private; }
static void pci_free_host_bridge(struct pci_host_bridge *bridge)
{
	struct resource_entry *entry = bridge->windows.first;
	while (entry) { struct resource_entry *next = entry->next; free(entry); entry = next; }
	assert(mock.allocations == 1 && (!mock.scans || mock.removes == 1));
	assert(!mock.resource_mode || (!iomem_resource.child && !mock.references));
	assert((mock.ecam[0x80a0 / 4] & 0xffff) == 1);
	if (mock.pme)
		assert(mock.ecam[0x10004c / 4] & 0x100);
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
	/* Regression: letting core see TLS1 triggers its unqualified retrain path. */
	assert((mock.ecam[0x80a0 / 4] & 0xffff) == 2);
	if (mock.pme)
		assert((mock.ecam[0x10004c / 4] & 0xffff) == 0x4008);
	if (mock.fault == SCAN_FAIL)
		return -ENOMEM;
	if (mock.fault == SCAN_NO_BUS)
		return 0;
	mock.bridge = bridge; mock.scans++;
	bridge->bus = calloc(1, sizeof(*bridge->bus)); assert(bridge->bus);
	bridge->bus->sysdata = bridge->sysdata;
	mock.endpoint_bus = (struct pci_bus){.sysdata = bridge->sysdata, .number = 1};
	mock.root = (struct pci_dev){.bus = bridge->bus, .devfn = 8, .vendor = 0x106b,
		.device = 0x1004, .class = 0x060400, .io_window = true, .pref_window = true,
		.io_window_1k = true}; /* Legacy cases leave the separate IO16 opt-in out of scope. */
	mock.endpoint = (struct pci_dev){.bus = &mock.endpoint_bus, .vendor = 0x14e4,
		.device = 0x43a3, .class = 0x028000};
	mock.root.subordinate = &mock.endpoint_bus; mock.endpoint_bus.self = &mock.root;
	mock.endpoint.resource[0] = (struct resource){.start = 0x7c0000000ULL,
		.end = 0x7c0003fffULL, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
	if (mock.fault == SCAN_PARTIAL_FAIL) {
		mock.returned = true;
		return -ENOMEM;
	}
	assert(bridge->ops->read(bridge->bus, 0, 0, 4, &value) == PCIBIOS_DEVICE_NOT_FOUND);
	assert(value == 0xffffffff);
	for (function = 0; function < 2; function++) {
		struct pci_bus *bus = function ? &mock.endpoint_bus : bridge->bus;
		unsigned int devfn = function ? 0 : 8;
		assert(bridge->ops->write(bus, devfn, 4, 2, function ? 0x100 : 0) == 0);
		for (index = 0; index < (function ? 6U : 2U); index++) {
			u32 original;
			assert(bridge->ops->read(bus, devfn, 0x10 + index * 4, 4, &original) == 0);
			assert(bridge->ops->write(bus, devfn, 0x10 + index * 4, 4, 0xffffffff) == 0);
			assert(bridge->ops->write(bus, devfn, 0x10 + index * 4, 4, original) == 0);
		}
		assert(bridge->ops->write(bus, devfn, 4, 2, function ? (mock.resource_mode ? 0x100 : 0x103) : 0) == 0);
	}
	if (mock.pme) {
		unsigned int reads;
		if (mock.fault == PME_CORE_EVENT)
			mock.ecam[0x10004c / 4] |= 0x8000;
		if (mock.fault == PME_CORE_LATCHED)
			assert(bridge->ops->write(&mock.endpoint_bus, 0, 0x80, 4, 1) == PCIBIOS_SET_FAILED);
		reads = mock.pme_reads;
		assert(bridge->ops->write(&mock.endpoint_bus, 0, 0x4c, 2, 0xc008) ==
		       (mock.fault == PME_CORE_EVENT || mock.fault == PME_CORE_LATCHED ? PCIBIOS_SET_FAILED : 0));
		if (mock.fault == PME_CORE_LATCHED)
			assert(mock.pme_reads == reads);
	}
	if (mock.fault == CAP_WRITE || mock.fault == REFUSAL_AND_RESTORE_DROP)
		assert(bridge->ops->write(&mock.endpoint_bus, 0, 0x80, 4, 1) == PCIBIOS_SET_FAILED);
	if (mock.fault == WRONG_FUNCTION)
		assert(bridge->ops->write(&mock.endpoint_bus, 8, 0x10, 4, 0xffffffff) == PCIBIOS_SET_FAILED);
	if (mock.fault == MASTER)
		mock.ecam[0x100004 / 4] |= 4;
	if (mock.fault == TARGET_OWNER_CHANGED)
		mock.ecam[0x8008 / 4] = 0x02800001;
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
	if (mock.resource_mode && mock.resource_fault == WRONG_TOPOLOGY) {
		struct pci_dev extra = {0}; callback(&extra, context);
	}
}
static void pci_stop_root_bus(struct pci_bus *bus)
{
	assert(bus && mock.locked && !mock.removes); mock.stops++;
	if (mock.fault == STOP_WRITE || mock.fault == STOP_AND_RESTORE)
		assert(mock.bridge->ops->write(bus, 8, 0x80, 4, 1) == PCIBIOS_SET_FAILED);
}
static void pci_remove_root_bus(struct pci_bus *bus)
{
	assert(mock.stops == 1 && mock.locked); mock.removes++;
	if (mock.resource_mode) {
		unsigned int index;
		struct resource *window = mock.root.resource[PCI_BRIDGE_MEM_WINDOW].parent;
		for (index = 0; index < 10; index++) {
			mock.root.resource[index].parent = mock.endpoint.resource[index].parent = NULL;
			mock.root.resource[index].child = NULL;
		}
		if (window) window->child = mock.resource_fault == CHILD_LEFT ? &foreign_resource : NULL;
	}
	free(bus); mock.bridge->bus = NULL;
	if (mock.fault == PME_LINK_LOST)
		mock.port[0x88 / 4] = 0;
}
static int request_resource(struct resource *parent, struct resource *res)
{
	assert(mock.locked && parent == &iomem_resource && !parent->child && !res->parent);
	mock.claims++;
	if (mock.resource_fault == CLAIM_CONFLICT) return -EBUSY;
	parent->child = res; res->parent = parent; return 0;
}
static int release_resource(struct resource *res)
{
	assert(mock.removes == 1 && res->parent == &iomem_resource && !res->child);
	assert(mock.ecam[0x8020 / 4] == 0x12301230 && mock.ecam[0x100010 / 4] == 4);
	mock.releases++;
	if (mock.resource_fault == RELEASE_FAIL) return -EIO;
	iomem_resource.child = res->parent = NULL; return 0;
}
#include "n71-pcie-scan.h"

static struct pci_dev *pci_get_slot(struct pci_bus *bus, unsigned int devfn)
{
	struct pci_dev *dev = bus->number == 0 && devfn == 8 ? &mock.root : bus->number == 1 && !devfn ? &mock.endpoint : NULL;
	assert(mock.locked); if (dev) mock.references++; return dev;
}
static void pci_dev_put(struct pci_dev *dev) { if (dev) { assert(mock.references); mock.references--; } }
static bool pci_is_enabled(struct pci_dev *dev) { return dev->enabled; }
struct pci_bus_region { uint64_t start, end; };
static void pcibios_resource_to_bus(struct pci_bus *bus, struct pci_bus_region *region, struct resource *res)
{
	(void)bus; region->start = res->start - 0x700000000ULL; region->end = res->end - 0x700000000ULL;
	if (mock.resource_fault == BAD_TRANSLATION) region->start++;
}
static void pci_bus_size_bridges(struct pci_bus *bus)
{
	assert(bus == mock.bridge->bus && mock.locked && mock.claims == 1);
	assert(iomem_resource.child && !mock.sizing); mock.sizing++;
}
static void pci_bus_assign_resources(const struct pci_bus *bus)
{
	struct n71_scan_host *host = pci_host_bridge_priv(mock.bridge);
	struct resource *window = &mock.root.resource[PCI_BRIDGE_MEM_WINDOW];
	const struct n71_scan_request steps[] = {
		{false, 0x10, 0xc0800004, 4}, {false, 0x14, 0, 4},
		{false, 0x18, 0xc0000004, 4}, {false, 0x1c, 0, 4},
		{true, 0x30, 0xffff, 4}, {true, 0x1c, 0xf0, 2}, {true, 0x30, 0, 4},
		{true, 0x20, 0xc080c000, 4}, {true, 0x2c, 0, 4},
		{true, 0x24, 0xfff0, 4}, {true, 0x28, 0, 4}, {true, 0x3e, 0, 2}
	};
	unsigned int index;
	assert(bus == mock.bridge->bus && mock.locked && mock.sizing == 1 && !mock.assigning);
	mock.assigning++; mock.allocating = true;
	if (mock.resource_fault == CORE_REFUSAL)
		mock.bridge->ops->write(&mock.endpoint_bus, 0, 0x80, 4, 1);
	for (index = 0; index < sizeof(steps) / sizeof(steps[0]); index++)
		mock.bridge->ops->write(steps[index].root ? mock.bridge->bus : &mock.endpoint_bus,
			steps[index].root ? 8 : 0, steps[index].where, steps[index].size, steps[index].value);
	mock.allocating = false;
	*window = (struct resource){.start = 0x7c0000000ULL, .end = 0x7c08fffffULL,
		.flags = IORESOURCE_MEM, .parent = &host->windows[1]};
	host->windows[1].child = window;
	mock.endpoint.resource[0] = (struct resource){.start = 0x7c0800000ULL, .end = 0x7c0807fffULL,
		.flags = IORESOURCE_MEM | IORESOURCE_MEM_64, .parent = window};
	mock.endpoint.resource[2] = (struct resource){.start = 0x7c0000000ULL, .end = 0x7c03fffffULL,
		.flags = IORESOURCE_MEM | IORESOURCE_MEM_64, .parent = window};
	if (mock.resource_fault == BAD_PARENT) mock.endpoint.resource[0].parent = &foreign_resource;
	if (mock.resource_fault == OVERLAP) {
		mock.endpoint.resource[0].start = 0x7c0000000ULL;
		mock.endpoint.resource[0].end = 0x7c0007fffULL;
		mock.ecam[0x100010 / 4] = 0xc0000004;
	}
	if (mock.resource_fault == BAD_BAR) mock.ecam[0x100010 / 4] ^= 0x8000;
	if (mock.resource_fault == MISSING_ASSIGNMENT) mock.endpoint.resource[2].parent = NULL;
	if (mock.resource_fault == ROOT_WINDOW_BAD) window->end++;
	if (mock.resource_fault == EXTRA_BAR) mock.endpoint.resource[4].flags = IORESOURCE_MEM;
	if (mock.resource_fault == AFTER_ASSIGN_DRIVER) mock.endpoint.driver = &mock;
}
#include "n71-pcie-resource-assign.h"

static void initialize_case(enum fault index, bool pme)
{
	memset(&mock, 0, sizeof(mock)); mock.fault = index;
	mock.pme = pme;
	mock.ecam = calloc(0x1000000 / 4, sizeof(u32)); assert(mock.ecam);
	mock.ecam[0x8000 / 4] = 0x1004106b; mock.ecam[0x100000 / 4] = 0x43a314e4;
	mock.ecam[0x8004 / 4] = 0xa9100000;
	mock.ecam[0x100004 / 4] = 0xa9000103;
	mock.ecam[0x8008 / 4] = 0x06040001; mock.ecam[0x100008 / 4] = 0x02800002;
	mock.ecam[0x800c / 4] = 0x00010000; mock.ecam[0x8018 / 4] = 0x44010100;
	mock.ecam[0x100010 / 4] = 0xc0000004;
	mock.ecam[0x8034 / 4] = 0x70;
	mock.ecam[0x8070 / 4] = 0x00420010;
	mock.ecam[0x807c / 4] = 0x00100002;
	mock.ecam[0x809c / 4] = 6;
	mock.ecam[0x8080 / 4] = 0x20010000;
	mock.ecam[0x80a0 / 4] = 0x5a5a0001;
	if (mock.pme) {
		mock.ecam[0x100004 / 4] |= 0x100000;
		mock.ecam[0x100034 / 4] = 0x48;
		mock.ecam[0x100048 / 4] = index == PME_CAP_BAD ? 0x40001 : 0x30001;
		mock.ecam[0x10004c / 4] = 0xabc04108;
	}
	if (index == ROOT_DECODE)
		mock.ecam[0x8004 / 4] |= 1;
	mock.port[0x88 / 4] = index == LINK_DOWN ? 0 : 5;
}

static unsigned int exercise_held_bus(void)
{
	const enum fault faults[] = {PME_NONE, STOP_WRITE, RESTORE_DROP,
		PME_RESTORE_DROP, TARGET_RESTORE_DROP, PME_LINK_LOST, STOP_AND_RESTORE};
	const int cleanup_errors[] = {0, -EPERM, -EIO, -EIO, -EIO, -ENOLINK, -EIO};
	const enum fault scan_faults[] = {CAP_WRITE, SCAN_FAIL, SCAN_NO_BUS,
		SCAN_PARTIAL_FAIL, MISSING_ENDPOINT, MASTER, PME_PREPARE_DROP, PME_CORE_EVENT};
	const int scan_errors[] = {-EPERM, -ENOMEM, -ENODEV, -ENOMEM,
		-ENODEV, -EACCES, -EAGAIN, -EPERM};
	struct device dev = {0};
	struct n71_diagnostic state;
	unsigned int index, cases = 0;

	for (index = 0; index < sizeof(faults) / sizeof(*faults); index++) {
		struct n71_scan_host *host;
		u32 identity;
		initialize_case(faults[index], true);
		state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
		assert(n71_pcie_scan_hold(&dev, &state) == 0);
		assert(state.scan_bridge && state.scan_bridge->bus && mock.allocations == 1);
		host = pci_host_bridge_priv(state.scan_bridge);
		assert(host->bus_held && host->config_pending && host->config.active);
		assert(host->pme.pending && host->pme.prepared && host->target.pending);
		assert(!mock.locked && !mock.stops && !mock.removes && !mock.target_restores && !mock.pme_restores);
		assert(state.scan_bridge->enable_device(state.scan_bridge, &mock.endpoint) == -EPERM);
		assert(state.scan_bridge->ops->read(&mock.endpoint_bus, 0, 0, 4, &identity) == 0);
		assert(identity == 0x43a314e4);
		assert(n71_pcie_scan_hold(&dev, &state) == -EBUSY && mock.scans == 1);
		assert(n71_pcie_scan(&dev, &state) == -EBUSY && mock.allocations == 1);
		assert(strstr(mock.log, "N71_PCIE_SCAN_HELD devices=2 endpoints=1"));
		assert(!strstr(mock.log, "N71_PCIE_SCAN_CLEANUP"));
		if (index == 0) {
			/* A bus with unproved ownership cannot be removed or restored. */
			unsigned int writes = mock.writes;
			host->bus_held = false;
			assert(n71_pcie_scan_cleanup(&state) == -EBUSY && state.scan_bridge);
			assert(mock.writes == writes && !mock.stops && !mock.removes);
			host->bus_held = true;
		}
		assert(n71_pcie_scan_cleanup(&state) == cleanup_errors[index]);
		assert(mock.stops == 1 && mock.removes == 1 && !mock.locked);
		if (index >= 2) {
			assert(state.scan_bridge && !state.scan_bridge->bus && mock.allocations == 1);
			host = pci_host_bridge_priv(state.scan_bridge);
			assert(!host->bus_held);
			assert(host->config_pending || host->pme.pending || host->target.pending);
			assert(n71_pcie_scan_hold(&dev, &state) == -EBUSY && mock.scans == 1);
			assert(n71_pcie_scan_cleanup(&state) == cleanup_errors[index]);
			mock.fault = NONE;
			mock.port[0x88 / 4] = 5;
			assert(n71_pcie_scan_cleanup(&state) == (faults[index] == STOP_AND_RESTORE ? -EPERM : 0));
		}
		assert(!state.scan_bridge && !mock.allocations);
		assert(n71_pcie_scan_cleanup(&state) == 0 && mock.scans == 1);
		assert(mock.stops == 1 && mock.removes == 1 && !mock.locked);
		assert(mock.ecam[0x80a0 / 4] == 0x5a5a0001);
		assert(mock.ecam[0x10004c / 4] == 0xabc04108);
		assert(mock.ecam[0x100010 / 4] == 0xc0000004);
		free(mock.ecam);
		cases++;
	}
	for (index = 0; index < sizeof(scan_faults) / sizeof(*scan_faults); index++) {
		initialize_case(scan_faults[index], true);
		state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
		assert(n71_pcie_scan_hold(&dev, &state) == scan_errors[index]);
		assert(!state.scan_bridge && !mock.allocations && !mock.locked);
		assert(!strstr(mock.log, "N71_PCIE_SCAN_HELD"));
		assert(n71_pcie_scan_cleanup(&state) == 0);
		if (mock.scans)
			assert(mock.stops == 1 && mock.removes == 1);
		free(mock.ecam);
		cases++;
	}
	initialize_case(PME_NONE, true);
	state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
	assert(n71_pcie_scan_with_mode(&dev, &state, false, true) == -EINVAL);
	assert(!state.scan_bridge && !mock.allocations && !mock.scans && !mock.writes);
	free(mock.ecam);
	return cases + 1;
}

static unsigned int exercise_resource_assignment(void)
{
	const int expected[] = {0, -EBUSY, -EINVAL, -EACCES, -EACCES, -ERANGE,
		-EIO, -EACCES, -EPERM, 0, 0, 0, 0, -ENODEV, -EACCES, -EACCES, -EACCES, -EACCES, 0, -EIO};
	struct device device = {0};
	unsigned int fault;
	for (fault = 0; fault < sizeof(expected) / sizeof(expected[0]); fault++) {
		struct n71_diagnostic state;
		struct n71_scan_host *host;
		int cleanup;
		initialize_case(PME_NONE, true); mock.resource_mode = true;
		iomem_resource = (struct resource){0};
		mock.ecam[0x100004 / 4] &= ~3U;
		mock.ecam[0x100010 / 4] = mock.ecam[0x100018 / 4] = 4;
		mock.ecam[0x8020 / 4] = 0x12301230;
		mock.ecam[0x802c / 4] = 0x55667788;
		mock.ecam[0x8030 / 4] = 0xaabbccdd;
		if (fault == READBACK_DROP) mock.ecam[0x8030 / 4] = 0;
		state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
		assert(n71_pcie_scan_hold(&device, &state) == 0);
		host = pci_host_bridge_priv(state.scan_bridge);
		mock.endpoint.resource[0] = (struct resource){.end = 0x7fff, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
		mock.endpoint.resource[2] = (struct resource){.end = 0x3fffff, .flags = IORESOURCE_MEM | IORESOURCE_MEM_64};
		mock.root.resource[PCI_BRIDGE_MEM_WINDOW].flags = IORESOURCE_MEM;
		mock.resource_fault = fault;
		if (fault == BAD_LAYOUT) mock.endpoint.resource[0].end--;
		if (fault == BRIDGE_CONTROL_MISMATCH) mock.endpoint_bus.bridge_ctl = 2;
		assert(n71_pcie_assign_resources(&state) == expected[fault]);
		/* Mutation captured: missing, duplicated, reordered or altered first-readback report. */
		{
			const char *readback = strstr(mock.log, "N71_PCIE_ASSIGN_READBACK ");
			const char *result = strstr(mock.log, "N71_PCIE_RESOURCE_RESULT ");
			assert(readback && result && readback < result);
			assert(!strstr(readback + 1, "N71_PCIE_ASSIGN_READBACK "));
			assert(strstr(readback, fault == READBACK_DROP ?
				"failed=1 root=1 where=030 size=4 value=0000ffff before=00000000 after_valid=1 after=00000000 write_error=0 read_error=0; no additional IO\n" :
				"failed=0 root=0 where=000 size=0 value=00000000 before=00000000 after_valid=0 after=00000000 write_error=0 read_error=0; no additional IO\n"));
		}
		assert(!host->resources.active && host->resources_assigned == !expected[fault]);
		assert(!mock.locked && !mock.references && mock.scans == 1);
		assert(n71_pcie_assign_resources(&state) == (expected[fault] ? expected[fault] : -EALREADY));
		assert(!strstr(strstr(mock.log, "N71_PCIE_ASSIGN_READBACK ") + 1, "N71_PCIE_ASSIGN_READBACK "));
		assert(mock.sizing <= 1 && mock.assigning == mock.sizing);
		if (fault == ACTIVE_PHASE) {
			host->resources.active = true;
			assert(n71_pcie_scan_cleanup(&state) == -EBUSY && !mock.removes);
			host->resources.active = false;
		}
		if (fault == ROLLBACK_BUDGET) host->reads = 4096;
		cleanup = n71_pcie_scan_cleanup(&state);
		if (fault == RESTORE_EXTRA_DROP || fault == RELEASE_FAIL || fault == CHILD_LEFT) {
			assert(cleanup == (fault == CHILD_LEFT ? -EBUSY : -EIO) && state.scan_bridge);
			assert(host->window_claimed && mock.removes == 1 && host->pme.pending && host->target.pending);
			assert(n71_pcie_scan_cleanup(&state) == cleanup && mock.scans == 1);
			assert(n71_pcie_assign_resources(&state) == -ENODEV);
			mock.resource_fault = RESOURCE_OK; host->windows[1].child = NULL;
			assert(n71_pcie_scan_cleanup(&state) == 0);
		} else assert(cleanup == expected[fault]);
		assert(!state.scan_bridge && !iomem_resource.child && !mock.allocations && !mock.references);
		assert(mock.ecam[0x8020 / 4] == 0x12301230 && mock.ecam[0x802c / 4] == 0x55667788);
		assert(mock.ecam[0x8030 / 4] == (fault == READBACK_DROP ? 0U : 0xaabbccddU) && mock.ecam[0x100010 / 4] == 4);
		assert(mock.ecam[0x100018 / 4] == 4 && mock.scans == 1 && mock.removes == 1);
		assert(n71_pcie_scan_cleanup(&state) == 0);
		free(mock.ecam);
	}
	assert(n71_pcie_assign_resources(NULL) == -ENODEV);
	return fault;
}

int main(void)
{
	const int expected[] = {0, -EPERM, -EPERM, -ENOMEM, -ENODEV, -EACCES,
		-ENOMEM, -ENOLINK, -EIO, -E2BIG, -ENODEV,
		-EIO, -EIO, -ENODEV, -EACCES, -EACCES, -ENOMEM, -EACCES,
		-EPERM, -ENOMEM, -ENODEV,
		0, -EAGAIN, -EIO, -EPERM, -EAGAIN, -EPERM, -EPERM, -ENOLINK};
	unsigned int index;
	for (index = 0; index < sizeof(expected) / sizeof(*expected); index++) {
		struct n71_diagnostic state;
		struct device device = {0};
		initialize_case(index, index >= PME_NONE);
		state = (struct n71_diagnostic){.ecam = mock.ecam, .port = mock.port};
		{
			int result = mock.pme ? n71_pcie_scan_with_pme(&device, &state, true) : n71_pcie_scan(&device, &state);
			if (result != expected[index])
				fprintf(stderr, "case=%u actual=%d expected=%d\n%s", index, result, expected[index], mock.log);
			assert(result == expected[index]);
		}
		if (index == RESTORE_DROP || index == TARGET_RESTORE_DROP ||
		    index == TARGET_OWNER_CHANGED || index == TARGET_LINK_CHANGED ||
		    index == TARGET_VERIFY_CHANGED || index == REFUSAL_AND_RESTORE_DROP ||
		    index == PME_RESTORE_DROP || index == PME_LINK_LOST) {
			unsigned int prepares = mock.target_prepares, restores = mock.target_restores;
			unsigned int pme_prepares = mock.pme_prepares;
			assert(state.scan_bridge && mock.allocations == 1 && !mock.locked);
			assert(n71_pcie_scan(&device, &state) == -EBUSY && mock.allocations == 1);
			assert(n71_pcie_scan_cleanup(&state) < 0 && state.scan_bridge);
			if (mock.pme) {
				struct n71_scan_host *host = pci_host_bridge_priv(state.scan_bridge);
				assert(host->pme.pending && host->target.pending);
				assert((mock.ecam[0x80a0 / 4] & 0xffff) == 2);
			}
			mock.fault = NONE;
			mock.ecam[0x8008 / 4] = 0x06040001;
			mock.ecam[0x8080 / 4] = 0x20010000;
			mock.port[0x88 / 4] = 5;
			assert(n71_pcie_scan_cleanup(&state) == 0 && !state.scan_bridge);
			assert(mock.target_prepares == prepares);
			assert(mock.pme_prepares == pme_prepares);
			if (index == TARGET_VERIFY_CHANGED)
				assert(mock.target_restores == restores);
		}
		assert(!mock.allocations && !mock.locked && !state.scan_bridge);
		assert(n71_pcie_scan_cleanup(&state) == 0);
		if (mock.scans)
			assert(mock.stops == 1 && mock.removes == 1);
		assert(mock.ecam[0x100010 / 4] == 0xc0000004);
		assert((mock.ecam[0x8004 / 4] & 0xffff0000) == 0xa9100000);
		assert((mock.ecam[0x100004 / 4] & 0xffff0000) ==
		       (mock.pme ? 0xa9100000U : 0xa9000000U));
		assert(mock.ecam[0x80a0 / 4] == 0x5a5a0001);
		assert(mock.ecam[0x8080 / 4] == 0x20010000);
		if (mock.pme) {
			bool event = index == PME_CORE_EVENT || index == PME_DISABLE_EVENT;
			assert(mock.ecam[0x10004c / 4] == (event ? 0xabc0c108U : 0xabc04108U));
			if (index != PME_CAP_BAD)
				assert(mock.pme_prepares == 1);
		}
		if (index != BRIDGE_ALLOC_FAIL)
			assert(strstr(mock.log, "N71_PCIE_SCAN_RESULT error="));
		if (!index) {
			assert(strstr(mock.log, "N71_PCIE_SCAN_BUS_REMOVED bus-null=1"));
			assert(strstr(mock.log, "N71_PCIE_SCAN_CONFIG_RESTORED error=0"));
			assert(strstr(mock.log, "index=0 start=00000007c0000000 end=00000007c0003fff"));
		}
		free(mock.ecam);
	}
	puts("N71_PCIE_SCAN_HOST_OK cases=29");
	assert(exercise_held_bus() == 16);
	puts("N71_PCIE_HELD_BUS_OK cases=16");
	assert(exercise_resource_assignment() == 20);
	puts("N71_PCIE_RESOURCE_ASSIGN_OK cases=20; PCI allocator synthetic");
	return 0;
}
