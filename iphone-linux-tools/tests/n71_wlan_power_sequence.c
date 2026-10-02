/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "n71-wlan-power.h"

struct mock {
	unsigned char value;
	unsigned int calls, fail_at, fail_again_at, writes;
	bool partial_error, dropped_write;
};

static int read_value(void *context, unsigned char *value)
{
	struct mock *m = context;
	if (++m->calls == m->fail_at || m->calls == m->fail_again_at)
		return -EACCES;
	*value = m->value;
	return 0;
}

static int write_value(void *context, unsigned char value)
{
	struct mock *m = context;
	bool failed = ++m->calls == m->fail_at || m->calls == m->fail_again_at;
	m->writes++;
	if ((!failed || m->partial_error) && !m->dropped_write)
		m->value = value;
	return failed ? -EACCES : 0;
}

int main(void)
{
	struct mock m = {.value = 0x62};
	struct n71_wlan_power_io io = {&m, read_value, write_value};
	struct n71_wlan_power_state state = {0};
	unsigned int i, calls;

	assert(n71_wlan_power_acquire(&io, &state) == 0);
	assert(m.value == 0x63 && state.active && state.restore_pending && state.original == 0x62);
	calls = m.calls;
	assert(n71_wlan_power_acquire(&io, &state) == -EBUSY && m.calls == calls);
	assert(n71_wlan_power_release(&io, &state) == 0);
	assert(m.value == 0x62 && !state.active && !state.restore_pending && m.writes == 2);
	calls = m.calls;
	assert(n71_wlan_power_release(&io, &state) == 0 && m.calls == calls);
	for (i = 1; i <= 3; i++) {
		m = (struct mock){.value = 0x40, .fail_at = i, .partial_error = true};
		state = (struct n71_wlan_power_state){0};
		/* Kills dropping cleanup or marking pending only after write success. */
		assert(n71_wlan_power_acquire(&io, &state) == -EACCES);
		assert(m.value == 0x40 && !state.active && !state.restore_pending);
	}
	for (i = 1; i <= 3; i++) {
		m = (struct mock){.value = 0x40};
		state = (struct n71_wlan_power_state){0};
		assert(n71_wlan_power_acquire(&io, &state) == 0);
		m.fail_at = m.calls + i;
		/* Failed restore is not reported as complete, even if its write applied. */
		assert(n71_wlan_power_release(&io, &state) == -EACCES);
		assert(state.restore_pending && state.active);
		m.fail_at = 0;
		assert(n71_wlan_power_release(&io, &state) == 0 && m.value == 0x40);
	}
	m = (struct mock){.value = 0x40, .fail_at = 2, .fail_again_at = 3, .partial_error = true};
	state = (struct n71_wlan_power_state){0};
	assert(n71_wlan_power_acquire(&io, &state) == -EACCES);
	assert(m.value == 0x41 && state.restore_pending && !state.active);
	calls = m.calls;
	assert(n71_wlan_power_acquire(&io, &state) == -EBUSY && m.calls == calls);
	m.fail_at = m.fail_again_at = 0;
	assert(n71_wlan_power_release(&io, &state) == 0 && m.value == 0x40);
	m = (struct mock){.value = 0x40};
	assert(n71_wlan_power_acquire(&io, &state) == 0);
	m.dropped_write = true;
	assert(n71_wlan_power_release(&io, &state) == -EIO);
	assert(m.value == 0x41 && state.restore_pending && state.active);
	m.dropped_write = false;
	assert(n71_wlan_power_release(&io, &state) == 0 && m.value == 0x40);
	m = (struct mock){.value = 0x40, .dropped_write = true};
	state = (struct n71_wlan_power_state){0};
	assert(n71_wlan_power_acquire(&io, &state) == -EIO);
	assert(!state.active && !state.restore_pending && m.value == 0x40);
	m = (struct mock){.value = 0x41};
	state = (struct n71_wlan_power_state){0};
	assert(n71_wlan_power_acquire(&io, &state) == 0 && !state.restore_pending && m.writes == 0);
	assert(n71_wlan_power_release(&io, &state) == 0 && m.value == 0x41 && m.calls == 1);
	m = (struct mock){.value = 0xff};
	state = (struct n71_wlan_power_state){0};
	assert(n71_wlan_power_acquire(&io, &state) == -EINVAL && m.writes == 0);
	m = (struct mock){.value = 0x40};
	assert(n71_wlan_power_acquire(&io, &state) == 0);
	m.value = 0x43; /* Simulated external owner changes another bit. */
	calls = m.writes;
	assert(n71_wlan_power_release(&io, &state) == -EBUSY);
	assert(m.value == 0x43 && m.writes == calls && state.restore_pending);
	assert(!n71_wlan_power_io_valid(NULL));
	assert(n71_wlan_power_acquire(NULL, &state) == -EINVAL);
	assert(n71_wlan_power_release(&io, NULL) == -EINVAL);
	puts("N71_WLAN_POWER_SEQUENCE_OK");
	return 0;
}
