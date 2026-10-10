/* SPDX-License-Identifier: GPL-2.0-only */
/* One private DART IRQ; parent conflict checks run under the IRQ root mutex. */
#ifndef N71_DART_IRQ_H
#define N71_DART_IRQ_H
#include <linux/irq.h>
#include <linux/irqdomain.h>
#include <linux/of_irq.h>

struct n71_dart_irq {
	struct device_node *node;
	struct fwnode_handle *fwnode;
	struct irq_domain *domain, *parent;
	struct irq_fwspec spec;
	irq_hw_number_t hwirq;
	unsigned int irq;
};

static const struct irq_chip n71_dart_irq_chip = {
	.name = "N71-DART",
	.irq_mask = irq_chip_mask_parent,
	.irq_unmask = irq_chip_unmask_parent,
	.irq_eoi = irq_chip_eoi_parent,
	.irq_set_affinity = irq_chip_set_affinity_parent,
	.irq_set_type = irq_chip_set_type_parent,
};

static int n71_dart_irq_alloc(struct irq_domain *domain, unsigned int virq,
			      unsigned int count, void *argument)
{
	struct n71_dart_irq *binding = domain->host_data;
	struct irq_data *parent_data;
	int error;

	lockdep_assert_held(&domain->root->mutex);
	if (!binding || argument != binding || count != 1 || !virq ||
	    domain != binding->domain || domain->parent != binding->parent ||
	    domain->root != binding->parent || binding->irq || domain->mapcount)
		return -EINVAL;
	/* This check and parent allocation share the core's root mutex. */
	if (irq_find_mapping(binding->parent, binding->hwirq))
		return -EBUSY;
	error = irq_domain_alloc_irqs_parent(domain, virq, count, &binding->spec);
	if (error)
		return error;
	parent_data = irq_domain_get_irq_data(binding->parent, virq);
	if (!parent_data || parent_data->hwirq != binding->hwirq ||
	    !parent_data->chip || !parent_data->chip->name || strcmp(parent_data->chip->name, "AIC")) {
		irq_domain_free_irqs_parent(domain, virq, count);
		return -EINVAL;
	}
	irq_domain_set_info(domain, virq, 0, &n71_dart_irq_chip, binding,
			    handle_fasteoi_irq, NULL, NULL);
	return 0;
}

static void n71_dart_irq_free(struct irq_domain *domain, unsigned int virq,
			     unsigned int count)
{
	irq_domain_free_irqs_common(domain, virq, count);
}

static const struct irq_domain_ops n71_dart_irq_ops = {
	.alloc = n71_dart_irq_alloc,
	.free = n71_dart_irq_free,
};

static int n71_dart_irq_acquire(struct n71_dart_irq *binding,
			       const struct irq_fwspec *spec)
{
	struct irq_domain *parent;
	struct irq_fwspec candidate;
	irq_hw_number_t hwirq;
	unsigned int type;
	int error;

	if (!binding || !spec || spec->param_count != 3 || spec->param[0] ||
	    spec->param[1] != 248 || spec->param[2] != IRQ_TYPE_LEVEL_HIGH ||
	    !is_of_node(spec->fwnode) ||
	    !of_device_is_compatible(to_of_node(spec->fwnode), "apple,aic"))
		return -EINVAL;
	if (binding->irq || binding->domain || binding->fwnode || binding->node)
		return -EBUSY;
	candidate = *spec;
	parent = irq_find_matching_fwspec(&candidate, DOMAIN_BUS_WIRED);
	if (!parent || parent->parent || parent->root != parent ||
	    !irq_domain_is_hierarchy(parent) || !parent->ops->translate ||
	    !parent->ops->alloc || !parent->ops->free || parent->fwnode != spec->fwnode)
		return -ENODEV;
	error = parent->ops->translate(parent, &candidate, &hwirq, &type);
	if (error || type != IRQ_TYPE_LEVEL_HIGH || hwirq != 0x100f8UL)
		return error ? error : -EINVAL;
	binding->node = of_node_get(to_of_node(spec->fwnode));
	binding->parent = parent;
	binding->spec = *spec;
	binding->hwirq = hwirq;
	binding->fwnode = irq_domain_alloc_named_fwnode("n71-dart");
	if (!binding->fwnode)
		return -ENOMEM;
	binding->domain = irq_domain_create_hierarchy(parent, 0, 1, binding->fwnode,
						     &n71_dart_irq_ops, binding);
	if (!binding->domain)
		return -ENOMEM;
	error = irq_domain_alloc_irqs(binding->domain, 1, NUMA_NO_NODE, binding);
	if (error < 0)
		return error;
	if (!error)
		return -EINVAL;
	binding->irq = error;
	return irq_set_irq_type(binding->irq, IRQ_TYPE_LEVEL_HIGH);
}

static int n71_dart_irq_release(struct n71_dart_irq *binding)
{
	struct irq_data *data;

	if (!binding)
		return -EINVAL;
	if (binding->irq) {
		if (!binding->domain || !binding->parent || !binding->fwnode)
			return -EINVAL;
		data = irq_get_irq_data(binding->irq);
		if (!data || data->domain != binding->domain || data->hwirq ||
		    !data->parent_data || data->parent_data->domain != binding->parent ||
		    data->parent_data->hwirq != binding->hwirq)
			return -EINVAL;
		if (irq_has_action(binding->irq) || irqd_is_started(data) ||
		    !irqd_irq_disabled(data) || !irqd_irq_masked(data))
			return -EBUSY;
		irq_domain_free_irqs(binding->irq, 1);
		binding->irq = 0;
	}
	if (binding->domain) {
		if (binding->domain->mapcount)
			return -EBUSY;
		irq_domain_remove(binding->domain);
		binding->domain = NULL;
	}
	if (binding->fwnode) {
		irq_domain_free_fwnode(binding->fwnode);
		binding->fwnode = NULL;
	}
	of_node_put(binding->node);
	binding->node = NULL;
	binding->parent = NULL;
	binding->spec = (struct irq_fwspec){0};
	binding->hwirq = 0;
	return 0;
}
#endif /* N71_DART_IRQ_H */
