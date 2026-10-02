/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-hdq-codec.h"

int main(void)
{
	const u8 one[] = {0xfe, 0xc0, 0xc0, 0xc0, 0xc0, 0xc0, 0xc0, 0xc0};
	const u8 top[] = {0xc0, 0xc0, 0xc0, 0xc0, 0xc0, 0xc0, 0xc0, 0xfe};
	u8 symbols[8], value;
	u16 word;
	unsigned int sample, bit, length;

	assert(N71_HDQ_BAUD == 57600 && N71_HDQ_STOP_BITS == 2);
	assert(n71_hdq_encode_byte(1, symbols, 8));
	assert(memcmp(symbols, one, 8) == 0);
	assert(n71_hdq_encode_byte(128, symbols, 8));
	assert(memcmp(symbols, top, 8) == 0);
	/* All receive byte values, at every bit: threshold is independent of TX. */
	for (sample = 0; sample < 256; sample++) {
		for (bit = 0; bit < 8; bit++) {
			memset(symbols, 0, 8);
			symbols[bit] = sample;
			assert(n71_hdq_decode_byte(symbols, 8, &value));
			assert(value == (sample >= 249 ? (1U << bit) : 0));
		}
		assert(n71_hdq_encode_byte(sample, symbols, 8));
		for (bit = 0; bit < 8; bit++)
			assert(symbols[bit] == ((sample >> bit) & 1 ? 254 : 192));
		assert(n71_hdq_echo_matches(sample, symbols, 8));
		assert(n71_hdq_decode_byte(symbols, 8, &value));
		assert(value == sample);
		for (bit = 0; bit < 8; bit++) {
			symbols[bit] ^= 1;
			assert(!n71_hdq_echo_matches(sample, symbols, 8));
			symbols[bit] ^= 1;
		}
	}
	for (length = 0; length < 17; length++) {
		if (length == 8)
			continue;
		memset(symbols, 0x5a, 8);
		value = 0xa5;
		assert(!n71_hdq_encode_byte(1, symbols, length));
		for (bit = 0; bit < 8; bit++)
			assert(symbols[bit] == 0x5a);
		assert(!n71_hdq_decode_byte(symbols, length, &value));
		assert(value == 0xa5);
		assert(!n71_hdq_echo_matches(1, symbols, length));
	}
	assert(!n71_hdq_encode_byte(1, NULL, 8));
	assert(!n71_hdq_decode_byte(NULL, 8, &value));
	assert(!n71_hdq_decode_byte(symbols, 8, NULL));
	assert(!n71_hdq_echo_matches(1, NULL, 8));
	assert(n71_hdq_stable_word(0x12, 0x34, 0x12, &word));
	assert(word == 0x1234);
	word = 0xa55a;
	assert(!n71_hdq_stable_word(0x12, 0x34, 0x13, &word));
	assert(word == 0xa55a);
	assert(!n71_hdq_stable_word(0x12, 0x34, 0x12, NULL));
	assert(n71_hdq_stable_word(0xff, 0xff, 0xff, &word));
	assert(word == 0xffff); /* Not a presence proof; can be a signed field. */
	puts("N71_HDQ_CODEC_OK");
	return 0;
}
