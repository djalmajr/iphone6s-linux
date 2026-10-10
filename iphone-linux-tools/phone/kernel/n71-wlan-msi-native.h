/* SPDX-License-Identifier: GPL-2.0-only */
/* Isolated N71 MSI parent; PCI association and DMA remain separate gates. */
#ifndef N71_WLAN_MSI_NATIVE_H
#define N71_WLAN_MSI_NATIVE_H
#include <linux/irq.h>
#include <linux/irqdomain.h>
#include <linux/irqchip/irq-msi-lib.h>
#include <linux/msi.h>
#include <linux/of_irq.h>
#include "n71-wlan-msi-message.h"

struct n71_wlan_msi {
	struct device_node *node;
	struct fwnode_handle *fwnode;
	struct irq_domain *domain, *parent, *child;
	struct device *child_device;
	struct irq_fwspec spec;
	struct n71_wlan_msi_request request;
	unsigned int slots;
};

/* The consumer must serialize creation, child teardown and owner release.
 * PCI free_irqs leaves its device domain alive. Its prepare/teardown pair,
 * not the number of allocated vectors, holds the parent lifetime here.
 */
static int n71_wlan_msi_prepare(struct irq_domain *child, struct device *device,
				int count, msi_alloc_info_t *argument)
{
	struct n71_wlan_msi *binding = child->parent->host_data;
	int error = 0;

	mutex_lock(&binding->parent->mutex);
	if (child->parent != binding->domain || !device || !argument || count <= 0)
		error = -EINVAL;
	else if (binding->child)
		error = -EBUSY;
	else {
		memset(argument, 0, sizeof(*argument));
		binding->child = child;
		binding->child_device = device;
	}
	mutex_unlock(&binding->parent->mutex);
	return error;
}

static void n71_wlan_msi_teardown(struct irq_domain *child, msi_alloc_info_t *argument)
{
	struct n71_wlan_msi *binding = child->parent->host_data;

	(void)argument;
	mutex_lock(&binding->parent->mutex);
	if (!WARN_ON_ONCE(binding->child != child || binding->slots || binding->domain->mapcount)) {
		binding->child = NULL;
		binding->child_device = NULL;
	}
	mutex_unlock(&binding->parent->mutex);
}

static bool n71_wlan_msi_init_child(struct device *device, struct irq_domain *domain,
				   struct irq_domain *real_parent, struct msi_domain_info *info)
{
	if (info->bus_token != DOMAIN_BUS_PCI_DEVICE_MSI ||
	    info->flags & MSI_FLAG_PCI_MSIX || !info->ops ||
	    info->ops->msi_prepare || info->ops->msi_teardown)
		return false;
	if (!msi_lib_init_dev_msi_info(device, domain, real_parent, info))
		return false;
	info->ops->msi_prepare = n71_wlan_msi_prepare;
	info->ops->msi_teardown = n71_wlan_msi_teardown;
	return true;
}

static void n71_wlan_msi_compose(struct irq_data *data, struct msi_msg *message)
{
	struct n71_wlan_msi *binding;
	struct n71_wlan_msi_request request;
	struct n71_wlan_msi_reference reference;

	if (!message)
		return;
	*message = (struct msi_msg){0};
	if (!data)
		return;
	binding = irq_data_get_irq_chip_data(data);
	if (!binding || data->domain != binding->domain || data->hwirq >= 8 ||
	    !(binding->slots & (1U << data->hwirq)))
		return;
	request = binding->request;
	request.irq.index = data->hwirq;
	if (n71_wlan_msi_message(&request, &reference))
		return;
	message->address_lo = reference.message[0];
	message->address_hi = reference.message[1];
	message->data = reference.message[2];
}

