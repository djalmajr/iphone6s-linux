/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise actual PMGR callbacks, including failed I/O with partial effects. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define BIT(n) (1U << (n))
#define GENMASK(high, low) ((UINT32_MAX >> (31 - (high))) & (UINT32_MAX << (low)))
#define FIELD_PREP(mask, value) (((value) << __builtin_ctz(mask)) & (mask))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctz(mask))
#define container_of(pointer, type, member) ((type *)((char *)(pointer) - offsetof(type, member)))
#define GENPD_STATE_OFF 1
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)

typedef uint32_t u32;
struct device { int unused; };
struct generic_pm_domain { const char *name; int status, slock; };
struct reset_controller_dev { int unused; };
struct regmap { uint32_t word; };
struct apple_pmgr_ps {
	struct device *dev;
	struct generic_pm_domain genpd;
	struct reset_controller_dev rcdev;
	struct regmap *regmap;
	u32 offset;
	u32 min_state;
};
#define genpd_to_apple_pmgr_ps(p) container_of(p, struct apple_pmgr_ps, genpd)
#define rcdev_to_apple_pmgr_ps(p) container_of(p, struct apple_pmgr_ps, rcdev)

static struct regmap map;
static unsigned int io_count, fail_at, locks, unlocks, delays;
static int selected_error, partial_effect, held, require_lock;
static char trace[16];
static unsigned int trace_count;

static int io(struct regmap *selected, unsigned int offset, char operation)
{
	assert(selected == &map && offset == 0x801a0);
	assert(held == require_lock && trace_count < sizeof(trace) - 1);
	trace[trace_count++] = operation;
	trace[trace_count] = 0;
	io_count++;
	return io_count == fail_at ? selected_error : 0;
}

static int regmap_read(struct regmap *selected, unsigned int offset, u32 *word)
{
	int error = io(selected, offset, 'R');
	if (!error) *word = selected->word;
	return error;
}

static int regmap_write(struct regmap *selected, unsigned int offset, u32 word)
{
	int error = io(selected, offset, 'W');
	if (!error || partial_effect) selected->word = word;
	return error;
}

static int regmap_update_bits(struct regmap *selected, unsigned int offset,
			      unsigned int mask, unsigned int word)
{
	int error = io(selected, offset, 'U');
	if (!error || partial_effect)
		selected->word = (selected->word & ~mask) | (word & mask);
	return error;
}

static int pmgr_poll(struct regmap *selected, unsigned int offset, u32 *word,
		     unsigned int delay, unsigned int timeout)
{
	int error = io(selected, offset, 'P');
	assert(delay == 1 && timeout == 100);
	if (!error || partial_effect)
		selected->word = (selected->word & ~0xf0U) | ((selected->word & 0xfU) << 4);
	*word = selected->word;
	return error;
}

#define regmap_read_poll_timeout_atomic(m, o, v, condition, delay, timeout) \
	({ int poll_error = pmgr_poll(m, o, &(v), delay, timeout); \
	   poll_error ? poll_error : ((condition) ? 0 : -ETIMEDOUT); })
#define spin_lock_irqsave(lock, flags) do { \
	assert(*(lock) == 0 && !held); *(lock) = 1; held = 1; locks++; (flags) = 17; \
} while (0)
#define spin_unlock_irqrestore(lock, flags) do { \
	assert(*(lock) == 1 && held && (flags) == 17); \
	*(lock) = 0; held = 0; unlocks++; \
} while (0)

static void usleep_range(unsigned int low, unsigned int high)
{
	assert(!held && low == 1 && high == 2 && trace_count < sizeof(trace) - 1);
	trace[trace_count++] = 'D'; trace[trace_count] = 0; delays++;
}

#include "n71-pmgr-provider-functions.h"

static void prepare(struct apple_pmgr_ps *ps, u32 seed, unsigned int failure,
		    int error, int partial, int locked)
{
	map.word = seed; io_count = locks = unlocks = delays = trace_count = 0;
	fail_at = failure; selected_error = error; partial_effect = partial;
	held = 0; require_lock = locked; trace[0] = 0; ps->genpd.slock = 0;
}

static u32 update(u32 word, u32 mask, u32 value)
{
	return (word & ~mask) | (value & mask);
}

