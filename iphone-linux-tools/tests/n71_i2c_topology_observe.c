/* SPDX-License-Identifier: GPL-2.0-only */
/* Execute the real module against bounded OF/device/regmap API contracts. */
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

struct device_node { const char *full_name; int refs; };
struct device_driver { const char *name; };
struct device { struct device_node *of_node; struct device_driver *driver; int refs, locked; };
struct platform_device { struct device dev; };
struct i2c_adapter { struct device dev; };
struct resource { u64 start, end; unsigned int flags; };
struct regmap { int unused; };
struct of_phandle_args { struct device_node *np; int args_count; u32 args[8]; };

enum node_id { I2C, GPIO, AIC, CLOCK, DOMAIN, PINS, OTHER, NODE_COUNT };
enum fault_id {
	NONE, RUN_OFF, BOARD_WRONG, I2C_MISSING, I2C_AVAILABLE, STATUS_MISSING,
	STATUS_WRONG, I2C_COMPAT, I2C_FALLBACK, CHILD_PRESENT, PLATFORM_PRESENT,
	ADAPTER_PRESENT, I2C_RESOURCE_ERROR, I2C_BASE, I2C_SIZE, I2C_TYPE,
	IRQ_COUNT, IRQ_PARSE_ERROR, IRQ_ARGS_COUNT, IRQ_KIND, IRQ_NUMBER, IRQ_TYPE,
	IRQ_UNAVAILABLE, IRQ_COMPAT, IRQ_RESOURCE_ERROR, IRQ_BASE, IRQ_SIZE, IRQ_RESOURCE_TYPE,
	CLOCK_COUNT, CLOCK_PARSE_ERROR, CLOCK_ARGS, CLOCK_PATH, CLOCK_UNAVAILABLE,
	CLOCK_COMPAT, CLOCK_WIDTH, CLOCK_READ_ERROR, CLOCK_FREQUENCY,
	DOMAIN_COUNT, DOMAIN_PARSE_ERROR, DOMAIN_ARGS, DOMAIN_PATH, DOMAIN_UNAVAILABLE,
	DOMAIN_COMPAT, DOMAIN_WIDTH, DOMAIN_READ_ERROR, DOMAIN_OFFSET, DOMAIN_SIZE,
	GPIO_MISSING, GPIO_UNAVAILABLE, GPIO_COMPAT, GPIO_RESOURCE_ERROR,
	GPIO_BASE, GPIO_SIZE, GPIO_TYPE, PIN_COUNT, PIN_NAME_COUNT, PIN_NAME_ERROR,
	PIN_NAME_WRONG, PIN_PARSE_ERROR, PIN_ARGS, PIN_PARENT, PIN_PATH,
	PIN_UNAVAILABLE, PIN_WIDTH, PIN_READ_ERROR, PIN_FIRST, PIN_SECOND,
	PROVIDER_MISSING, PROVIDER_NODE, DRIVER_MISSING, DRIVER_NAME, MAP_MISSING,
	MAP_WIDTH, MAP_STRIDE, FAULT_COUNT
};

static enum fault_id fault;
static struct device_node nodes[NODE_COUNT];
static struct device_driver driver;
static struct platform_device provider, controller;
static struct i2c_adapter adapter_device;
static struct regmap map;
static unsigned int reads, read_error, samples[2][4];
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

static struct device_node *get_node(enum node_id id)
{
	nodes[id].refs++;
	return &nodes[id];
}

static void of_node_put(struct device_node *node)
{
	if (node) {
		assert(node->refs > 0);
		node->refs--;
	}
}

static bool of_machine_is_compatible(const char *name)
{
	assert(!strcmp(name, "apple,n71"));
	return fault != BOARD_WRONG;
}

static struct device_node *of_find_node_by_path(const char *path)
{
	if (!strcmp(path, "/soc/i2c@20a111000"))
		return fault == I2C_MISSING ? NULL : get_node(I2C);
	assert(!strcmp(path, "/soc/pinctrl@20f100000"));
	return fault == GPIO_MISSING ? NULL : get_node(GPIO);
}

static bool of_device_is_available(const struct device_node *node)
{
	if (node == &nodes[I2C])
		return fault == I2C_AVAILABLE;
	return !((node == &nodes[GPIO] && fault == GPIO_UNAVAILABLE) ||
		 (node == &nodes[AIC] && fault == IRQ_UNAVAILABLE) ||
		 (node == &nodes[CLOCK] && fault == CLOCK_UNAVAILABLE) ||
		 (node == &nodes[DOMAIN] && fault == DOMAIN_UNAVAILABLE) ||
		 (node == &nodes[PINS] && fault == PIN_UNAVAILABLE));
}

