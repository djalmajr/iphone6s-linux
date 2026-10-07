/* SPDX-License-Identifier: GPL-2.0-only */
/* The session owns the provider, original tables and incomplete restoration. */
#ifndef N71_DART_PROVIDER_H
#define N71_DART_PROVIDER_H
#include <linux/irqdomain.h>
#include <linux/of_irq.h>
#include "n71-dart-lease.h"

struct n71_dart_provider {
	struct device *parent;
	struct device_node *node;
	struct platform_device *device;
	struct n71_dart_mmio mmio;
	struct n71_dart_lease lease;
	struct resource *claimed;
	unsigned int irq, snapshots, reads, guards, quiet, writes;
	unsigned int snapshot_budget, quiet_budget;
	bool added, new_mapping, bound, restore_guard;
};

static int n71_provider_snapshot(void *context, struct n71_dart_observation *out)
{
	struct n71_dart_provider *provider = context;
	struct n71_dart_io io = {&provider->mmio, n71_dart_quiet, n71_dart_read32};
	unsigned int index;
	int error;

	if (++provider->snapshot_budget > 4)
		return -E2BIG;
	provider->snapshots++;
	provider->mmio.reads = provider->mmio.guards = 0;
	error = n71_dart_observe(&io, out);
	provider->reads += provider->mmio.reads;
	provider->guards += provider->mmio.guards;
	if (error)
		return error;
	dev_info(provider->parent, "N71_DART_CYCLE_SNAPSHOT index=%u command=%08x tcr=%08x error=%08x valid=%04x; stable\n",
		 provider->snapshots, out->command, out->tcr, out->error, out->valid_ttbrs);
	if (provider->snapshots == 1) {
		for (index = 0; index < 16; index++)
			dev_info(provider->parent, "N71_DART_TTBR index=%02u value=%08x; stable\n", index, out->ttbr[index]);
	}
	return 0;
}

static int n71_provider_quiet(void *context)
{
	struct n71_dart_provider *provider = context;
	int error;

	provider->restore_guard = false;
	if (++provider->quiet_budget > 17)
		return -E2BIG;
	provider->quiet++;
	provider->mmio.guards = 0;
	error = n71_dart_quiet(&provider->mmio);
	provider->restore_guard = !error;
	return error;
}

static int n71_provider_start(void *context)
{
	struct n71_dart_provider *provider = context;
	struct of_phandle_args args;
	struct irq_fwspec spec = {0};
	struct irq_domain *domain;
	struct irq_data *data;
	struct device_node *parent;
	struct resource resources[2];
	irq_hw_number_t hwirq;
	unsigned int prior, type;
	int error;

	error = of_irq_parse_one(provider->node, 0, &args);
	if (error)
		return error;
	parent = of_irq_find_parent(provider->parent->of_node);
	if (args.args_count != 3 || args.args[0] || args.args[1] != 248 ||
	    args.args[2] != IRQ_TYPE_LEVEL_HIGH || args.np != parent) {
		error = -EINVAL;
		goto irq_done;
	}
	spec.fwnode = of_fwnode_handle(args.np);
	spec.param_count = 3;
	memcpy(spec.param, args.args, sizeof(u32) * 3);
	domain = irq_find_matching_fwspec(&spec, DOMAIN_BUS_WIRED);
	if (!domain)
		domain = irq_find_matching_fwspec(&spec, DOMAIN_BUS_ANY);
	if (!domain || !domain->ops->translate) {
		error = -ENODEV;
		goto irq_done;
	}
	error = domain->ops->translate(domain, &spec, &hwirq, &type);
	if (error || type != IRQ_TYPE_LEVEL_HIGH) {
		error = error ? error : -EINVAL;
		goto irq_done;
	}
	prior = irq_find_mapping(domain, hwirq);
	provider->irq = irq_create_of_mapping(&args);
	provider->new_mapping = !prior && provider->irq;
	data = irq_get_irq_data(provider->irq);
	if (!provider->irq || !data || data->domain != domain || data->hwirq != hwirq ||
	    (prior && prior != provider->irq))
		error = -EINVAL;
irq_done:
	of_node_put(parent);
	of_node_put(args.np);
	if (error)
		return error;
	provider->device = platform_device_alloc("n71-dart-cycle", PLATFORM_DEVID_AUTO);
	if (!provider->device)
		return -ENOMEM;
	device_set_node(&provider->device->dev, of_fwnode_handle(of_node_get(provider->node)));
	provider->device->dev.parent = provider->parent;
	resources[0] = (struct resource){.start = N71_DART_CPU,
		.end = N71_DART_CPU + N71_DART_BYTES - 1, .flags = IORESOURCE_MEM};
	resources[1] = (struct resource){.start = provider->irq, .end = provider->irq,
		.flags = IORESOURCE_IRQ | IORESOURCE_IRQ_HIGHLEVEL};
	error = platform_device_add_resources(provider->device, resources, 2);
	if (error)
		return error;
	release_mem_region(N71_DART_CPU, N71_DART_BYTES);
	provider->claimed = NULL;
	error = platform_device_add(provider->device);
	if (error)
		return error;
	provider->added = true;
	device_lock(&provider->device->dev);
	provider->bound = provider->device->dev.driver &&
		!strcmp(provider->device->dev.driver->name, "apple-dart") &&
		platform_get_drvdata(provider->device);
	device_unlock(&provider->device->dev);
	dev_info(provider->parent, "N71_DART_CYCLE_PROVIDER bound=%u irq-hwirq=248 mapping-new=%u; no DMA attachment\n",
		 provider->bound, provider->new_mapping);
	return provider->bound ? 0 : -ENODEV;
}

