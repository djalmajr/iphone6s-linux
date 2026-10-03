/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-pcie-ecam.h"

struct mock {
	u32 offset;
	unsigned int calls;
	int error;
};

static int read32(void *context, u32 offset, u32 *value)
{
	struct mock *mock = context;

	mock->offset = offset;
	mock->calls++;
	*value = 0xd4c3b2a1;
	return mock->error;
}

int main(void)
{
	struct n71_pcie_ecam_location location, sentinel;
	struct mock mock = {0};
	struct n71_pcie_ecam_io io = {&mock, read32};
	unsigned int bus, devfn, size, offset;
	u32 out;
	int error;

	/* Exhaustive root/endpoint coordinates and 256 devfns for two buses. */
	for (bus = 0; bus < 2; bus++)
		for (devfn = 0; devfn < 256; devfn++) {
			memset(&location, 0xa5, sizeof(location));
			memcpy(&sentinel, &location, sizeof(location));
			error = n71_pcie_ecam_locate(0x1000000, bus, devfn, 0, 4, &location);
			if (devfn == (bus == 0 ? 8U : 0U)) {
				assert(error == 0 && location.root == (bus == 0));
				assert(location.dword_offset == (bus == 0 ? 0x8000U : 0x100000U));
			} else {
				assert(error == -ENODEV);
				assert(memcmp(&location, &sentinel, sizeof(location)) == 0);
			}
		}
	/* Every legal byte/word/DWORD in both 4 KiB functions, and crossing offsets. */
	for (bus = 0; bus < 2; bus++)
		for (size = 1; size <= 4; size++)
			for (offset = 0; offset <= 0x1004; offset++) {
				mock.calls = 0;
				out = 0xdeadbeef;
				error = n71_pcie_ecam_read(&io, 0x1000000, bus,
						   bus == 0 ? 8 : 0, (int)offset, size, &out);
				if (size != 3 && offset <= 0x1000 - size && offset % size == 0) {
					u32 expected = size == 4 ? 0xd4c3b2a1 :
						(0xd4c3b2a1 >> (8 * (offset % 4))) &
						(size == 2 ? 0xffffU : 0xffU);
					assert(error == 0 && mock.calls == 1 && out == expected);
					assert(mock.offset == (bus == 0 ? 0x8000U : 0x100000U) +
						(offset & ~3U));
				} else {
					assert(error == -EINVAL && mock.calls == 0 && out == 0xdeadbeef);
				}
			}
	for (size = 0; size < 4; size++) {
		mock.error = size == 0 ? -EIO : size == 1 ? -ETIMEDOUT : size == 2 ? 1 : 255;
		out = 0xdeadbeef;
		assert(n71_pcie_ecam_read(&io, 0x1000000, 1, 0, 0, 4, &out) ==
			(mock.error < 0 ? mock.error : -EIO));
		assert(out == 0xdeadbeef);
	}
	mock.calls = 0; mock.error = 0; out = 0xdeadbeef;
	assert(n71_pcie_ecam_read(&io, 0x2000000, 1, 0, 0, 4, &out) == -EINVAL);
	assert(n71_pcie_ecam_read(&io, 0x1000000, 2, 0, 0, 4, &out) == -ENODEV);
	assert(n71_pcie_ecam_read(&io, 0x1000000, 0, 0, 0, 4, &out) == -ENODEV);
	assert(n71_pcie_ecam_read(&io, 0x1000000, 1, 0, -1, 1, &out) == -EINVAL);
	assert(n71_pcie_ecam_read(&io, 0x1000000, 1, 0, 0, 0, &out) == -EINVAL);
	assert(n71_pcie_ecam_read(&io, 0x1000000, 1, 0, 0, 0xffffffff, &out) == -EINVAL);
	assert(n71_pcie_ecam_read(NULL, 0x1000000, 1, 0, 0, 4, &out) == -EINVAL);
	assert(n71_pcie_ecam_read(&io, 0x1000000, 1, 0, 0, 4, NULL) == -EINVAL);
	assert(mock.calls == 0 && out == 0xdeadbeef);
	io.read32 = NULL;
	assert(n71_pcie_ecam_read(&io, 0x1000000, 1, 0, 0, 4, &out) == -EINVAL);
	assert(n71_pcie_ecam_locate(0x1000000, 1, 0, 0, 4, NULL) == -EINVAL);
	puts("N71_PCIE_ECAM_READONLY_OK");
	return 0;
}
