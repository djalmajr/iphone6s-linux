/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-hdq-handshake.h"

struct fake {
	struct n71_hdq_handshake_state state;
	unsigned int calls, fail, reads, writes, delays, ack_after, returned;
	unsigned int operations[104];
};

static int write_value(void *context, unsigned int reg, unsigned int value)
{
	struct fake *fake = context;
	assert(reg == 0x1d && fake->state.cleanup_required);
	assert(value == (fake->writes ? 0x06 : 0x04));
	assert(fake->calls < 104);
	fake->operations[fake->calls++] = value;
	fake->writes++;
	return fake->calls == fake->fail ? -EIO : 0;
}

static int read_value(void *context, unsigned int reg, unsigned int *out)
{
	struct fake *fake = context;
	assert(reg == 0x1d && fake->writes == 1);
	assert(fake->calls < 104);
	fake->operations[fake->calls++] = 0x100;
	fake->reads++;
	if (fake->calls == fake->fail)
		return -EIO;
	*out = fake->reads > fake->ack_after ? fake->returned : 0;
	return 0;
}

static void delay(void *context, unsigned int milliseconds)
{
	struct fake *fake = context;
	assert(milliseconds == 10 && !fake->state.acknowledged);
	fake->delays++;
}

int main(void)
{
	struct fake fake;
	struct n71_hdq_handshake_io io = { &fake, read_value, write_value, delay };
	unsigned int final, fail;
	/* Kills wrong register/values, early final write, ACK bit and dropped errors. */
	for (final = 0; final < 2; final++) {
		for (fail = 0; fail <= 5; fail++) {
			memset(&fake, 0, sizeof(fake));
			fake.ack_after = 2;
			fake.returned = 0x20;
			fake.fail = fail;
			int result = n71_hdq_handshake(&io, &fake.state, final);
			unsigned int count = 4 + final;
			bool failed = fail && fail <= count;
			assert(result == (failed ? -EIO : 0));
			assert(fake.calls == (failed ? fail : count));
			assert(fake.state.cleanup_required);
			assert(fake.state.acknowledged == (!failed || fail == 5));
			assert(fake.state.final_write_accepted == (final && !failed));
			assert(n71_hdq_handshake(&io, &fake.state, final) == -EBUSY);
			assert(fake.calls == (failed ? fail : count));
		}
	}
	/* Kills timeout extension, incorrect delay budget and acceptance without ACK. */
	memset(&fake, 0, sizeof(fake)); fake.returned = 0x40;
	assert(n71_hdq_handshake(&io, &fake.state, true) == -ETIMEDOUT);
	assert(fake.reads == 100 && fake.delays == 100 && fake.writes == 1);
	assert(fake.state.cleanup_required && !fake.state.acknowledged);
	/* Kills acceptance of a wide status byte and cleanup before a failed write. */
	memset(&fake, 0, sizeof(fake)); fake.returned = 0x120;
	assert(n71_hdq_handshake(&io, &fake.state, true) == -ERANGE);
	assert(fake.reads == 1 && fake.writes == 1 && fake.state.cleanup_required);
	/* Kills stale success flags when a subsequent partial write fails. */
	memset(&fake, 0, sizeof(fake)); fake.fail = 1;
	fake.state.acknowledged = true; fake.state.final_write_accepted = true;
	assert(n71_hdq_handshake(&io, &fake.state, true) == -EIO);
	assert(!fake.state.acknowledged && !fake.state.final_write_accepted);
	assert(fake.calls == 1 && fake.state.cleanup_required);
	assert(n71_hdq_handshake(NULL, &fake.state, false) == -EINVAL);
	assert(n71_hdq_handshake(&io, NULL, false) == -EINVAL);
	io.read = NULL;
	assert(n71_hdq_handshake(&io, &fake.state, false) == -EINVAL);
	io.read = read_value; io.write = NULL;
	assert(n71_hdq_handshake(&io, &fake.state, false) == -EINVAL);
	io.write = write_value; io.delay_ms = NULL;
	assert(n71_hdq_handshake(&io, &fake.state, false) == -EINVAL);
	puts("N71_HDQ_HANDSHAKE_OK");
	return 0;
}