static bool of_device_is_compatible(const struct device_node *node, const char *name)
{
	if (node == &nodes[I2C]) {
		if (!strcmp(name, "apple,s8000-i2c"))
			return fault != I2C_COMPAT;
		assert(!strcmp(name, "apple,i2c"));
		return fault != I2C_FALLBACK;
	}
	if (node == &nodes[GPIO]) {
		assert(!strcmp(name, "apple,pinctrl"));
		return fault != GPIO_COMPAT;
	}
	if (node == &nodes[AIC]) {
		assert(!strcmp(name, "apple,s8000-aic"));
		return fault != IRQ_COMPAT;
	}
	if (node == &nodes[CLOCK]) {
		assert(!strcmp(name, "fixed-clock"));
		return fault != CLOCK_COMPAT;
	}
	assert(node == &nodes[DOMAIN] && !strcmp(name, "apple,s8000-pmgr-pwrstate"));
	return fault != DOMAIN_COMPAT;
}

static int of_property_read_string(const struct device_node *node, const char *property,
				   const char **value)
{
	assert(node == &nodes[I2C]);
	if (!strcmp(property, "status")) {
		if (fault == STATUS_MISSING)
			return -EINVAL;
		*value = fault == STATUS_WRONG ? "reserved" : "disabled";
		return 0;
	}
	assert(!strcmp(property, "pinctrl-names"));
	if (fault == PIN_NAME_ERROR)
		return -EINVAL;
	*value = fault == PIN_NAME_WRONG ? "sleep" : "default";
	return 0;
}

static int of_property_count_strings(const struct device_node *node, const char *property)
{
	assert(node == &nodes[I2C] && !strcmp(property, "pinctrl-names"));
	return fault == PIN_NAME_COUNT ? 2 : 1;
}

static int of_get_child_count(const struct device_node *node)
{
	assert(node == &nodes[I2C]);
	return fault == CHILD_PRESENT;
}

static struct platform_device *of_find_device_by_node(struct device_node *node)
{
	if (node == &nodes[I2C]) {
		if (fault != PLATFORM_PRESENT)
			return NULL;
		controller.dev.refs++;
		return &controller;
	}
	assert(node == &nodes[GPIO]);
	if (fault == PROVIDER_MISSING)
		return NULL;
	provider.dev.refs++;
	return &provider;
}

static struct i2c_adapter *of_find_i2c_adapter_by_node(struct device_node *node)
{
	assert(node == &nodes[I2C]);
	if (fault != ADAPTER_PRESENT)
		return NULL;
	adapter_device.dev.refs++;
	return &adapter_device;
}

static void put_device(struct device *device)
{
	assert(device->refs > 0 && !device->locked);
	device->refs--;
}

static int of_address_to_resource(struct device_node *node, int index, struct resource *resource)
{
	u64 base, size;
	enum fault_id failure, wrong_base, wrong_size, wrong_type;

	assert(index == 0);
	if (node == &nodes[I2C]) {
		base = 0x20a111000ULL; size = 0x1000;
		failure = I2C_RESOURCE_ERROR; wrong_base = I2C_BASE;
		wrong_size = I2C_SIZE; wrong_type = I2C_TYPE;
	} else if (node == &nodes[AIC]) {
		base = 0x20e100000ULL; size = 0x100000;
		failure = IRQ_RESOURCE_ERROR; wrong_base = IRQ_BASE;
		wrong_size = IRQ_SIZE; wrong_type = IRQ_RESOURCE_TYPE;
	} else {
		assert(node == &nodes[GPIO]);
		base = 0x20f100000ULL; size = 0x100000;
		failure = GPIO_RESOURCE_ERROR; wrong_base = GPIO_BASE;
		wrong_size = GPIO_SIZE; wrong_type = GPIO_TYPE;
	}
	if (fault == failure)
		return -EIO;
	resource->start = base + (fault == wrong_base ? 4 : 0);
	resource->end = resource->start + size - 1 + (fault == wrong_size ? 4 : 0);
	resource->flags = fault == wrong_type ? 0x100 : IORESOURCE_MEM;
	return 0;
}

static u64 resource_size(const struct resource *resource) { return resource->end - resource->start + 1; }
static unsigned int resource_type(const struct resource *resource) { return resource->flags; }

static int of_property_count_u32_elems(const struct device_node *node, const char *property)
{
	if (node == &nodes[I2C]) {
		assert(!strcmp(property, "interrupts"));
		return fault == IRQ_COUNT ? 6 : 3;
	}
	if (node == &nodes[CLOCK]) {
		assert(!strcmp(property, "clock-frequency"));
		return fault == CLOCK_WIDTH ? 2 : 1;
	}
	if (node == &nodes[DOMAIN]) {
		assert(!strcmp(property, "reg"));
		return fault == DOMAIN_WIDTH ? 3 : 2;
	}
	assert(node == &nodes[PINS] && !strcmp(property, "pinmux"));
	return fault == PIN_WIDTH ? 3 : 2;
}

