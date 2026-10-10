/* SPDX-License-Identifier: GPL-2.0-only */
/* Execute the real module with synthetic provider lifetime and GPIO contracts. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif

typedef uint32_t u32;
typedef uint64_t u64;
#ifndef EUCLEAN
#define EUCLEAN 117
#endif
#define __init
#define __exit
#define module_param(...)
#define MODULE_PARM_DESC(...)
#define module_init(...)
#define module_exit(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define IORESOURCE_MEM 0x200U
#define GFP_KERNEL 0
#define GPIOD_ASIS 0
#define GPIO_LOOKUP_FLAGS_DEFAULT 0
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define struct_size(p, member, n) (sizeof(*(p)) + (n) * sizeof((p)->member[0]))

struct device_node { int id, refs; };
struct device_driver { const char *name; };
struct device { struct device_node *of_node; struct device_driver *driver; int refs, locked; };
struct platform_device { struct device dev; };
struct i2c_adapter { struct device dev; };
struct resource { u64 start, end; unsigned int flags; };
struct regmap { int unused; };
struct gpio_device { int refs; };
struct gpio_desc { unsigned int pin; bool owned; struct gpio_device *gdev; };
struct gpiod_lookup { const char *key; unsigned int chip_hwnum; const char *con_id; unsigned int idx, flags; };
struct gpiod_lookup_table { const char *dev_id; struct gpiod_lookup table[]; };
#define GPIO_LOOKUP_IDX(k, p, c, i, f) ((struct gpiod_lookup) {k, p, c, i, f})

enum fault_id {
	NONE, RUN_OFF, WRONG_BOARD, MISSING_I2C, ENABLED_I2C, HAS_CHILD,
	MISSING_STATUS, WRONG_STATUS, WRONG_I2C_COMPAT, WRONG_I2C_FALLBACK,
	HAS_CONTROLLER, HAS_ADAPTER, I2C_RESOURCE_FAIL, I2C_BASE, I2C_SIZE, I2C_TYPE,
	MISSING_GPIO, GPIO_DISABLED, GPIO_COMPAT, NPINS_FAIL, NPINS_WRONG,
	GPIO_RESOURCE_FAIL, GPIO_BASE, GPIO_SIZE, GPIO_TYPE, MISSING_PROVIDER,
	PROVIDER_NODE, MISSING_DRIVER, DRIVER_NAME, MISSING_MAP, MAP_WIDTH, MAP_STRIDE,
	MISSING_GDEV, MISSING_LABEL, WRONG_LABEL, MISSING_LABEL_DEVICE, WRONG_LABEL_DEVICE,
	ROOT_FAIL, ALLOC_FAIL, EXPECTED_DESC_FAIL, WRONG_DESCRIPTOR, WRONG_HWGPIO,
	FAULT_COUNT
};
static enum fault_id fault;
static struct device_node nodes[3];
static struct device_driver driver;
static struct platform_device provider, controller;
static struct i2c_adapter adapter;
static struct device consumer;
static struct regmap map;
static struct gpio_device gdev, other_gdev;
static struct gpio_desc descriptors[3];
static struct gpiod_lookup_table *active_lookup;
static unsigned int reads, read_failure, requests, request_failure, drift_at;
static unsigned int releases[4], release_count, bypass_reads;
static unsigned int word, changed_word, corrupt_at, corrupt_pattern;
static bool allocated, registered;
static char output[4096];
static size_t output_size;

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

static bool of_machine_is_compatible(const char *name)
{
	assert(!strcmp(name, "apple,n71"));
	return fault != WRONG_BOARD;
}
static struct device_node *of_find_node_by_path(const char *path)
{
	int id;
	if (!strcmp(path, "/soc/i2c@20a111000")) {
		if (fault == MISSING_I2C) return NULL;
		id = 0;
	} else {
		assert(!strcmp(path, "/soc/pinctrl@20f100000"));
		if (fault == MISSING_GPIO) return NULL;
		id = 1;
	}
	nodes[id].refs++;
	return &nodes[id];
}
static void of_node_put(struct device_node *node)
{
	assert(node && node->refs > 0);
	node->refs--;
}
static bool of_device_is_available(struct device_node *node)
{
	return node == &nodes[0] ? fault == ENABLED_I2C : fault != GPIO_DISABLED;
}
static unsigned int of_get_child_count(struct device_node *node)
{
	assert(node == &nodes[0]);
	return fault == HAS_CHILD;
}
static int of_property_read_string(struct device_node *node, const char *name, const char **value)
{
	assert(node == &nodes[0] && !strcmp(name, "status"));
	if (fault == MISSING_STATUS) return -EINVAL;
	*value = fault == WRONG_STATUS ? "reserved" : "disabled";
	return 0;
}
static bool of_device_is_compatible(struct device_node *node, const char *name)
{
	if (node == &nodes[0]) {
		if (!strcmp(name, "apple,s8000-i2c")) return fault != WRONG_I2C_COMPAT;
		assert(!strcmp(name, "apple,i2c"));
		return fault != WRONG_I2C_FALLBACK;
	}
	assert(node == &nodes[1] && !strcmp(name, "apple,pinctrl"));
	return fault != GPIO_COMPAT;
}
static struct platform_device *of_find_device_by_node(struct device_node *node)
{
	struct platform_device *result;
	if (node == &nodes[0]) {
		if (fault != HAS_CONTROLLER) return NULL;
		result = &controller;
	} else {
		assert(node == &nodes[1]);
		if (fault == MISSING_PROVIDER) return NULL;
		result = &provider;
	}
	result->dev.refs++;
	return result;
}
static struct i2c_adapter *of_find_i2c_adapter_by_node(struct device_node *node)
{
	assert(node == &nodes[0]);
	if (fault != HAS_ADAPTER) return NULL;
	adapter.dev.refs++;
	return &adapter;
}
static void put_device(struct device *dev)
{
	assert(dev->refs > 0 && !dev->locked);
	dev->refs--;
}
static int of_address_to_resource(struct device_node *node, int index, struct resource *resource)
{
	bool i2c = node == &nodes[0];
	u64 base = i2c ? 0x20a111000ULL : 0x20f100000ULL;
	u64 size = i2c ? 0x1000 : 0x100000;
	assert((i2c || node == &nodes[1]) && index == 0);
	if (fault == (i2c ? I2C_RESOURCE_FAIL : GPIO_RESOURCE_FAIL)) return -EIO;
	resource->start = base + (fault == (i2c ? I2C_BASE : GPIO_BASE) ? 4 : 0);
	resource->end = resource->start + size - 1 + (fault == (i2c ? I2C_SIZE : GPIO_SIZE) ? 4 : 0);
	resource->flags = fault == (i2c ? I2C_TYPE : GPIO_TYPE) ? 0 : IORESOURCE_MEM;
	return 0;
}
static u64 resource_size(struct resource *resource) { return resource->end - resource->start + 1; }
static unsigned int resource_type(struct resource *resource) { return resource->flags; }
static int of_property_read_u32(struct device_node *node, const char *name, u32 *value)
{
	assert(node == &nodes[1] && !strcmp(name, "apple,npins"));
	if (fault == NPINS_FAIL) return -EIO;
	*value = fault == NPINS_WRONG ? 209 : 208;
	return 0;
}
static void device_lock(struct device *dev)
{
	assert(dev == &provider.dev && dev->refs == 1 && !dev->locked);
	dev->locked = 1;
}
static void device_unlock(struct device *dev)
{
	assert(dev == &provider.dev && dev->locked && !active_lookup && !registered);
	assert(!gdev.refs && !other_gdev.refs);
	dev->locked = 0;
}
static struct regmap *dev_get_regmap(struct device *dev, const char *name)
{
	assert(dev == &provider.dev && dev->locked && !name);
	return fault == MISSING_MAP ? NULL : &map;
}
static int regmap_get_val_bytes(struct regmap *value)
{
	assert(value == &map && provider.dev.locked);
	return fault == MAP_WIDTH ? 2 : 4;
}
static int regmap_get_reg_stride(struct regmap *value)
{
	assert(value == &map && provider.dev.locked);
	return fault == MAP_STRIDE ? 8 : 4;
}
static int read_word(struct regmap *value, unsigned int offset, unsigned int *result, bool bypass)
{
	assert(value == &map && provider.dev.locked && (offset == 115 * 4 || offset == 114 * 4));
	if (!read_failure && !corrupt_at && !corrupt_pattern) {
		assert(offset == (reads % 8 < 4 ? 115U : 114U) * 4);
		assert(bypass == (reads % 4 == 1 || reads % 4 == 2));
	}
	reads++;
	bypass_reads += bypass;
	if (reads == read_failure) return -EIO;
	*result = drift_at && reads >= drift_at ? changed_word : word;
	if (reads == corrupt_at) *result ^= 1;
	if (reads <= 8 && (corrupt_pattern & (1U << (reads - 1)))) *result ^= 1;
	return 0;
}
static int regmap_read(struct regmap *map_value, unsigned int offset, unsigned int *value)
{
	return read_word(map_value, offset, value, false);
}
static int regmap_read_bypassed(struct regmap *map_value, unsigned int offset, unsigned int *value)
{
	return read_word(map_value, offset, value, true);
}
static struct device_node *of_fwnode_handle(struct device_node *node) { return node; }
static struct gpio_device *gpio_device_find_by_fwnode(struct device_node *node)
{
	assert(node == &nodes[1] && provider.dev.locked);
	if (fault == MISSING_GDEV) return NULL;
	gdev.refs++;
	return &gdev;
}
static const char *gpio_device_get_label(struct gpio_device *dev)
{
	assert(dev == &gdev && dev->refs > 0 && provider.dev.locked);
	if (fault == MISSING_LABEL) return NULL;
	return fault == WRONG_LABEL ? "other" : "20f100000.pinctrl";
}
static const char *dev_name(struct device *dev)
{
	assert(dev == &provider.dev || (dev == &consumer && registered));
	return dev == &provider.dev ? "20f100000.pinctrl" : "n71-i2c1-pin-cycle";
}
static struct gpio_device *gpio_device_find_by_label(const char *label)
{
	struct gpio_device *result;
	assert(!strcmp(label, "20f100000.pinctrl") && provider.dev.locked);
	if (fault == MISSING_LABEL_DEVICE) return NULL;
	result = fault == WRONG_LABEL_DEVICE ? &other_gdev : &gdev;
	result->refs++;
	return result;
}
static void gpio_device_put(struct gpio_device *dev)
{
	assert(dev && dev->refs > 0 && provider.dev.locked);
	dev->refs--;
}
static struct device *root_device_register(const char *name)
{
	assert(!strcmp(name, "n71-i2c1-pin-cycle") && !registered && provider.dev.locked);
	if (fault == ROOT_FAIL) return ERR_PTR(-EEXIST);
	registered = true;
	return &consumer;
}
static void root_device_unregister(struct device *dev)
{
	assert(dev == &consumer && registered && !active_lookup && !allocated);
	registered = false;
}
static void *kzalloc(size_t size, int flags)
{
	assert(size == sizeof(struct gpiod_lookup_table) + 3 * sizeof(struct gpiod_lookup));
	assert(flags == GFP_KERNEL && !allocated && registered);
	if (fault == ALLOC_FAIL) return NULL;
	allocated = true;
	return calloc(1, size);
}
static void kfree(void *value)
{
	assert(allocated && !active_lookup);
	allocated = false;
	free(value);
}
static void gpiod_add_lookup_table(struct gpiod_lookup_table *table)
{
	assert(!active_lookup && allocated && registered && provider.dev.locked);
	assert(!strcmp(table->dev_id, "n71-i2c1-pin-cycle") && !table->table[2].key);
	for (unsigned int i = 0; i < 2; i++) {
		assert(!strcmp(table->table[i].key, "20f100000.pinctrl"));
		assert(table->table[i].chip_hwnum == (i ? 114U : 115U));
		assert(!strcmp(table->table[i].con_id, "pins") && table->table[i].idx == i);
		assert(table->table[i].flags == GPIO_LOOKUP_FLAGS_DEFAULT);
	}
	active_lookup = table;
}
static void gpiod_remove_lookup_table(struct gpiod_lookup_table *table)
{
	assert(table == active_lookup && !descriptors[0].owned && !descriptors[1].owned && !descriptors[2].owned);
	active_lookup = NULL;
}
static struct gpio_desc *gpio_device_get_desc(struct gpio_device *dev, unsigned int pin)
{
	assert(dev == &gdev && dev->refs > 0 && provider.dev.locked);
	assert(pin == 115 || pin == 114);
	if (fault == EXPECTED_DESC_FAIL) return ERR_PTR(-EINVAL);
	return &descriptors[pin == 114];
}
static struct gpio_desc *gpiod_get_index(struct device *dev, const char *name, unsigned int index, int flags)
{
	struct gpio_desc *result;
	assert(dev == &consumer && registered && active_lookup && provider.dev.locked);
	assert(!dev->of_node && !dev->driver && !strcmp(name, "pins") && index < 2 && flags == GPIOD_ASIS);
	assert(index == requests % 2);
	requests++;
	if (requests == request_failure) return ERR_PTR(-EBUSY);
	result = &descriptors[fault == WRONG_DESCRIPTOR ? 2 : index];
	assert(!result->owned);
	result->owned = true;
	result->gdev->refs++;
	return result;
}
static unsigned int gpiod_hwgpio(struct gpio_desc *desc)
{
	assert(desc->owned && provider.dev.locked);
	return desc->pin + (fault == WRONG_HWGPIO ? 1 : 0);
}
static void gpiod_put(struct gpio_desc *desc)
{
	assert(desc->owned && active_lookup && provider.dev.locked && release_count < 4);
	desc->owned = false;
	desc->gdev->refs--;
	releases[release_count++] = desc->pin;
}

#include "n71-i2c-pin-cycle.c"

static void reset(enum fault_id selected)
{
	fault = selected;
	memset(nodes, 0, sizeof(nodes));
	memset(&provider, 0, sizeof(provider));
	memset(&controller, 0, sizeof(controller));
	memset(&adapter, 0, sizeof(adapter));
	memset(&consumer, 0, sizeof(consumer));
	driver.name = fault == DRIVER_NAME ? "other" : "apple-gpio-pinctrl";
	provider.dev.of_node = &nodes[fault == PROVIDER_NODE ? 2 : 1];
	provider.dev.driver = fault == MISSING_DRIVER ? NULL : &driver;
	gdev.refs = other_gdev.refs = 0;
	for (unsigned int i = 0; i < 3; i++)
		descriptors[i] = (struct gpio_desc) {i ? 114 : 115, false, &gdev};
	/* A different provider may expose the same hardware offset. */
	descriptors[2].pin = 115;
	descriptors[2].gdev = &other_gdev;
	run = fault != RUN_OFF;
	active_lookup = NULL;
	allocated = registered = false;
	reads = read_failure = requests = request_failure = release_count = bypass_reads = 0;
	drift_at = corrupt_at = corrupt_pattern = 0;
	word = 0x76221;
	changed_word = word ^ (1U << 20);
	output_size = 0;
	output[0] = 0;
}
static void assert_released(void)
{
	for (unsigned int i = 0; i < 3; i++) assert(!nodes[i].refs && !descriptors[i].owned);
	assert(!provider.dev.refs && !provider.dev.locked && !controller.dev.refs && !adapter.dev.refs);
	assert(!gdev.refs && !other_gdev.refs && !active_lookup && !allocated && !registered);
}
int main(void)
{
	unsigned int cases = 0;
#ifdef __linux__
	assert(prctl(PR_SET_DUMPABLE, 0) == 0);
#endif
	/* Mutations captured: wrong board/provider/resource/descriptor scope and leaks. */
	for (enum fault_id f = RUN_OFF; f < FAULT_COUNT; f++) {
		reset(f);
		assert(n71_i2c_pin_cycle_init() < 0);
		assert(!strstr(output, "N71_I2C_PIN_CYCLES_OK"));
		assert_released();
		cases++;
	}
	/* Mutations captured: ignored read/acquisition errors or missing reverse cleanup. */
	for (unsigned int position = 1; position <= 40; position++) {
		reset(NONE);
		read_failure = position;
		assert(n71_i2c_pin_cycle_init() == -EIO);
		assert(!strstr(output, "N71_I2C_PIN_CYCLES_OK"));
		assert_released();
		cases++;
	}
	for (unsigned int position = 1; position <= 4; position++) {
		reset(NONE);
		request_failure = position;
		assert(n71_i2c_pin_cycle_init() == -EBUSY && requests == position);
		assert(release_count == position - 1);
		if (position == 2) assert(releases[0] == 115);
		assert_released();
		cases++;
	}
	/* Mutations captured: accepting incoherent cached/hardware samples or changed pads. */
	for (unsigned int position = 1; position <= 8; position++) {
		reset(NONE);
		corrupt_at = position;
		assert(n71_i2c_pin_cycle_init() == -EUCLEAN && !requests);
		assert_released();
		cases++;
	}
	for (unsigned int position = 9; position <= 33; position += 8) {
		reset(NONE);
		drift_at = position;
		assert(n71_i2c_pin_cycle_init() == -EUCLEAN);
		assert(!strstr(output, "N71_I2C_PIN_CYCLES_OK"));
		assert_released();
		cases++;
	}
	reset(NONE);
	corrupt_pattern = (1U << 2) | (1U << 3);
	assert(n71_i2c_pin_cycle_init() == -EUCLEAN && !requests);
	assert_released();
	cases++;
	for (unsigned int selector = 0; selector < 8; selector++) {
		reset(NONE);
		word = (word & ~0x260U) | (selector & 3U) * 0x20U | ((selector & 4U) ? 0x200U : 0);
		assert(n71_i2c_pin_cycle_init() == (selector == 5 ? 0 : -EUCLEAN));
		assert_released();
		cases++;
	}
	/* Mutations captured: skipping the second cycle, bypass reads, or reverse release. */
	reset(NONE);
	assert(n71_i2c_pin_cycle_init() == 0 && reads == 40 && bypass_reads == 20);
	assert(requests == 4 && release_count == 4);
	assert(releases[0] == 114 && releases[1] == 115 && releases[2] == 114 && releases[3] == 115);
	assert(strstr(output, "N71_I2C_PIN_CYCLES_OK cycles=2 pins=115,114"));
	assert_released();
	n71_i2c_pin_cycle_exit();
	assert(strstr(output, "N71_I2C_PIN_UNLOADED"));
	cases++;
	printf("N71_I2C_PIN_CYCLE_OK cases=%u\n", cases);
	return 0;
}