static const struct irq_chip n71_wlan_msi_chip = {
	.name = "N71-MSI",
	.irq_mask = irq_chip_mask_parent,
	.irq_unmask = irq_chip_unmask_parent,
	.irq_eoi = irq_chip_eoi_parent,
	.irq_set_affinity = irq_chip_set_affinity_parent,
	.irq_set_type = irq_chip_set_type_parent,
	.irq_compose_msi_msg = n71_wlan_msi_compose,
};

static int n71_wlan_msi_alloc(struct irq_domain *domain, unsigned int virq,
			      unsigned int count, void *argument)
{
	struct n71_wlan_msi *binding = domain->host_data;
	msi_alloc_info_t *info = argument;
	struct irq_fwspec spec;
	struct irq_data *data;
	unsigned int first, mask, i;
	int error;

	lockdep_assert_held(&domain->root->mutex);
	if (!binding || domain != binding->domain || domain->parent != binding->parent ||
	    domain->root != binding->parent || !virq || !info || !info->desc ||
	    !binding->child || info->desc->dev != binding->child_device ||
	    !count || count > 8 || (count & (count - 1)))
		return -EINVAL;
	for (first = 0; first + count <= 8; first += count) {
		mask = ((1U << count) - 1) << first;
		if (!(binding->slots & mask))
			break;
	}
	if (first + count > 8)
		return -ENOSPC;
	for (i = 0; i < count; i++)
		if (irq_find_mapping(binding->parent, 0x10108UL + first + i))
			return -EBUSY;
	binding->slots |= mask;
	spec = binding->spec;
	spec.param[1] += first;
	error = irq_domain_alloc_irqs_parent(domain, virq, count, &spec);
	if (error) {
		/* Parent allocation may have initialized only a prefix of irq_data. */
		for (i = 0; i < count; i++) {
			data = irq_domain_get_irq_data(binding->parent, virq + i);
			if (data && data->chip)
				irq_domain_free_irqs_parent(domain, virq + i, 1);
		}
		goto release_slots;
	}
	for (i = 0; i < count; i++) {
		data = irq_domain_get_irq_data(binding->parent, virq + i);
		if (!data || data->domain != binding->parent || data->hwirq != 0x10108UL + first + i ||
		    !data->chip || !data->chip->name || strcmp(data->chip->name, "AIC")) {
			error = -EINVAL;
			goto release_parent;
		}
		/* AIC allocation translates the type but does not store it. Its
		 * MSI edge semantics are implicit; keep shared core state consistent.
		 */
		irqd_set_trigger_type(irq_domain_get_irq_data(domain, virq + i), IRQ_TYPE_EDGE_RISING);
	}
	for (i = 0; i < count; i++) {
		error = irq_domain_set_hwirq_and_chip(domain, virq + i, first + i,
						   &n71_wlan_msi_chip, binding);
		if (error) {
			while (i)
				irq_domain_reset_irq_data(irq_domain_get_irq_data(domain, virq + --i));
			goto release_parent;
		}
	}
	return 0;
release_parent:
	irq_domain_free_irqs_parent(domain, virq, count);
release_slots:
	binding->slots &= ~mask;
	return error;
}

/* The pinned IRQ core invokes free once per vector, including multi-MSI. */
static void n71_wlan_msi_free(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	struct n71_wlan_msi *binding = domain->host_data;
	struct irq_data *data = irq_domain_get_irq_data(domain, virq);
	unsigned int mask;

	lockdep_assert_held(&domain->root->mutex);
	if (WARN_ON_ONCE(count != 1 || !data || data->chip != &n71_wlan_msi_chip ||
			 data->chip_data != binding || data->hwirq >= 8))
		return;
	mask = 1U << data->hwirq;
	if (WARN_ON_ONCE(!(binding->slots & mask)))
		return;
	irq_domain_free_irqs_common(domain, virq, count);
	binding->slots &= ~mask;
}

