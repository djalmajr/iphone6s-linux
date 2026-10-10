/* SPDX-License-Identifier: GPL-2.0-only */
/* Fixed SN2400 HDQ-control read; caller retains pins, power and controller. */
#ifndef N71_I2C_HDQ_READ_H
#define N71_I2C_HDQ_READ_H
#include "n71-i2c-controller.h"

#define N71_I2C_HDQ_ACK_FLAGS ((1U << 27) | (1U << 25) | (1U << 23) | \
			      (1U << 22) | (1U << 21) | (1U << 6))
#define N71_I2C_HDQ_FIFO_FLAGS ((1U << 19) | (1U << 16))
#define N71_I2C_HDQ_BUSY_FLAGS ((1U << 28) | (1U << 24))

struct n71_i2c_hdq_read_request {
	struct n71_i2c_controller *controller;
	const struct n71_i2c_controller_request *ownership;
};

struct n71_i2c_hdq_read_state {
	int cleanup_error;
	bool cleanup_pending;
	struct n71_i2c_controller *controller;
	u32 last_status;
};

static inline int n71_i2c_hdq_read_ready(const struct n71_i2c_hdq_read_request *request)
{
	struct n71_i2c_controller *controller;

	if (!request || !n71_i2c_controller_powered(request->ownership))
		return -EINVAL;
	controller = request->controller;
	if (!controller || controller->consumer != request->ownership->consumer ||
	    !controller->base || !controller->claimed || !controller->clock ||
	    !controller->clock_enabled || !controller->clock_protected ||
	    !controller->restore_pending)
		return -EINVAL;
	if (clk_get_rate(controller->clock) != 24000000)
		return -ERANGE;
	return n71_i2c_controller_pins(request->ownership);
}

static inline int n71_i2c_hdq_read_sample(const struct n71_i2c_hdq_read_request *request,
					  u32 words[N71_I2C_WORDS])
{
	struct n71_i2c_controller *controller = request->controller;
	u32 variable = N71_I2C_HDQ_ACK_FLAGS | N71_I2C_HDQ_FIFO_FLAGS | N71_I2C_HDQ_BUSY_FLAGS;
	int error = n71_i2c_controller_sample(controller->base, words);

	if (error)
		return error;
	if (words[N71_I2C_REV] != 2 || words[N71_I2C_IMASK] || words[N71_I2C_XFSTA] ||
	    (words[N71_I2C_CTL] != 0x0f && words[N71_I2C_CTL] != 0x70f) ||
	    (words[N71_I2C_SMSTA] & ~variable) != (controller->saved[N71_I2C_SMSTA] & ~variable))
		return -EUCLEAN;
	return 0;
}

static inline int n71_i2c_hdq_read_cleanup(const struct n71_i2c_hdq_read_request *request,
					   struct n71_i2c_hdq_read_state *state)
{
	struct n71_i2c_controller *controller;
	u32 words[N71_I2C_WORDS], status;
	unsigned int attempt;
	int error;

	if (!state || !request || !request->controller)
		return -EINVAL;
	if (!state->cleanup_pending)
		return state->controller ? -EINVAL : 0;
	controller = request->controller;
	if (state->controller != controller || !controller->transfer_pending)
		return -EINVAL;
	error = n71_i2c_hdq_read_ready(request);
	if (error)
		goto pending;
	for (attempt = 0; attempt < 100; attempt++) {
		status = ioread32(controller->base + 0x14);
		state->last_status = status;
		if (status == ~0U) {
			error = -ENODEV;
			goto pending;
		}
		if (!(status & N71_I2C_HDQ_BUSY_FLAGS))
			break;
		usleep_range(1000, 1100);
	}
	if (attempt == 100) {
		error = -EBUSY;
		goto pending;
	}
	error = n71_i2c_hdq_read_sample(request, words);
	if (error)
		goto pending;
	status = words[N71_I2C_SMSTA];
	if (status & N71_I2C_HDQ_BUSY_FLAGS) {
		error = -EBUSY;
		goto pending;
	}
	if ((status & (N71_I2C_HDQ_ACK_FLAGS & ~(1U << 27))) ||
	    (status & (1U << 19)) || !(status & (1U << 16)))
		iowrite32(0x70f, controller->base + 0x1c);
	error = n71_i2c_hdq_read_sample(request, words);
	if (error)
		goto pending;
	status = words[N71_I2C_SMSTA];
	if ((status & ~N71_I2C_HDQ_ACK_FLAGS) !=
	    (controller->saved[N71_I2C_SMSTA] & ~N71_I2C_HDQ_ACK_FLAGS)) {
		error = -EBUSY;
		goto pending;
	}
	if (status & N71_I2C_HDQ_ACK_FLAGS) {
		controller->status_acknowledged = true;
		iowrite32(status & N71_I2C_HDQ_ACK_FLAGS, controller->base + 0x14);
	}
	error = n71_i2c_hdq_read_sample(request, words);
	if (error)
		goto pending;
	if (words[N71_I2C_SMSTA] != n71_i2c_controller_expected(controller, N71_I2C_SMSTA)) {
		error = -EUCLEAN;
		goto pending;
	}
	error = n71_i2c_hdq_read_ready(request);
	if (error)
		goto pending;
	controller->transfer_pending = false;
	state->controller = NULL;
	state->cleanup_pending = false;
	state->cleanup_error = 0;
	return 0;
pending:
	state->cleanup_error = error;
	return error;
}

