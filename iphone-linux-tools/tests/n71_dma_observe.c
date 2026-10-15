/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
/* Linux cleanup.h defines this function-like macro in the real build. */
#define guard(...) invalid_kernel_guard_macro
#include "n71-dma-observe.h"

static unsigned int cases;
#define OBS(io, request, out) (++cases, n71_dma_observe(io, request, out))

struct mock {
	u64 iova, physical[2], time[2];
	u32 words[2][N71_DMA_WORDS];
	unsigned int effects, guards, times, translations, reads;
	unsigned int fail_effect, fail_guard;
	int failure;
};

static int validate(void *context)
{
	struct mock *mock = context;
	return ++mock->guards == mock->fail_guard ? mock->failure : 0;
}

static int effect(struct mock *mock)
{
	assert(mock->guards == mock->effects + 1);
	return ++mock->effects == mock->fail_effect ? mock->failure : 0;
}

static int clock_ns(void *context, u64 *value)
{
	struct mock *mock = context;
	unsigned int sample = mock->times++;
	int error = effect(mock);

	assert(sample < 2);
	assert(mock->effects == 1 + sample * 10);
	if (!error)
		*value = mock->time[sample];
	return error;
}

static int translate(void *context, u64 iova, u64 *physical)
{
	struct mock *mock = context;
	unsigned int sample = mock->translations++;
	int error = effect(mock);

	assert(sample < 2 && iova == mock->iova);
	assert(mock->effects == 2 + sample * 10);
	if (!error)
		*physical = mock->physical[sample];
	return error;
}

static int read32(void *context, u32 offset, u32 *value)
{
	const u32 offsets[] = {0, 0xc, 0x10, 0x1c, 0x40, 0x44, 0x48, 0x4c};
	struct mock *mock = context;
	unsigned int index = mock->reads++;
	int error = effect(mock);

	assert(index < 16 && offset == offsets[index % 8]);
	assert(mock->effects == 3 + index + (index / 8) * 2);
	if (!error)
		*value = mock->words[index / 8][index % 8];
	return error;
}

static struct n71_dma_io initialize(struct mock *mock)
{
	unsigned int sample, index;

	memset(mock, 0, sizeof(*mock));
	mock->iova = 0x3ffff028;
	mock->failure = -EACCES;
	for (sample = 0; sample < 2; sample++) {
		mock->time[sample] = 100 + sample;
		mock->physical[sample] = 0x800012028ULL;
		mock->words[sample][1] = 0x80;
		mock->words[sample][2] = 0x80000102;
		mock->words[sample][3] = 0x3ffff028;
		for (index = 4; index < 8; index++)
			mock->words[sample][index] = 0x80801234 + index;
	}
	return (struct n71_dma_io){mock, validate, clock_ns, translate, read32};
}

static void prefix_valid(const struct n71_dma_observation *result, unsigned int completed_effects)
{
	unsigned int sample;

	assert(!result->stable && result->complete == completed_effects / 10);
	for (sample = 0; sample < 2; sample++) {
		unsigned int count = completed_effects > sample * 10 ? completed_effects - sample * 10 : 0;
		if (count > 10)
			count = 10;
		assert(result->samples[sample].valid == (1U << count) - 1);
		if (count >= 1)
			assert(result->samples[sample].time_ns == 100 + sample);
		if (count >= 2)
			assert(result->samples[sample].physical == 0x800012028ULL);
	}
}

