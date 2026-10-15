/* SPDX-License-Identifier: GPL-2.0-only */
/* Execute the production provider callbacks with ownership-aware kernel fixtures. */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "n71-dart-observe.h"

#define N71_DART_CPU 0x602008000ULL
#define N71_DART_BYTES 0x4000U
#define PLATFORM_DEVID_AUTO -1
#define IORESOURCE_MEM 1
#define IORESOURCE_IRQ 2
#define IORESOURCE_IRQ_HIGHLEVEL 4
#define GFP_KERNEL 0
#include "n71_dart_irq_fixture.h"
struct device_driver { const char *name; };
struct device { struct device_node *of_node; struct device *parent; struct device_driver *driver; };
struct platform_device { struct device dev; bool added; };
struct resource { unsigned long long start, end; unsigned int flags; };
struct n71_dart_provider;
struct n71_diagnostic { unsigned int powered, attached; struct n71_dart_provider *dart; int primary_error; };
struct n71_dart_mmio { struct n71_diagnostic *state; void *regs; unsigned int reads, guards; };

struct fixture {
	u32 regs[N71_DART_BYTES / 4], original[16];
	char result[512], release[128];
	struct device_node dart, aic;
	struct platform_device other;
	unsigned int heap, mappings, devices, claims, writes;
	unsigned int fail_stage;
	bool mmio_claimed, provider_claimed, fail_claim, other_owner, fail_quiet, lingering_irq;
};
static struct fixture fixture;
static struct device_driver dart_driver = {"apple-dart"};
static struct resource claimed;
static unsigned int cases;

static int of_irq_parse_one(struct device_node *node, int index, struct of_phandle_args *args)
{
	assert(node == &fixture.dart && index == 0);
	*args = (struct of_phandle_args){of_node_get(&fixture.aic), 3, {0, 248, 4, 0}};
	return 0;
}
static struct device_node *of_irq_find_parent(struct device_node *node)
{
	assert(node == &fixture.aic);
	return of_node_get(node);
}
static void *kzalloc(size_t bytes, int flags)
{
	assert(flags == GFP_KERNEL);
	if (fixture.fail_stage == 1) return NULL;
	fixture.heap++;
	return calloc(1, bytes);
}
static void kfree(void *pointer) { assert(fixture.heap); fixture.heap--; free(pointer); }
static struct device_node *of_find_node_by_path(const char *path)
{
	assert(strcmp(path, "/soc/iommu@602008000") == 0);
	return fixture.fail_stage == 2 ? NULL : of_node_get(&fixture.dart);
}
static struct resource *request_mem_region(unsigned long long base, unsigned int bytes, const char *name)
{
	assert(base == N71_DART_CPU && bytes == N71_DART_BYTES && name);
	if (fixture.fail_claim || fixture.mmio_claimed || fixture.provider_claimed) return NULL;
	fixture.mmio_claimed = true; fixture.claims++;
	return &claimed;
}
static void release_mem_region(unsigned long long base, unsigned int bytes)
{
	assert(base == N71_DART_CPU && bytes == N71_DART_BYTES && fixture.mmio_claimed);
	fixture.mmio_claimed = false;
}
static void *ioremap(unsigned long long base, unsigned int bytes)
{
	assert(base == N71_DART_CPU && bytes == N71_DART_BYTES && fixture.mmio_claimed);
	if (fixture.fail_stage == 3) return NULL;
	fixture.mappings++;
	return fixture.regs;
}
static void iounmap(void *pointer)
{
	assert(pointer == fixture.regs && fixture.mappings == 1 && !fixture.devices && !irq_fixture.descriptors);
	fixture.mappings--;
}
static void writel(u32 value, void *pointer)
{
	u32 *word = pointer;
	assert(word >= fixture.regs + 0x40 / 4 && word < fixture.regs + 0x80 / 4);
	assert(fixture.mmio_claimed && !fixture.provider_claimed && !fixture.devices);
	fixture.writes++; *word = value;
}
static void dev_info(struct device *dev, const char *format, ...)
{
	va_list arguments;
	(void)dev;
	va_start(arguments, format);
	if (strncmp(format, "N71_DART_CYCLE_RESULT", 21) == 0)
		vsnprintf(fixture.result, sizeof(fixture.result), format, arguments);
	if (strncmp(format, "N71_DART_CYCLE_RELEASED", 23) == 0)
		vsnprintf(fixture.release, sizeof(fixture.release), format, arguments);
	va_end(arguments);
}
static struct platform_device *platform_device_alloc(const char *name, int id)
{
	assert(strcmp(name, "n71-dart-cycle") == 0 && id == PLATFORM_DEVID_AUTO);
	if (fixture.fail_stage == 4) return NULL;
	fixture.devices++;
	return calloc(1, sizeof(struct platform_device));
}
static void device_set_node(struct device *dev, struct fwnode_handle *node) { dev->of_node = to_of_node(node); }
static int platform_device_add_resources(struct platform_device *dev, struct resource *resources, int count)
{
	assert(dev && count == 2 && resources[0].start == N71_DART_CPU && resources[1].start == 32);
	return fixture.fail_stage == 5 ? -EIO : 0;
}
static int platform_device_add(struct platform_device *dev)
{
	assert(!fixture.mmio_claimed && !fixture.provider_claimed);
	if (fixture.fail_stage == 6) return -EIO;
	dev->added = true;
	fixture.provider_claimed = true;
	memset(fixture.regs + 0x40 / 4, 0, sizeof(fixture.original));
	assert(irq_fixture.descriptors && irq_fixture.state.type == 4);
	irq_fixture.action = true; irq_fixture.state.started = true; irq_fixture.state.disabled = false;
	irq_fixture.leaf_data.chip->irq_unmask(&irq_fixture.leaf_data);
	if (fixture.fail_stage != 7) {
		dev->dev.driver = &dart_driver;
	} else {
		/* A failed probe releases its devres IRQ before add returns. */
		irq_fixture.action = false; irq_fixture.state.started = false; irq_fixture.state.disabled = true;
		irq_fixture.leaf_data.chip->irq_mask(&irq_fixture.leaf_data);
	}
	return 0;
}
static void platform_device_put(struct platform_device *dev)
{
	assert(dev && !dev->added && fixture.devices);
	of_node_put(dev->dev.of_node); fixture.devices--; free(dev);
}
static void platform_device_unregister(struct platform_device *dev)
{
	assert(dev && dev->added && fixture.provider_claimed);
	irq_fixture.action = false; irq_fixture.state.started = false; irq_fixture.state.disabled = true;
	irq_fixture.leaf_data.chip->irq_mask(&irq_fixture.leaf_data);
	if (fixture.lingering_irq)
		irq_fixture.action = true;
	fixture.provider_claimed = false; dev->added = false;
	platform_device_put(dev);
}
static void device_lock(struct device *dev) { (void)dev; }
static void device_unlock(struct device *dev) { (void)dev; }
static void *platform_get_drvdata(struct platform_device *dev) { return dev->dev.driver ? &fixture : NULL; }
static struct platform_device *of_find_device_by_node(struct device_node *node)
{
	assert(node == &fixture.dart);
	return fixture.other_owner ? &fixture.other : NULL;
}
static void put_device(struct device *dev) { assert(dev == &fixture.other.dev); }
static int n71_dart_validate(struct device *dev) { (void)dev; return 0; }
static int n71_dart_quiet(void *context)
{
	struct n71_dart_mmio *mmio = context;
	if (++mmio->guards > N71_DART_READS + 1 || mmio->state->powered != 4 || !mmio->regs)
		return -EACCES;
	return fixture.fail_quiet ? -ENOLINK : 0;
}
static int n71_dart_read32(void *context, u32 offset, u32 *value)
{
	struct n71_dart_mmio *mmio = context;
	assert(mmio->reads < N71_DART_READS && mmio->guards == mmio->reads + 1);
	assert(offset == n71_dart_offset(mmio->reads % N71_DART_WORDS));
	mmio->reads++; *value = fixture.regs[offset / 4];
	return 0;
}

