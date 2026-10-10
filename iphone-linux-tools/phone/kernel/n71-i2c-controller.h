/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller retains qualified pins, consumer and active genpd until clean release. */
#ifndef N71_I2C_CONTROLLER_H
#define N71_I2C_CONTROLLER_H
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/of.h>
#include "n71-i2c-controller-observe.h"

enum n71_i2c_controller_word {
	N71_I2C_REV,
	N71_I2C_SMSTA,
	N71_I2C_XFSTA,
	N71_I2C_IMASK,
	N71_I2C_CTL,
	N71_I2C_WORDS,
};

struct n71_i2c_controller_request {
	struct device *consumer;
	void *pin_context;
	const struct n71_i2c_power_state *power;
	int (*verify_pins)(void *context);
};

struct n71_i2c_controller {
	void __iomem *base;
	bool claimed;
	int cleanup_error;
	struct clk *clock;
	bool clock_enabled;
	bool clock_protected;
	struct device *consumer;
	bool restore_pending;
	u32 saved[N71_I2C_WORDS];
	bool status_acknowledged;
	bool transfer_pending;
};

static inline bool n71_i2c_controller_clean(const struct n71_i2c_controller *state)
{
	return !state->base && !state->clock && !state->consumer && !state->claimed &&
		!state->clock_enabled && !state->clock_protected && !state->restore_pending &&
		!state->status_acknowledged && !state->transfer_pending;
}

static inline u32 n71_i2c_controller_expected(const struct n71_i2c_controller *state,
					      unsigned int word)
{
	return word == N71_I2C_SMSTA && state->status_acknowledged ?
		state->saved[word] & ~(1U << 27) : state->saved[word];
}

static inline bool n71_i2c_controller_powered(const struct n71_i2c_controller_request *request)
{
	const struct n71_i2c_power_state *power;
	struct device *consumer;

	if (!request || !request->verify_pins || !request->power || !request->consumer)
		return false;
	power = request->power;
	consumer = request->consumer;
	return power->active && power->attached && power->usage_held && power->cleanup_pending &&
		consumer->of_node && !consumer->bus && !consumer->driver && !consumer->pm_domain &&
		device_is_registered(consumer);
}

static inline int n71_i2c_controller_pins(const struct n71_i2c_controller_request *request)
{
	int error = request->verify_pins(request->pin_context);

	return error > 0 ? -EIO : error;
}

static inline int n71_i2c_controller_sample(void __iomem *base, u32 words[N71_I2C_WORDS])
{
	static const unsigned int offsets[] = {0x28, 0x14, 0x0c, 0x18, 0x1c};
	unsigned int sample, word;

	for (sample = 0; sample < 2; sample++) {
		for (word = 0; word < N71_I2C_WORDS; word++) {
			u32 value = ioread32(base + offsets[word]);

			if (value == ~0U)
				return -ENODEV;
			if (!sample)
				words[word] = value;
			else if (words[word] != value)
				return -EUCLEAN;
		}
	}
	return 0;
}

static inline bool n71_i2c_controller_idle(const u32 words[N71_I2C_WORDS])
{
	return words[N71_I2C_REV] == 2 && n71_i2c_observe_idle_status(words[N71_I2C_SMSTA]) &&
		!words[N71_I2C_XFSTA] && !words[N71_I2C_IMASK];
}

static inline int n71_i2c_controller_release(const struct n71_i2c_controller_request *request,
					     struct n71_i2c_controller *state)
{
	u32 words[N71_I2C_WORDS];
	unsigned int word;
	int error;

	if (!request || !state || !request->consumer)
		return -EINVAL;
	if (n71_i2c_controller_clean(state))
		return 0;
	if (state->consumer != request->consumer)
		return -EINVAL;
	if (state->transfer_pending) {
		error = -EBUSY;
		goto pending;
	}
	if (state->restore_pending) {
		if (!n71_i2c_controller_powered(request) || !state->base || !state->clock_enabled) {
			error = -EINVAL;
			goto pending;
		}
		error = n71_i2c_controller_pins(request);
		if (error)
			goto pending;
		error = n71_i2c_controller_sample(state->base, words);
		if (error)
			goto pending;
		if (!n71_i2c_controller_idle(words) || (words[N71_I2C_CTL] & ~0x7ffU)) {
			error = -EBUSY;
			goto pending;
		}
		iowrite32(state->saved[N71_I2C_CTL], state->base + 0x1c);
		iowrite32(state->saved[N71_I2C_IMASK], state->base + 0x18);
		error = n71_i2c_controller_sample(state->base, words);
		if (error)
			goto pending;
		for (word = 0; word < N71_I2C_WORDS; word++) {
			if (words[word] != n71_i2c_controller_expected(state, word)) {
				error = -EUCLEAN;
				goto pending;
			}
		}
		state->restore_pending = false;
	}
	if (state->base) {
		iounmap(state->base);
		state->base = NULL;
	}
	if (state->claimed) {
		release_mem_region(0x20a111000ULL, 0x1000);
		state->claimed = false;
	}
	if (state->clock_enabled) {
		clk_disable_unprepare(state->clock);
		state->clock_enabled = false;
	}
	if (state->clock_protected) {
		clk_rate_exclusive_put(state->clock);
		state->clock_protected = false;
	}
	if (state->clock) {
		clk_put(state->clock);
		state->clock = NULL;
	}
	state->consumer = NULL;
	state->cleanup_error = 0;
	state->status_acknowledged = false;
	return 0;
pending:
	state->cleanup_error = error;
	return error;
}

