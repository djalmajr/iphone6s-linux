/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-dart-observe.h"

struct mock {
	u32 values[N71_DART_WORDS];
	unsigned int reads, guards, fail_read, fail_guard, change;
	int failure;
};

static int quiet(void *context)
{
	struct mock *mock = context;
	return ++mock->guards == mock->fail_guard ? mock->failure : 0;
}

static int read32(void *context, u32 offset, u32 *value)
{
	struct mock *mock = context;
	unsigned int index = mock->reads % N71_DART_WORDS;
	u32 expected = index == 0 ? 0 : index == 1 ? 0xc : index == 2 ? 0x10 :
		0x40 + (index - 3) * 4;
	assert(offset == expected && mock->guards == mock->reads + 1);
	if (++mock->reads == mock->fail_read)
		return mock->failure;
	*value = mock->values[index];
	if (mock->reads == mock->change)
		*value ^= 1;
	return 0;
}

static void initialize(struct mock *mock)
{
	unsigned int index;
	memset(mock, 0, sizeof(*mock));
	mock->failure = -EACCES;
	mock->values[1] = 0x01800280;
	mock->values[2] = 0x82000005;
	for (index = 0; index < 16; index++)
		mock->values[index + 3] = 0x01234000 + index;
	mock->values[3] = 0x80123456;
	mock->values[18] = 0x80abcdef;
}

int main(void)
{
	struct mock mock;
	struct n71_dart_io io = {&mock, quiet, read32};
	struct n71_dart_observation result, sentinel;
	unsigned int index;
	initialize(&mock);
	assert(n71_dart_observe(&io, &result) == 0);
	assert(mock.reads == 38 && mock.guards == 39);
	assert(result.command == 0 && result.tcr == 0x01800280 &&
	       result.error == 0x82000005 && result.enabled == 5 && result.valid_ttbrs == 0x8001);
	/* Mutation captured: dropping, truncating or reordering any TTBR loses restore state. */
	for (index = 0; index < 16; index++)
		assert(result.ttbr[index] == mock.values[index + 3]);
	memset(&sentinel, 0xa5, sizeof(sentinel));
	for (index = 1; index <= 38; index++) {
		initialize(&mock); result = sentinel; mock.fail_read = index;
		assert(n71_dart_observe(&io, &result) == -EACCES && mock.reads == index);
		assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
	}
	for (index = 1; index <= 39; index++) {
		initialize(&mock); result = sentinel; mock.fail_guard = index;
		assert(n71_dart_observe(&io, &result) == -EACCES && mock.reads == index - 1);
		assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
	}
	for (index = 20; index <= 38; index++) {
		initialize(&mock); result = sentinel; mock.change = index;
		assert(n71_dart_observe(&io, &result) == -EAGAIN);
		assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
	}
	for (index = 0; index < N71_DART_WORDS; index++) {
		initialize(&mock); result = sentinel; mock.values[index] = 0xffffffffU;
		assert(n71_dart_observe(&io, &result) == -EIO);
		assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
	}
	initialize(&mock); result = sentinel; mock.values[0] = 8;
	assert(n71_dart_observe(&io, &result) == -EBUSY && mock.reads == 1);
	assert(memcmp(&result, &sentinel, sizeof(result)) == 0);
	initialize(&mock); mock.fail_guard = 39; mock.failure = 1;
	assert(n71_dart_observe(&io, &result) == -EIO);
	initialize(&mock); mock.fail_read = 1; mock.failure = 1;
	assert(n71_dart_observe(&io, &result) == -EIO);
	assert(n71_dart_observe(NULL, &result) == -EINVAL);
	assert(n71_dart_observe(&io, NULL) == -EINVAL);
	io.quiet = NULL;
	assert(n71_dart_observe(&io, &result) == -EINVAL);
	puts("N71_DART_OBSERVE_OK");
	return 0;
}
