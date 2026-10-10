/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "n71-i2c-power-lifecycle.h"

struct model {
	struct n71_i2c_power_state state;
	int attach_error;
	int resume_error;
	int active_error;
	int suspend_result;
	int quiescent_error;
	int detach_error;
	int usage;
	unsigned int attachments;
	unsigned int puts;
	unsigned int retries;
	unsigned int detachments;
	bool live;
	bool powered;
};

static unsigned int cases;

static int attach(void *context)
{
	struct model *m = context;

	assert(!m->live && !m->usage && !m->powered);
	if (m->attach_error)
		return m->attach_error;
	m->live = true;
	m->attachments++;
	return 0;
}

static int resume(void *context)
{
	struct model *m = context;

	assert(m->live && !m->usage && m->state.attached && m->state.cleanup_pending);
	/* A failed activation can leave hardware changed without owning usage. */
	m->powered = true;
	if (m->resume_error)
		return m->resume_error;
	m->usage++;
	return 0;
}

static int verify_active(void *context)
{
	struct model *m = context;

	assert(m->live && m->powered && m->usage == 1 && m->state.usage_held);
	return m->active_error;
}

static int suspend_model(struct model *m)
{
	assert(m->live && !m->usage);
	if (m->suspend_result < 0)
		return m->suspend_result;
	m->powered = false;
	return m->suspend_result;
}

static int put_and_suspend(void *context)
{
	struct model *m = context;

	assert(m->usage == 1);
	m->usage--;
	m->puts++;
	return suspend_model(m);
}

static int suspend_zero_usage(void *context)
{
	struct model *m = context;

	m->retries++;
	return suspend_model(m);
}

static int verify_quiescent(void *context)
{
	struct model *m = context;

	assert(m->live && !m->usage && !m->powered);
	return m->quiescent_error;
}

static int detach_verified(void *context)
{
	struct model *m = context;

	assert(m->live && !m->usage && !m->powered && !m->quiescent_error);
	if (m->detach_error)
		return m->detach_error;
	m->live = false;
	m->detachments++;
	return 0;
}

static struct n71_i2c_power_io io_for(struct model *m)
{
	return (struct n71_i2c_power_io) {
		.context = m, .attach = attach, .resume_and_get = resume,
		.put_and_suspend = put_and_suspend, .suspend_zero_usage = suspend_zero_usage,
		.verify_active = verify_active, .verify_quiescent = verify_quiescent,
		.detach_verified = detach_verified,
	};
}

static void released(const struct model *m)
{
	assert(!m->live && !m->powered && !m->usage);
	assert(!m->state.active && !m->state.attached && !m->state.cleanup_pending);
	assert(!m->state.usage_held && !m->state.cleanup_error);
}

static void baseline(void)
{
	struct model m = {0};
	struct n71_i2c_power_io io = io_for(&m);

	assert(n71_i2c_power_acquire(&io, &m.state) == 0);
	assert(m.live && m.powered && m.usage == 1 && m.state.active);
	assert(n71_i2c_power_acquire(&io, &m.state) == -EBUSY);
	assert(m.usage == 1 && m.attachments == 1);
	assert(n71_i2c_power_release(&io, &m.state) == 0);
	released(&m);
	assert(m.puts == 1 && m.detachments == 1 && !m.retries);
	assert(n71_i2c_power_release(&io, &m.state) == 0);
	released(&m);
	assert(m.puts == 1 && m.detachments == 1 && !m.retries);
	assert(n71_i2c_power_acquire(&io, &m.state) == 0);
	m.suspend_result = 1;
	assert(n71_i2c_power_release(&io, &m.state) == 0);
	released(&m);
	assert(m.puts == 2 && m.detachments == 2);
	cases++;
}

