/* SPDX-License-Identifier: GPL-2.0-only */
/* Selected SN2400 handshake. No hardware backend or charger probe. */
#ifndef N71_HDQ_HANDSHAKE_H
#define N71_HDQ_HANDSHAKE_H
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/types.h>
#else
#include <errno.h>
#include <stdbool.h>
#endif

#define N71_HDQ_HANDSHAKE_REGISTER 0x1dU
#define N71_HDQ_HANDSHAKE_POLLS 100U

struct n71_hdq_handshake_io {
	void *context;
	int (*read)(void *context, unsigned int reg, unsigned int *value);
	int (*write)(void *context, unsigned int reg, unsigned int value);
	void (*delay_ms)(void *context, unsigned int milliseconds);
};

struct n71_hdq_handshake_state {
	bool cleanup_required;
	bool acknowledged;
	bool final_write_accepted;
};

/* The caller serializes ownership and performs qualified, verified cleanup.
 * Never clear cleanup_required here: accepted writes and ACK are not restore.
 * 100 polls/10ms delays bound the nominal delay budget, not backend runtime.
 */
static inline int n71_hdq_handshake(const struct n71_hdq_handshake_io *io,
				   struct n71_hdq_handshake_state *state,
				   bool final_write)
{
	unsigned int attempt, value;
	int error;
	if (!io || !state || !io->read || !io->write || !io->delay_ms)
		return -EINVAL;
	if (state->cleanup_required)
		return -EBUSY;
	state->acknowledged = false;
	state->final_write_accepted = false;
	state->cleanup_required = true;
	error = io->write(io->context, N71_HDQ_HANDSHAKE_REGISTER, 0x04);
	if (error)
		return error;
	for (attempt = 0; attempt < N71_HDQ_HANDSHAKE_POLLS; attempt++) {
		error = io->read(io->context, N71_HDQ_HANDSHAKE_REGISTER, &value);
		if (error)
			return error;
		if (value > 0xff)
			return -ERANGE;
		if (value & 0x20) {
			state->acknowledged = true;
			if (!final_write)
				return 0;
			error = io->write(io->context, N71_HDQ_HANDSHAKE_REGISTER, 0x06);
			if (!error)
				state->final_write_accepted = true;
			return error;
		}
		io->delay_ms(io->context, 10);
	}
	return -ETIMEDOUT;
}

#endif /* N71_HDQ_HANDSHAKE_H */
