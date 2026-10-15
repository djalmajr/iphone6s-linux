/* SPDX-License-Identifier: GPL-2.0-only */
/* Selected N71 arithmetic only: no I/O or permission to apply these limits. */
#ifndef N71_SN2400_INPUT_REFERENCE_H
#define N71_SN2400_INPUT_REFERENCE_H
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
#endif

struct n71_sn2400_input_request {
	unsigned int milliamps;
	unsigned int calibration_enabled;
};

struct n71_sn2400_input_setting {
	unsigned int register_value;
	unsigned int encoded_milliamps;
	unsigned int suspend;
};

/* getInputCurrentSetting, N71 005d69560..005d696f8, uncalibrated path.
 * Code zero also encodes 90mA; suspend is a separate result and control path.
 * The representable range is not a qualified battery/USB operating limit.
 */
static inline int n71_sn2400_input_reference(
		const struct n71_sn2400_input_request *request,
		struct n71_sn2400_input_setting *output)
{
	struct n71_sn2400_input_setting setting;
	unsigned int milliamps;

	if (!request || !output || request->calibration_enabled != 0)
		return -EINVAL;
	milliamps = request->milliamps;
	if (milliamps < 90U)
		milliamps = 90U;
	if (milliamps > 2000U)
		milliamps = 2000U;
	setting.register_value = (milliamps - 90U) / 10U;
	setting.encoded_milliamps = 90U + setting.register_value * 10U;
	setting.suspend = request->milliamps == 0;
	*output = setting;
	return 0;
}

#endif /* N71_SN2400_INPUT_REFERENCE_H */