int main(void)
{
	struct mock mock;
	struct n71_dma_io io = initialize(&mock), broken;
	struct n71_dma_request request = {0x3ffff028, 0, 0xffffffffULL, true}, invalid;
	struct n71_dma_observation result;
	unsigned int index;

	assert(OBS(&io, &request, &result) == 0 && result.stable && result.complete == 2);
	assert(result.iova == request.iova && result.error == 0);
	assert(mock.guards == 21 && mock.effects == 20 && mock.reads == 16 && mock.translations == 2 && mock.times == 2);
	for (index = 0; index < 2; index++) {
		assert(result.samples[index].valid == N71_DMA_VALID_MASK);
		assert(result.samples[index].physical == 0x800012028ULL);
		assert(result.samples[index].time_ns == 100 + index);
		assert(memcmp(result.samples[index].words, mock.words[index], sizeof(mock.words[index])) == 0);
	}
	for (index = 1; index <= 20; index++) {
		io = initialize(&mock); mock.fail_effect = index;
		assert(OBS(&io, &request, &result) == -EACCES && result.error == -EACCES);
		assert(mock.effects == index && mock.guards == index);
		prefix_valid(&result, index - 1);
	}
	for (index = 1; index <= 21; index++) {
		io = initialize(&mock); mock.fail_guard = index;
		assert(OBS(&io, &request, &result) == -EACCES && result.error == -EACCES);
		assert(mock.effects == index - 1 && mock.guards == index);
		prefix_valid(&result, index - 1);
	}
	for (index = 1; index <= 20; index++) {
		io = initialize(&mock); mock.fail_effect = index; mock.failure = 1;
		assert(OBS(&io, &request, &result) == -EIO && result.error == -EIO);
		prefix_valid(&result, index - 1);
	}
	io = initialize(&mock); mock.fail_guard = 21; mock.failure = 1;
	assert(OBS(&io, &request, &result) == -EIO); prefix_valid(&result, 20);
	for (index = 0; index < 8; index++) {
		io = initialize(&mock); mock.words[1][index] ^= 1;
		assert(OBS(&io, &request, &result) == -EAGAIN && !result.stable && result.complete == 2);
		assert(result.samples[1].words[index] == mock.words[1][index]);
		assert(result.samples[0].valid == N71_DMA_VALID_MASK && result.samples[1].valid == N71_DMA_VALID_MASK);
		io = initialize(&mock); mock.words[0][index] = 0xffffffffU;
		assert(OBS(&io, &request, &result) == -EIO && result.complete == 0 && !result.stable);
		assert(result.samples[0].words[index] == 0xffffffffU);
		assert(result.samples[0].valid == (1U << (index + 3)) - 1);
	}
	io = initialize(&mock); mock.physical[1]++;
	assert(OBS(&io, &request, &result) == -EAGAIN && !result.stable && result.complete == 2);
	assert(result.samples[0].physical != result.samples[1].physical);
	io = initialize(&mock); mock.time[1] = 99;
	assert(OBS(&io, &request, &result) == -EAGAIN && !result.stable);
	io = initialize(&mock); mock.words[0][0] = mock.words[1][0] = 8;
	assert(OBS(&io, &request, &result) == -EAGAIN && !result.stable && result.complete == 2);
	io = initialize(&mock); mock.physical[0] = mock.physical[1] = 0;
	assert(OBS(&io, &request, &result) == 0 && result.stable && result.samples[0].physical == 0);
	io = initialize(&mock); mock.physical[0] = mock.physical[1] = N71_DMA_PA_MAX;
	assert(OBS(&io, &request, &result) == 0 && result.samples[1].physical == N71_DMA_PA_MAX);
	io = initialize(&mock); mock.physical[0] = 1ULL << 36;
	assert(OBS(&io, &request, &result) == -ERANGE && result.samples[0].valid == 3 && mock.reads == 0);
	for (index = 0; index < 2; index++) {
		io = initialize(&mock); invalid = request;
		invalid.iova = mock.iova = index ? 0xffffffffULL : 0;
		assert(OBS(&io, &invalid, &result) == 0 && result.iova == invalid.iova);
	}
	for (index = 0; index < 6; index++) {
		io = initialize(&mock); invalid = request;
		switch (index) {
		case 0: invalid.requested = false; break;
		case 1: invalid.aperture_end = 1ULL << 32; break;
		case 2: invalid.aperture_start = request.iova + 1; break;
		case 3: invalid.aperture_end = request.iova - 1; break;
		case 4: invalid.iova = ~0ULL; break;
		case 5: invalid.aperture_start = 2; invalid.aperture_end = 1; break;
		}
		assert(OBS(&io, &invalid, &result) == -EINVAL && result.error == -EINVAL);
		assert(mock.guards == 0 && mock.effects == 0 && !result.stable && result.complete == 0);
		assert(result.samples[0].valid == 0 && result.samples[1].valid == 0);
	}
	for (index = 0; index < 7; index++) {
		io = initialize(&mock); broken = io;
		switch (index) {
		case 0: broken.validate = NULL; break;
		case 1: broken.time_ns = NULL; break;
		case 2: broken.translate = NULL; break;
		case 3: broken.read32 = NULL; break;
		}
		assert(OBS(index == 4 ? NULL : &broken, index == 5 ? NULL : &request,
			   index == 6 ? NULL : &result) == -EINVAL);
		assert(mock.guards == 0 && mock.effects == 0);
	}
	printf("N71_DMA_OBSERVE_OK cases=%u; callbacks modeled, no hardware\n", cases);
	return 0;
}
