/* SPDX-License-Identifier: GPL-2.0-only */
/* N71 HDQ byte codec only. No UART, GPIO, charger or gauge access. */
#ifndef N71_HDQ_CODEC_H
#define N71_HDQ_CODEC_H

#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stdbool.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
#endif

#define N71_HDQ_BYTE_SYMBOLS 8U
#define N71_HDQ_BAUD 57600U
#define N71_HDQ_STOP_BITS 2U

/* One HDQ byte is eight UART symbols, least significant bit first. */
static inline bool n71_hdq_encode_byte(u8 value, u8 *symbols,
				       unsigned int length)
{
	unsigned int bit;

	if (!symbols || length != N71_HDQ_BYTE_SYMBOLS)
		return false;
	for (bit = 0; bit < N71_HDQ_BYTE_SYMBOLS; bit++)
		symbols[bit] = (value & (1U << bit)) ? 0xfe : 0xc0;
	return true;
}

/* Apple N71 decodes one iff the unsigned received byte is greater than F8. */
static inline bool n71_hdq_decode_byte(const u8 *symbols,
				       unsigned int length, u8 *out)
{
	unsigned int bit;
	u8 value = 0;

	if (!symbols || !out || length != N71_HDQ_BYTE_SYMBOLS)
		return false;
	for (bit = 0; bit < N71_HDQ_BYTE_SYMBOLS; bit++)
		if (symbols[bit] > 0xf8)
			value |= 1U << bit;
	*out = value;
	return true;
}

/* Optional strict echo check; the Apple uncollated path is less strict. */
static inline bool n71_hdq_echo_matches(u8 command, const u8 *echo,
					unsigned int length)
{
	unsigned int bit;

	if (!echo || length != N71_HDQ_BYTE_SYMBOLS)
		return false;
	for (bit = 0; bit < N71_HDQ_BYTE_SYMBOLS; bit++)
		if (echo[bit] != ((command & (1U << bit)) ? 0xfe : 0xc0))
			return false;
	return true;
}

/* Join high/low/high only when stable; register meaning/presence is separate. */
static inline bool n71_hdq_stable_word(u8 high_before, u8 low, u8 high_after,
				       u16 *out)
{
	if (!out || high_before != high_after)
		return false;
	*out = ((u16)high_before << 8) | low;
	return true;
}

#endif /* N71_HDQ_CODEC_H */
