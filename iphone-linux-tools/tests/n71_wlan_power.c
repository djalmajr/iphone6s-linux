/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include "n71-wlan-power-contract.h"

int main(void)
{
	unsigned char address[2] = {0xaa, 0xbb}, value;
	unsigned int old, enable, requested;

	/* Kills address byte order and wrong GPIO register mutations. */
	assert(n71_wlan_reg_on_address(address));
	assert(address[0] == 0x08 && address[1] == 0xfc);
	assert(!n71_wlan_reg_on_address(NULL));
	for (old = 0; old < 256; old++) {
		for (enable = 0; enable < 2; enable++) {
			bool accepted;
			value = 0xa5;
			accepted = n71_wlan_reg_on_plan(0x8fc, old, enable, &value);
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
	assert(!n71_wlan_reg_on_plan(0x8f6, 0x00, true, &value));
	assert(!n71_wlan_reg_on_plan(0x8fc, 0x100, true, &value));
	assert(value == 0xa5);
	assert(!n71_wlan_reg_on_plan(0x8fc, 0x00, true, NULL));
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
	assert(n71_wlan_reg_on_plan(0x8fc, 0x00, true, &value) && value == 0x01);
	assert(!n71_wlan_reg_on_plan(0x8fc, 0x40, true, &value));
	puts("N71_WLAN_POWER_CONTRACT_OK");
	return 0;
}