static int n71_provider_stop(void *context)
{
	struct n71_dart_provider *provider = context;
	struct platform_device *owner;

	if (provider->device) {
		if (provider->added)
			platform_device_unregister(provider->device);
		else
			platform_device_put(provider->device);
		provider->device = NULL;
		provider->added = false;
	}
	provider->bound = false;
	if (provider->new_mapping)
		irq_dispose_mapping(provider->irq);
	provider->irq = 0;
	provider->new_mapping = false;
	owner = of_find_device_by_node(provider->node);
	if (owner) {
		put_device(&owner->dev);
		return -EBUSY;
	}
	if (!provider->claimed)
		provider->claimed = request_mem_region(N71_DART_CPU, N71_DART_BYTES, "n71-dart-restore");
	if (!provider->claimed)
		return -EBUSY;
	dev_info(provider->parent, "N71_DART_CYCLE_REMOVED device=0 mapping-new=0 claimed=1; restore ownership held\n");
	return 0;
}

static int n71_provider_write(void *context, unsigned int index, u32 value)
{
	struct n71_dart_provider *provider = context;
	if (provider->device || !provider->claimed || !provider->mmio.regs ||
	    !provider->lease.stopped || provider->lease.restored || !provider->restore_guard ||
	    index != provider->lease.restore_index || index >= 16 ||
	    value != provider->lease.saved.ttbr[index])
		return -EACCES;
	provider->restore_guard = false;
	provider->writes++;
	writel(value, provider->mmio.regs + 0x40 + index * 4);
	return 0;
}

static struct n71_dart_cycle_io n71_provider_io(struct n71_dart_provider *provider)
{
	return (struct n71_dart_cycle_io){provider, n71_provider_snapshot, n71_provider_quiet,
		n71_provider_start, n71_provider_stop, n71_provider_write};
}

static int n71_pcie_dart_acquire(struct device *dev, struct n71_diagnostic *state)
{
	struct n71_dart_provider *provider;
	struct n71_dart_cycle_io io;
	int error;

	if (state->dart)
		return state->dart->lease.running ? -EALREADY : -EBUSY;
	if (state->powered != 4 || state->attached != 4)
		return -EACCES;
	error = n71_dart_validate(dev);
	if (error)
		return error;
	provider = kzalloc(sizeof(*provider), GFP_KERNEL);
	if (!provider)
		return -ENOMEM;
	provider->parent = dev;
	provider->mmio.state = state;
	/* Publish ownership before any start/probe can partially change hardware. */
	state->dart = provider;
	provider->node = of_find_node_by_path("/soc/iommu@602008000");
	if (!provider->node) {
		error = -ENODEV;
		goto done;
	}
	provider->claimed = request_mem_region(N71_DART_CPU, N71_DART_BYTES, "n71-dart-cycle");
	if (!provider->claimed) {
		error = -EBUSY;
		goto done;
	}
	provider->mmio.regs = ioremap(N71_DART_CPU, N71_DART_BYTES);
	if (!provider->mmio.regs) {
		error = -ENOMEM;
		goto done;
	}
	io = n71_provider_io(provider);
	error = n71_dart_lease_acquire(&io, &provider->lease);
done:
	provider->lease.operation_error = error;
	dev_info(dev, "N71_DART_LEASE_ACQUIRE error=%d running=%u pending=%u; no DMA attachment\n",
		 error, provider->lease.running, n71_dart_lease_pending(&provider->lease));
	return error;
}

static int n71_pcie_dart_cleanup(struct device *dev, struct n71_diagnostic *state)
{
	struct n71_dart_provider *provider = state->dart;
	struct n71_dart_cycle_io io;
	int error;

	if (!provider)
		return 0;
	io = n71_provider_io(provider);
	provider->snapshot_budget = provider->quiet_budget = 0;
	provider->restore_guard = false;
	error = n71_dart_lease_cleanup(&io, &provider->lease);
	if (!state->primary_error && provider->lease.operation_error)
		state->primary_error = provider->lease.operation_error;
	if (!error && (provider->device || provider->new_mapping || provider->bound))
		error = -EBUSY;
	dev_info(dev, "N71_DART_LEASE_CLEANUP error=%d pending=%u index=%u device=%u mapping-new=%u claimed=%u mapped=%u; ownership retained until restore\n",
		 error, n71_dart_lease_pending(&provider->lease), provider->lease.restore_index,
		 !!provider->device, provider->new_mapping, !!provider->claimed, !!provider->mmio.regs);
	dev_info(dev, "N71_DART_CYCLE_RESULT error=%d snapshots=%u reads=%u guards=%u quiet=%u writes=%u attempted=%u stopped=%u restored=%u control-changed=%u; no DMA\n",
		 error ? error : provider->lease.operation_error, provider->snapshots,
		 provider->reads, provider->guards, provider->quiet, provider->writes,
		 provider->lease.attempted, provider->lease.stopped, provider->lease.restored,
		 provider->lease.control_changed);
	if (error)
		return error;
	if (provider->mmio.regs)
		iounmap(provider->mmio.regs);
	if (provider->claimed)
		release_mem_region(N71_DART_CPU, N71_DART_BYTES);
	of_node_put(provider->node);
	kfree(provider);
	state->dart = NULL;
	dev_info(dev, "N71_DART_CYCLE_RELEASED device=0 mapping-new=0 claimed=0 mapped=0\n");
	return 0;
}

static int n71_pcie_dart_cycle(struct device *dev, struct n71_diagnostic *state)
{
	int error = n71_pcie_dart_acquire(dev, state);
	int cleanup = n71_pcie_dart_cleanup(dev, state);

	return cleanup ? cleanup : error ? error : state->primary_error;
}
#endif /* N71_DART_PROVIDER_H */
