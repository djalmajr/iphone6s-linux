/* SPDX-License-Identifier: GPL-2.0-only */
/* Config-only PCI scan: no bus-master, BAR mapping or resource assignment. */
#ifndef N71_PCIE_SCAN_CONFIG_H
#define N71_PCIE_SCAN_CONFIG_H
#include "n71-pcie-ecam.h"

#define N71_SCAN_MAX_WRITES 128U

struct n71_scan_io {
	void *context;
	int (*read)(void *context, bool root, u32 where, unsigned int size, u32 *value);
	int (*write)(void *context, bool root, u32 where, unsigned int size, u32 value);
};

struct n71_scan_function {
	u32 identity, command, bars[6], rom, control;
};

struct n71_scan_config {
	struct n71_scan_function saved[2]; /* Root first, endpoint second. */
	unsigned int attempts, writes, refusals;
	int error;
	bool active;
};

struct n71_scan_request {
	bool root;
	u32 where, value;
	unsigned int size;
};

static inline int n71_scan_read(const struct n71_scan_io *io, bool root,
				 u32 where, unsigned int size, u32 *value)
{
	int error = io->read(io->context, root, where, size, value);
	return error > 0 ? -EIO : error;
}

static inline int n71_scan_capture(const struct n71_scan_io *io,
				    struct n71_scan_config *out)
{
	struct n71_scan_config result = {0};
	unsigned int function, bar;
	u32 header, class_revision, buses;
	int error;

	if (!io || !io->read || !io->write || !out)
		return -EINVAL;
	for (function = 0; function < 2; function++) {
		struct n71_scan_function *saved = &result.saved[function];
		bool root = function == 0;

		error = n71_scan_read(io, root, 0, 4, &saved->identity);
		if (error)
			return error;
		if (saved->identity != (root ? 0x1004106b : 0x43a314e4))
			return -ENODEV;
		error = n71_scan_read(io, root, 4, 2, &saved->command);
		if (error)
			return error;
		if (saved->command & 4)
			return -EACCES;
		error = n71_scan_read(io, root, 8, 4, &class_revision);
		if (!error)
			error = n71_scan_read(io, root, 0xc, 4, &header);
		if (error)
			return error;
		if ((class_revision >> 8) != (root ? 0x060400 : 0x028000) ||
		    ((header >> 16) & 0x7f) != (root ? 1U : 0U))
			return -ENODEV;
		for (bar = 0; bar < (root ? 2U : 6U); bar++) {
			error = n71_scan_read(io, root, 0x10 + bar * 4, 4, &saved->bars[bar]);
			if (error)
				return error;
		}
		error = n71_scan_read(io, root, root ? 0x38 : 0x30, 4, &saved->rom);
		if (error)
			return error;
		if (saved->rom & 1)
			return -EACCES;
		if (!root)
			continue;
		error = n71_scan_read(io, true, 0x18, 4, &buses);
		if (!error)
			error = n71_scan_read(io, true, 0x3e, 2, &saved->control);
		if (error)
			return error;
		if ((buses & 0xffffff) != 0x010100 || (saved->control & 0x40))
			return -EINVAL;
	}
	result.active = true;
	*out = result;
	return 0;
}

static inline int n71_scan_refuse(struct n71_scan_config *config, int error)
{
	config->refusals++;
	if (!config->error)
		config->error = error;
	return error;
}

