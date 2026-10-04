/* SPDX-License-Identifier: GPL-2.0-only */
/* Claim only the selected BAR0 aperture, read chip-ID once, restore and unmap. */
#ifndef N71_PCIE_CHIP_MMIO_H
#define N71_PCIE_CHIP_MMIO_H
#include <linux/ioport.h>
#include "n71-pcie-chip-id.h"

struct n71_chip_mmio {
	struct n71_scan_host host;
	void __iomem *bar0;
	unsigned int reads;
};

static int n71_chip_read_mmio(void *context, u32 *value)
{
	struct n71_scan_host *host = context;
	struct n71_chip_mmio *mmio = container_of(host, struct n71_chip_mmio, host);
	u32 status = readl(host->port + 0x88);

	if (!mmio->bar0 || !value || mmio->reads)
		return -EINVAL;
	if (status == 0xffffffff || !(status & 1))
		return -ENOLINK;
	mmio->reads++;
	*value = readl(mmio->bar0); /* ChipCommon chipid at BAR0 offset0 only. */
	return 0;
}

static int n71_pcie_chip_id(struct device *dev, struct n71_diagnostic *state)
{
	struct n71_chip_mmio mmio = {.host = {.dev = dev, .ecam = state->ecam, .port = state->port}};
	struct n71_chip_io io = {{&mmio.host, n71_scan_raw_read, n71_scan_raw_write}, n71_chip_read_mmio};
	struct n71_bar_sizes measured;
	struct n71_chip_identity result;
	struct resource *claimed = NULL;
	int error, restore = 0;

	error = n71_pcie_size_bars(dev, state, &measured);
	if (error)
		goto done;
	claimed = request_mem_region(N71_CHIP_BAR0_CPU, N71_CHIP_BAR0_BYTES, "n71-chip-id");
	if (!claimed) {
		error = -EBUSY;
		goto done;
	}
	mmio.bar0 = ioremap(N71_CHIP_BAR0_CPU, N71_CHIP_BAR0_BYTES);
	if (!mmio.bar0) {
		error = -ENOMEM;
		goto done;
	}
	error = n71_chip_collect(&io, &measured, &mmio.host.config, &result, &restore);
	if (mmio.host.config.saved[0].identity)
		dev_info(dev, "N71_PCIE_CHIP_CONFIG_RESTORED error=%d; route/window/readback checked\n", restore);
	if (!error)
		dev_info(dev, "N71_PCIE_CHIP_ID raw=%08x chip=%04x revision=%u; one read only\n",
			 result.raw, result.chip, result.revision);
done:
	if (mmio.bar0)
		iounmap(mmio.bar0);
	if (claimed)
		release_mem_region(N71_CHIP_BAR0_CPU, N71_CHIP_BAR0_BYTES);
	dev_info(dev, "N71_PCIE_CHIP_MAP_RELEASED mapped=0 claimed=0\n");
	dev_info(dev, "N71_PCIE_CHIP_RESULT error=%d config_reads=%u mmio_reads=%u; no DMA or radio\n",
		 error, mmio.host.reads, mmio.reads);
	return error;
}
#endif /* N71_PCIE_CHIP_MMIO_H */
