/* Real runtime policy; ECAM effects and upstream driver ordering are modeled. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71-brcmfmac-config.h"

static struct {
	u32 registers[2][64], original[2][64];
	unsigned int reads, writes, events, fail_read, fail_write, drop_write, drift_read;
	int write_error;
	struct n71_brcmfmac_config state;
} mock;
static unsigned int cases;

static u32 peek(bool root, u32 where, unsigned int size)
{
	u32 mask = size == 4 ? 0xffffffffU : (1U << (size * 8)) - 1;
	return (mock.registers[root ? 0 : 1][where / 4] >> ((where & 3) * 8)) & mask;
}

static int read_config(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	assert(context == &mock && value && where < 256 && !(where % size));
	if (++mock.reads == mock.fail_read)
		return -ETIMEDOUT;
	if (mock.reads == mock.drift_read)
		mock.registers[1][0x80 / 4] ^= 0x1000;
	*value = peek(root, where, size);
	return 0;
}

static int write_config(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	assert(context == &mock && where < 256 && !(where % size));
	assert(size == 2 || size == 4);
	if (++mock.writes == mock.fail_write)
		return mock.write_error;
	if (mock.writes == mock.drop_write)
		return 0;
	if (where == 0x98) {
		assert(!root && size == 4 && value == 1);
		mock.events++;
	}
	u32 *reg = &mock.registers[root ? 0 : 1][where / 4];
	unsigned int shift = (where & 3) * 8;
	if (where == 0xbc && size == 4) {
		/* Real STATUS semantics make an accidental DWORD visibly destructive. */
		*reg = (*reg & ~(value & 0xffff0000U) & 0xffff0000U) | (value & 0xffffU);
	} else {
		u32 mask = size == 4 ? 0xffffffffU : 0xffffU << shift;
		*reg = (*reg & ~mask) | ((value << shift) & mask);
	}
	return 0;
}

static const struct n71_scan_io io = {&mock, read_config, write_config};

static void fresh(void)
{
	memset(&mock, 0, sizeof(mock));
	mock.registers[0][0] = 0x1004106b;
	mock.registers[1][0] = 0x43a314e4;
	mock.registers[0][0x44 / 4] = 8;
	mock.registers[1][0x4c / 4] = 0x4008;
	mock.registers[1][0x58 / 4] = 0x00886805;
	mock.registers[1][0xbc / 4] = 0xf0000003;
	mock.registers[1][0x80 / 4] = 0x18003000;
	memcpy(mock.original, mock.registers, sizeof(mock.original));
	mock.write_error = -EIO;
	cases++;
}

static void capture(void)
{
	assert(n71_brcmfmac_capture(&io, &mock.state) == 0);
	assert(mock.state.active && !mock.state.error && !mock.writes);
}

static int emit(bool root, u32 where, unsigned int size, u32 value, unsigned int slots)
{
	struct n71_msi_config_request request = {{root, where, value, size}, slots};
	return n71_brcmfmac_write(&io, &mock.state, &request);
}

static void driver(void)
{
	assert(emit(true, 4, 2, 6, 0) == 0);
	assert(emit(false, 4, 2, 6, 0) == 0);
	assert(peek(true, 4, 2) == 6 && peek(false, 4, 2) == 6);
	assert(emit(true, 0x44, 2, 8, 0) == 0);
	assert(emit(false, 0x4c, 2, 0x4008, 0) == 0);
	assert(emit(false, 0x80, 4, 0x18000000, 0) == 0);
	assert(peek(false, 0x80, 4) == 0x18000000);
	assert(emit(false, 0xbc, 4, 0xf0000000, 0) == 0);
	assert(peek(false, 0xbc, 4) == 0xf0000000);
	assert(emit(false, 0x98, 4, 1, 0) == 0);
	assert(emit(false, 0x98, 4, 1, 0) == 0);
	assert(mock.events == 2);
	assert(emit(false, 4, 2, 0x406, 1) == 0);
	assert(emit(false, 0x5c, 4, 0xbffff000U, 1) == 0);
	assert(emit(false, 0x60, 4, 0, 1) == 0);
	assert(emit(false, 0x64, 2, 8, 1) == 0);
	assert(emit(false, 0x5a, 2, 0x89, 1) == 0);
	assert(peek(false, 0x5a, 2) == 0x89);
	unsigned int writes = mock.writes;
	assert(emit(false, 0x5c, 4, 0xbffff000U, 1) == 0);
	assert(mock.writes == writes);
	assert(emit(false, 0x5a, 2, 0x88, 1) == 0);
	assert(emit(false, 0x5c, 4, 0, 1) == 0);
	assert(emit(false, 0x64, 2, 0, 1) == 0);
}

static void baseline_restored(void)
{
	assert(!mock.state.active);
	for (unsigned int root = 0; root < 2; root++)
		for (unsigned int word = 0; word < 64; word++)
			if (word != 0x98 / 4)
				assert(mock.registers[root][word] == mock.original[root][word]);
}