/* A latched refusal stops later writes; final restore uses its own path. */
static inline int n71_scan_write(const struct n71_scan_io *io,
				  struct n71_scan_config *config,
				  const struct n71_scan_request *request)
{
	struct n71_pcie_ecam_location location;
	const struct n71_scan_function *saved;
	u32 observed, command, original = 0, mask;
	bool bar = false, allowed = false;
	int error;

	if (!io || !io->read || !io->write || !config || !request)
		return -EINVAL;
	if (!config->active)
		return n71_scan_refuse(config, -EPERM);
	if (config->error)
		return config->error;
	if (++config->attempts > N71_SCAN_MAX_WRITES)
		return n71_scan_refuse(config, -E2BIG);
	error = n71_pcie_ecam_locate(0x1000000, request->root ? 0 : 1,
				     request->root ? 8 : 0, request->where,
				     request->size, &location);
	if (error || request->value & ~location.mask)
		return n71_scan_refuse(config, error ? error : -EINVAL);
	saved = &config->saved[request->root ? 0 : 1];
	if (request->where == 4 && request->size == 2) {
		if (request->value & 4)
			return n71_scan_refuse(config, -EACCES);
		/* The core probes INTx masking; no other saved COMMAND bit may change. */
		command = request->value & ~0x400U;
		allowed = command == (saved->command & ~0x400U) ||
			command == (saved->command & ~0x403U);
	} else if (request->size == 4 && request->where >= 0x10 &&
		   request->where <= (request->root ? 0x14U : 0x24U)) {
		bar = true;
		original = saved->bars[(request->where - 0x10) / 4];
		allowed = request->value == 0xffffffff || request->value == original;
	} else if (request->size == 4 && request->where == (request->root ? 0x38U : 0x30U)) {
		bar = true;
		original = saved->rom;
		allowed = request->value == 0xfffff800 || request->value == original;
	} else if (request->root && request->where == 0x3e && request->size == 2) {
		allowed = request->value == saved->control ||
			request->value == (saved->control & ~0x20U);
	}
	error = n71_scan_read(io, request->root, request->where, request->size, &observed);
	if (error)
		return n71_scan_refuse(config, error);
	/* No-op emulation avoids writing W1C bits and unsupported capabilities. */
	if (observed == request->value)
		return 0;
	mask = 0xf900; /* Secondary STATUS error bits, all write-one-to-clear. */
	if (request->root && request->where == 0x1e && request->size == 2 &&
	    request->value == 0xffff && !(observed & mask))
		return 0;
	if (!allowed)
		return n71_scan_refuse(config, -EPERM);
	if (bar) {
		error = n71_scan_read(io, request->root, 4, 2, &command);
		if (error || (command & 7))
			return n71_scan_refuse(config, error ? error : -EACCES);
	}
	error = io->write(io->context, request->root, request->where,
			  request->size, request->value);
	if (error)
		return n71_scan_refuse(config, error < 0 ? error : -EIO);
	config->writes++;
	return 0;
}

static inline int n71_scan_restore_value(const struct n71_scan_io *io, bool root,
					 u32 where, unsigned int size, u32 value)
{
	u32 actual;
	int error = io->write(io->context, root, where, size, value);
	if (error)
		return error < 0 ? error : -EIO;
	error = n71_scan_read(io, root, where, size, &actual);
	return error ? error : actual == value ? 0 : -EIO;
}

/* Caller removes all PCI devices first. Restore runs even after a scan error. */
static inline int n71_scan_restore(const struct n71_scan_io *io,
				    struct n71_scan_config *config)
{
	unsigned int function, bar;
	int error, first = 0, function_error;
	u32 identity;

	if (!io || !io->read || !io->write || !config || !config->active)
		return -EINVAL;
	config->active = false;
	for (function = 0; function < 2; function++) {
		const struct n71_scan_function *saved = &config->saved[function];
		bool root = function == 0;

		error = n71_scan_read(io, root, 0, 4, &identity);
		if (!error && identity != saved->identity)
			error = -ENODEV;
		if (!error)
			error = n71_scan_restore_value(io, root, 4, 2, saved->command & ~3U);
		if (error) {
			if (!first)
				first = error;
			continue; /* Never rewrite BARs without confirmed decode-off. */
		}
		function_error = 0;
		for (bar = 0; bar < (root ? 2U : 6U); bar++) {
			error = n71_scan_restore_value(io, root, 0x10 + bar * 4, 4, saved->bars[bar]);
			if (error && !function_error)
				function_error = error;
		}
		error = n71_scan_restore_value(io, root, root ? 0x38 : 0x30, 4, saved->rom);
		if (error && !function_error)
			function_error = error;
		if (root) {
			error = n71_scan_restore_value(io, true, 0x3e, 2, saved->control);
			if (error && !function_error)
				function_error = error;
		}
		/* Leave decode off if any BAR/ROM/control restoration failed. */
		if (!function_error)
			function_error = n71_scan_restore_value(io, root, 4, 2, saved->command);
		if (function_error && !first)
			first = function_error;
	}
	return first;
}
#endif /* N71_PCIE_SCAN_CONFIG_H */
