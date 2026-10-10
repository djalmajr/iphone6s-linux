/* SPDX-License-Identifier: GPL-2.0-only */
/* One MSI grant; caller retains link/providers and stops sources before free. */
#ifndef N71_WLAN_MSI_CONFIG_H
#define N71_WLAN_MSI_CONFIG_H
#include "n71-pcie-scan-config.h"

#define N71_MSI_CONFIG_MAX_ATTEMPTS 64U
#define N71_MSI_CONFIG_MAX_CLEANUP 32U

enum n71_msi_config_phase {
	N71_MSI_CONFIG_EMPTY, N71_MSI_CONFIG_ACTIVE, N71_MSI_CONFIG_STOPPED
};

struct n71_msi_config {
	u32 command[2], saved[4];
	unsigned int attempts, cleanup_attempts, write_attempts, writes;
	int error;
	enum n71_msi_config_phase phase;
};

struct n71_msi_config_request {
	struct n71_scan_request config;
	unsigned int slots;
};

struct n71_msi_config_core {
	unsigned int slots, mappings;
	bool enabled;
};

static const u32 n71_msi_config_offsets[] = {0x5a, 0x5c, 0x60, 0x64};
static const unsigned int n71_msi_config_sizes[] = {2, 4, 4, 2};

static inline int n71_msi_config_error(struct n71_msi_config *state, int error)
{
	if (error > 0)
		error = -EIO;
	if (error && !state->error)
		state->error = error;
	return error;
}

static inline bool n71_msi_config_grant(unsigned int slots)
{
	return slots && !(slots & ~0xffU) && !(slots & (slots - 1));
}

static inline u32 n71_msi_config_vector(unsigned int slots)
{
	u32 vector = 8;

	while (slots > 1) {
		slots >>= 1;
		vector++;
	}
	return vector;
}

static inline int n71_msi_config_guard(const struct n71_scan_io *io,
				       const struct n71_msi_config *state)
{
	u32 identity, command, header;
	unsigned int index;
	int error;

	for (index = 0; index < 2; index++) {
		error = n71_scan_read(io, index == 0, 0, 4, &identity);
		if (!error)
			error = n71_scan_read(io, index == 0, 4, 2, &command);
		if (error)
			return error;
		if (identity != (index == 0 ? 0x1004106b : 0x43a314e4))
			return -ENODEV;
		if (command & 7)
			return -EACCES;
		if (state->phase != N71_MSI_CONFIG_EMPTY &&
		    ((command ^ state->command[index]) & (index == 0 ? ~0U : ~0x400U)))
			return -EAGAIN;
	}
	error = n71_scan_read(io, false, 0x58, 4, &header);
	if (error)
		return error;
	return (header & ~0x10000U) == 0x00886805U ? 0 : -ENODEV;
}

static inline int n71_msi_config_capture(const struct n71_scan_io *io,
					 struct n71_msi_config *out)
{
	struct n71_msi_config result = {0};
	unsigned int index;
	u32 actual;
	int error;

	if (!io || !io->read || !io->write || !out)
		return -EINVAL;
	if (out->phase != N71_MSI_CONFIG_EMPTY)
		return -EBUSY;
	if (out->error || out->attempts || out->cleanup_attempts)
		return -EALREADY;
	error = n71_msi_config_guard(io, &result);
	for (index = 0; !error && index < 2; index++)
		error = n71_scan_read(io, index == 0, 4, 2, &result.command[index]);
	for (index = 0; !error && index < 4; index++)
		error = n71_scan_read(io, false, n71_msi_config_offsets[index],
				      n71_msi_config_sizes[index], &result.saved[index]);
	if (error)
		return error;
	if (result.saved[0] != 0x88)
		return -EACCES;
	result.phase = N71_MSI_CONFIG_ACTIVE;
	error = n71_msi_config_guard(io, &result);
	for (index = 0; !error && index < 4; index++) {
		error = n71_scan_read(io, false, n71_msi_config_offsets[index],
				      n71_msi_config_sizes[index], &actual);
		if (!error && actual != result.saved[index])
			error = -EAGAIN;
	}
	for (index = 0; !error && index < 2; index++) {
		error = n71_scan_read(io, index == 0, 4, 2, &actual);
		if (!error && actual != result.command[index])
			error = -EAGAIN;
	}
	if (error)
		return error;
	*out = result;
	return 0;
}

static inline int n71_msi_config_message(const struct n71_scan_io *io, unsigned int slots)
{
	u32 actual;
	const u32 expected[] = {0xbffff000U, 0, n71_msi_config_vector(slots)};
	unsigned int index;
	int error;

	if (!n71_msi_config_grant(slots))
		return -EINVAL;
	for (index = 0; index < 3; index++) {
		error = n71_scan_read(io, false, n71_msi_config_offsets[index + 1],
				      n71_msi_config_sizes[index + 1], &actual);
		if (error)
			return error;
		if (actual != expected[index])
			return -EIO;
	}
	error = n71_scan_read(io, false, 4, 2, &actual);
	return error ? error : (actual & 0x400) ? 0 : -EACCES;
}

static inline int n71_msi_config_checked_write(const struct n71_scan_io *io,
					       struct n71_msi_config *state,
					       const struct n71_scan_request *request)
{
	u32 actual;
	int error = n71_scan_read(io, false, request->where, request->size, &actual);

	if (error || actual == request->value)
		return error;
	state->write_attempts++;
	error = io->write(io->context, false, request->where, request->size, request->value);
	if (!error)
		error = n71_scan_read(io, false, request->where, request->size, &actual);
	if (!error && actual != request->value)
		error = -EIO;
	if (!error)
		state->writes++;
	return error > 0 ? -EIO : error;
}

