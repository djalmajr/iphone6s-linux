/* SPDX-License-Identifier: GPL-2.0-only */
/* Selected D2255/N71 REG_ON facts. Pure calculations, no I2C or GPIO access. */
#ifndef N71_WLAN_POWER_CONTRACT_H
#define N71_WLAN_POWER_CONTRACT_H
#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stdbool.h>
#endif

#define N71_WLAN_PMU_ADDRESS 0x74U
#define N71_WLAN_PMU_PIN 10U
#define N71_WLAN_REG_ON_REGISTER 0x8fcU

/* D2255 GPIO mapper uses 0x8c0 + 6*pin below17; GPIO10 maps to0x8fc.
 * Dialog wire descriptor: two address bytes, not paged; high byte first.
 */
static inline bool n71_wlan_reg_on_address(unsigned char *out)
{
	if (!out)
		return false;
	out[0] = N71_WLAN_REG_ON_REGISTER >> 8;
	out[1] = N71_WLAN_REG_ON_REGISTER & 0xff;
	return true;
}

/* Restricted subset of the Apple GPIO writer: preserve all other bits.
 * Apple set-mode helper classifies value<0x40 as mode1; require bits7:6
 * and bits4:3 clear. Do not change
 * direction/drive settings, infer an unknown mode, or accept another register.
 * Physical activation and polarity still require separate verification.
 */
static inline bool n71_wlan_reg_on_plan(unsigned int reg, unsigned int old,
				      bool enabled, unsigned char *out)
{
	if (!out || reg != N71_WLAN_REG_ON_REGISTER || old > 0xff ||
	    (old & 0xd8) != 0)
		return false;
	*out = (old & ~1U) | (enabled ? 1U : 0U);
	return true;
}

/* Shared MFD regmap: reject stale mode/drive assumptions and return bit0 only.
 * The caller uses regmap_update_bits(mask=1), never a whole-byte PMIC write.
 */
static inline bool n71_wlan_shared_write_plan(unsigned int current_value,
					     unsigned int requested, unsigned char *bit)
{
	unsigned char planned;
	if (!bit || requested > 0xff || ((current_value ^ requested) & 0xfe) != 0 ||
	    !n71_wlan_reg_on_plan(N71_WLAN_REG_ON_REGISTER, current_value,
				 requested & 1, &planned))
		return false;
	*bit = planned & 1;
	return true;
}

#endif /* N71_WLAN_POWER_CONTRACT_H */