static inline int n71_i2c_controller_acquire(const struct n71_i2c_controller_request *request,
					     struct n71_i2c_controller *state)
{
	struct device_node *expected;
	struct of_phandle_args spec;
	struct resource resource;
	struct clk *clock;
	u32 cells, frequency, words[N71_I2C_WORDS];
	unsigned int attempt, word;
	int error;

	if (!state || !n71_i2c_controller_powered(request))
		return -EINVAL;
	if (!n71_i2c_controller_clean(state))
		return -EBUSY;
	error = n71_i2c_controller_pins(request);
	if (error)
		return error;
	error = of_address_to_resource(request->consumer->of_node, 0, &resource);
	if (error)
		return error;
	if (resource.start != 0x20a111000ULL || resource_size(&resource) != 0x1000 ||
	    resource_type(&resource) != IORESOURCE_MEM ||
	    of_count_phandle_with_args(request->consumer->of_node, "clocks", "#clock-cells") != 1)
		return -ENODEV;
	error = of_parse_phandle_with_args(request->consumer->of_node, "clocks",
					   "#clock-cells", 0, &spec);
	if (error)
		return error;
	expected = of_find_node_by_path("/clock-ref");
	error = !expected || spec.np != expected || spec.args_count ||
		!of_device_is_available(spec.np) ||
		!of_device_is_compatible(spec.np, "fixed-clock") ||
		of_property_read_u32(spec.np, "#clock-cells", &cells) || cells ||
		of_property_read_u32(spec.np, "clock-frequency", &frequency) ||
		frequency != 24000000 ?
		-ENODEV : 0;
	of_node_put(expected);
	of_node_put(spec.np);
	if (error)
		return error;
	clock = of_clk_get(request->consumer->of_node, 0);
	if (IS_ERR(clock))
		return PTR_ERR(clock);
	if (!clock)
		return -ENODEV;
	state->consumer = request->consumer;
	state->clock = clock;
	state->cleanup_error = 0;
	error = clk_rate_exclusive_get(clock);
	if (error)
		goto failed;
	state->clock_protected = true;
	error = clk_prepare_enable(clock);
	if (error)
		goto failed;
	state->clock_enabled = true;
	if (clk_get_rate(clock) != 24000000) {
		error = -ERANGE;
		goto failed;
	}
	if (!request_mem_region_exclusive(resource.start, resource_size(&resource),
					  "n71-i2c1-controller")) {
		error = -EBUSY;
		goto failed;
	}
	state->claimed = true;
	state->base = ioremap(resource.start, resource_size(&resource));
	if (!state->base) {
		error = -ENOMEM;
		goto failed;
	}
	error = n71_i2c_controller_sample(state->base, state->saved);
	if (error)
		goto failed;
	if (!n71_i2c_controller_idle(state->saved) || (state->saved[N71_I2C_CTL] & ~0xffU)) {
		error = -EBUSY;
		goto failed;
	}
	error = n71_i2c_controller_pins(request);
	if (error)
		goto failed;
	state->restore_pending = true;
	iowrite32(0, state->base + 0x18);
	iowrite32(0x70f, state->base + 0x1c);
	for (attempt = 0; attempt < 100; attempt++) {
		error = n71_i2c_controller_sample(state->base, words);
		if (error)
			goto failed;
		for (word = 0; word < N71_I2C_CTL; word++)
			if (words[word] != state->saved[word]) {
				error = -EUCLEAN;
				goto failed;
			}
		if (words[N71_I2C_CTL] == 0x0f || words[N71_I2C_CTL] == 0x70f) {
			error = n71_i2c_controller_pins(request);
			if (error)
				goto failed;
			return 0;
		}
		usleep_range(1000, 1100);
	}
	error = -ETIMEDOUT;
failed:
	n71_i2c_controller_release(request, state);
	return error;
}
#endif /* N71_I2C_CONTROLLER_H */
