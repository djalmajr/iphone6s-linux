/* SPDX-License-Identifier: GPL-2.0-only */
/* Observe the separate DART block under the existing PCI power ownership. */
#ifndef N71_DART_MMIO_H
#define N71_DART_MMIO_H
#include <linux/of_platform.h>
#include "n71-dart-observe.h"

#define N71_DART_CPU 0x602008000ULL
#define N71_DART_BYTES 0x4000U

struct n71_dart_mmio {
	struct n71_diagnostic *state;
	void __iomem *regs;
	unsigned int reads, guards;
};

static int n71_dart_quiet(void *context)
{
	struct n71_dart_mmio *mmio = context;
	struct n71_diagnostic *state = mmio->state;
	u32 status;

	if (++mmio->guards > N71_DART_READS + 1 || state->powered != 4 || !mmio->regs)
		return -EACCES;
	status = readl(state->port + 0x88);
	if (status == 0xffffffff || !(status & 1))
		return -ENOLINK;
	if (readl(state->ecam + 0x8000) != 0x1004106b ||
	    readl(state->ecam + 0x100000) != 0x43a314e4 ||
	    (readw(state->ecam + 0x8004) & 7) ||
	    (readw(state->ecam + 0x100004) & 7))
		return -EACCES;
	return 0;
}

static int n71_dart_read32(void *context, u32 offset, u32 *value)
{
	struct n71_dart_mmio *mmio = context;
	if (!value || !mmio->regs || mmio->reads >= N71_DART_READS ||
	    mmio->guards != mmio->reads + 1 ||
	    offset != n71_dart_offset(mmio->reads % N71_DART_WORDS))
		return -EINVAL;
	mmio->reads++;
	*value = readl(mmio->regs + offset);
	return 0;
}

static int n71_dart_validate(struct device *dev)
{
	struct device_node *node, *power, *pcie_power;
	struct platform_device *owner;
	struct resource resource, extra;
	const char *status;
	u32 irq[3], cells;
	int error = -EINVAL;

	node = of_find_node_by_path("/soc/iommu@602008000");
	if (!node)
		return -ENODEV;
	power = of_parse_phandle(node, "power-domains", 0);
	pcie_power = of_parse_phandle(dev->of_node, "power-domains", 0);
	if (!of_device_is_compatible(node, "apple,s8000-dart") ||
	    !of_device_is_compatible(node, "apple,s5l8960x-dart") ||
	    of_property_read_string(node, "status", &status) || strcmp(status, "disabled") ||
	    of_address_to_resource(node, 0, &resource) ||
	    !of_address_to_resource(node, 1, &extra) ||
	    resource.start != N71_DART_CPU || resource_size(&resource) != N71_DART_BYTES ||
	    of_property_count_u32_elems(node, "interrupts") != 3 ||
	    of_property_read_u32_array(node, "interrupts", irq, 3) ||
	    irq[0] != 0 || irq[1] != 248 || irq[2] != 4 ||
	    of_property_read_u32(node, "#iommu-cells", &cells) || cells != 1 ||
	    of_property_count_u32_elems(node, "power-domains") != 1 ||
	    !power || power != pcie_power)
		goto done;
	owner = of_find_device_by_node(node);
	if (owner) {
		put_device(&owner->dev);
		error = -EBUSY;
		goto done;
	}
	error = 0;
done:
	of_node_put(power);
	of_node_put(pcie_power);
	of_node_put(node);
	return error;
}

static int n71_pcie_dart_observe(struct device *dev, struct n71_diagnostic *state)
{
	struct n71_dart_mmio mmio = {.state = state};
	struct n71_dart_io io = {&mmio, n71_dart_quiet, n71_dart_read32};
	struct n71_dart_observation result;
	struct resource *claimed = NULL;
	int error;

	if (state->powered != 4 || state->attached != 4)
		return -EACCES;
	error = n71_dart_validate(dev);
	if (error)
		goto done;
	claimed = request_mem_region(N71_DART_CPU, N71_DART_BYTES, "n71-dart-observe");
	if (!claimed) {
		error = -EBUSY;
		goto done;
	}
	mmio.regs = ioremap(N71_DART_CPU, N71_DART_BYTES);
	if (!mmio.regs) {
		error = -ENOMEM;
		goto done;
	}
	dev_info(dev, "N71_DART_SOURCE physical=%016llx bytes=%08x irq=248 provider=disabled owner=none\n",
		 N71_DART_CPU, N71_DART_BYTES);
	error = n71_dart_observe(&io, &result);
	if (!error)
		dev_info(dev, "N71_DART_STATE command=%08x tcr=%08x error=%08x enabled=%01x ttbr-valid=%04x; stable\n",
			 result.command, result.tcr, result.error, result.enabled, result.valid_ttbrs);
done:
	if (mmio.regs)
		iounmap(mmio.regs);
	if (claimed)
		release_mem_region(N71_DART_CPU, N71_DART_BYTES);
	dev_info(dev, "N71_DART_MAP_RELEASED mapped=0 claimed=0\n");
	dev_info(dev, "N71_DART_RESULT error=%d reads=%u guards=%u; no DART writes or DMA\n",
		 error, mmio.reads, mmio.guards);
	return error;
}
#endif /* N71_DART_MMIO_H */