static const struct irq_domain_ops n71_wlan_msi_ops = {
	.alloc = n71_wlan_msi_alloc,
	.free = n71_wlan_msi_free,
};
static const struct msi_parent_ops n71_wlan_msi_parent_ops = {
	.supported_flags = MSI_GENERIC_FLAGS_MASK | MSI_FLAG_MULTI_PCI_MSI,
	.required_flags = MSI_FLAG_USE_DEF_DOM_OPS | MSI_FLAG_USE_DEF_CHIP_OPS | MSI_FLAG_PCI_MSI_MASK_PARENT,
	.chip_flags = MSI_CHIP_FLAG_SET_EOI,
	.bus_select_token = DOMAIN_BUS_PCI_MSI,
	.init_dev_msi_info = n71_wlan_msi_init_child,
};

static int n71_wlan_msi_acquire(struct n71_wlan_msi *binding, const struct irq_fwspec *spec,
				const struct n71_wlan_msi_request *request)
{
	struct n71_wlan_msi_reference reference;
	struct irq_domain_info info = {.size = 8, .ops = &n71_wlan_msi_ops};
	struct irq_fwspec candidate;
	struct irq_domain *parent;
	irq_hw_number_t hwirq;
	unsigned int type, i;
	int error;

	if (!binding || !spec || !request || request->irq.index ||
	    n71_wlan_msi_message(request, &reference) || spec->param_count != 3 ||
	    spec->param[0] || spec->param[1] != 264 || spec->param[2] != IRQ_TYPE_EDGE_RISING ||
	    !is_of_node(spec->fwnode) || !of_device_is_compatible(to_of_node(spec->fwnode), "apple,aic"))
		return -EINVAL;
	if (binding->domain || binding->fwnode || binding->node || binding->slots || binding->child)
		return -EBUSY;
	candidate = *spec;
	parent = irq_find_matching_fwspec(&candidate, DOMAIN_BUS_WIRED);
	if (!parent || parent->parent || parent->root != parent || !irq_domain_is_hierarchy(parent) ||
	    !parent->ops || !parent->ops->translate || !parent->ops->alloc || !parent->ops->free ||
	    parent->fwnode != spec->fwnode)
		return -ENODEV;
	for (i = 0; i < 8; i++) {
		candidate.param[1] = 264 + i;
		error = parent->ops->translate(parent, &candidate, &hwirq, &type);
		if (error || hwirq != 0x10108UL + i || type != IRQ_TYPE_EDGE_RISING)
			return error ? error : -EINVAL;
	}
	binding->node = of_node_get(to_of_node(spec->fwnode));
	binding->parent = parent;
	binding->spec = *spec;
	binding->request = *request;
	binding->fwnode = irq_domain_alloc_named_fwnode("n71-wlan-msi");
	if (!binding->fwnode)
		return -ENOMEM;
	info.fwnode = binding->fwnode;
	info.parent = parent;
	info.host_data = binding;
	binding->domain = msi_create_parent_irq_domain(&info, &n71_wlan_msi_parent_ops);
	return binding->domain ? 0 : -ENOMEM;
}

static int n71_wlan_msi_release(struct n71_wlan_msi *binding)
{
	int error = 0;

	if (!binding)
		return -EINVAL;
	if (binding->domain) {
		if (binding->domain->host_data != binding || binding->domain->ops != &n71_wlan_msi_ops ||
		    binding->domain->parent != binding->parent || binding->domain->fwnode != binding->fwnode)
			return -EINVAL;
		mutex_lock(&binding->parent->mutex);
		if (binding->slots || binding->domain->mapcount || binding->child)
			error = -EBUSY;
		mutex_unlock(&binding->parent->mutex);
		if (error)
			return error;
		irq_domain_remove(binding->domain);
		binding->domain = NULL;
	}
	if (binding->fwnode) {
		irq_domain_free_fwnode(binding->fwnode);
		binding->fwnode = NULL;
	}
	of_node_put(binding->node);
	*binding = (struct n71_wlan_msi){0};
	return 0;
}
#endif /* N71_WLAN_MSI_NATIVE_H */
