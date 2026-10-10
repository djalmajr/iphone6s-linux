/* Faults exercise the production MSI owner, not a duplicated implementation. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-wlan-msi-config.h"

struct backend {
	u32 config[2][64], baseline[2][64];
	unsigned int reads, writes, fail_read, fail_write, drop_write, drift_read;
	int failure;
};

static unsigned int cases;

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	struct backend *backend = context;
	u32 raw;

	assert(where < 256 && (size == 2 || size == 4));
	if (++backend->reads == backend->drift_read)
		backend->config[1][1] ^= 0x400;
	if (backend->reads == backend->fail_read) {
		*value = 0xdeadbeef;
		return backend->failure;
	}
	raw = backend->config[root ? 0 : 1][where / 4];
	*value = size == 4 ? raw : (raw >> ((where & 3) * 8)) & 0xffff;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct backend *backend = context;
	u32 *target = &backend->config[1][where / 4];
	unsigned int shift = (where & 3) * 8;

	assert(!root && where < 256);
	assert((where == 4 || where == 0x5a || where == 0x64) ? size == 2 : size == 4);
	assert(!(backend->config[0][1] & 7) && !(backend->config[1][1] & 7));
	if (++backend->writes == backend->fail_write)
		return backend->failure;
	if (backend->writes != backend->drop_write) {
		if (size == 4)
			*target = value;
		else
			*target = (*target & ~(0xffffU << shift)) | ((value & 0xffff) << shift);
	}
	return 0;
}

static void reset(struct backend *backend, struct n71_msi_config *state)
{
	memset(backend, 0, sizeof(*backend));
	memset(state, 0, sizeof(*state));
	backend->failure = -EIO;
	backend->config[0][0] = 0x1004106b;
	backend->config[1][0] = 0x43a314e4;
	backend->config[0][1] = 0xa5a50100;
	backend->config[1][1] = 0x5a5a0100;
	backend->config[1][0x58 / 4] = 0x00886805;
	backend->config[1][0x5c / 4] = 0x12345000;
	backend->config[1][0x60 / 4] = 0x42;
	backend->config[1][0x64 / 4] = 0xbeef0013;
	memcpy(backend->baseline, backend->config, sizeof(backend->config));
}

static int request(const struct n71_scan_io *io, struct n71_msi_config *state,
		   struct n71_msi_config_request write)
{
	return n71_msi_config_write(io, state, &write);
}

static void enable(const struct n71_scan_io *io, struct n71_msi_config *state, unsigned int slots)
{
	assert(request(io, state, (struct n71_msi_config_request){{false, 0x5a, 0x88, 2}, 0}) == 0);
	assert(request(io, state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, slots}) == 0);
	assert(request(io, state, (struct n71_msi_config_request){{false, 0x60, 0, 4}, slots}) == 0);
	assert(request(io, state, (struct n71_msi_config_request){{false, 0x64, n71_msi_config_vector(slots), 2}, slots}) == 0);
	assert(request(io, state, (struct n71_msi_config_request){{false, 4, 0x500, 2}, slots}) == 0);
	assert(request(io, state, (struct n71_msi_config_request){{false, 0x5a, 0x89, 2}, slots}) == 0);
}

static void release(const struct n71_scan_io *io, struct n71_msi_config *state,
		    struct backend *backend)
{
	const struct n71_msi_config_core gone = {0};
	int error = state->error;

	assert(n71_msi_config_stop(io, state) == 0);
	assert(state->phase == N71_MSI_CONFIG_STOPPED);
	assert(n71_msi_config_restore(io, state, &gone) == 0);
	assert(state->phase == N71_MSI_CONFIG_EMPTY && state->error == error);
	assert(!memcmp(backend->baseline, backend->config, sizeof(backend->config)));
}

int main(void)
{
	struct backend backend;
	struct n71_msi_config state, untouched;
	struct n71_scan_io io = {&backend, read_config, write_config};
	struct n71_msi_config_core core = {0};
	unsigned int index, capture_reads, restore_reads, writes, reads;
	const struct n71_msi_config_request refused[] = {
		{{true, 0x5a, 0x88, 2}, 1}, {{false, 4, 0x500, 4}, 1},
		{{false, 4, 0x104, 2}, 1}, {{false, 4, 0x102, 2}, 1},
		{{false, 0x5a, 0x99, 2}, 1}, {{false, 0x5a, 0x88, 4}, 1},
		{{false, 0x5c, 0xbffff001, 4}, 1}, {{false, 0x5c, 0xbffff000, 2}, 1},
		{{false, 0x60, 1, 4}, 1}, {{false, 0x64, 9, 2}, 1},
		{{false, 0x64, 8, 4}, 1}, {{false, 0x5c, 0xbffff000, 4}, 0},
		{{false, 0x5c, 0xbffff000, 4}, 3}, {{false, 0x5c, 0xbffff000, 4}, 256},
		{{false, 0x68, 0, 4}, 1}, {{false, 4, 0x500, 2}, 0},
		{{false, 0x5a, 0x89, 2}, 1}, {{false, 0x64, 8, 1}, 1}
	};

	reset(&backend, &state);
	assert(n71_msi_config_capture(&io, &state) == 0);
	capture_reads = backend.reads;
	for (index = 1; index <= capture_reads; index++) {
		reset(&backend, &state);
		untouched = state;
		backend.fail_read = index;
		backend.failure = index % 2 ? -EIO : 1;
		assert(n71_msi_config_capture(&io, &state) == -EIO);
		assert(!memcmp(&untouched, &state, sizeof(state)) && !backend.writes);
		cases++;
	}
	reset(&backend, &state);
	backend.drift_read = capture_reads;
	assert(n71_msi_config_capture(&io, &state) == -EAGAIN);
	assert(state.phase == N71_MSI_CONFIG_EMPTY);
	cases++;
	for (index = 0; index < 8; index++) {
		reset(&backend, &state);
		assert(n71_msi_config_capture(&io, &state) == 0);
		assert(n71_msi_config_capture(&io, &state) == -EBUSY);
		enable(&io, &state, 1U << index);
		assert(state.phase == N71_MSI_CONFIG_ACTIVE && !state.error);
		assert((backend.config[1][0x58 / 4] >> 16) == 0x89);
		assert((backend.config[1][0x64 / 4] & 0xffff) == 8 + index);
		writes = backend.writes;
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, 1U << index}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x60, 0, 4}, 1U << index}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x64, 8 + index, 2}, 1U << index}) == 0);
		assert(backend.writes == writes);
		assert(n71_msi_config_restore(&io, &state, &core) == -EBUSY);
		assert(n71_msi_config_stop(&io, &state) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5a, 0x89, 2}, 1U << index}) == -EPERM);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5a, 0x88, 2}, 1U << index}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0, 4}, 1U << index}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x60, 0, 4}, 1U << index}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x64, 0, 2}, 1U << index}) == 0);
		core.slots = 1U << index;
		assert(n71_msi_config_restore(&io, &state, &core) == -EBUSY);
		core.slots = 0; core.mappings = 1;
		assert(n71_msi_config_restore(&io, &state, &core) == -EBUSY);
		core.mappings = 0; core.enabled = true;
		assert(n71_msi_config_restore(&io, &state, &core) == -EBUSY);
		core.enabled = false;
		release(&io, &state, &backend);
		writes = backend.writes;
		assert(n71_msi_config_restore(&io, &state, &core) == 0 && backend.writes == writes);
		cases++;
	}
	for (index = 0; index < 3; index++) {
		reset(&backend, &state);
		assert(n71_msi_config_capture(&io, &state) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, 1}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x60, 0, 4}, 1}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x64, 8, 2}, 1}) == 0);
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 4, 0x500, 2}, 1}) == 0);
		backend.config[1][(0x5c + index * 4) / 4] ^= 1;
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5a, 0x89, 2}, 1}) == -EIO);
		assert((backend.config[1][0x58 / 4] >> 16) == 0x88);
		release(&io, &state, &backend);
		cases++;
	}
	for (index = 0; index < 9; index++) {
		reset(&backend, &state);
		if (index < 2) backend.config[index][0] ^= 1;
		else if (index < 6) backend.config[index % 2][1] |= index < 4 ? 4 : 2;
		else backend.config[1][0x58 / 4] ^= index == 6 ? 0x10000 : index == 7 ? 0x1000000 : 0x100;
		assert(n71_msi_config_capture(&io, &state) < 0);
		assert(state.phase == N71_MSI_CONFIG_EMPTY && !backend.writes);
		cases++;
	}
	reset(&backend, &state);
	assert(n71_msi_config_capture(&io, &state) == 0);
	enable(&io, &state, 1);
	assert(n71_msi_config_stop(&io, &state) == 0);
	reads = backend.reads;
	assert(n71_msi_config_restore(&io, &state, &core) == 0);
	restore_reads = backend.reads - reads;
	for (index = 1; index <= restore_reads; index++) {
		reset(&backend, &state);
		assert(n71_msi_config_capture(&io, &state) == 0);
		enable(&io, &state, 1);
		assert(n71_msi_config_stop(&io, &state) == 0);
		backend.fail_read = backend.reads + index;
		assert(n71_msi_config_restore(&io, &state, &core) == -EIO);
		assert(state.phase == N71_MSI_CONFIG_STOPPED && state.error == -EIO);
		backend.fail_read = 0;
		release(&io, &state, &backend);
		cases++;
	}
	for (index = 0; index < sizeof(refused) / sizeof(refused[0]); index++) {
		reset(&backend, &state);
		assert(n71_msi_config_capture(&io, &state) == 0);
		assert(n71_msi_config_write(&io, &state, &refused[index]) < 0);
		assert(state.error && state.phase == N71_MSI_CONFIG_ACTIVE && !backend.writes);
		reads = backend.reads;
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, 1}) == state.error);
		assert(backend.reads == reads);
		release(&io, &state, &backend);
		cases++;
	}
	for (index = 0; index < 3; index++) {
		reset(&backend, &state);
		assert(n71_msi_config_capture(&io, &state) == 0);
		if (index == 0) backend.fail_write = 1;
		if (index == 1) backend.drop_write = 1;
		if (index == 2) backend.fail_read = backend.reads + 8;
		assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, 1}) == -EIO);
		assert(state.phase == N71_MSI_CONFIG_ACTIVE && state.error == -EIO);
		backend.fail_write = backend.drop_write = backend.fail_read = 0;
		release(&io, &state, &backend);
		cases++;
	}
	reset(&backend, &state);
	assert(n71_msi_config_capture(&io, &state) == 0);
	enable(&io, &state, 1);
	backend.drop_write = backend.writes + 1;
	assert(n71_msi_config_stop(&io, &state) == -EIO);
	assert(state.phase == N71_MSI_CONFIG_ACTIVE && state.error == -EIO);
	assert(n71_msi_config_restore(&io, &state, &core) == -EBUSY);
	backend.drop_write = 0;
	assert(n71_msi_config_stop(&io, &state) == 0);
	backend.fail_write = backend.writes + 1;
	backend.failure = -ENOMEM;
	assert(n71_msi_config_restore(&io, &state, &core) == -ENOMEM);
	assert(state.phase == N71_MSI_CONFIG_STOPPED && state.error == -EIO);
	backend.fail_write = 0;
	release(&io, &state, &backend);
	cases++;
	reset(&backend, &state);
	assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, 1}) == -EPERM && !backend.reads);
	assert(n71_msi_config_capture(&io, &state) == 0);
	state.attempts = N71_MSI_CONFIG_MAX_ATTEMPTS;
	assert(request(&io, &state, (struct n71_msi_config_request){{false, 0x5c, 0xbffff000, 4}, 1}) == -E2BIG);
	release(&io, &state, &backend);
	cases++;
	reset(&backend, &state);
	assert(n71_msi_config_capture(&io, &state) == 0);
	enable(&io, &state, 1);
	state.cleanup_attempts = N71_MSI_CONFIG_MAX_CLEANUP;
	writes = backend.writes;
	assert(n71_msi_config_stop(&io, &state) == -E2BIG);
	assert(state.phase == N71_MSI_CONFIG_ACTIVE && backend.writes == writes);
	cases++;
	printf("N71_WLAN_MSI_CONFIG_OK cases=%u\n", cases);
	return 0;
}
