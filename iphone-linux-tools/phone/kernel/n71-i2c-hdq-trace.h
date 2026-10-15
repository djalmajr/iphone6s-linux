/* SPDX-License-Identifier: GPL-2.0-only */
/* Per-call diagnostics only; these fields never authorize hardware access. */
#ifndef N71_I2C_HDQ_TRACE_H
#define N71_I2C_HDQ_TRACE_H

enum n71_hdq_stage {
	N71_HDQ_ARGUMENTS = 1, N71_HDQ_READY, N71_HDQ_OWNERSHIP,
	N71_HDQ_SAMPLE, N71_HDQ_IDLE, N71_HDQ_ACK, N71_HDQ_SUBMIT,
	N71_HDQ_POLL, N71_HDQ_DATA, N71_HDQ_RECOVERY, N71_HDQ_COMPLETE,
};

enum n71_hdq_cleanup_stage {
	N71_HDQ_C_ARGUMENTS = 1, N71_HDQ_C_READY, N71_HDQ_C_POLL,
	N71_HDQ_C_SAMPLE, N71_HDQ_C_FLUSH, N71_HDQ_C_ACK,
	N71_HDQ_C_VERIFY, N71_HDQ_C_FINAL_READY, N71_HDQ_C_COMPLETE,
};

struct n71_i2c_hdq_trace {
	bool cleanup_sampled;
	unsigned int cleanup_stage;
	u32 cleanup_status;
	bool sampled;
	unsigned int stage;
	u32 status;
};

static inline void n71_hdq_trace_begin(struct n71_i2c_hdq_trace *trace, bool cleanup)
{
	if (!trace)
		return;
	if (cleanup) {
		trace->cleanup_stage = N71_HDQ_C_ARGUMENTS;
		trace->cleanup_status = 0;
		trace->cleanup_sampled = false;
	} else {
		*trace = (struct n71_i2c_hdq_trace){.stage = N71_HDQ_ARGUMENTS};
	}
}

static inline void n71_hdq_trace_stage(struct n71_i2c_hdq_trace *trace,
				     unsigned int stage, bool cleanup)
{
	if (!trace)
		return;
	if (cleanup)
		trace->cleanup_stage = stage;
	else
		trace->stage = stage;
}

static inline void n71_hdq_trace_status(struct n71_i2c_hdq_trace *trace,
				      u32 status, bool cleanup)
{
	if (!trace)
		return;
	if (cleanup) {
		trace->cleanup_status = status;
		trace->cleanup_sampled = true;
	} else {
		trace->status = status;
		trace->sampled = true;
	}
}
#endif /* N71_I2C_HDQ_TRACE_H */
