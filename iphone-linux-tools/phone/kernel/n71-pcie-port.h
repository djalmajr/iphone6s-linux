/* SPDX-License-Identifier: GPL-2.0-only */
/* N71 port1 preparation. Caller owns power, endpoint reset and failure cleanup. */
#ifndef N71_PCIE_PORT_H
#define N71_PCIE_PORT_H

#include "n71-pcie-init.h"

struct n71_pcie_port_io {
	struct n71_pcie_io common;
	int (*read_port)(void *context, u32 offset, u32 *value);
	int (*write_port)(void *context, u32 offset, u32 value);
};

static inline int n71_pcie_poll_common(const struct n71_pcie_io *io,
				      u32 offset, u32 mask)
{
	unsigned int attempt;
	u32 value;
	int error;

	for (attempt = 0; attempt < N71_PCIE_POLL_ATTEMPTS; attempt++) {
		error = io->read32(io->context, N71_PCIE_COMMON, offset, &value);
		if (error)
			return error;
		if (value == 0xffffffff)
			return -EIO;
		if (value & mask)
			return 0;
		if (attempt + 1 < N71_PCIE_POLL_ATTEMPTS)
			io->delay_us(io->context, N71_PCIE_POLL_INTERVAL_US);
	}
	return -ETIMEDOUT;
}

static inline int n71_pcie_set_wlan_control(const struct n71_pcie_io *io,
					   enum n71_pcie_control control,
					   bool enabled)
{
	struct n71_pcie_update update;
	u32 value;
	int error;

	if (!n71_pcie_control_update(control, N71_PCIE_WLAN_PORT, enabled, 0, &update))
		return -EINVAL;
	error = io->read32(io->context, N71_PCIE_COMMON, update.offset, &value);
	if (error)
		return error;
	if (value == 0xffffffff)
		return -EIO;
	n71_pcie_control_update(control, N71_PCIE_WLAN_PORT, enabled, value, &update);
	return io->write32(io->context, N71_PCIE_COMMON, update.offset, update.value);
}

/* S800x port-enable prefix. N71 has neither optional clock property below.
 * This does not release PERST, apply config/port tunables or enable bus mastering.
 */
static inline int n71_pcie_prepare_wlan(const struct n71_pcie_port_io *io,
				       bool muxed_auxclk_auto_disable,
				       bool no_refclk_gating)
{
	const struct n71_pcie_io *common;
	u32 pending;
	int error;

	if (!io || !io->common.read32 || !io->common.write32 ||
	    !io->common.delay_us || !io->read_port || !io->write_port ||
	    muxed_auxclk_auto_disable || no_refclk_gating)
		return -EINVAL;
	common = &io->common;
	error = n71_pcie_set_wlan_control(common, N71_ID4_BIT0_INVERTED, true);
	if (error)
		return error;
	error = n71_pcie_set_wlan_control(common, N71_ID3_BIT0, true);
	if (error)
		return error;
	error = n71_pcie_poll_common(common, 0x2c, 1U << 4);
	if (error)
		return error;
	common->delay_us(common->context, 100);
	error = n71_pcie_set_wlan_control(common, N71_ID2_BIT0, true);
	if (error)
		return error;
	error = n71_pcie_poll_common(common, 0x1ac, 1);
	if (error)
		return error;
	error = n71_pcie_set_wlan_control(common, N71_ID2_BIT8, false);
	if (error)
		return error;
	/* N71 t-refclk-to-perst is 100us, as distinct from the earlier delay. */
	common->delay_us(common->context, 100);
	error = n71_pcie_set_wlan_control(common, N71_ID4_BIT0_INVERTED, false);
	if (error)
		return error;
	error = common->write32(common->context, N71_PCIE_COMMON, 0x4060, 3);
	if (error)
		return error;
	error = io->read_port(common->context, 0x210, &pending);
	if (error)
		return error;
	if (pending == 0xffffffff)
		return -EIO;
	if (pending) {
		error = io->write_port(common->context, 0x210, pending);
		if (error)
			return error;
	}
	return n71_pcie_set_wlan_control(common, N71_ID3_BIT8_INVERTED, true);
}

#endif /* N71_PCIE_PORT_H */