static inline int n71_msi_config_write(const struct n71_scan_io *io,
				       struct n71_msi_config *state,
				       const struct n71_msi_config_request *request)
{
	const struct n71_scan_request *config;
	u32 control;
	bool grant, allowed = false;
	int error;

	if (!io || !io->read || !io->write || !state || !request)
		return -EINVAL;
	if (state->phase == N71_MSI_CONFIG_EMPTY)
		return -EPERM;
	if (state->error && state->phase != N71_MSI_CONFIG_STOPPED)
		return state->error;
	if (++state->attempts > N71_MSI_CONFIG_MAX_ATTEMPTS)
		return n71_msi_config_error(state, -E2BIG);
	config = &request->config;
	grant = n71_msi_config_grant(request->slots);
	if (config->root)
		return n71_msi_config_error(state, -EPERM);
	error = n71_msi_config_guard(io, state);
	if (!error)
		error = n71_scan_read(io, false, 0x5a, 2, &control);
	if (error)
		return n71_msi_config_error(state, error);
	if (config->where == 0x5a && config->size == 2) {
		allowed = config->value == 0x88;
		if (state->phase == N71_MSI_CONFIG_ACTIVE && config->value == 0x89 && grant) {
			error = n71_msi_config_message(io, request->slots);
			if (error)
				return n71_msi_config_error(state, error);
			allowed = true;
		}
	} else if (config->where == 4 && config->size == 2) {
		allowed = ((config->value ^ state->command[1]) & ~0x400U) == 0 &&
			  ((config->value & 0x400) ? grant : !(control & 1));
	} else if (state->phase == N71_MSI_CONFIG_ACTIVE && grant) {
		allowed = (config->where == 0x5c && config->size == 4 && config->value == 0xbffff000U) ||
			  (config->where == 0x60 && config->size == 4 && config->value == 0) ||
			  (config->where == 0x64 && config->size == 2 &&
			   config->value == n71_msi_config_vector(request->slots));
		/* IRQ activation/affinity may replay the same live message. Never
		 * change it while enabled; validate the whole tuple and do no write.
		 */
		if (allowed && (control & 1))
			return n71_msi_config_error(state, n71_msi_config_message(io, request->slots));
	} else if (state->phase == N71_MSI_CONFIG_STOPPED && !(control & 1)) {
		/* The IRQ core deactivates a vector by writing an all-zero message. */
		allowed = !config->value &&
			((config->where == 0x5c && config->size == 4) ||
			 (config->where == 0x60 && config->size == 4) ||
			 (config->where == 0x64 && config->size == 2));
	}
	if (!allowed)
		return n71_msi_config_error(state, -EPERM);
	error = n71_msi_config_checked_write(io, state, config);
	return n71_msi_config_error(state, error);
}

static inline int n71_msi_config_stop(const struct n71_scan_io *io,
				      struct n71_msi_config *state)
{
	const struct n71_scan_request disable = {false, 0x5a, 0x88, 2};
	int error;

	if (!io || !io->read || !io->write || !state)
		return -EINVAL;
	if (state->phase == N71_MSI_CONFIG_EMPTY)
		return 0;
	if (++state->cleanup_attempts > N71_MSI_CONFIG_MAX_CLEANUP)
		return n71_msi_config_error(state, -E2BIG);
	error = n71_msi_config_guard(io, state);
	if (!error)
		error = n71_msi_config_checked_write(io, state, &disable);
	if (error)
		return n71_msi_config_error(state, error);
	state->phase = N71_MSI_CONFIG_STOPPED;
	return 0;
}

static inline int n71_msi_config_restore(const struct n71_scan_io *io,
					 struct n71_msi_config *state,
					 const struct n71_msi_config_core *core)
{
	struct n71_scan_request request = {false, 0, 0, 0};
	unsigned int index;
	u32 actual;
	int error;

	if (!io || !io->read || !io->write || !state || !core)
		return -EINVAL;
	if (state->phase == N71_MSI_CONFIG_EMPTY)
		return 0;
	if (state->phase != N71_MSI_CONFIG_STOPPED || core->enabled || core->slots || core->mappings)
		return -EBUSY;
	if (++state->cleanup_attempts > N71_MSI_CONFIG_MAX_CLEANUP)
		return n71_msi_config_error(state, -E2BIG);
	error = n71_msi_config_guard(io, state);
	if (!error)
		error = n71_scan_read(io, false, 0x5a, 2, &actual);
	if (!error && actual != 0x88)
		error = -EAGAIN;
	for (index = 1; !error && index < 5; index++) {
		request.where = index == 4 ? 4 : n71_msi_config_offsets[index];
		request.size = index == 4 ? 2 : n71_msi_config_sizes[index];
		request.value = index == 4 ? state->command[1] : state->saved[index];
		error = n71_msi_config_checked_write(io, state, &request);
	}
	if (!error)
		error = n71_msi_config_guard(io, state);
	for (index = 0; !error && index < 4; index++) {
		error = n71_scan_read(io, false, n71_msi_config_offsets[index],
				      n71_msi_config_sizes[index], &actual);
		if (!error && actual != state->saved[index])
			error = -EIO;
	}
	if (!error)
		error = n71_scan_read(io, false, 4, 2, &actual);
	if (!error && actual != state->command[1])
		error = -EIO;
	if (error)
		return n71_msi_config_error(state, error);
	state->phase = N71_MSI_CONFIG_EMPTY;
	return 0;
}
#endif /* N71_WLAN_MSI_CONFIG_H */
