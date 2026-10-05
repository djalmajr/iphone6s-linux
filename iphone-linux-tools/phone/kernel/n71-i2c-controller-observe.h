/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller serializes a qualified N71 genpd consumer with a held usage reference. */
#ifndef N71_I2C_CONTROLLER_OBSERVE_H
#define N71_I2C_CONTROLLER_OBSERVE_H
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/of_address.h>
#include "n71-i2c-power-lifecycle.h"

enum n71_i2c_observe_word {
	N71_I2C_OBSERVE_REV,
	N71_I2C_OBSERVE_SMSTA,
	N71_I2C_OBSERVE_XFSTA,
	N71_I2C_OBSERVE_WORDS,
};

struct n71_i2c_controller_observation {
	u32 words[2][N71_I2C_OBSERVE_WORDS];
	bool complete;
	bool idle_status;
	bool stable;
};

static inline bool n71_i2c_observe_idle_status(u32 status)
{
	/* Pinned PASemi clear path: no transfer/jam/errors/RX data, TX FIFO empty. */
	const u32 busy = (1U << 28) | (1U << 25) | (1U << 24) | (1U << 23) |
		(1U << 22) | (1U << 21) | (1U << 19) | (1U << 6);

	return !(status & busy) && (status & (1U << 16));
}

static inline int n71_i2c_controller_observe(struct device *consumer,
		const struct n71_i2c_power_state *power,
		struct n71_i2c_controller_observation *result)
{
	static const unsigned int offsets[] = {0x28, 0x14, 0x0c};
	struct resource resource;
	void __iomem *base;
	unsigned int sample, word;
	int error;

	if (!result)
		return -EINVAL;
	*result = (struct n71_i2c_controller_observation) {0};
	if (!consumer || !consumer->of_node || !power || !power->active ||
	    !power->attached || !power->usage_held || !power->cleanup_pending)
		return -EINVAL;
	if (consumer->bus || consumer->driver || consumer->pm_domain ||
	    !device_is_registered(consumer))
		return -ENODEV;
	error = of_address_to_resource(consumer->of_node, 0, &resource);
	if (error)
		return error;
	if (resource.start != 0x20a111000ULL || resource_size(&resource) != 0x1000 ||
	    resource_type(&resource) != IORESOURCE_MEM)
		return -ENODEV;
	if (!request_mem_region_exclusive(resource.start, resource_size(&resource),
					 "n71-i2c1-inspect"))
		return -EBUSY;
	base = ioremap(resource.start, resource_size(&resource));
	if (!base) {
		error = -ENOMEM;
		goto release;
	}
	for (sample = 0; sample < 2; sample++)
		for (word = 0; word < N71_I2C_OBSERVE_WORDS; word++)
			result->words[sample][word] = ioread32(base + offsets[word]);
	result->complete = true;
	result->stable = true;
	error = 0;
	for (word = 0; word < N71_I2C_OBSERVE_WORDS; word++) {
		if (result->words[0][word] != result->words[1][word])
			result->stable = false;
		if (result->words[0][word] == ~0U || result->words[1][word] == ~0U)
			error = -ENODEV;
	}
	result->idle_status = !error && result->stable &&
		n71_i2c_observe_idle_status(result->words[0][N71_I2C_OBSERVE_SMSTA]) &&
		n71_i2c_observe_idle_status(result->words[1][N71_I2C_OBSERVE_SMSTA]);
	iounmap(base);
release:
	release_mem_region(resource.start, resource_size(&resource));
	return error;
}
#endif /* N71_I2C_CONTROLLER_OBSERVE_H */
