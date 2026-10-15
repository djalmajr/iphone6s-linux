// SPDX-License-Identifier: GPL-2.0-only
/* Compile the actual patched installer and domain configuration with modeled APIs. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#define BIT(n) (1ULL << (n))
#define APPLE_DART_PTE_VALID BIT(0)
typedef uint64_t dart_iopte;
enum { APPLE_DART, APPLE_DART2 };
enum { DART_S5L8960X, DART_T8020, DART_T8110 };
struct io_pgtable_cfg {
	unsigned long quirks, pgsize_bitmap;
	unsigned int ias, oas;
	bool coherent_walk;
	void *iommu_dev;
};
struct dart_io_pgtable {
	struct {
		int fmt;
		struct io_pgtable_cfg cfg;
	} iop;
};
struct apple_dart_hw { int type; };
struct apple_dart {
	struct apple_dart_hw *hw;
	unsigned long pgsize;
	unsigned int oas;
	void *dev;
};
static dart_iopte table[512], slot, fake_pa;
static bool race;
static unsigned int barriers, exchanges, encodes;

static uint64_t model_pa(dart_iopte *pointer)
{
	assert(pointer == table);
	return fake_pa;
}
#define __pa(pointer) model_pa(pointer)

static dart_iopte paddr_to_iopte(uint64_t pa, struct dart_io_pgtable *data)
{
	encodes++;
	assert(exchanges == 0 && barriers == 0);
	return data->iop.fmt == APPLE_DART ? pa & 0xffffff000ULL :
		(pa >> 4) & 0x3ffffffc00ULL;
}

static void dma_wmb(void)
{
	assert(encodes == 1 && exchanges == 0 && barriers == 0);
	barriers++;
	if (race)
		slot = 0xabc003;
}

static dart_iopte cmpxchg64_relaxed(dart_iopte *pointer, dart_iopte expected,
				   dart_iopte value)
{
	dart_iopte old = *pointer;

	assert(pointer == &slot && barriers == 1 && exchanges == 0);
	exchanges++;
	if (old == expected)
		*pointer = value;
	return old;
}

#include "pmd-subject.h"

int main(void)
{
	const uint64_t addresses[] = {0, 0x1000, 0x123456789ULL, 0xffffff000ULL,
		0x1000000000ULL, UINT64_MAX};
	const unsigned long quirks[] = {0, BIT(10), BIT(9), BIT(10) | BIT(9)};
	unsigned int cases = 0;

	for (int type = DART_S5L8960X; type <= DART_T8110; type++) {
		struct apple_dart_hw hardware = {.type = type};
		struct apple_dart dart = {.hw = &hardware, .pgsize = 4096,
			.oas = 36, .dev = table};
		struct io_pgtable_cfg cfg = selected_config(&dart);

		/* Kills broad hardware selection and dropped cfg fields. */
		assert(cfg.quirks == (type == DART_S5L8960X ? BIT(10) : 0));
		assert(cfg.pgsize_bitmap == 4096 && cfg.ias == 32 && cfg.oas == 36);
		assert(cfg.coherent_walk && cfg.iommu_dev == table);
		cases++;
	}
	for (int fmt = APPLE_DART; fmt <= APPLE_DART2; fmt++)
	for (unsigned int q = 0; q < sizeof(quirks) / sizeof(quirks[0]); q++)
	for (unsigned int a = 0; a < sizeof(addresses) / sizeof(addresses[0]); a++)
	for (int occupied = 0; occupied < 2; occupied++)
	for (int racing = 0; racing < 2; racing++)
	for (int replacing = 0; replacing < 2; replacing++) {
		struct dart_io_pgtable data = {.iop = {.fmt = fmt,
			.cfg = {.quirks = quirks[q]}}};
		dart_iopte initial = occupied ? 0xdef003 : 0;
		dart_iopte expected = replacing ? initial : 0;
		dart_iopte actual_old = racing ? 0xabc003 : initial;
		dart_iopte encoded = fmt == APPLE_DART ? addresses[a] & 0xffffff000ULL :
			(addresses[a] >> 4) & 0x3ffffffc00ULL;
		dart_iopte flags = fmt == APPLE_DART && (quirks[q] & BIT(10)) ? 3 : 1;
		dart_iopte new = encoded | flags;

		fake_pa = addresses[a];
		race = racing;
		slot = initial;
		barriers = exchanges = encodes = 0;
		/* Kills missing/extra flags, PA damage, skipped barrier and clobbered CAS winner. */
		assert(dart_install_table(table, &slot, expected, &data) == actual_old);
		assert(slot == (actual_old == expected ? new : actual_old));
		assert(barriers == 1 && exchanges == 1 && encodes == 1);
		cases++;
	}
	printf("N71_DART_PMD_OK cases=%u\n", cases);
	return 0;
}
