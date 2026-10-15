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
#define N71_WLAN_REG_ON_REGISTER 0x914U

/* The pinned D2255 mapper selects 0x900 + 2*pin when pin < 17;
 * otherwise 0x8c0 + 6*pin. Pins above 20 are invalid.
 * CSEL LO selects its first source (w9), not its second (w10).
 */
static inline bool n71_d2255_gpio_register(unsigned int pin, unsigned int *out)
{
	if (!out || pin > 20)
		return false;
	*out = pin < 17 ? 0x900U + 2U * pin : 0x8c0U + 6U * pin;
	return true;
}

/* GPIO10 maps to0x914.
 * Dialog wire descriptor: two address bytes, not paged; high byte first.
 */
static inline bool n71_wlan_reg_on_address(unsigned char *out)
{
	unsigned int mapped;
	if (!out || !n71_d2255_gpio_register(N71_WLAN_PMU_PIN, &mapped) ||
	    mapped != N71_WLAN_REG_ON_REGISTER)
		return false;
	out[0] = mapped >> 8;
	out[1] = mapped & 0xff;
	return true;
}

/* Restricted subset of the N71 GPIO writer with packet polarity1.
 * Allow the original low-byte subset and exact observed latch bytes80/81.
 * The table-free writer preserves bits7:6; it clears bits0/3/4, then sets
 * bit0 for bool1. For80/81, changing bit0 alone reproduces that path.
 * This is not a set-mode operation:80 remains Apple classifier mode2.
 * Never change drive/mode, infer a table, or accept another register.
 * Physical activation still requires readback, level and verified cleanup.
 */
static inline bool n71_wlan_reg_on_plan(unsigned int reg, unsigned int old,
				      bool enabled, unsigned char *out)
{
	if (!out || reg != N71_WLAN_REG_ON_REGISTER || old > 0xff ||
	    ((old & 0xd8) != 0 && old != 0x80 && old != 0x81))
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