int main(void)
{
#ifdef __linux__
	assert(prctl(PR_SET_DUMPABLE, 0) == 0);
#endif
	const struct n71_brcmfmac_quiescent empty = {0};
	/* Mutations: bypass opt-in, lose capture or keep decode/MASTER forbidden. */
	fresh();
	assert(emit(false, 4, 2, 6, 0) == -EPERM && !mock.reads && !mock.writes);
	capture();
	assert(n71_brcmfmac_capture(&io, &mock.state) == -EBUSY);
	driver();
	assert(n71_brcmfmac_restore(&io, &mock.state, &empty) == 0);
	baseline_restored();
	assert(n71_brcmfmac_capture(&io, &mock.state) == -EALREADY);
	/* Mutations: retain an incomplete capture or overlook baseline drift. */
	fresh(); capture();
	unsigned int capture_reads = mock.reads;
	for (unsigned int index = 1; index <= capture_reads; index++) {
		fresh(); mock.fail_read = index;
		int result = n71_brcmfmac_capture(&io, &mock.state);
		assert(result == -ETIMEDOUT && !mock.state.active && !mock.writes);
	}
	fresh(); mock.registers[1][0x4c / 4] = 0x400b;
	assert(n71_brcmfmac_capture(&io, &mock.state) == -EACCES && !mock.state.active);
	fresh(); mock.drift_read = 26;
	assert(n71_brcmfmac_capture(&io, &mock.state) == -EAGAIN && !mock.state.active);
	/* Mutations: accept other registers, IO, multi-MSI, bad message or W1C. */
	const struct n71_msi_config_request bad[] = {
		{{true, 4, 7, 2}, 0}, {{false, 4, 7, 2}, 0},
		{{false, 4, 6, 4}, 0}, {{true, 0x80, 0x18000000, 4}, 0},
		{{false, 0x80, 0x18000001, 4}, 0}, {{false, 0x98, 2, 4}, 0},
		{{false, 0xbc, 0x10, 2}, 0}, {{false, 0x4c, 0xc008, 2}, 0},
		{{false, 0x10, 0xc0400004, 4}, 0}, {{false, 0x5a, 0x89, 2}, 0},
		{{false, 0x5a, 0x89, 2}, 3}, {{false, 0x5c, 0xbffff000, 4}, 0},
		{{false, 0x64, 9, 2}, 1}, {{false, 0x60, 1, 4}, 1},
	};
	for (unsigned int index = 0; index < sizeof(bad) / sizeof(bad[0]); index++) {
		fresh(); capture(); unsigned int writes = mock.writes;
		assert(n71_brcmfmac_write(&io, &mock.state, &bad[index]) == -EPERM);
		assert(mock.state.error == -EPERM && mock.writes == writes);
	}
	fresh(); capture();
	assert(emit(false, 0x5a, 2, 0x89, 1) == -EIO);
	assert(!mock.writes && mock.state.error == -EIO);
	fresh(); capture(); driver();
	mock.registers[1][0x5c / 4] = 0xbffff000;
	mock.registers[1][0x64 / 4] = 8;
	mock.registers[1][0x58 / 4] |= 0x10000;
	unsigned int writes = mock.writes;
	assert(emit(false, 0x5c, 4, 0, 1) == -EPERM && mock.writes == writes);
	assert(emit(false, 4, 2, 6, 1) == -EPERM && mock.writes == writes);
	/* Mutations: ignore readback/write errors or overwrite the first cause. */
	fresh(); capture(); mock.drop_write = 1;
	assert(emit(false, 4, 2, 6, 0) == -EIO && mock.state.active);
	mock.drop_write = 0;
	assert(emit(false, 0x10, 4, 0, 0) == -EPERM && mock.state.error == -EIO);
	assert(n71_brcmfmac_restore(&io, &mock.state, &empty) == 0);
	assert(mock.state.error == -EIO); baseline_restored();
	fresh(); capture();
	assert(emit(false, 0x10, 4, 0, 0) == -EPERM);
	driver();
	assert(n71_brcmfmac_restore(&io, &mock.state, &empty) == 0);
	assert(mock.state.error == -EPERM); baseline_restored();
	fresh(); capture(); mock.fail_write = 1; mock.write_error = 1;
	assert(emit(false, 0x98, 4, 1, 0) == -EIO && mock.state.error == -EIO);
	/* Mutations: restore while firmware/driver/IRQ still owns the device. */
	for (unsigned int index = 0; index < 6; index++) {
		fresh(); capture(); driver();
		struct n71_brcmfmac_quiescent core = {0};
		if (index == 0) core.driver_registered = true;
		if (index == 1) core.driver_bound = true;
		if (index == 2) core.software_enabled = true;
		if (index == 3) core.slots = 1;
		if (index == 4) core.mappings = 1;
		if (index == 5) core.child_mappings = 1;
		unsigned int reads = mock.reads, previous = mock.writes;
		assert(n71_brcmfmac_restore(&io, &mock.state, &core) == -EBUSY);
		assert(mock.state.active && reads == mock.reads && previous == mock.writes);
	}
	/* Mutations: release after failed restore or restore a different endpoint. */
	fresh(); capture(); driver(); mock.registers[1][0] ^= 1;
	writes = mock.writes;
	assert(n71_brcmfmac_restore(&io, &mock.state, &empty) == -ENODEV);
	assert(mock.state.active && mock.writes == writes);
	fresh(); capture(); driver(); mock.drop_write = mock.writes + 1;
	assert(n71_brcmfmac_restore(&io, &mock.state, &empty) == -EIO && mock.state.active);
	mock.drop_write = 0;
	assert(n71_brcmfmac_restore(&io, &mock.state, &empty) == 0);
	baseline_restored(); assert(mock.state.error == -EIO);
	printf("N71_BRCMFMAC_CONFIG_OK cases=%u\n", cases);
	return 0;
}
