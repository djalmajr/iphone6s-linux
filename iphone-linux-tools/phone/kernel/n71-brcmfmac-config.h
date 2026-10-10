/* SPDX-License-Identifier: GPL-2.0-only */
/* PCI semantics for the pinned driver; caller owns bind/unload and providers. */
#ifndef N71_BRCMFMAC_CONFIG_H
#define N71_BRCMFMAC_CONFIG_H
#include "n71-wlan-msi-config.h"

struct n71_brcmfmac_config {
	struct n71_msi_config baseline;
	u32 window, link;
	int error;
	bool active;
};

struct n71_brcmfmac_quiescent {
	unsigned int slots, mappings, child_mappings;
	bool driver_registered, driver_bound, software_enabled;
};

static inline int n71_brcmfmac_error(struct n71_brcmfmac_config *state, int error)
{
	if (error > 0)
		error = -EIO;
	if (error && !state->error)
		state->error = error;
	return error;
}

static inline int n71_brcmfmac_checked_write(const struct n71_scan_io *io,
					   const struct n71_scan_request *request)
{
	u32 actual;
	int error = n71_scan_read(io, request->root, request->where, request->size, &actual);

	if (error || actual == request->value)
		return error;
	error = io->write(io->context, request->root, request->where, request->size, request->value);
	if (!error)
		error = n71_scan_read(io, request->root, request->where, request->size, &actual);
	if (!error && actual != request->value)
		error = -EIO;
	return error > 0 ? -EIO : error;
}

static inline int n71_brcmfmac_capture(const struct n71_scan_io *io,
				     struct n71_brcmfmac_config *state)
{
	struct n71_brcmfmac_config result = {0};
	u32 power, window, link;
	int error;

	if (!io || !io->read || !io->write || !state)
		return -EINVAL;
	if (state->active)
		return -EBUSY;
	if (state->baseline.phase != N71_MSI_CONFIG_EMPTY || state->error)
		return -EALREADY;
	error = n71_msi_config_capture(io, &result.baseline);
	if (!error)
		error = n71_scan_read(io, false, 0x4c, 2, &power);
	if (!error && power != 0x4008)
		error = -EACCES;
	if (!error)
		error = n71_scan_read(io, false, 0x80, 4, &result.window);
	if (!error)
		error = n71_scan_read(io, false, 0xbc, 2, &result.link);
	if (!error)
		error = n71_scan_read(io, false, 0x80, 4, &window);
	if (!error)
		error = n71_scan_read(io, false, 0xbc, 2, &link);
	if (!error && (window != result.window || link != result.link))
		error = -EAGAIN;
	if (error)
		return error;
	result.active = true;
	*state = result;
	return 0;
}

static inline int n71_brcmfmac_write(const struct n71_scan_io *io,
				   struct n71_brcmfmac_config *state,
				   const struct n71_msi_config_request *request)
{
	struct n71_scan_request write;
	u32 control;
	bool allowed = false, grant;
	int error;

	if (!io || !io->read || !io->write || !state || !request)
		return -EINVAL;
	if (!state->active)
		return -EPERM;
	write = request->config;
	grant = n71_msi_config_grant(request->slots);
	if (write.where == 4 && write.size == 2) {
		u32 baseline = state->baseline.command[write.root ? 0 : 1];
		u32 mask = write.root ? 6U : 0x406U;

		allowed = ((write.value ^ baseline) & ~mask) == 0;
		if (allowed && !write.root && !(write.value & 0x400U)) {
			error = n71_scan_read(io, false, 0x5a, 2, &control);
			if (error)
				return n71_brcmfmac_error(state, error);
			allowed = !(control & 1);
		}
	} else if (write.root) {
		/* Root PME is already disabled; PCI D0 may replay this value. */
		allowed = write.where == 0x44 && write.size == 2 && write.value == 8;
	} else if (write.where == 0x4c && write.size == 2) {
		allowed = write.value == 0x4008;
	} else if (write.where == 0x80 && write.size == 4) {
		allowed = !(write.value & 0xfffU);
	} else if (write.where == 0xbc && (write.size == 2 || write.size == 4)) {
		/* brcmfmac replays a DWORD; its upper half is Link STATUS W1C. */
		write.size = 2;
		write.value &= 0xffffU;
		allowed = ((write.value ^ state->link) & ~3U) == 0;
	} else if (write.where == 0x98 && write.size == 4 && write.value == 1) {
		/* This doorbell is an event, including two identical writes. */
		error = io->write(io->context, false, 0x98, 4, 1);
		return n71_brcmfmac_error(state, error);
	} else if (write.where == 0x5a && write.size == 2) {
		allowed = write.value == 0x88;
		if (write.value == 0x89 && grant) {
			error = n71_msi_config_message(io, request->slots);
			if (error)
				return n71_brcmfmac_error(state, error);
			allowed = true;
		}
	} else if ((write.where == 0x5c && write.size == 4) ||
		   (write.where == 0x60 && write.size == 4) ||
		   (write.where == 0x64 && write.size == 2)) {
		error = n71_scan_read(io, false, 0x5a, 2, &control);
		if (error)
			return n71_brcmfmac_error(state, error);
		allowed = grant && write.value == (write.where == 0x5c ? 0xbffff000U :
			write.where == 0x60 ? 0 : n71_msi_config_vector(request->slots));
		if (control & 1) {
			if (allowed)
				return n71_brcmfmac_error(state, n71_msi_config_message(io, request->slots));
		} else if (!write.value) {
			allowed = true; /* Core deactivation after MSI is disabled. */
		}
	}
	if (!allowed)
		return n71_brcmfmac_error(state, -EPERM);
	error = n71_brcmfmac_checked_write(io, &write);
	return n71_brcmfmac_error(state, error);
}

