/* SPDX-License-Identifier: GPL-2.0-only */
/* Execute the real observer with bounded OF, driver-lock and syscon contracts. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define __init
#define __exit
#define module_param(...)
#define MODULE_PARM_DESC(...)
#define module_init(...)
#define module_exit(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define IORESOURCE_MEM 0x200U
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))

struct device_node { int index, refs; const char *full_name; };
struct property { int unused; };
struct device_driver { const char *name; };
struct device { struct device_node *of_node; struct device_driver *driver; int refs, locked; };
struct platform_device { struct device dev; };
struct resource { u64 start, end; unsigned int flags; };
struct of_phandle_args { struct device_node *np; int args_count; u32 args[8]; };
struct regmap { int unused; };
enum { PMGR = 3, OTHER, NODE_COUNT };
enum fault_id {
	NONE, NODE_MISSING, NODE_UNAVAILABLE, COMPAT_WRONG, FALLBACK_WRONG,
	REG_WIDTH, REG_READ_ERROR, REG_OFFSET, REG_SIZE, LABEL_ERROR, LABEL_WRONG,
	PARENT_WRONG, CHAIN_COUNT, CHAIN_PARSE_ERROR, CHAIN_ARGS, CHAIN_WRONG,
	CHAIN_LOOKUP_MISSING, ROOT_HAS_CHAIN, DEVICE_MISSING, DEVICE_NODE,
	DRIVER_MISSING, DRIVER_WRONG, MAP_ERROR, MAP_NULL, MAP_WIDTH, MAP_STRIDE,
	ROOT_CLOCKS, ROOT_RESETS, RESOURCE_ERROR, RESOURCE_BASE, RESOURCE_SIZE,
	RESOURCE_TYPE, FAULT_COUNT
};
static enum fault_id fault;
static int fault_index, board_bad;
static struct device_node nodes[NODE_COUNT];
static struct device_driver drivers[3];
static struct platform_device devices[3];
static struct property property;
static struct regmap map;
static unsigned int reads, read_error, map_calls, samples[3][2];
static char output[2048];
static size_t output_size;
static const u32 offsets[] = {0x801a0, 0x80158, 0x80150};
static const char *const labels[] = {"i2c1", "sio_p", "sio_busif"};
static const char *const paths[] = {
	"/soc/power-management@20e000000/power-controller@801a0",
	"/soc/power-management@20e000000/power-controller@80158",
	"/soc/power-management@20e000000/power-controller@80150",
	"/soc/power-management@20e000000",
};

static bool is_fault(const struct device_node *node, enum fault_id id)
{
	return fault == id && node->index == fault_index;
}
static struct device_node *get_node(int index)
{
	nodes[index].refs++;
	return &nodes[index];
}
static void of_node_put(struct device_node *node)
{
	if (node) { assert(node->refs > 0); node->refs--; }
}
static struct device_node *of_find_node_by_path(const char *path)
{
	unsigned int index;
	for (index = 0; index < 4; index++) if (!strcmp(path, paths[index])) {
		if (is_fault(&nodes[index], NODE_MISSING) ||
		    (fault == CHAIN_LOOKUP_MISSING && (int)index == fault_index + 1)) return NULL;
		return get_node((int)index);
	}
	assert(!"Unexpected OF path");
	return NULL;
}
static bool of_machine_is_compatible(const char *value)
{
	assert(!strcmp(value, "apple,n71")); return !board_bad;
}
static bool of_device_is_available(const struct device_node *node)
{
	return !is_fault(node, NODE_UNAVAILABLE);
}
static bool of_device_is_compatible(const struct device_node *node, const char *value)
{
	const char *first = node->index == PMGR ? "apple,s8000-pmgr" : "apple,s8000-pmgr-pwrstate";
	const char *fallback = node->index == PMGR ? "syscon" : "apple,pmgr-pwrstate";
	if (!strcmp(first, value)) return !is_fault(node, COMPAT_WRONG);
	assert(!strcmp(fallback, value)); return !is_fault(node, FALLBACK_WRONG);
}
static struct device_node *of_get_parent(struct device_node *node)
{
	assert(node->index < 3); return get_node(is_fault(node, PARENT_WRONG) ? OTHER : PMGR);
}
static struct property *of_find_property(const struct device_node *node, const char *name, int *size)
{
	assert(size == NULL);
	if (node->index == PMGR) {
		if (!strcmp(name, "clocks")) return fault == ROOT_CLOCKS ? &property : NULL;
		assert(!strcmp(name, "resets")); return fault == ROOT_RESETS ? &property : NULL;
	}
	assert(node->index == 2 && !strcmp(name, "power-domains"));
	return fault == ROOT_HAS_CHAIN ? &property : NULL;
}
static int of_property_count_u32_elems(const struct device_node *node, const char *name)
{
	assert(node->index < 3 && !strcmp(name, "reg"));
	return is_fault(node, REG_WIDTH) ? 1 : 2;
}
static int of_property_read_u32_array(const struct device_node *node, const char *name, u32 *values, unsigned int count)
{
	assert(node->index < 3 && !strcmp(name, "reg") && count == 2);
	if (is_fault(node, REG_READ_ERROR)) return -EIO;
	values[0] = offsets[node->index] + (is_fault(node, REG_OFFSET) ? 4 : 0);
	values[1] = is_fault(node, REG_SIZE) ? 8 : 4;
	return 0;
}
static int of_property_read_string(const struct device_node *node, const char *name, const char **value)
{
	assert(node->index < 3 && !strcmp(name, "label"));
	if (is_fault(node, LABEL_ERROR)) return -EIO;
	*value = is_fault(node, LABEL_WRONG) ? "other" : labels[node->index];
	return 0;
}
static int of_count_phandle_with_args(const struct device_node *node, const char *name, const char *cells)
{
	assert(node->index < 2 && !strcmp(name, "power-domains") && !strcmp(cells, "#power-domain-cells"));
	return is_fault(node, CHAIN_COUNT) ? 2 : 1;
}
static int of_parse_phandle_with_args(const struct device_node *node, const char *name, const char *cells,
				     int index, struct of_phandle_args *args)
{
	assert(node->index < 2 && index == 0 && !strcmp(name, "power-domains") && !strcmp(cells, "#power-domain-cells"));
	if (is_fault(node, CHAIN_PARSE_ERROR)) return -EIO;
	args->np = get_node(is_fault(node, CHAIN_WRONG) ? OTHER : node->index + 1);
	args->args_count = is_fault(node, CHAIN_ARGS) ? 1 : 0;
	return 0;
}
static int of_address_to_resource(struct device_node *node, int index, struct resource *resource)
{
	assert(node->index == PMGR && index == 0);
	if (fault == RESOURCE_ERROR) return -EIO;
	resource->start = 0x20e000000ULL + (fault == RESOURCE_BASE ? 4 : 0);
	resource->end = resource->start + (fault == RESOURCE_SIZE ? 0x100000 : 0x8c000) - 1;
	resource->flags = fault == RESOURCE_TYPE ? 0x100 : IORESOURCE_MEM;
	return 0;
}
static u64 resource_size(const struct resource *r) { return r->end - r->start + 1; }
static unsigned int resource_type(const struct resource *r) { return r->flags; }
static struct platform_device *of_find_device_by_node(struct device_node *node)
{
	assert(node->index < 3);
	if (is_fault(node, DEVICE_MISSING)) return NULL;
	devices[node->index].dev.refs++;
	return &devices[node->index];
}
static void put_device(struct device *dev) { assert(dev->refs > 0 && !dev->locked); dev->refs--; }
static void device_lock(struct device *dev) { assert(!dev->locked); dev->locked = 1; }
static void device_unlock(struct device *dev) { assert(dev->locked); dev->locked = 0; }
static struct regmap *syscon_node_to_regmap(struct device_node *node)
{
	unsigned int index;
	int locked = 0;
	assert(node == &nodes[PMGR]);
	assert(fault != ROOT_CLOCKS && fault != ROOT_RESETS);
	for (index = 0; index < 3; index++) if (devices[index].dev.locked) {
		struct device *dev = &devices[index].dev;
		assert(dev->refs == 1 && dev->of_node == &nodes[index]);
		assert(dev->driver && !strcmp(dev->driver->name, "apple-pmgr-pwrstate"));
		locked++;
	}
	assert(locked >= 1 && locked <= 3);
	map_calls++;
	if (fault == MAP_ERROR && (int)map_calls == fault_index + 1) return (void *)(intptr_t)-EIO;
	if (fault == MAP_NULL && (int)map_calls == fault_index + 1) return NULL;
	return &map;
}
static unsigned int regmap_get_val_bytes(struct regmap *value)
{
	assert(value == &map); return fault == MAP_WIDTH && (int)map_calls == fault_index + 1 ? 8 : 4;
}
static unsigned int regmap_get_reg_stride(struct regmap *value)
{
	assert(value == &map); return fault == MAP_STRIDE && (int)map_calls == fault_index + 1 ? 8 : 4;
}
static int regmap_read_bypassed(struct regmap *value, unsigned int offset, unsigned int *word)
{
	unsigned int index = reads / 2, sample = reads % 2;
	assert(value == &map && index < 3 && offset == offsets[index]);
	assert(devices[index].dev.locked && devices[index].dev.refs == 1);
	reads++;
	if (read_error == reads) return -EIO;
	*word = samples[index][sample];
	return 0;
}
static void info(const char *format, ...)
{
	va_list arguments;
	int size;
	va_start(arguments, format);
	size = vsnprintf(output + output_size, sizeof(output) - output_size, format, arguments);
	va_end(arguments);
	assert(size >= 0 && (size_t)size < sizeof(output) - output_size);
	output_size += (size_t)size;
}
#define pr_info(...) info(__VA_ARGS__)
#include "n71-pmgr-power-observe.c"

static void reset(enum fault_id failure, int index)
{
	unsigned int n;
	fault = failure; fault_index = index; board_bad = 0;
	reads = read_error = map_calls = 0; output_size = 0; output[0] = 0;
	memset(nodes, 0, sizeof(nodes)); memset(devices, 0, sizeof(devices));
	for (n = 0; n < NODE_COUNT; n++) { nodes[n].index = (int)n; nodes[n].full_name = "unit-name"; }
	for (n = 0; n < 3; n++) {
		drivers[n].name = failure == DRIVER_WRONG && (int)n == index ? "other" : "apple-pmgr-pwrstate";
		devices[n].dev.of_node = failure == DEVICE_NODE && (int)n == index ? &nodes[OTHER] : &nodes[n];
		devices[n].dev.driver = failure == DRIVER_MISSING && (int)n == index ? NULL : &drivers[n];
		samples[n][0] = samples[n][1] = 0x100000ffU + n;
	}
	run = true;
}
static void balanced(void)
{
	unsigned int n;
	for (n = 0; n < NODE_COUNT; n++) assert(nodes[n].refs == 0);
	for (n = 0; n < 3; n++) assert(devices[n].dev.refs == 0 && !devices[n].dev.locked);
}
static void failed(void)
{
	assert(n71_pmgr_power_observe_init() < 0);
	assert(output_size == 0); balanced();
}

static unsigned int access_cases(void)
{
	struct n71_pmgr_reference reference;
	struct n71_pmgr_access access = {0};
	unsigned int count = 0, words[2] = {0xdeadbeef, 0xdeadbeef};

	reset(NONE, 0);
	reference = (struct n71_pmgr_reference) {
		.index = 0, .node = get_node(0), .pmgr = get_node(PMGR),
	};
	assert(n71_pmgr_access_lock(&reference, &access) == 0);
	assert(access.provider == &devices[0] && access.map == &map);
	assert(n71_pmgr_access_lock(&reference, &access) == -EBUSY);
	assert(map_calls == 1 && devices[0].dev.refs == 1 && devices[0].dev.locked);
	n71_pmgr_access_unlock(&access);
	assert(!access.provider && !access.map);
	n71_pmgr_access_unlock(&access);
	n71_pmgr_access_unlock(NULL);
	of_node_put(reference.node); of_node_put(reference.pmgr); balanced(); count++;

	reset(NONE, 0);
	reference = (struct n71_pmgr_reference) {
		.index = 0, .node = &nodes[0], .pmgr = &nodes[PMGR],
	};
	assert(n71_pmgr_access_lock(NULL, &access) == -EINVAL);
	assert(n71_pmgr_access_lock(&reference, NULL) == -EINVAL);
	assert(!access.provider && !access.map && !map_calls);
	balanced(); count++;

	reference.index = 3;
	assert(n71_pmgr_access_lock(&reference, &access) == -EINVAL);
	assert(!map_calls); balanced(); count++;
	reference.index = 0; reference.node = NULL;
	assert(n71_pmgr_access_lock(&reference, &access) == -EINVAL);
	assert(!map_calls); balanced(); count++;
	reference.node = &nodes[0]; reference.pmgr = NULL;
	assert(n71_pmgr_access_lock(&reference, &access) == -EINVAL);
	assert(!map_calls); balanced(); count++;
	reference.pmgr = &nodes[PMGR]; reference.node = &nodes[OTHER];
	assert(n71_pmgr_access_lock(&reference, &access) == -ENODEV);
	assert(!map_calls); balanced(); count++;
	reference.node = &nodes[0]; reference.pmgr = &nodes[OTHER];
	assert(n71_pmgr_access_lock(&reference, &access) == -ENODEV);
	assert(!map_calls); balanced(); count++;
	reference.pmgr = &nodes[PMGR];
	assert(n71_pmgr_sample(&reference, NULL) == -EINVAL);
	assert(n71_pmgr_sample(NULL, words) == -EINVAL);
	assert(words[0] == 0xdeadbeef && words[1] == 0xdeadbeef && !map_calls);
	balanced(); count++;

	{
		struct n71_pmgr_reference references[3];
		struct n71_pmgr_access held[3] = {0};
		struct device_node *pmgr = get_node(PMGR);
		unsigned int index;

		for (index = 0; index < 3; index++) {
			references[index] = (struct n71_pmgr_reference) {
				.index = index, .node = get_node((int)index), .pmgr = pmgr,
			};
			assert(n71_pmgr_access_lock(&references[index], &held[index]) == 0);
			assert(held[index].map == &map && devices[index].dev.locked);
		}
		assert(map_calls == 3 && !reads && !output_size);
		for (index = 3; index > 0; index--) {
			n71_pmgr_access_unlock(&held[index - 1]);
			assert(!held[index - 1].provider && !held[index - 1].map);
			of_node_put(references[index - 1].node);
		}
		of_node_put(pmgr); balanced(); count++;
	}
	return count;
}
int main(void)
{
	unsigned int cases = 0, n, id;
	const enum fault_id common[] = {NODE_MISSING, NODE_UNAVAILABLE, COMPAT_WRONG, FALLBACK_WRONG,
		REG_WIDTH, REG_READ_ERROR, REG_OFFSET, REG_SIZE, LABEL_ERROR, LABEL_WRONG, PARENT_WRONG,
		DEVICE_MISSING, DEVICE_NODE, DRIVER_MISSING, DRIVER_WRONG, MAP_ERROR, MAP_NULL, MAP_WIDTH, MAP_STRIDE};
	const enum fault_id chain[] = {CHAIN_COUNT, CHAIN_PARSE_ERROR, CHAIN_ARGS, CHAIN_WRONG, CHAIN_LOOKUP_MISSING};
	const enum fault_id parent[] = {NODE_MISSING, NODE_UNAVAILABLE, COMPAT_WRONG, FALLBACK_WRONG,
		ROOT_CLOCKS, ROOT_RESETS, RESOURCE_ERROR, RESOURCE_BASE, RESOURCE_SIZE, RESOURCE_TYPE};
	/* Kills metadata, existing-provider, reference and locking boundary mutations. */
	for (n = 0; n < 3; n++) for (id = 0; id < sizeof(common) / sizeof(common[0]); id++) {
		reset(common[id], (int)n); failed(); cases++;
	}
	for (n = 0; n < 2; n++) for (id = 0; id < sizeof(chain) / sizeof(chain[0]); id++) {
		reset(chain[id], (int)n); failed(); cases++;
	}
	for (id = 0; id < sizeof(parent) / sizeof(parent[0]); id++) {
		reset(parent[id], PMGR); failed(); assert(map_calls == 0 && reads == 0); cases++;
	}
	reset(ROOT_HAS_CHAIN, 2); failed(); cases++;
	reset(NONE, 0); run = false; failed(); cases++;
	reset(NONE, 0); board_bad = 1; failed(); cases++;
	/* Kills swallowed read errors and partial success output. */
	for (n = 1; n <= 6; n++) {
		reset(NONE, 0); read_error = n; failed(); assert(reads == n); cases++;
	}
	reset(NONE, 0);
	assert(n71_pmgr_power_observe_init() == 0 && reads == 6 && map_calls == 3);
	assert(strstr(output, "domain=i2c1 offset=801a0 sample0=100000ff sample1=100000ff stable=1"));
	assert(strstr(output, "domain=sio_p offset=80158 sample0=10000100 sample1=10000100 stable=1"));
	assert(strstr(output, "domain=sio_busif offset=80150 sample0=10000101 sample1=10000101 stable=1"));
	assert(strstr(output, "N71_PMGR_OBSERVED writes=0 reads=6 atomic-chain=0 ownership=0"));
	balanced(); cases++;
	n71_pmgr_power_observe_exit(); assert(strstr(output, "N71_PMGR_UNLOADED hardware-changes=0"));
	reset(NONE, 0); samples[1][1] ^= 0x10;
	assert(n71_pmgr_power_observe_init() == 0);
	assert(strstr(output, "domain=sio_p offset=80158 sample0=10000100 sample1=10000110 stable=0"));
	balanced(); cases++;
	cases += access_cases();
	printf("N71_PMGR_POWER_OBSERVE_OK cases=%u\n", cases);
	return 0;
}
