/* SPDX-License-Identifier: GPL-2.0-only */
/* Endpoint PME ownership; never acknowledge PME_STATUS or change D-state. */
#ifndef N71_PCIE_PME_CONTROL_H
#define N71_PCIE_PME_CONTROL_H
#include "n71-pcie-control-reference.h"

struct n71_pme_state {
	u32 original;
	bool pending, prepared;
};

static inline int n71_pme_observe(const struct n71_scan_io *io, u32 *out)
{
	struct n71_control_reference reference;
	u32 pmcsr = 0, actual, command, version;
	unsigned int index, headers = 0, words = 0;
	int error;

	if (!out)
		return -EINVAL;
	error = n71_control_capture(io, false, &reference);
	if (error)
		return error;
	for (index = 0; index < reference.capabilities; index++) {
		if (reference.offsets[index] >= 0x100 ||
		    (reference.headers[index] & 0xff) != 1)
			continue;
		version = (reference.headers[index] >> 16) & 7;
		if (reference.offsets[index] != 0x48 || !version || version > 3)
			return -EPERM;
		headers++;
	}
	for (index = 0; index < reference.count; index++) {
		const struct n71_control_word *word = &reference.words[index];
		if (word->capability != 1)
			continue;
		if (word->where != 0x4c || word->size != 2)
			return -EPERM;
		pmcsr = word->value;
		words++;
	}
	if (headers != 1 || words != 1)
		return -EPERM;
	error = n71_scan_read(io, false, 4, 2, &command);
	if (error || command & 4)
		return error ? error : -EACCES;
	error = n71_scan_read(io, false, 0x4c, 2, &actual);
	if (error || actual != pmcsr)
		return error ? error : -EAGAIN;
	*out = actual;
	return 0;
}

/* Caller owns the link and retains this state until restoration succeeds. */
static inline int n71_pme_disable(const struct n71_scan_io *io,
				  struct n71_pme_state *state)
{
	u32 observed, actual;
	int error;

	if (!io || !io->read || !io->write || !state)
		return -EINVAL;
	if (state->pending || state->prepared)
		return -EBUSY;
	error = n71_pme_observe(io, &observed);
	if (error || observed != 0x4108)
		return error ? error : -EPERM;
	state->original = observed;
	state->pending = true; /* A failed write may still have changed PME_ENABLE. */
	error = io->write(io->context, false, 0x4c, 2, observed & ~0x8100U);
	if (error)
		return error < 0 ? error : -EIO;
	error = n71_scan_read(io, false, 0x4c, 2, &actual);
	if (error || actual != 0x4008)
		return error ? error : -EAGAIN;
	state->prepared = true;
	return 0;
}

/* Restore only the owned enable bit; write zero to the W1C event bit. */
static inline int n71_pme_restore(const struct n71_scan_io *io,
				  struct n71_pme_state *state)
{
	u32 observed, value, actual;
	int error;

	if (!io || !io->read || !io->write || !state)
		return -EINVAL;
	if (!state->pending)
		return 0;
	if (state->original != 0x4108)
		return -EINVAL;
	error = n71_pme_observe(io, &observed);
	if (error || (observed & 3))
		return error ? error : -EPERM;
	value = (observed & ~0x8100U) | (state->original & 0x100U);
	if ((observed & 0x100U) != (state->original & 0x100U)) {
		error = io->write(io->context, false, 0x4c, 2, value);
		if (error)
			return error < 0 ? error : -EIO;
	}
	error = n71_scan_read(io, false, 0x4c, 2, &actual);
	if (error || (actual & ~0x8000U) != value ||
	    ((observed & 0x8000U) && !(actual & 0x8000U)))
		return error ? error : -EIO;
	state->pending = false;
	state->prepared = false;
	return 0;
}

/* Only an owned, verified disable can satisfy the core's PME_STATUS request. */
static inline int n71_pme_scan_write(const struct n71_scan_io *io,
				     struct n71_scan_config *config,
				     const struct n71_pme_state *state,
				     const struct n71_scan_request *request)
{
	struct n71_scan_request noop;
	u32 observed;
	int error;

	if (!io || !io->read || !io->write || !config || !state || !request)
		return -EINVAL;
	if (request->root || (request->where != 0x4c && request->where != 0x4d))
		return n71_scan_write(io, config, request);
	if (config->error)
		return config->error;
	if (!config->active || request->where != 0x4c || request->size != 2)
		return n71_scan_refuse(config, -EPERM);
	if (!(request->value & 0x8000))
		return n71_scan_write(io, config, request);
	if (!state->pending || !state->prepared ||
	    state->original != 0x4108 || request->value != 0xc008)
		return n71_scan_refuse(config, -EPERM);
	error = n71_pme_observe(io, &observed);
	if (error || observed != 0x4008)
		return n71_scan_refuse(config, error ? error : -EPERM);
	noop = *request;
	noop.value = 0x4008;
	/* The existing policy performs one more fresh read; no W1C write occurs. */
	return n71_scan_write(io, config, &noop);
}
#endif