static void failures(void)
{
	for (unsigned int phase = 0; phase < 6; phase++) {
		struct model m = {0};
		struct n71_i2c_power_io io = io_for(&m);

		if (phase == 0) m.attach_error = -ENOMEM;
		if (phase == 1) m.resume_error = -EPIPE;
		if (phase == 2) m.active_error = -EIO;
		if (phase < 3) {
			int expected = phase == 0 ? -ENOMEM : phase == 1 ? -EPIPE : -EIO;

			assert(n71_i2c_power_acquire(&io, &m.state) == expected);
			released(&m);
			assert(m.puts == (phase == 2) && m.retries == (phase == 1));
			cases++;
			continue;
		}
		assert(n71_i2c_power_acquire(&io, &m.state) == 0);
		if (phase == 3) m.suspend_result = -ETIMEDOUT;
		if (phase == 4) m.quiescent_error = -EAGAIN;
		if (phase == 5) m.detach_error = -EBUSY;
		int expected = phase == 3 ? -ETIMEDOUT : phase == 4 ? -EAGAIN : -EBUSY;

		assert(n71_i2c_power_release(&io, &m.state) == expected);
		assert(m.live && !m.usage && m.puts == 1 && !m.detachments);
		assert(!m.state.active && !m.state.usage_held);
		assert(m.state.attached && m.state.cleanup_pending && m.state.cleanup_error == expected);
		assert(n71_i2c_power_acquire(&io, &m.state) == -EBUSY);
		assert(m.attachments == 1);
		m.suspend_result = 0; m.quiescent_error = 0; m.detach_error = 0;
		assert(n71_i2c_power_release(&io, &m.state) == 0);
		released(&m);
		assert(m.puts == 1 && m.retries == 1 && m.detachments == 1);
		cases++;
	}
}

static void combined_failure(void)
{
	struct model m = {.resume_error = -EPIPE, .suspend_result = -ETIMEDOUT};
	struct n71_i2c_power_io io = io_for(&m);

	assert(n71_i2c_power_acquire(&io, &m.state) == -EPIPE);
	assert(m.live && m.powered && !m.usage && !m.puts && m.retries == 1);
	assert(m.state.cleanup_pending && m.state.attached && !m.state.active);
	assert(m.state.cleanup_error == -ETIMEDOUT);
	assert(n71_i2c_power_acquire(&io, &m.state) == -EBUSY);
	m.suspend_result = 0;
	assert(n71_i2c_power_release(&io, &m.state) == 0);
	released(&m);
	assert(!m.puts && m.retries == 2 && m.detachments == 1);
	cases++;
}

static void positive_verification(void)
{
	for (unsigned int phase = 0; phase < 3; phase++) {
		struct model m = {0};
		struct n71_i2c_power_io io = io_for(&m);

		if (phase == 0) {
			m.active_error = 1;
			assert(n71_i2c_power_acquire(&io, &m.state) == -EIO);
			released(&m);
		} else {
			assert(n71_i2c_power_acquire(&io, &m.state) == 0);
			if (phase == 1) m.quiescent_error = 1;
			if (phase == 2) m.detach_error = 1;
			assert(n71_i2c_power_release(&io, &m.state) == -EIO);
			assert(m.live && m.state.cleanup_pending && m.state.cleanup_error == -EIO);
			m.quiescent_error = 0; m.detach_error = 0;
			assert(n71_i2c_power_release(&io, &m.state) == 0);
			released(&m);
		}
		cases++;
	}
}

static void invalid_inputs(void)
{
	struct model m = {0};
	struct n71_i2c_power_io io = io_for(&m), invalid = io;

	assert(n71_i2c_power_acquire(NULL, &m.state) == -EINVAL);
	assert(n71_i2c_power_acquire(&io, NULL) == -EINVAL);
	assert(n71_i2c_power_release(NULL, &m.state) == -EINVAL);
	assert(n71_i2c_power_release(&io, NULL) == -EINVAL);
	invalid.detach_verified = NULL;
	assert(n71_i2c_power_acquire(&invalid, &m.state) == -EINVAL);
	assert(n71_i2c_power_release(&invalid, &m.state) == -EINVAL);
	m.state.cleanup_pending = true;
	assert(n71_i2c_power_release(&io, &m.state) == -EINVAL);
	assert(n71_i2c_power_acquire(&io, &m.state) == -EBUSY);
	m.state.cleanup_pending = false;
	m.state.usage_held = true;
	assert(n71_i2c_power_acquire(&io, &m.state) == -EBUSY);
	m.state.usage_held = false;
	m.state.attached = true;
	assert(n71_i2c_power_release(&io, &m.state) == -EINVAL);
	assert(!m.live && !m.usage && !m.attachments && !m.puts && !m.retries);
	cases++;
}

int main(void)
{
	baseline(); failures(); combined_failure(); positive_verification(); invalid_inputs();
	printf("N71_I2C_POWER_LIFECYCLE_OK cases=%u\n", cases);
	return 0;
}
