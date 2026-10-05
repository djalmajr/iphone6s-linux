/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-pme-control.h"

struct mock {
	u32 config[64];
	unsigned int reads, writes, fail_read, fail_write, event_read, master_read, clear_event_read;
	bool partial, positive, event_write, bad_readback;
};

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *out)
{
	struct mock *mock = context;
	u32 mask = size == 4 ? 0xffffffff : (1U << (size * 8)) - 1;
	assert(!root && where < 256 && where % size == 0);
	mock->reads++;
	if (mock->reads == mock->event_read)
		mock->config[0x4c / 4] |= 0x8000;
	if (mock->reads == mock->master_read)
		mock->config[1] |= 4;
	if (mock->reads == mock->clear_event_read)
		mock->config[0x4c / 4] &= ~0x8000U;
	if (mock->reads == mock->fail_read)
		return mock->positive ? 1 : -EIO;
	*out = (mock->config[where / 4] >> (8 * (where & 3))) & mask;
	if (mock->bad_readback && mock->writes && where == 0x4c)
		*out ^= 0x100;
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	struct mock *mock = context;
	u32 *target = &mock->config[0x4c / 4];
	bool failed = ++mock->writes == mock->fail_write;
	assert(!root && where == 0x4c && size == 2 && value <= 0xffff);
	assert(!(value & 0x8000)); /* Mutation captured: a W1C write destroys an unowned event. */
	assert((value & ~0x8100U) == (*target & 0xffff & ~0x8100U));
	if (!failed || mock->partial)
		*target = (*target & ~0x100U) | (value & 0x100U);
	if (mock->event_write)
		*target |= 0x8000;
	return failed ? mock->positive ? 1 : -EIO : 0;
}

static void initialize(struct mock *mock)
{
	memset(mock, 0, sizeof(*mock));
	mock->config[0] = 0x43a314e4;
	mock->config[1] = 0x00100000;
	mock->config[0x34 / 4] = 0x48;
	mock->config[0x48 / 4] = 0x00030001;
	mock->config[0x4c / 4] = 0xabc04108;
}

static void rejected(struct mock *mock)
{
	struct n71_scan_io io = {mock, read_config, write_config};
	struct n71_pme_state state, original;
	u32 before[64];
	memset(&state, 0, sizeof(state)); memcpy(&original, &state, sizeof(state));
	memcpy(before, mock->config, sizeof(before));
	assert(n71_pme_disable(&io, &state) < 0);
	assert(!mock->writes && memcmp(&state, &original, sizeof(state)) == 0);
	if (!mock->event_read && !mock->master_read)
		assert(memcmp(mock->config, before, sizeof(before)) == 0);
}

static void lifecycle(void)
{
	struct mock mock;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_pme_state state = {0};
	unsigned int reads, writes;

	/* Mutation captured: skipping disable, ownership or restore changes the observable CSR. */
	initialize(&mock);
	assert(n71_pme_disable(&io, &state) == 0);
	assert(state.original == 0x4108 && state.pending && state.prepared);
	assert(mock.config[0x4c / 4] == 0xabc04008 && mock.writes == 1);
	reads = mock.reads;
	assert(n71_pme_disable(&io, &state) == -EBUSY);
	assert(mock.reads == reads && mock.writes == 1);
	assert(n71_pme_restore(&io, &state) == 0);
	assert(!state.pending && !state.prepared && mock.config[0x4c / 4] == 0xabc04108);
	reads = mock.reads; writes = mock.writes;
	assert(n71_pme_restore(&io, &state) == 0);
	assert(mock.reads == reads && mock.writes == writes);
}