static int of_irq_parse_one(struct device_node *node, int index, struct of_phandle_args *args)
{
	assert(node == &nodes[I2C] && index == 0);
	if (fault == IRQ_PARSE_ERROR)
		return -EIO;
	args->np = get_node(AIC);
	args->args_count = fault == IRQ_ARGS_COUNT ? 2 : 3;
	args->args[0] = fault == IRQ_KIND ? 1 : 0;
	args->args[1] = fault == IRQ_NUMBER ? 197 : 207;
	args->args[2] = fault == IRQ_TYPE ? 1 : 4;
	return 0;
}

static enum node_id phandle_id(const struct device_node *node, const char *property, const char *cells)
{
	assert(node == &nodes[I2C]);
	if (!strcmp(property, "clocks")) {
		assert(cells && !strcmp(cells, "#clock-cells"));
		return CLOCK;
	}
	if (!strcmp(property, "power-domains")) {
		assert(cells && !strcmp(cells, "#power-domain-cells"));
		return DOMAIN;
	}
	assert(!strcmp(property, "pinctrl-0") && !cells);
	return PINS;
}

static int of_count_phandle_with_args(const struct device_node *node, const char *property, const char *cells)
{
	enum node_id id = phandle_id(node, property, cells);
	return (id == CLOCK && fault == CLOCK_COUNT) ||
	       (id == DOMAIN && fault == DOMAIN_COUNT) || (id == PINS && fault == PIN_COUNT) ? 2 : 1;
}

static int of_parse_phandle_with_args(const struct device_node *node, const char *property,
				     const char *cells, int index, struct of_phandle_args *args)
{
	enum node_id id = phandle_id(node, property, cells);
	assert(index == 0);
	if ((id == CLOCK && fault == CLOCK_PARSE_ERROR) ||
	    (id == DOMAIN && fault == DOMAIN_PARSE_ERROR) || (id == PINS && fault == PIN_PARSE_ERROR))
		return -EIO;
	args->np = get_node(id);
	args->args_count = (id == CLOCK && fault == CLOCK_ARGS) ||
		(id == DOMAIN && fault == DOMAIN_ARGS) || (id == PINS && fault == PIN_ARGS);
	return 0;
}

static int of_property_read_u32(const struct device_node *node, const char *property, u32 *value)
{
	assert(node == &nodes[CLOCK] && !strcmp(property, "clock-frequency"));
	if (fault == CLOCK_READ_ERROR)
		return -EIO;
	*value = fault == CLOCK_FREQUENCY ? 12000000 : 24000000;
	return 0;
}

static int of_property_read_u32_array(const struct device_node *node, const char *property,
				    u32 *values, size_t count)
{
	assert(count == 2);
	if (node == &nodes[DOMAIN]) {
		assert(!strcmp(property, "reg"));
		if (fault == DOMAIN_READ_ERROR)
			return -EIO;
		values[0] = fault == DOMAIN_OFFSET ? 0x80198 : 0x801a0;
		values[1] = fault == DOMAIN_SIZE ? 8 : 4;
	} else {
		assert(node == &nodes[PINS] && !strcmp(property, "pinmux"));
		if (fault == PIN_READ_ERROR)
			return -EIO;
		values[0] = fault == PIN_FIRST ? 0x20073 : 0x10073;
		values[1] = fault == PIN_SECOND ? 0x10071 : 0x10072;
	}
	return 0;
}

static struct device_node *of_get_parent(const struct device_node *node)
{
	assert(node == &nodes[PINS]);
	return get_node(fault == PIN_PARENT ? OTHER : GPIO);
}

static void device_lock(struct device *device)
{
	assert(device == &provider.dev && device->refs == 1 && !device->locked);
	device->locked = 1;
}

static void device_unlock(struct device *device)
{
	assert(device == &provider.dev && device->locked);
	device->locked = 0;
}

