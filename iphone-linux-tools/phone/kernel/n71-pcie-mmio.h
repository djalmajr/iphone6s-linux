/* SPDX-License-Identifier: GPL-2.0-only */
/* Kernel backend; only the validated N71 diagnostic module may use this. */
#ifndef N71_PCIE_MMIO_H
#define N71_PCIE_MMIO_H

struct n71_diagnostic {
	void __iomem *common, *phy, *port, *ecam;
	struct gpio_desc *perst;
	struct device *domains[4];
	unsigned int attached, powered;
};

static int n71_read(void *context, enum n71_pcie_region region, u32 offset, u32 *value)
{
	struct n71_diagnostic *state = context;
	void __iomem *base = region == N71_PCIE_COMMON ? state->common : state->phy;
	u32 size = region == N71_PCIE_COMMON ? 0x8000 : 0x4000;

	if (!value || (region != N71_PCIE_COMMON && region != N71_PCIE_PHY) ||
	    offset % 4 || offset > size - 4)
		return -EINVAL;
	*value = readl(base + offset);
	return 0;
}

static int n71_write(void *context, enum n71_pcie_region region, u32 offset, u32 value)
{
	struct n71_diagnostic *state = context;
	void __iomem *base = region == N71_PCIE_COMMON ? state->common : state->phy;
	u32 size = region == N71_PCIE_COMMON ? 0x8000 : 0x4000;

	if ((region != N71_PCIE_COMMON && region != N71_PCIE_PHY) || offset % 4 || offset > size - 4)
		return -EINVAL;
	writel(value, base + offset);
	return 0;
}

static int n71_read_link(void *context, bool root, u32 offset, u32 *value)
{
	struct n71_diagnostic *state = context;
	void __iomem *base = root ? state->ecam + 0x8000 : state->port;
	if (!value || offset % 4 || offset > (root ? 0xffc : 0x3ffc))
		return -EINVAL;
	*value = readl(base + offset);
	return 0;
}

static int n71_write_link(void *context, bool root, u32 offset, u32 value)
{
	struct n71_diagnostic *state = context;
	void __iomem *base = root ? state->ecam + 0x8000 : state->port;
	if (offset % 4 || offset > (root ? 0xffc : 0x3ffc))
		return -EINVAL;
	writel(value, base + offset);
	return 0;
}

static int n71_read_port(void *context, u32 offset, u32 *value)
{
	return n71_read_link(context, false, offset, value);
}

static int n71_write_port(void *context, u32 offset, u32 value)
{
	return n71_write_link(context, false, offset, value);
}

static void n71_delay(void *context, unsigned int microseconds)
{
	(void)context;
	if (microseconds >= 1000)
		usleep_range(microseconds, microseconds + 100);
	else
		udelay(microseconds);
}

static int n71_reset(void *context, bool asserted)
{
	struct n71_diagnostic *state = context;
	return gpiod_direction_output(state->perst, asserted);
}

static int n71_endpoint(void *context, u32 offset, u32 *value)
{
	struct n71_diagnostic *state = context;
	if (!value || (offset != 0 && offset != 4))
		return -EINVAL;
	*value = readl(state->ecam + 0x100000 + offset);
	return 0;
}

#endif /* N71_PCIE_MMIO_H */