/* No SN2400 value is written. Register selection still transmits on the bus.
 * Output commits only after recovery; neither ACK nor data identifies a gauge.
 */
static inline int n71_i2c_read_hdq_control(const struct n71_i2c_hdq_read_request *request,
					   struct n71_i2c_hdq_read_state *state, u32 *output)
{
	struct n71_i2c_controller *controller;
	u32 words[N71_I2C_WORDS], status, value;
	unsigned int attempt;
	int error;

	if (!state || !output)
		return -EINVAL;
	error = n71_i2c_hdq_read_ready(request);
	if (error)
		return error;
	controller = request->controller;
	if (state->cleanup_pending || state->controller || controller->transfer_pending)
		return -EBUSY;
	error = n71_i2c_hdq_read_sample(request, words);
	if (error)
		return error;
	if (!n71_i2c_controller_idle(words) ||
	    words[N71_I2C_SMSTA] != n71_i2c_controller_expected(controller, N71_I2C_SMSTA))
		return -EBUSY;
	state->controller = controller;
	state->cleanup_pending = true;
	state->cleanup_error = 0;
	controller->transfer_pending = true;
	if (words[N71_I2C_SMSTA] & (1U << 27)) {
		controller->status_acknowledged = true;
		iowrite32(1U << 27, controller->base + 0x14);
		error = n71_i2c_hdq_read_sample(request, words);
		if (error)
			goto failed;
		if (words[N71_I2C_SMSTA] !=
		    n71_i2c_controller_expected(controller, N71_I2C_SMSTA)) {
			error = -EUCLEAN;
			goto failed;
		}
	}
	iowrite32(0x1ea, controller->base + 0x00);
	iowrite32(0x1d, controller->base + 0x00);
	iowrite32(0x1eb, controller->base + 0x00);
	iowrite32(0x601, controller->base + 0x00);
	for (attempt = 0; attempt < 100; attempt++) {
		status = ioread32(controller->base + 0x14);
		state->last_status = status;
		if (status == ~0U) {
			error = -ENODEV;
			goto failed;
		}
		if (status & (1U << 27))
			break;
		usleep_range(1000, 1100);
	}
	error = attempt == 100 ? -ETIMEDOUT :
		status & (1U << 6) ? -EIO : status & (1U << 23) ? -ETIME :
		status & (N71_I2C_HDQ_BUSY_FLAGS | (1U << 25)) ? -EIO :
		status & (1U << 22) ? -EBUSY : status & (1U << 21) ? -ENXIO : 0;
	if (error)
		goto failed;
	value = ioread32(controller->base + 0x04);
	if (value & ~0xffU) {
		error = value == ~0U ? -ENODEV : value & (1U << 8) ? -ENODATA : -EUCLEAN;
		goto failed;
	}
	error = n71_i2c_hdq_read_cleanup(request, state);
	if (error)
		return error;
	*output = value;
	return 0;
failed:
	n71_i2c_hdq_read_cleanup(request, state);
	return error;
}
#endif /* N71_I2C_HDQ_READ_H */
