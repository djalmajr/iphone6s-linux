/* SPDX-License-Identifier: GPL-2.0-only */
/* Probe must not publish a domain after failed PMGR I/O. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define BIT(n) (1U << (n))
#define GENMASK(high, low) ((UINT32_MAX >> (31 - (high))) & (UINT32_MAX << (low)))
#define FIELD_PREP(mask, value) (((value) << __builtin_ctz(mask)) & (mask))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctz(mask))
#define container_of(pointer, type, member) ((type *)((char *)(pointer) - offsetof(type, member)))
#define GENPD_FLAG_IRQ_SAFE 1U
#define GENPD_FLAG_ALWAYS_ON 2U
#define GFP_KERNEL 0
#define EPROBE_DEFER 517
#define MAX_PHANDLE_ARGS 16
#define THIS_MODULE NULL
#define IS_ERR(value) ((uintptr_t)(value) > UINTPTR_MAX - 4095)
#define PTR_ERR(value) ((int)(intptr_t)(value))
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define dev_warn(...) ((void)0)

typedef uint32_t u32;
struct device_node { struct device_node *parent; const char *name; };
struct device { struct device_node *of_node; };
struct platform_device { struct device dev; };
struct generic_pm_domain {
	const char *name;
	unsigned int flags;
	int (*power_on)(struct generic_pm_domain *);
	int (*power_off)(struct generic_pm_domain *);
};
struct reset_control_ops { int unused; };
struct of_phandle_args { struct device_node *np; int args_count; u32 args[16]; };
struct of_phandle_iterator { struct device_node *node; };
struct reset_controller_dev {
	void *owner;
	unsigned int nr_resets, of_reset_n_cells;
	const struct reset_control_ops *ops;
	struct device_node *of_node;
	int (*of_xlate)(struct reset_controller_dev *, const struct of_phandle_args *);
};
struct regmap { u32 word; };
struct apple_pmgr_ps {
	struct device *dev;
	struct generic_pm_domain genpd;
	struct reset_controller_dev rcdev;
	struct regmap *regmap;
	u32 offset, min_state;
};
#define genpd_to_apple_pmgr_ps(p) container_of(p, struct apple_pmgr_ps, genpd)
static const struct reset_control_ops apple_pmgr_reset_ops = {0};
static struct device_node parent = {NULL, "pmgr"}, node = {&parent, "i2c1"};
static struct apple_pmgr_ps allocated;
static struct regmap map;
static unsigned int io_count, fail_at, writes, genpd_count, provider_count, reset_count;
static int io_error, partial_effect, min_kind, always_on, domain_off;

static struct regmap *syscon_node_to_regmap(struct device_node *selected)
{
	assert(selected == &parent); return &map;
}

static void *devm_kzalloc(struct device *dev, size_t size, int flags)
{
	assert(dev->of_node == &node && size == sizeof(allocated) && flags == 0);
	memset(&allocated, 0, sizeof(allocated)); return &allocated;
}

static int of_property_read_string(struct device_node *selected, const char *key,
				   const char **value)
{
	assert(selected == &node && !strcmp(key, "label")); *value = "i2c1"; return 0;
}

static int of_property_read_u32(struct device_node *selected, const char *key, u32 *value)
{
	assert(selected == &node);
	if (!strcmp(key, "reg")) { *value = 0x801a0; return 0; }
	assert(!strcmp(key, "apple,min-state"));
	if (!min_kind) return -EINVAL;
	*value = min_kind == 1 ? 4 : 16; return 0;
}

static bool of_property_read_bool(struct device_node *selected, const char *key)
{
	assert(selected == &node && !strcmp(key, "apple,always-on")); return always_on;
}

static int io(struct regmap *selected, unsigned int offset)
{
	assert(selected == &map && offset == 0x801a0);
	io_count++; return io_count == fail_at ? io_error : 0;
}

static int regmap_read(struct regmap *selected, unsigned int offset, u32 *value)
{
	int error = io(selected, offset);
	if (!error) *value = selected->word;
	return error;
}

static int regmap_write(struct regmap *selected, unsigned int offset, u32 value)
{
	int error = io(selected, offset); writes++;
	if (!error || partial_effect) selected->word = value;
	return error;
}

static int regmap_update_bits(struct regmap *selected, unsigned int offset, u32 mask, u32 value)
{
	int error = io(selected, offset); writes++;
	if (!error || partial_effect) selected->word = (selected->word & ~mask) | (value & mask);
	return error;
}

static int pmgr_poll(struct regmap *selected, unsigned int offset, u32 *value,
		     unsigned int delay, unsigned int timeout)
{
	int error = io(selected, offset);
	assert(delay == 1 && timeout == 100);
	if (!error || partial_effect)
		selected->word = (selected->word & ~0xf0U) | ((selected->word & 0xfU) << 4);
	*value = selected->word; return error;
}
#define regmap_read_poll_timeout_atomic(m, o, v, condition, delay, timeout) \
	({ int e = pmgr_poll(m, o, &(v), delay, timeout); \
	   e ? e : ((condition) ? 0 : -ETIMEDOUT); })

static int pm_genpd_init(struct generic_pm_domain *domain, void *governor, bool off)
{
	assert(domain == &allocated.genpd && !governor);
	assert(!off || !(domain->flags & GENPD_FLAG_ALWAYS_ON));
	genpd_count++; domain_off = off; return 0;
}

static int of_genpd_add_provider_simple(struct device_node *selected, struct generic_pm_domain *domain)
{
	assert(selected == &node && domain == &allocated.genpd && genpd_count == 1);
	provider_count++; return 0;
}

#define of_for_each_phandle(it, ret, selected, list, cells, nargs) \
	for ((it)->node = NULL, (ret) = -ENOENT; (ret) == 0; (ret) = -ENOENT)
static int of_phandle_iterator_args(struct of_phandle_iterator *it, u32 *args, int count) { return 0; }
static int of_genpd_add_subdomain(struct of_phandle_args *parent_domain, struct of_phandle_args *child) { return 0; }
static void of_node_put(struct device_node *selected) { }
static void pm_genpd_remove_device(struct device *dev) { assert(dev == allocated.dev); }
static void of_genpd_del_provider(struct device_node *selected) { assert(selected == &node); }
static int pm_genpd_remove(struct generic_pm_domain *domain) { return 0; }

static int devm_reset_controller_register(struct device *dev, struct reset_controller_dev *reset)
{
	assert(dev == allocated.dev && reset == &allocated.rcdev && provider_count == 1);
	assert(reset->nr_resets == 1 && reset->ops == &apple_pmgr_reset_ops);
	assert(reset->of_node == &node && reset->of_reset_n_cells == 0 && reset->of_xlate);
	reset_count++; return 0;
}

#include "n71-pmgr-probe-functions.h"

static void prepare(u32 word, unsigned int failure, int error, int partial)
{
	map.word = word; io_count = writes = genpd_count = provider_count = reset_count = 0;
	fail_at = failure; io_error = error; partial_effect = partial; domain_off = -1;
}

int main(void)
{
	struct platform_device device = {{&node}};
	const int errors[] = {-EIO, -ENOMEM, -ETIMEDOUT};
	unsigned int actual, target, automatic, minimum, on, cases = 0, scenario, ei, partial;
	u32 seed;

	/* Kills changed active semantics and incorrect min-state/auto-PM masks. */
	for (actual = 0; actual < 16; actual++)
	for (target = 0; target < 16; target++)
	for (automatic = 0; automatic < 2; automatic++)
	for (minimum = 0; minimum < 3; minimum++)
	for (on = 0; on < 2; on++) {
		u32 expected;
		bool active = actual == 15 || (target == 15 && automatic);
		min_kind = minimum; always_on = on;
		seed = (0xa0550300U & ~0x100000ffU) | (actual << 4) | target | (automatic << 28);
		expected = seed;
		if (minimum == 1) expected = (expected & ~0xf0300U) | 0x40000;
		if (on && !active) expected = (expected & ~0x100003ffU) | 0x100000ffU;
		if (active || on) expected = (expected & ~0x300U) | 0x10000000U;
		prepare(seed, 0, 0, 0);
		assert(apple_pmgr_ps_probe(&device) == 0);
		assert(genpd_count == 1 && provider_count == 1 && reset_count == 1);
		assert(domain_off == !(active || on) && map.word == expected);
		assert(allocated.genpd.flags == (GENPD_FLAG_IRQ_SAFE | (on ? GENPD_FLAG_ALWAYS_ON : 0)));
		assert(!strcmp(allocated.genpd.name, "i2c1") && allocated.offset == 0x801a0);
		assert(allocated.genpd.power_on == apple_pmgr_ps_power_on);
		assert(allocated.genpd.power_off == apple_pmgr_ps_power_off);
		cases++;
	}

	/* Kills masked first errors and domain publication after partial failed I/O. */
	for (scenario = 0; scenario < 9; scenario++)
	for (ei = 0; ei < 3; ei++)
	for (partial = 0; partial < 2; partial++) {
		unsigned int failure;
		min_kind = scenario == 0 || scenario == 8 ? 1 : 0;
		always_on = scenario >= 3 && scenario < 8;
		seed = scenario == 2 ? 0xa05503f0U : 0xa0550340U;
		failure = scenario == 0 || scenario == 1 ? 1 : scenario == 8 ? 2 : scenario == 2 ? 2 : scenario - 1;
		prepare(seed, failure, errors[ei], partial);
		assert(apple_pmgr_ps_probe(&device) == errors[ei]);
		assert(io_count == failure && !genpd_count && !provider_count && !reset_count);
		assert((map.word & ~0x100f03ffU) == (seed & ~0x100f03ffU));
		cases++;
	}

#if N71_NEW_ACTIVE_API
	/* Kills modifying the caller's bool before a failed state read. */
	for (on = 0; on < 2; on++)
	for (ei = 0; ei < 3; ei++)
	for (scenario = 0; scenario < 2; scenario++) {
		bool active = on;
		prepare(0x1000004f, scenario, errors[ei], 0);
		allocated.regmap = &map; allocated.offset = 0x801a0;
		assert(apple_pmgr_ps_is_active(&allocated, &active) == (scenario ? errors[ei] : 0));
		assert(active == (scenario ? (bool)on : true));
		assert(io_count == 1 && !writes && !genpd_count && !provider_count && !reset_count);
		cases++;
	}
#endif
	printf("N71_PMGR_PROBE_OK cases=%u\n", cases);
	return 0;
}
