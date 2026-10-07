/* SPDX-License-Identifier: GPL-2.0-only */
/* Track IRQ core ownership and require the root lock at conflict/allocation. */
#ifndef N71_DART_IRQ_FIXTURE_H
#define N71_DART_IRQ_FIXTURE_H
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define IRQ_TYPE_LEVEL_HIGH 4U
#define DOMAIN_BUS_WIRED 1
#define DOMAIN_BUS_ANY 0
#define NUMA_NO_NODE -1
typedef unsigned long irq_hw_number_t;
struct device_node;
struct fwnode_handle { struct device_node *node; unsigned int refs; };
struct device_node { unsigned int refs; bool aic; struct fwnode_handle fwnode; };
struct mutex { bool held; };
#define lockdep_assert_held(lock) assert((lock)->held)
struct cpumask { int unused; };
struct irq_domain;
struct irq_data;
struct irq_chip {
	const char *name;
	void (*irq_mask)(struct irq_data *);
	void (*irq_unmask)(struct irq_data *);
	void (*irq_eoi)(struct irq_data *);
	int (*irq_set_affinity)(struct irq_data *, const struct cpumask *, bool);
	int (*irq_set_type)(struct irq_data *, unsigned int);
};
struct irq_fwspec { struct fwnode_handle *fwnode; unsigned int param_count, param[4]; };
struct of_phandle_args { struct device_node *np; unsigned int args_count, args[4]; };
struct irq_domain_ops {
	int (*translate)(struct irq_domain *, struct irq_fwspec *, irq_hw_number_t *, unsigned int *);
	int (*alloc)(struct irq_domain *, unsigned int, unsigned int, void *);
	void (*free)(struct irq_domain *, unsigned int, unsigned int);
};
struct irq_domain {
	const struct irq_domain_ops *ops;
	struct irq_domain *root, *parent;
	struct fwnode_handle *fwnode;
	struct mutex mutex;
	void *host_data;
	unsigned int mapcount;
	bool hierarchical;
};
struct irq_state { bool started, disabled, masked; unsigned int type; };
struct irq_data {
	struct irq_domain *domain;
	struct irq_data *parent_data;
	const struct irq_chip *chip;
	struct irq_state *state;
	irq_hw_number_t hwirq;
};
struct irq_fixture {
	struct irq_domain root;
	struct irq_data leaf_data, parent_data;
	struct irq_state state;
	unsigned int named, domains, descriptors, parent_allocs, parent_frees, irq_frees, lookups;
	unsigned int fail_stage, mask_writes, unmask_writes;
	bool conflict, race_conflict, parent_allocated, action, hardware_masked;
};
static struct irq_fixture irq_fixture;

