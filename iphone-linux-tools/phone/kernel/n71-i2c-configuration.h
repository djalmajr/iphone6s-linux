/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller retains every pointed-to object and serializes configuration/recovery. */
#ifndef N71_I2C_CONFIGURATION_H
#define N71_I2C_CONFIGURATION_H
#include "n71-i2c-hdq-read.h"
#include "n71-i2c-pin-owner.h"

struct n71_i2c_configuration_request {
	struct device *consumer;
	struct n71_i2c_controller *controller;
	struct n71_i2c_pin_owner *pins;
	struct n71_i2c_power_state *power;
	const struct n71_i2c_power_io *power_io;
	struct n71_i2c_hdq_read_state *read;
};

enum n71_i2c_configuration_stage {
	N71_I2C_STAGE_PINS = 1,
	N71_I2C_STAGE_POWER,
	N71_I2C_STAGE_CONTROLLER,
	N71_I2C_STAGE_HDQ,
	N71_I2C_STAGE_COMPLETE,
};

struct n71_i2c_configuration_result {
	int cleanup_error;
	int error;
	unsigned int stage;
	struct n71_i2c_hdq_trace trace;
	struct n71_i2c_reset_trace reset_trace;
	u32 value;
	bool value_valid;
};

static inline struct n71_i2c_controller_request
n71_i2c_configuration_ownership(const struct n71_i2c_configuration_request *request)
{
	return (struct n71_i2c_controller_request) {
		.consumer = request->consumer, .pin_context = request->pins,
		.power = request->power, .verify_pins = n71_i2c_pin_owner_verify,
	};
}

static inline int n71_i2c_configuration_release(const struct n71_i2c_configuration_request *request)
{
	struct n71_i2c_controller_request ownership = n71_i2c_configuration_ownership(request);
	struct n71_i2c_hdq_read_request read = {
		.controller = request->controller, .ownership = &ownership,
	};
	int error;

	error = n71_i2c_hdq_read_cleanup(&read, request->read);
	if (error || request->read->cleanup_pending || request->read->controller)
		return error ? error : -EUCLEAN;
	error = n71_i2c_controller_release(&ownership, request->controller);
	if (error || !n71_i2c_controller_clean(request->controller))
		return error ? error : -EUCLEAN;
	error = n71_i2c_pin_owner_release(request->pins);
	if (error || !n71_i2c_pin_owner_clean(request->pins))
		return error ? error : -EUCLEAN;
	return n71_i2c_power_release(request->power_io, request->power);
}

/* Only call with the qualified consumer and all state objects initially clean. */
static inline void n71_i2c_configuration_run(const struct n71_i2c_configuration_request *request,
					     bool read_control,
					     struct n71_i2c_configuration_result *result)
{
	struct n71_i2c_controller_request ownership = n71_i2c_configuration_ownership(request);
	struct n71_i2c_hdq_read_request read = {
		.controller = request->controller, .ownership = &ownership, .trace = &result->trace,
	};

	*result = (struct n71_i2c_configuration_result) {0};
	result->stage = N71_I2C_STAGE_PINS;
	result->error = n71_i2c_pin_owner_acquire(request->consumer, request->pins);
	if (!result->error) {
		result->stage = N71_I2C_STAGE_POWER;
		result->error = n71_i2c_power_acquire(request->power_io, request->power);
	}
	if (!result->error) {
		result->stage = N71_I2C_STAGE_CONTROLLER;
		/* A refusal before reset must not publish a previous acquisition. */
		request->controller->reset_trace = (struct n71_i2c_reset_trace) {0};
		result->error = n71_i2c_controller_acquire(&ownership, request->controller);
		result->reset_trace = request->controller->reset_trace;
	}
	if (!result->error && read_control) {
		result->stage = N71_I2C_STAGE_HDQ;
		result->error = n71_i2c_read_hdq_control(&read, request->read, &result->value);
		result->value_valid = !result->error;
	}
	if (!result->error)
		result->stage = N71_I2C_STAGE_COMPLETE;
	result->cleanup_error = n71_i2c_configuration_release(request);
}
#endif /* N71_I2C_CONFIGURATION_H */