int main(void)
{
	struct apple_pmgr_ps ps = {.genpd = {.name = "i2c1"}, .regmap = &map,
				  .offset = 0x801a0};
	const int errors[] = {-EIO, -ENOMEM, -ETIMEDOUT};
	const u32 seeds[] = {0xa5f00340U, 0x500003f0U};
	unsigned int si, ei, partial, failure, automatic, state, operation, off, cases = 0;

	/* Kills swallowed errors, auto-enable after failed polls and wrong masks. */
	for (si = 0; si < 2; si++)
	for (ei = 0; ei < 3; ei++)
	for (partial = 0; partial < 2; partial++)
	for (automatic = 0; automatic < 2; automatic++)
	for (state = 0; state < 2; state++)
	for (failure = 0; failure <= (automatic ? 4U : 3U); failure++) {
		u32 target = state ? 0xf : 0, expected = seeds[si];
		unsigned int count = failure ? failure : (automatic ? 4U : 3U);
		int result;
		prepare(&ps, expected, failure, errors[ei], partial, 0);
		result = apple_pmgr_ps_set(&ps.genpd, target, automatic);
		assert(result == (failure ? errors[ei] : 0));
		assert(io_count == count && !locks && !unlocks && !delays);
		assert(!strncmp(trace, "RWPW", count) && strlen(trace) == count);
		if (count >= 2 && (failure != 2 || partial))
			expected = update(expected, 0x1000030fU, target);
		if (count >= 3 && (failure != 3 || partial))
			expected = update(expected, 0xf0, target << 4);
		if (count == 4 && (failure != 4 || partial))
			expected = update(expected, 0x300, 0) | 0x10000000;
		assert(map.word == expected && !held && !ps.genpd.slock);
		cases++;
	}

	/* Kills reset writes after failure, missing unlocks and reordered resets. */
	for (si = 0; si < 2; si++)
	for (ei = 0; ei < 3; ei++)
	for (partial = 0; partial < 2; partial++)
	for (operation = 0; operation < 3; operation++)
	for (off = 0; off < 2; off++)
	for (failure = 0; failure <= (operation == 2 ? 4U : 2U); failure++) {
		u32 expected = seeds[si];
		unsigned int index, count = failure ? failure : (operation == 2 ? 4U : 2U);
		int result;
		prepare(&ps, expected, failure, errors[ei], partial, 1);
		ps.genpd.status = off ? GENPD_STATE_OFF : 0;
		if (operation == 0) result = apple_pmgr_reset_assert(&ps.rcdev, 0);
		else if (operation == 1) result = apple_pmgr_reset_deassert(&ps.rcdev, 0);
		else result = apple_pmgr_reset_reset(&ps.rcdev, 0);
		assert(result == (failure ? errors[ei] : 0) && io_count == count);
		assert(!held && !ps.genpd.slock && locks == unlocks);
		assert(locks == (operation == 2 && (!failure || failure > 2) ? 2U : 1U));
		assert(delays == (operation == 2 && (!failure || failure > 2) ? 1U : 0U));
		if (operation == 2 && delays) {
			assert(trace[0] == 'U' && trace[1] == 'U' && trace[2] == 'D');
			assert(trace[3] == 'U' && (count != 4 || trace[4] == 'U'));
			assert(strlen(trace) == count + 1);
		} else assert(!strncmp(trace, "UU", count) && strlen(trace) == count);
		for (index = 1; index <= count; index++) {
			u32 mask, value;
			if (failure == index && !partial) continue;
			if (operation == 1 || index > 2) {
				mask = index == (operation == 1 ? 1U : 3U) ? 0x80000300U : 0x700;
				value = 0;
			} else {
				mask = index == 1 ? 0x700 : 0x80000300U;
				value = index == 1 ? 0x400 : 0x80000000U;
			}
			expected = update(expected, mask, value);
		}
		assert(map.word == expected);
		cases++;
	}

	/* Kills a read error being reported as an inactive reset. */
	for (si = 0; si < 2; si++)
	for (ei = 0; ei < 3; ei++)
	for (failure = 0; failure < 2; failure++) {
		int result;
		prepare(&ps, seeds[si], failure, errors[ei], 0, 0);
		result = apple_pmgr_reset_status(&ps.rcdev, 0);
		assert(result == (failure ? errors[ei] : !!(seeds[si] & 0x80000000U)));
		assert(io_count == 1 && !strcmp(trace, "R") && map.word == seeds[si]);
		assert(!locks && !unlocks && !delays);
		cases++;
	}
	printf("N71_PMGR_ERRORS_OK cases=%u\n", cases);
	return 0;
}