#include "n71-dart-provider.h"

static void initialize(struct n71_diagnostic *state)
{
	unsigned int index;
	cases++;
	memset(&fixture, 0, sizeof(fixture));
	*state = (struct n71_diagnostic){.powered = 4, .attached = 4};
	irq_fixture_initialize(&fixture.aic);
	fixture.regs[0] = 0xf02; fixture.regs[0x10 / 4] = 0x100;
	for (index = 0; index < 16; index++)
		fixture.regs[0x40 / 4 + index] = fixture.original[index] = 0x80123400 + index;
}
static void released(struct n71_diagnostic *state)
{
	assert(!state->dart && !fixture.heap && !fixture.devices && !fixture.mappings);
	assert(!fixture.mmio_claimed && !fixture.provider_claimed);
	irq_fixture_released(&fixture.aic);
	assert(!fixture.dart.refs && !fixture.aic.refs);
	assert(memcmp(fixture.regs + 0x40 / 4, fixture.original, sizeof(fixture.original)) == 0);
	assert(state->powered == 4 && state->attached == 4);
}

int main(void)
{
	struct n71_diagnostic state;
	struct device dev = {.of_node = &fixture.aic};
	struct n71_dart_provider *owner;
	unsigned int index, before;

	/* Mutations: drop retained owner, unmap on failure, skip unregister or forget bound state. */
	initialize(&state);
	assert(n71_pcie_dart_acquire(&dev, &state) == 0);
	owner = state.dart;
	assert(owner && owner->lease.running && owner->bound && owner->device && !owner->claimed);
	assert(fixture.heap == 1 && fixture.mappings == 1 && fixture.devices == 1 && fixture.dart.refs == 2);
	assert(n71_pcie_dart_acquire(&dev, &state) == -EALREADY && state.dart == owner);
	fixture.fail_claim = true;
	assert(n71_pcie_dart_cleanup(&dev, &state) == -EBUSY);
	assert(state.dart == owner && fixture.heap == 1 && fixture.mappings == 1 && fixture.dart.refs == 1);
	assert(!owner->device && !owner->interrupt.irq && !owner->bound && !owner->lease.stopped);
	assert(!fixture.writes && irq_fixture.irq_frees == 1);
	fixture.fail_claim = false;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
	released(&state);
	before = fixture.writes;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0 && fixture.writes == before);
	assert(n71_pcie_dart_cycle(&dev, &state) == 0);
	released(&state);
	assert(fixture.writes == 32 && irq_fixture.irq_frees == 2);
	assert(strcmp(fixture.result, "N71_DART_CYCLE_RESULT error=0 snapshots=4 reads=152 guards=156 quiet=17 writes=16 attempted=1 stopped=1 restored=1 control-changed=0; no DMA\n") == 0);
	assert(strcmp(fixture.release, "N71_DART_CYCLE_RELEASED device=0 mapping-new=0 claimed=0 mapped=0\n") == 0);

	for (index = 1; index <= 7; index++) {
		initialize(&state); fixture.fail_stage = index;
		assert(n71_pcie_dart_acquire(&dev, &state) < 0);
		assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
		released(&state);
	}
	initialize(&state); irq_fixture.conflict = true;
	assert(n71_pcie_dart_cycle(&dev, &state) == -EBUSY);
	released(&state);
	assert(irq_fixture.irq_frees == 0 && fixture.writes == 16 && irq_fixture.conflict);
	for (index = 1; index <= 11; index++) {
		initialize(&state); irq_fixture.fail_stage = index;
		assert(n71_pcie_dart_acquire(&dev, &state) < 0);
		assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
		released(&state);
	}
	initialize(&state);
	assert(n71_pcie_dart_acquire(&dev, &state) == 0);
	owner = state.dart; fixture.lingering_irq = true;
	assert(n71_pcie_dart_cleanup(&dev, &state) == -EBUSY);
	assert(state.dart == owner && !owner->device && owner->interrupt.irq);
	assert(owner->interrupt.domain && owner->interrupt.fwnode && fixture.mappings == 1 && fixture.heap == 1);
	assert(!fixture.writes && fixture.aic.refs == 1 && !irq_fixture.irq_frees);
	irq_fixture.action = false;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
	released(&state);
	initialize(&state);
	assert(n71_pcie_dart_acquire(&dev, &state) == 0);
	owner = state.dart; fixture.other_owner = true;
	assert(n71_pcie_dart_cleanup(&dev, &state) == -EBUSY && state.dart == owner);
	assert(fixture.mappings == 1 && fixture.heap == 1 && fixture.writes == 0);
	fixture.other_owner = false;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
	released(&state);
	initialize(&state);
	assert(n71_pcie_dart_acquire(&dev, &state) == 0);
	owner = state.dart; fixture.fail_quiet = true;
	assert(n71_pcie_dart_cleanup(&dev, &state) == -ENOLINK && state.dart == owner);
	assert(owner->claimed && owner->lease.stopped && fixture.mappings == 1 && !fixture.writes);
	fixture.fail_quiet = false;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
	released(&state);

	/* Mutations: omit saved-value/index/guard/device/stopped checks or reuse one write grant. */
	initialize(&state);
	assert(n71_pcie_dart_acquire(&dev, &state) == 0);
	owner = state.dart;
	assert(n71_provider_write(owner, 0, fixture.original[0]) == -EACCES);
	assert(n71_provider_stop(owner) == 0);
	assert(n71_provider_write(owner, 0, fixture.original[0]) == -EACCES);
	owner->lease.stopped = true;
	owner->restore_guard = false;
	assert(n71_provider_write(owner, 0, fixture.original[0]) == -EACCES);
	assert(n71_provider_quiet(owner) == 0);
	assert(n71_provider_write(owner, 16, 0) == -EACCES);
	assert(n71_provider_write(owner, 1, fixture.original[1]) == -EACCES);
	assert(n71_provider_write(owner, 0, fixture.original[0] ^ 1) == -EACCES);
	assert(n71_provider_write(owner, 0, fixture.original[0]) == 0);
	assert(n71_provider_write(owner, 0, fixture.original[0]) == -EACCES && fixture.writes == 1);
	owner->lease.restore_index = 1;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0);
	released(&state);
	assert(fixture.writes == 16);
	initialize(&state);
	assert(n71_pcie_dart_acquire(&dev, &state) == 0);
	fixture.regs[0x10 / 4] = 0;
	assert(n71_pcie_dart_cleanup(&dev, &state) == 0 && state.primary_error == -EIO);
	released(&state);
	initialize(&state); state.powered = 3;
	assert(n71_pcie_dart_acquire(&dev, &state) == -EACCES && !state.dart && !fixture.heap);
	initialize(&state); state.attached = 3;
	assert(n71_pcie_dart_acquire(&dev, &state) == -EACCES && !state.dart && !fixture.heap);
	printf("N71_DART_PROVIDER_OK cases=%u\n", cases);
	return 0;
}
