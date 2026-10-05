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
	mock.endpoint_bus = (struct pci_bus){bridge->sysdata, 1};
	mock.root = (struct pci_dev){.bus = bridge->bus, .devfn = 8, .vendor = 0x106b,
		.device = 0x1004, .class = 0x060400};
	mock.endpoint = (struct pci_dev){.bus = &mock.endpoint_bus, .vendor = 0x14e4,
		.device = 0x43a3, .class = 0x028000};
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
		assert(bridge->ops->write(bus, devfn, 4, 2, function ? 0x103 : 0) == 0);
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
	free(bus); mock.bridge->bus = NULL;
	if (mock.fault == PME_LINK_LOST)
		mock.port[0x88 / 4] = 0;
}
#include "n71-pcie-scan.h"

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
	return 0;
}