static void scope_and_faults(void)
{
	struct mock mock;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_pme_state state;
	unsigned int index, reads;

	/* Mutation captured: broadening CSR/capability/master guards permits an unowned effect. */
	for (index = 0; index < 16; index++) {
		initialize(&mock); mock.config[0x4c / 4] ^= 1U << index; rejected(&mock);
	}
	for (index = 0; index < 8; index++) {
		initialize(&mock); mock.config[0x48 / 4] = 1 | (index << 16);
		if (index >= 1 && index <= 3) {
			memset(&state, 0, sizeof(state));
			assert(n71_pme_disable(&io, &state) == 0);
			assert(n71_pme_restore(&io, &state) == 0);
		} else rejected(&mock);
	}
	initialize(&mock); mock.config[0] ^= 1; rejected(&mock);
	initialize(&mock); mock.config[1] |= 4; rejected(&mock);
	initialize(&mock); mock.config[1] &= ~0x100000U; rejected(&mock);
	initialize(&mock); mock.config[0x34 / 4] = 0x49; rejected(&mock);
	initialize(&mock); mock.config[0x34 / 4] = 0x50; mock.config[0x50 / 4] = 0x30001; rejected(&mock);
	initialize(&mock); mock.config[0x48 / 4] = 0x35001; mock.config[0x50 / 4] = 0x30001; rejected(&mock);
	initialize(&mock); mock.config[0x48 / 4] = 0x30005; rejected(&mock);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0); reads = mock.reads;
	for (index = 1; index <= reads; index++) {
		initialize(&mock); mock.fail_read = index; memset(&state, 0, sizeof(state));
		assert(n71_pme_disable(&io, &state) == -EIO);
		assert(state.pending == (index == reads));
		assert(!state.prepared && mock.writes == (index == reads ? 1U : 0U));
		mock.fail_read = 0;
		assert(n71_pme_restore(&io, &state) == 0);
		assert(mock.config[0x4c / 4] == 0xabc04108 && !state.pending);
	}
	initialize(&mock); mock.positive = true; mock.fail_read = 1; rejected(&mock);
	initialize(&mock); mock.event_read = reads - 1; memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == -EAGAIN && !state.pending && !mock.writes);
	initialize(&mock); mock.master_read = reads - 2; rejected(&mock);
}

static void partial_and_retry(void)
{
	struct mock mock;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_pme_state state;
	unsigned int partial, positive, index, restore_reads, start_reads;

	/* Mutation captured: clearing ownership on partial I/O loses the ability to restore. */
	for (partial = 0; partial < 2; partial++) {
		for (positive = 0; positive < 2; positive++) {
			initialize(&mock); memset(&state, 0, sizeof(state));
			mock.fail_write = 1; mock.partial = partial; mock.positive = positive;
			assert(n71_pme_disable(&io, &state) == -EIO);
			assert(state.pending && !state.prepared);
			assert((mock.config[0x4c / 4] & 0x100) == (partial ? 0U : 0x100U));
			mock.fail_write = 0;
			assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
			assert(mock.config[0x4c / 4] == 0xabc04108);
		}
	}
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0); start_reads = mock.reads;
	assert(n71_pme_restore(&io, &state) == 0); restore_reads = mock.reads - start_reads;
	for (index = 1; index <= restore_reads; index++) {
		initialize(&mock); memset(&state, 0, sizeof(state));
		assert(n71_pme_disable(&io, &state) == 0);
		mock.fail_read = mock.reads + index;
		assert(n71_pme_restore(&io, &state) == -EIO && state.pending);
		mock.fail_read = 0;
		assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
		assert(mock.config[0x4c / 4] == 0xabc04108);
	}
	for (partial = 0; partial < 2; partial++) {
		for (positive = 0; positive < 2; positive++) {
			initialize(&mock); memset(&state, 0, sizeof(state));
			assert(n71_pme_disable(&io, &state) == 0);
			mock.partial = partial; mock.positive = positive; mock.fail_write = 2;
			assert(n71_pme_restore(&io, &state) == -EIO && state.pending);
			mock.fail_write = 0;
			assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
			assert(mock.config[0x4c / 4] == 0xabc04108);
		}
	}
	initialize(&mock); memset(&state, 0, sizeof(state)); mock.bad_readback = true;
	assert(n71_pme_disable(&io, &state) == -EAGAIN && state.pending);
	mock.bad_readback = false;
	assert(n71_pme_restore(&io, &state) == 0);
}

static void preserve_events(void)
{
	struct mock mock;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_pme_state state;
	unsigned int reads, restore_reads;

	/* Mutation captured: restoring the saved word overwrites current controls or an event. */
	initialize(&mock); memset(&state, 0, sizeof(state)); mock.event_write = true;
	assert(n71_pme_disable(&io, &state) == -EAGAIN && state.pending && !state.prepared);
	assert(mock.config[0x4c / 4] == 0xabc0c008);
	mock.config[0x4c / 4] ^= 0x200;
	assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
	assert(mock.config[0x4c / 4] == 0xabc0c308);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0);
	reads = mock.reads;
	mock.config[0x4c / 4] |= 3;
	assert(n71_pme_restore(&io, &state) == -EPERM && state.pending);
	assert(mock.writes == 1 && mock.reads > reads);
	mock.config[0x4c / 4] &= ~3U;
	mock.config[0] ^= 1;
	assert(n71_pme_restore(&io, &state) == -ENODEV && state.pending);
	mock.config[0] ^= 1;
	assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0); reads = mock.reads;
	assert(n71_pme_restore(&io, &state) == 0); restore_reads = mock.reads - reads;
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0);
	mock.config[0x4c / 4] |= 0x8000;
	mock.clear_event_read = mock.reads + restore_reads;
	assert(n71_pme_restore(&io, &state) == -EIO && state.pending);
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0);
	mock.config[0x48 / 4] = 0x30009;
	mock.config[0x4c / 4] = 0;
	reads = mock.writes;
	assert(n71_pme_restore(&io, &state) == -EPERM && state.pending && mock.writes == reads);
}

