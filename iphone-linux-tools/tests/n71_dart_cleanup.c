/* SPDX-License-Identifier: GPL-2.0-only */
/* Production cleanup functions are extracted verbatim by the Python runner. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

struct device { int unused; };
struct n71_diagnostic {
	void *dart, *scan_bridge;
	unsigned int attached, powered;
	bool module_retained, power_put_pending, reset_pending;
	int primary_error, cleanup_error;
};
struct device *session_device;
static struct n71_diagnostic *current;
static unsigned int fail_stage, released_pins;
static bool leave_dart;
static int module;
#define THIS_MODULE (&module)

static void dev_info(struct device *dev, const char *format, ...)
{
	(void)dev; (void)format;
}
static int n71_pcie_dart_cleanup(struct device *dev, struct n71_diagnostic *state)
{
	(void)dev;
	assert(state->powered == 4 && state->attached == 4 && state->reset_pending && state->scan_bridge);
	if (fail_stage == 1) return -ENOLINK;
	if (!leave_dart) state->dart = NULL;
	return 0;
}
static int n71_pcie_scan_cleanup(struct n71_diagnostic *state)
{
	assert(!state->dart && state->powered == 4 && state->reset_pending);
	if (fail_stage == 2) return -EBUSY;
	state->scan_bridge = NULL;
	return 0;
}
static int n71_reset(struct n71_diagnostic *state, bool asserted)
{
	assert(asserted && !state->dart && !state->scan_bridge && state->powered == 4);
	return fail_stage == 3 ? -EIO : 0;
}
static int n71_release_power(struct n71_diagnostic *state)
{
	assert(!state->dart && !state->scan_bridge && !state->reset_pending);
	if (fail_stage == 4) {
		state->powered = 3; state->power_put_pending = true;
		return -EAGAIN;
	}
	state->powered = state->attached = 0; state->power_put_pending = false;
	return 0;
}
static void module_put(int *owner)
{
	assert(owner == THIS_MODULE && !current->dart && !current->scan_bridge);
	assert(!current->reset_pending && !current->powered && !current->attached);
	assert(!current->power_put_pending && !current->module_retained);
	released_pins++;
}

#include "n71-dart-cleanup-under-test.h"

int main(void)
{
	struct n71_diagnostic state;
	unsigned int stage;
	for (stage = 0; stage <= 2; stage++) {
		state = (struct n71_diagnostic){.dart = &state, .scan_bridge = &state,
			.powered = 4, .attached = 4, .reset_pending = true, .module_retained = true,
			.primary_error = -ENODEV};
		current = &state; released_pins = 0; fail_stage = stage; leave_dart = false;
		assert(n71_finish_cleanup(&state) == (stage == 1 ? -ENOLINK : stage == 2 ? -EBUSY : 0));
		if (stage) {
			assert(state.module_retained && !released_pins && state.scan_bridge);
			assert(state.reset_pending && state.powered == 4 && state.attached == 4);
			assert((state.dart != NULL) == (stage == 1));
			/* Retry fixture permits the already removed DART to be absent. */
			fail_stage = 0;
			assert(n71_finish_cleanup(&state) == 0);
		}
		assert(!state.module_retained && released_pins == 1 && state.primary_error == -ENODEV);
	}
	state = (struct n71_diagnostic){.dart = &state, .scan_bridge = &state,
		.powered = 4, .attached = 4, .reset_pending = true, .module_retained = true};
	current = &state; released_pins = 0; leave_dart = true; fail_stage = 0;
	assert(n71_finish_cleanup(&state) == -EBUSY);
	assert(state.dart && state.scan_bridge && state.module_retained && !released_pins);
	leave_dart = false;
	assert(n71_finish_cleanup(&state) == 0 && released_pins == 1);
	puts("N71_DART_CLEANUP_OK cases=4");
	return 0;
}
