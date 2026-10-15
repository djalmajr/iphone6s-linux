/* SPDX-License-Identifier: GPL-2.0-only */
/* Bounded live observations; the caller holds the domain/provider lifetime. */
#ifndef N71_DMA_OBSERVE_H
#define N71_DMA_OBSERVE_H
#include "n71-pcie-contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#else
#include <errno.h>
typedef uint64_t u64;
#endif

#define N71_DMA_WORDS 8U
#define N71_DMA_TIME_VALID 1U
#define N71_DMA_TRANSLATION_VALID 2U
#define N71_DMA_WORD_VALID(index) (4U << (index))
#define N71_DMA_VALID_MASK ((1U << (N71_DMA_WORDS + 2)) - 1)
#define N71_DMA_PA_MAX ((1ULL << 36) - 1)

struct n71_dma_request {
	u64 iova, aperture_start, aperture_end;
	bool requested;
};

struct n71_dma_io {
	void *context;
	int (*validate)(void *context);
	int (*time_ns)(void *context, u64 *value);
	int (*translate)(void *context, u64 iova, u64 *physical);
	int (*read32)(void *context, u32 offset, u32 *value);
};

struct n71_dma_sample {
	u64 time_ns, physical;
	u32 words[N71_DMA_WORDS], valid;
};

struct n71_dma_observation {
	u64 iova;
	struct n71_dma_sample samples[2];
	unsigned int complete;
	int error;
	bool stable;
};

static inline int n71_dma_error(int error)
{
	return error > 0 ? -EIO : error;
}

static inline u32 n71_dma_offset(unsigned int index)
{
	return index == 0 ? 0 : index == 1 ? 0xc : index == 2 ? 0x10 :
		index == 3 ? 0x1c : 0x40 + (index - 4) * 4;
}

static inline int n71_dma_observe(const struct n71_dma_io *io,
				  const struct n71_dma_request *request,
				  struct n71_dma_observation *out)
{
	struct n71_dma_observation result = {0};
	unsigned int sample, index;
	int error = -EINVAL;

	if (!out)
		return -EINVAL;
	if (!io || !request || !io->validate || !io->time_ns || !io->translate || !io->read32)
		goto done;
	result.iova = request->iova;
	if (!request->requested || request->aperture_start > request->aperture_end ||
	    request->aperture_end > 0xffffffffULL || request->iova < request->aperture_start ||
	    request->iova > request->aperture_end)
		goto done;
	for (sample = 0; sample < 2; sample++) {
		struct n71_dma_sample *row = &result.samples[sample];

		error = n71_dma_error(io->validate(io->context));
		if (error)
			goto done;
		error = n71_dma_error(io->time_ns(io->context, &row->time_ns));
		if (error)
			goto done;
		row->valid |= N71_DMA_TIME_VALID;
		error = n71_dma_error(io->validate(io->context));
		if (error)
			goto done;
		error = n71_dma_error(io->translate(io->context, request->iova, &row->physical));
		if (error)
			goto done;
		row->valid |= N71_DMA_TRANSLATION_VALID;
		if (row->physical > N71_DMA_PA_MAX) {
			error = -ERANGE;
			goto done;
		}
		for (index = 0; index < N71_DMA_WORDS; index++) {
			error = n71_dma_error(io->validate(io->context));
			if (error)
				goto done;
			error = n71_dma_error(io->read32(io->context, n71_dma_offset(index), &row->words[index]));
			if (error)
				goto done;
			row->valid |= N71_DMA_WORD_VALID(index);
			if (row->words[index] == 0xffffffffU) {
				error = -EIO;
				goto done;
			}
		}
		result.complete++;
	}
	error = n71_dma_error(io->validate(io->context));
	if (error)
		goto done;
	error = -EAGAIN;
	if (result.samples[1].time_ns < result.samples[0].time_ns ||
	    result.samples[0].physical != result.samples[1].physical)
		goto done;
	for (index = 0; index < N71_DMA_WORDS; index++)
		if (result.samples[0].words[index] != result.samples[1].words[index])
			goto done;
	if (result.samples[0].words[0] & 8U)
		goto done;
	result.stable = true;
	error = 0;
done:
	result.error = error;
	*out = result;
	return error;
}
#endif /* N71_DMA_OBSERVE_H */