static inline int n71_brcmfmac_restore(const struct n71_scan_io *io,
				     struct n71_brcmfmac_config *state,
				     const struct n71_brcmfmac_quiescent *core)
{
	struct n71_scan_request write = {false, 0x5a, 0x88, 2};
	u32 identity;
	unsigned int index;
	int error = 0;

	if (!io || !io->read || !io->write || !state || !core)
		return -EINVAL;
	if (!state->active)
		return 0;
	if (core->driver_registered || core->driver_bound || core->software_enabled ||
	    core->slots || core->mappings || core->child_mappings)
		return -EBUSY;
	for (index = 0; !error && index < 2; index++) {
		error = n71_scan_read(io, index == 0, 0, 4, &identity);
		if (!error && identity != (index == 0 ? 0x1004106bU : 0x43a314e4U))
			error = -ENODEV;
	}
	if (!error)
		error = n71_brcmfmac_checked_write(io, &write);
	for (index = 0; !error && index < 2; index++) {
		write = (struct n71_scan_request){index == 0, 4, state->baseline.command[index], 2};
		error = n71_brcmfmac_checked_write(io, &write);
	}
	for (index = 1; !error && index < 4; index++) {
		write = (struct n71_scan_request){false, n71_msi_config_offsets[index],
			state->baseline.saved[index], n71_msi_config_sizes[index]};
		error = n71_brcmfmac_checked_write(io, &write);
	}
	if (!error) {
		write = (struct n71_scan_request){false, 0x80, state->window, 4};
		error = n71_brcmfmac_checked_write(io, &write);
	}
	if (!error) {
		write = (struct n71_scan_request){false, 0xbc, state->link, 2};
		error = n71_brcmfmac_checked_write(io, &write);
	}
	if (!error)
		error = n71_msi_config_guard(io, &state->baseline);
	for (index = 0; !error && index < 2; index++) {
		error = n71_scan_read(io, index == 0, 4, 2, &identity);
		if (!error && identity != state->baseline.command[index])
			error = -EIO;
	}
	for (index = 0; !error && index < 4; index++) {
		error = n71_scan_read(io, false, n71_msi_config_offsets[index],
				      n71_msi_config_sizes[index], &identity);
		if (!error && identity != state->baseline.saved[index])
			error = -EIO;
	}
	if (!error)
		error = n71_scan_read(io, false, 0x80, 4, &identity);
	if (!error && identity != state->window)
		error = -EIO;
	if (!error)
		error = n71_scan_read(io, false, 0xbc, 2, &identity);
	if (!error && identity != state->link)
		error = -EIO;
	if (!error)
		error = n71_scan_read(io, false, 0x4c, 2, &identity);
	if (!error && identity != 0x4008)
		error = -EIO;
	if (error)
		return n71_brcmfmac_error(state, error);
	state->active = false;
	return 0;
}
#endif /* N71_BRCMFMAC_CONFIG_H */