static struct device_node *of_node_get(struct device_node *node)
{
	if (node) node->refs++;
	return node;
}
static void of_node_put(struct device_node *node)
{
	if (node) { assert(node->refs); node->refs--; }
}
static struct fwnode_handle *of_fwnode_handle(struct device_node *node)
{
	if (!node) return NULL;
	node->fwnode.node = node;
	return &node->fwnode;
}
static bool is_of_node(struct fwnode_handle *node) { return node && node->node; }
static struct device_node *to_of_node(struct fwnode_handle *node) { return node ? node->node : NULL; }
static bool of_device_is_compatible(struct device_node *node, const char *name)
{
	return node && node->aic && strcmp(name, "apple,aic") == 0;
}
static void root_mask(struct irq_data *data)
{
	assert(data == &irq_fixture.parent_data);
	irq_fixture.mask_writes++; irq_fixture.hardware_masked = true;
	data->state->masked = true;
}
static void root_unmask(struct irq_data *data)
{
	assert(data == &irq_fixture.parent_data);
	irq_fixture.unmask_writes++; irq_fixture.hardware_masked = false;
	data->state->masked = false;
}
static void irq_chip_mask_parent(struct irq_data *data) { root_mask(data->parent_data); }
static void irq_chip_unmask_parent(struct irq_data *data) { root_unmask(data->parent_data); }
static void irq_chip_eoi_parent(struct irq_data *data) { assert(data->parent_data); }
static int irq_chip_set_affinity_parent(struct irq_data *data, const struct cpumask *mask, bool force)
{
	(void)mask; (void)force; assert(data->parent_data); return 0;
}
static int irq_chip_set_type_parent(struct irq_data *data, unsigned int type)
{
	assert(data->parent_data);
	return type == 4 ? 0 : -EINVAL;
}
static const struct irq_chip root_chip = {.name = "AIC"};
static const struct irq_chip wrong_chip = {.name = "AIC2"};
static int root_translate(struct irq_domain *root, struct irq_fwspec *spec,
			  irq_hw_number_t *number, unsigned int *type)
{
	assert(root == &irq_fixture.root && spec->fwnode == root->fwnode);
	if (irq_fixture.fail_stage == 1) return -EIO;
	*number = irq_fixture.fail_stage == 2 ? 248 : 0x10000 + spec->param[1];
	*type = irq_fixture.fail_stage == 3 ? 1 : spec->param[2];
	return 0;
}
static int root_alloc(struct irq_domain *root, unsigned int virq, unsigned int count, void *arg)
{
	assert(root->mutex.held && virq == 32 && count == 1 && arg);
	assert(!irq_fixture.conflict);
	irq_fixture.parent_allocs++;
	if (irq_fixture.fail_stage == 7) return -EIO;
	irq_fixture.parent_allocated = true;
	irq_fixture.parent_data = (struct irq_data){.domain = root, .state = &irq_fixture.state,
		.hwirq = irq_fixture.fail_stage == 8 ? 249 : 0x100f8,
		.chip = irq_fixture.fail_stage == 9 ? &wrong_chip : &root_chip};
	return 0;
}
static void root_free(struct irq_domain *root, unsigned int virq, unsigned int count)
{
	assert(root->mutex.held && virq == 32 && count == 1 && irq_fixture.parent_allocated);
	irq_fixture.parent_frees++; irq_fixture.parent_allocated = false;
}
static const struct irq_domain_ops root_ops = {.translate = root_translate, .alloc = root_alloc, .free = root_free};
static struct irq_domain *irq_find_matching_fwspec(struct irq_fwspec *spec, int bus)
{
	assert(bus == DOMAIN_BUS_WIRED && spec->fwnode == irq_fixture.root.fwnode);
	return &irq_fixture.root;
}
static bool irq_domain_is_hierarchy(struct irq_domain *domain) { return domain->hierarchical; }
static unsigned int irq_find_mapping(struct irq_domain *domain, irq_hw_number_t number)
{
	assert(domain == &irq_fixture.root && number == 0x100f8 && domain->mutex.held);
	irq_fixture.lookups++;
	return irq_fixture.conflict ? 64 : irq_fixture.descriptors ? 32 : 0;
}
static struct fwnode_handle *irq_domain_alloc_named_fwnode(const char *name)
{
	assert(strcmp(name, "n71-dart") == 0);
	if (irq_fixture.fail_stage == 4) return NULL;
	struct fwnode_handle *node = calloc(1, sizeof(*node));
	assert(node); node->refs = 1; irq_fixture.named++; return node;
}
static void irq_domain_free_fwnode(struct fwnode_handle *node)
{
	assert(node && !node->node && node->refs == 1 && irq_fixture.named);
	irq_fixture.named--; free(node);
}
static struct irq_domain *irq_domain_create_hierarchy(struct irq_domain *parent, unsigned int flags,
	unsigned int size, struct fwnode_handle *node, const struct irq_domain_ops *ops, void *owner)
{
	assert(parent == &irq_fixture.root && !flags && size == 1 && node && ops && owner);
	if (irq_fixture.fail_stage == 5) return NULL;
	struct irq_domain *child = calloc(1, sizeof(*child)); assert(child);
	*child = (struct irq_domain){.ops = ops, .root = parent, .parent = parent,
		.fwnode = node, .host_data = owner, .hierarchical = true};
	node->refs++; irq_fixture.domains++; return child;
}
static void irq_domain_remove(struct irq_domain *domain)
{
	assert(domain && domain != &irq_fixture.root && !domain->mapcount && irq_fixture.domains);
	assert(domain->fwnode->refs == 2); domain->fwnode->refs--;
	irq_fixture.domains--; free(domain);
}
static int irq_domain_alloc_irqs_parent(struct irq_domain *domain, unsigned int virq, unsigned int count, void *arg)
{
	return domain->parent->ops->alloc(domain->parent, virq, count, arg);
}
static struct irq_data *irq_domain_get_irq_data(struct irq_domain *domain, unsigned int virq)
{
	assert(virq == 32);
	if (domain == &irq_fixture.root)
		return irq_fixture.fail_stage == 10 ? NULL : &irq_fixture.parent_data;
	return &irq_fixture.leaf_data;
}
static void irq_domain_free_irqs_parent(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	domain->parent->ops->free(domain->parent, virq, count);
}
static void handle_fasteoi_irq(void) {}
static void irq_domain_set_info(struct irq_domain *domain, unsigned int virq, irq_hw_number_t number,
	const struct irq_chip *chip, void *owner, void (*handler)(void), void *data, const char *name)
{
	assert(virq == 32 && number == 0 && chip && owner && handler == handle_fasteoi_irq && !data && !name);
	irq_fixture.leaf_data.domain = domain; irq_fixture.leaf_data.hwirq = number;
	irq_fixture.leaf_data.chip = chip;
}
static int irq_domain_alloc_irqs(struct irq_domain *domain, unsigned int count, int node, void *argument)
{
	assert(count == 1 && node == NUMA_NO_NODE && !irq_fixture.descriptors);
	if (irq_fixture.fail_stage == 6) return -ENOMEM;
	if (irq_fixture.race_conflict) irq_fixture.conflict = true;
	irq_fixture.state = (struct irq_state){.disabled = true, .masked = true};
	irq_fixture.leaf_data = (struct irq_data){.domain = domain, .parent_data = &irq_fixture.parent_data,
		.state = &irq_fixture.state};
	assert(!domain->root->mutex.held); domain->root->mutex.held = true;
	int error = domain->ops->alloc(domain, 32, count, argument);
	domain->root->mutex.held = false;
	if (error) { assert(!irq_fixture.parent_allocated); return error; }
	assert(irq_fixture.leaf_data.chip && irq_fixture.parent_allocated);
	irq_fixture.descriptors = 1; domain->mapcount++; domain->parent->mapcount++;
	return 32;
}
static int irq_set_irq_type(unsigned int irq, unsigned int type)
{
	assert(irq == 32 && irq_fixture.descriptors && type == 4);
	if (irq_fixture.fail_stage == 11) return -EIO;
	int error = irq_fixture.leaf_data.chip->irq_set_type(&irq_fixture.leaf_data, type);
	if (!error) irq_fixture.state.type = type;
	return error;
}
static struct irq_data *irq_get_irq_data(unsigned int irq)
{
	assert(irq == 32); return irq_fixture.descriptors ? &irq_fixture.leaf_data : NULL;
}
static bool irq_has_action(unsigned int irq) { assert(irq == 32); return irq_fixture.action; }
static bool irqd_is_started(struct irq_data *data) { return data->state->started; }
static bool irqd_irq_disabled(struct irq_data *data) { return data->state->disabled; }
static bool irqd_irq_masked(struct irq_data *data) { return data->state->masked; }
static void irq_domain_free_irqs_common(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	irq_domain_free_irqs_parent(domain, virq, count);
}
static void irq_domain_free_irqs(unsigned int virq, unsigned int count)
{
	struct irq_domain *domain = irq_fixture.leaf_data.domain;
	assert(virq == 32 && count == 1 && !irq_fixture.action && !irq_fixture.state.started);
	assert(irq_fixture.state.disabled && irq_fixture.state.masked && irq_fixture.hardware_masked);
	assert(domain->mapcount == 1 && !domain->root->mutex.held);
	domain->root->mutex.held = true;
	domain->mapcount--; domain->parent->mapcount--;
	domain->ops->free(domain, virq, count);
	domain->root->mutex.held = false;
	irq_fixture.descriptors = 0; irq_fixture.irq_frees++;
}
static void irq_fixture_initialize(struct device_node *node)
{
	memset(&irq_fixture, 0, sizeof(irq_fixture));
	node->aic = true;
	irq_fixture.root = (struct irq_domain){.ops = &root_ops, .fwnode = of_fwnode_handle(node),
		.hierarchical = true};
	irq_fixture.root.root = &irq_fixture.root;
	irq_fixture.hardware_masked = true;
}
static void irq_fixture_released(struct device_node *node)
{
	assert(!irq_fixture.named && !irq_fixture.domains && !irq_fixture.descriptors);
	assert(!irq_fixture.parent_allocated && !node->refs && irq_fixture.hardware_masked);
}
#endif /* N71_DART_IRQ_FIXTURE_H */
