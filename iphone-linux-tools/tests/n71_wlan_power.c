/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "n71-wlan-power-contract.h"

int main(void)
{
	unsigned char address[2] = {0xaa, 0xbb}, value;
	unsigned int old, enable, requested;
	unsigned int reg = 0xdead, pin;
	/* Kills reversed CSEL sources, boundary and upper-bank stride mutations. */
	const unsigned int registers[] = {
		0x900, 0x902, 0x904, 0x906, 0x908, 0x90a, 0x90c,
		0x90e, 0x910, 0x912, 0x914, 0x916, 0x918, 0x91a,
		0x91c, 0x91e, 0x920, 0x926, 0x92c, 0x932, 0x938,
	};
	for (pin = 0; pin < sizeof(registers) / sizeof(registers[0]); pin++) {
		assert(n71_d2255_gpio_register(pin, &reg));
		assert(reg == registers[pin]);
	}
	reg = 0xdead;
	assert(!n71_d2255_gpio_register(21, &reg));
	assert(!n71_d2255_gpio_register(~0U, &reg));
	assert(reg == 0xdead);
	assert(!n71_d2255_gpio_register(10, NULL));

	/* Kills address byte order and wrong GPIO register mutations. */
	assert(n71_wlan_reg_on_address(address));
	assert(address[0] == 0x09 && address[1] == 0x14);
	assert(!n71_wlan_reg_on_address(NULL));
	for (old = 0; old < 256; old++) {
		for (enable = 0; enable < 2; enable++) {
			bool accepted;
			value = 0xa5;
			accepted = n71_wlan_reg_on_plan(0x914, old, enable, &value);
			/* Kills mode guard removal and unrelated-bit clearing. */
			if ((old & 0xc0) == 0 && !(old & 0x18)) {
				assert(accepted && value == ((old & 0xfe) | enable));
				assert((value & 0xfe) == (old & 0xfe));
			} else {
				assert(!accepted && value == 0xa5);
			}
		}
	}
	value = 0xa5;
	assert(!n71_wlan_reg_on_plan(0x8fc, 0x00, true, &value));
	assert(!n71_wlan_reg_on_plan(0x914, 0x100, true, &value));
	assert(value == 0xa5);
	assert(!n71_wlan_reg_on_plan(0x914, 0x00, true, NULL));
	/* Kills shared-owner mismatch, wide request and whole-byte output mutations. */
	for (old = 0; old < 256; old++) {
		for (requested = 0; requested < 256; requested++) {
			bool allowed = (old & 0xd8) == 0 && (old & 0xfe) == (requested & 0xfe);
			value = 0xa5;
			assert(n71_wlan_shared_write_plan(old, requested, &value) == allowed);
			assert(value == (allowed ? (requested & 1) : 0xa5));
		}
	}
	value = 0xa5;
	assert(!n71_wlan_shared_write_plan(0x00, 0x100, &value));
	assert(!n71_wlan_shared_write_plan(0x100, 0x00, &value));
	assert(!n71_wlan_shared_write_plan(0x00, 0x01, NULL));
	assert(value == 0xa5);
	/* Physical regression: Apple mode1 is value<0x40, not bit6 set. */
	assert(n71_wlan_reg_on_plan(0x914, 0x00, true, &value) && value == 0x01);
	assert(!n71_wlan_reg_on_plan(0x914, 0x40, true, &value));
	puts("N71_WLAN_POWER_CONTRACT_OK");
	return 0;
}