static void core_noop(void)
{
	struct mock mock;
	struct n71_scan_io io = {&mock, read_config, write_config};
	struct n71_pme_state state = {0};
	struct n71_scan_config config = {.active = true};
	struct n71_scan_request request = {false, 0x4c, 0xc008, 2};
	unsigned int reads, writes, index, event;

	/* Mutation captured: an unowned/core W1C request cannot masquerade as a verified disable. */
	initialize(&mock);
	assert(n71_pme_scan_write(&io, &config, &state, &request) == -EPERM);
	assert(mock.reads == 0 && mock.writes == 0);
	config.error = 0; config.refusals = 0;
	assert(n71_pme_disable(&io, &state) == 0);
	reads = mock.reads; writes = mock.writes;
	assert(n71_pme_scan_write(&io, &config, &state, &request) == 0);
	assert(mock.writes == writes && mock.config[0x4c / 4] == 0xabc04008);
	assert(config.attempts == 1 && config.writes == 0 && config.error == 0);
	reads = mock.reads - reads;
	for (index = 0; index < 16; index++) {
		config.error = 0; request.value = 0xc008 ^ (1U << index);
		assert(n71_pme_scan_write(&io, &config, &state, &request) == (index == 15 ? 0 : -EPERM));
		assert(mock.writes == writes && state.pending && state.prepared);
	}
	request.value = 0xc008;
	for (index = 1; index <= 4; index++) {
		if (index == 2) continue;
		request.size = index; config.error = 0;
		assert(n71_pme_scan_write(&io, &config, &state, &request) == -EPERM);
		assert(mock.writes == writes);
	}
	request.where = 0x4d; request.size = 1; request.value = 0x40; config.error = 0;
	assert(n71_pme_scan_write(&io, &config, &state, &request) == -EPERM);
	request.where = 0x4c; request.size = 2; request.value = 0xc008;
	for (index = 0; index < 3; index++) {
		struct n71_pme_state bad = state;
		if (index == 0) bad.pending = false;
		if (index == 1) bad.prepared = false;
		if (index == 2) bad.original ^= 0x100;
		config.error = 0;
		assert(n71_pme_scan_write(&io, &config, &bad, &request) == -EPERM);
		assert(mock.writes == writes);
	}
	for (event = 1; event <= reads; event++) {
		initialize(&mock); memset(&state, 0, sizeof(state));
		assert(n71_pme_disable(&io, &state) == 0);
		mock.event_read = mock.reads + event; config.error = 0;
		assert(n71_pme_scan_write(&io, &config, &state, &request) < 0);
		assert(mock.writes == 1 && state.pending);
		mock.event_read = 0;
		assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
		assert(mock.config[0x4c / 4] == 0xabc0c108);
	}
	initialize(&mock); memset(&state, 0, sizeof(state));
	assert(n71_pme_disable(&io, &state) == 0);
	mock.config[0x4c / 4] |= 0x8000;
	mock.clear_event_read = mock.reads + reads; config.error = 0;
	assert(n71_pme_scan_write(&io, &config, &state, &request) == -EPERM);
	assert(mock.config[0x4c / 4] == 0xabc0c008 && state.pending && mock.writes == 1);
	mock.clear_event_read = 0;
	assert(n71_pme_restore(&io, &state) == 0 && !state.pending);
	config.error = -ENOLINK; reads = mock.reads;
	assert(n71_pme_scan_write(&io, &config, &state, &request) == -ENOLINK);
	assert(mock.reads == reads);
	config.error = 0; config.active = false;
	assert(n71_pme_scan_write(&io, &config, &state, &request) == -EPERM);
	assert(mock.reads == reads);
}

int main(void)
{
	lifecycle(); scope_and_faults(); partial_and_retry(); preserve_events(); core_noop();
	puts("N71_PME_CONTROL_OK");
	return 0;
}