static struct regmap *dev_get_regmap(struct device *device, const char *name)
{
	assert(device == &provider.dev && device->locked && !name);
	return fault == MAP_MISSING ? NULL : &map;
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

static int read_sample(struct regmap *value, unsigned int offset, unsigned int *word, bool bypassed)
{
	unsigned int pin = reads / 4, position = reads % 4;
	assert(value == &map && provider.dev.locked && reads < 8);
	assert(offset == (114 + pin) * 4);
	assert(bypassed == (position == 1 || position == 2));
	reads++;
	*word = samples[pin][position];
	if (read_error == reads)
		return -EIO;
	return 0;
}

static int regmap_read(struct regmap *value, unsigned int offset, unsigned int *word)
{
	return read_sample(value, offset, word, false);
}

static int regmap_read_bypassed(struct regmap *value, unsigned int offset, unsigned int *word)
{
	return read_sample(value, offset, word, true);
}

#include "n71-i2c-topology-observe.c"

static void reset(enum fault_id selected)
{
	const char *paths[NODE_COUNT] = {
		"/soc/i2c@20a111000", "/soc/pinctrl@20f100000", "/soc/interrupt-controller@20e100000",
		"/clock-ref", "/soc/power-management@20e000000/power-controller@801a0",
		"/soc/pinctrl@20f100000/i2c1-pins", "/other"
	};
	unsigned int i, pin, sample;

	for (i = 0; i < NODE_COUNT; i++) {
		nodes[i].refs = 0;
		nodes[i].full_name = paths[i];
	}
	fault = selected;
	if (fault == CLOCK_PATH) nodes[CLOCK].full_name = "/other-clock";
	if (fault == DOMAIN_PATH) nodes[DOMAIN].full_name = "/other-domain";
	if (fault == PIN_PATH) nodes[PINS].full_name = "/other-pins";
	memset(&provider, 0, sizeof(provider));
	memset(&controller, 0, sizeof(controller));
	memset(&adapter_device, 0, sizeof(adapter_device));
	driver.name = fault == DRIVER_NAME ? "other-driver" : "apple-gpio-pinctrl";
	provider.dev.of_node = &nodes[fault == PROVIDER_NODE ? OTHER : GPIO];
	provider.dev.driver = fault == DRIVER_MISSING ? NULL : &driver;
	run = fault != RUN_OFF;
	reads = read_error = 0;
	output_size = 0;
	output[0] = 0;
	for (pin = 0; pin < 2; pin++)
		for (sample = 0; sample < 4; sample++)
			samples[pin][sample] = 0x70000 + pin * 0x100 + sample;
}

static void assert_released(void)
{
	unsigned int i;
	for (i = 0; i < NODE_COUNT; i++) assert(!nodes[i].refs);
	assert(!provider.dev.refs && !provider.dev.locked);
	assert(!controller.dev.refs && !adapter_device.dev.refs);
}

int main(void)
{
	unsigned int cases = 0, position;
	enum fault_id selected;

	/* Mutations captured: missing board/status/scope/owner checks and leaked refs. */
	for (selected = RUN_OFF; selected < FAULT_COUNT; selected++) {
		int result;
		reset(selected);
		result = n71_i2c_topology_observe_init();
		assert(result < 0);
		if (selected == PLATFORM_PRESENT || selected == ADAPTER_PRESENT) assert(result == -EBUSY);
		assert(reads == 0 && !strstr(output, "N71_I2C1_OBSERVED") && !strstr(output, "N71_I2C1_GPIO"));
		assert_released();
		cases++;
	}
	/* Mutations captured: swallowed read failures and premature success output. */
	for (position = 1; position <= 8; position++) {
		reset(NONE);
		read_error = position;
		assert(n71_i2c_topology_observe_init() == -EIO);
		assert(reads == position && !strstr(output, "N71_I2C1_OBSERVED") && !strstr(output, "N71_I2C1_GPIO"));
		assert_released();
		cases++;
	}
	/* Mutations captured: missing lock, wrong offsets/read kind and a fabricated sample. */
	reset(NONE);
	assert(n71_i2c_topology_observe_init() == 0 && reads == 8);
	assert(strstr(output, "pin=114 cached-before=00070000 hardware-first=00070001 hardware-second=00070002 cached-after=00070003 stable=0 cache-matches=0"));
	assert(strstr(output, "pin=115 cached-before=00070100 hardware-first=00070101 hardware-second=00070102 cached-after=00070103 stable=0 cache-matches=0"));
	assert(strstr(output, "N71_I2C1_OBSERVED disabled=1 children=0 platform=absent adapter=absent"));
	assert(strstr(output, "no writes, activation or ownership claim"));
	assert_released();
	n71_i2c_topology_observe_exit();
	assert(reads == 8 && strstr(output, "N71_I2C1_UNLOADED"));
	cases++;
	reset(NONE);
	samples[0][1] = samples[0][2] = samples[0][3] = 0x12345;
	assert(n71_i2c_topology_observe_init() == 0);
	assert(strstr(output, "pin=114 cached-before=00070000 hardware-first=00012345 hardware-second=00012345 cached-after=00012345 stable=1 cache-matches=1"));
	assert_released();
	cases++;
	printf("N71_I2C_TOPOLOGY_OBSERVE_OK cases=%u reads-per-observation=8\n", cases);
	return 0;
}
