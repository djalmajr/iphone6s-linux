/* SPDX-License-Identifier: GPL-2.0-only */
/* Model core dependencies; execute the production MSI callbacks directly. */
#ifndef N71_WLAN_MSI_NATIVE_FIXTURE_H
#define N71_WLAN_MSI_NATIVE_FIXTURE_H
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define IRQ_TYPE_EDGE_RISING 1U
#define DOMAIN_BUS_WIRED 1U
#define DOMAIN_BUS_PCI_MSI 2U
#define DOMAIN_BUS_PCI_DEVICE_MSI 3U
#define DOMAIN_BUS_PCI_DEVICE_MSIX 4U
#define MSI_GENERIC_FLAGS_MASK 0xffffU
#define MSI_FLAG_MULTI_PCI_MSI (1U << 16)
#define MSI_FLAG_PCI_MSIX (1U << 17)
#define MSI_FLAG_USE_DEF_DOM_OPS 1U
#define MSI_FLAG_USE_DEF_CHIP_OPS 2U
#define MSI_FLAG_PCI_MSI_MASK_PARENT (1U << 9)
#define MSI_CHIP_FLAG_SET_EOI 1U
typedef unsigned long irq_hw_number_t;
struct device_node;
struct fwnode_handle { struct device_node *node; unsigned int refs; };
struct device_node { bool aic; unsigned int refs; struct fwnode_handle fwnode; };
struct mutex { bool held; };
#define lockdep_assert_held(lock) assert((lock)->held)
static void mutex_lock(struct mutex *lock) { assert(!lock->held); lock->held = true; }
static void mutex_unlock(struct mutex *lock) { assert(lock->held); lock->held = false; }
struct device { unsigned int identity; };
struct msi_desc { struct device *dev; };
typedef struct { struct msi_desc *desc; irq_hw_number_t hwirq; } msi_alloc_info_t;
struct msi_msg { unsigned int address_lo, address_hi, data; };
struct cpumask { int unused; };
struct irq_domain;
struct irq_data;
struct irq_chip {
	const char *name;
	void (*irq_mask)(struct irq_data *), (*irq_unmask)(struct irq_data *), (*irq_eoi)(struct irq_data *);
	int (*irq_set_affinity)(struct irq_data *, const struct cpumask *, bool);
	int (*irq_set_type)(struct irq_data *, unsigned int);
	void (*irq_compose_msi_msg)(struct irq_data *, struct msi_msg *);
};
struct irq_fwspec { struct fwnode_handle *fwnode; unsigned int param_count, param[4]; };
struct irq_domain_ops {
	int (*translate)(struct irq_domain *, struct irq_fwspec *, irq_hw_number_t *, unsigned int *);
	int (*alloc)(struct irq_domain *, unsigned int, unsigned int, void *);
	void (*free)(struct irq_domain *, unsigned int, unsigned int);
};
struct msi_domain_ops {
	int (*msi_prepare)(struct irq_domain *, struct device *, int, msi_alloc_info_t *);
	void (*msi_teardown)(struct irq_domain *, msi_alloc_info_t *);
};
struct msi_domain_info {
	unsigned int flags, bus_token;
	struct msi_domain_ops *ops;
};
struct msi_parent_ops {
	unsigned int supported_flags, required_flags, chip_flags, bus_select_token;
	bool (*init_dev_msi_info)(struct device *, struct irq_domain *, struct irq_domain *, struct msi_domain_info *);
};
struct irq_domain {
	const struct irq_domain_ops *ops;
	const struct msi_parent_ops *msi_parent_ops;
	struct irq_domain *root, *parent;
	struct fwnode_handle *fwnode;
	struct mutex mutex;
	void *host_data;
	unsigned int mapcount;
	bool hierarchical;
};
struct irq_domain_info {
	unsigned int size;
	struct fwnode_handle *fwnode;
	struct irq_domain *parent;
	const struct irq_domain_ops *ops;
	void *host_data;
};
struct irq_data {
	struct irq_domain *domain;
	struct irq_data *parent_data;
	const struct irq_chip *chip;
	void *chip_data;
	irq_hw_number_t hwirq;
	unsigned int *type;
};
struct msi_fixture {
	struct irq_domain root, child;
	struct irq_data leaf[128], parent[128];
	unsigned int type[128];
	bool allocated[128], parent_allocated[128], child_present;
	struct device device, foreign;
	struct msi_desc desc;
	msi_alloc_info_t argument;
	struct msi_domain_ops child_ops;
	struct msi_domain_info child_info;
	unsigned int named, domains, descriptors, parent_frees, resets, warnings, foreign_mask;
	int fail_parent_after, fail_leaf_after, bad_parent_index, bad_parent_kind, translate_index, translate_kind;
	bool fail_named, fail_domain, fail_library;
};
static struct msi_fixture msi_fixture;
#define WARN_ON_ONCE(condition) ((condition) ? (msi_fixture.warnings++, true) : false)

static struct device_node *of_node_get(struct device_node *node) { if (node) node->refs++; return node; }
static void of_node_put(struct device_node *node) { if (node) { assert(node->refs); node->refs--; } }
static bool is_of_node(struct fwnode_handle *node) { return node && node->node; }
static struct device_node *to_of_node(struct fwnode_handle *node) { return node ? node->node : NULL; }
static bool of_device_is_compatible(struct device_node *node, const char *name)
{
	return node && node->aic && strcmp(name, "apple,aic") == 0;
}
static void irq_chip_mask_parent(struct irq_data *data) { assert(data->parent_data->chip); }
static void irq_chip_unmask_parent(struct irq_data *data) { assert(data->parent_data->chip); }
static void irq_chip_eoi_parent(struct irq_data *data) { assert(data->parent_data->chip); }
static int irq_chip_set_affinity_parent(struct irq_data *data, const struct cpumask *mask, bool force)
{
	(void)mask; (void)force; assert(data->parent_data->chip); return 0;
}
static int irq_chip_set_type_parent(struct irq_data *data, unsigned int type)
{
	assert(data->parent_data->chip); return type == 1 ? 0 : -EINVAL;
}
static const struct irq_chip root_chip = {.name = "AIC"}, wrong_chip = {.name = "AIC2"};
static int root_translate(struct irq_domain *domain, struct irq_fwspec *spec,
			  irq_hw_number_t *hwirq, unsigned int *type)
{
	assert(domain == &msi_fixture.root && spec->fwnode == domain->fwnode);
	int index = (int)spec->param[1] - 264;
	if (index == msi_fixture.translate_index && msi_fixture.translate_kind == 1) return -EIO;
	*hwirq = 0x10000 + spec->param[1]; *type = spec->param[2];
	if (index == msi_fixture.translate_index && msi_fixture.translate_kind == 2) (*hwirq)++;
	if (index == msi_fixture.translate_index && msi_fixture.translate_kind == 3) *type = 4;
	return 0;
}
static int root_alloc(struct irq_domain *domain, unsigned int virq, unsigned int count, void *arg)
{
	struct irq_fwspec *spec = arg;
	assert(domain->mutex.held && spec && spec->param_count == 3 && spec->param[0] == 0 && spec->param[2] == 1);
	for (unsigned int i = 0; i < count; i++) {
		if ((int)i == msi_fixture.fail_parent_after) return -EIO;
		unsigned int v = virq + i; assert(v < 128 && !msi_fixture.parent_allocated[v]);
		assert(!(msi_fixture.foreign_mask & (1U << (spec->param[1] - 264 + i))));
		msi_fixture.parent_allocated[v] = true;
		msi_fixture.parent[v] = (struct irq_data){.domain = domain, .hwirq = 0x10000 + spec->param[1] + i,
			.chip = &root_chip, .type = &msi_fixture.type[v]};
		if ((int)i == msi_fixture.bad_parent_index) {
			if (msi_fixture.bad_parent_kind == 1) msi_fixture.parent[v].hwirq++;
			if (msi_fixture.bad_parent_kind == 2) msi_fixture.parent[v].chip = &wrong_chip;
			if (msi_fixture.bad_parent_kind == 3) msi_fixture.parent[v].domain = NULL;
		}
	}
	return 0;
}
static void root_free(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	assert(domain->mutex.held && count == 1 && msi_fixture.parent_allocated[virq]);
	msi_fixture.parent_allocated[virq] = false;
	msi_fixture.parent[virq].chip = NULL; msi_fixture.parent_frees++;
}
static const struct irq_domain_ops root_ops = {.translate = root_translate, .alloc = root_alloc, .free = root_free};
static bool irq_domain_is_hierarchy(struct irq_domain *domain) { return domain->hierarchical; }
static struct irq_domain *irq_find_matching_fwspec(struct irq_fwspec *spec, unsigned int bus)
{
	assert(bus == DOMAIN_BUS_WIRED && spec->fwnode == msi_fixture.root.fwnode); return &msi_fixture.root;
}
static unsigned int irq_find_mapping(struct irq_domain *domain, irq_hw_number_t hwirq)
{
	assert(domain == &msi_fixture.root && domain->mutex.held && hwirq >= 0x10108 && hwirq < 0x10110);
	if (msi_fixture.foreign_mask & (1U << (hwirq - 0x10108))) return 127;
	for (unsigned int v = 0; v < 128; v++)
		if (msi_fixture.allocated[v] && msi_fixture.parent[v].hwirq == hwirq) return v;
	return 0;
}
static struct fwnode_handle *irq_domain_alloc_named_fwnode(const char *name)
{
	assert(strcmp(name, "n71-wlan-msi") == 0);
	if (msi_fixture.fail_named) return NULL;
	struct fwnode_handle *node = calloc(1, sizeof(*node)); assert(node);
	node->refs = 1; msi_fixture.named++; return node;
}
static void irq_domain_free_fwnode(struct fwnode_handle *node)
{
	assert(node && node->refs == 1 && msi_fixture.named); msi_fixture.named--; free(node);
}
static struct irq_domain *msi_create_parent_irq_domain(struct irq_domain_info *info, const struct msi_parent_ops *ops)
{
	assert(info->size == 8 && info->parent == &msi_fixture.root && info->host_data);
	if (msi_fixture.fail_domain) return NULL;
	struct irq_domain *domain = calloc(1, sizeof(*domain)); assert(domain);
	*domain = (struct irq_domain){.ops = info->ops, .parent = info->parent, .root = info->parent,
		.host_data = info->host_data, .fwnode = info->fwnode, .msi_parent_ops = ops, .hierarchical = true};
	info->fwnode->refs++; msi_fixture.domains++; return domain;
}
static void irq_domain_remove(struct irq_domain *domain)
{
	assert(!msi_fixture.child_present && !domain->mapcount && !msi_fixture.descriptors && msi_fixture.domains);
	assert(domain->fwnode->refs == 2); domain->fwnode->refs--; msi_fixture.domains--; free(domain);
}
static bool msi_lib_init_dev_msi_info(struct device *device, struct irq_domain *domain,
				    struct irq_domain *real_parent, struct msi_domain_info *info)
{
	assert(device && domain == real_parent && domain->msi_parent_ops);
	if (msi_fixture.fail_library) return false;
	info->flags = (info->flags & domain->msi_parent_ops->supported_flags) | domain->msi_parent_ops->required_flags;
	return true;
}
static int irq_domain_alloc_irqs_parent(struct irq_domain *domain, unsigned int virq, unsigned int count, void *arg)
{
	return domain->parent->ops->alloc(domain->parent, virq, count, arg);
}
static void irq_domain_free_irqs_parent(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	/* Match the pinned core: parent free is invoked separately for each vector. */
	for (unsigned int i = 0; i < count; i++) domain->parent->ops->free(domain->parent, virq + i, 1);
}
static struct irq_data *irq_domain_get_irq_data(struct irq_domain *domain, unsigned int virq)
{
	assert(virq < 128);
	return domain == &msi_fixture.root ? &msi_fixture.parent[virq] : &msi_fixture.leaf[virq];
}
static void *irq_data_get_irq_chip_data(struct irq_data *data) { return data->chip_data; }
static void irqd_set_trigger_type(struct irq_data *data, unsigned int type) { *data->type = type; }
static int irq_domain_set_hwirq_and_chip(struct irq_domain *domain, unsigned int virq, irq_hw_number_t hwirq,
				       const struct irq_chip *chip, void *owner)
{
	if ((int)(virq - 32) == msi_fixture.fail_leaf_after) return -EIO;
	struct irq_data *data = &msi_fixture.leaf[virq]; assert(data->domain == domain);
	data->hwirq = hwirq; data->chip = chip; data->chip_data = owner; return 0;
}
static void irq_domain_reset_irq_data(struct irq_data *data)
{
	assert(data); data->chip = NULL; data->chip_data = NULL; data->hwirq = 0; msi_fixture.resets++;
}
static void irq_domain_free_irqs_common(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	for (unsigned int i = 0; i < count; i++) irq_domain_reset_irq_data(&msi_fixture.leaf[virq + i]);
	irq_domain_free_irqs_parent(domain, virq, count);
}
static int core_allocate(struct irq_domain *domain, unsigned int virq, unsigned int count, void *argument)
{
	assert(virq + count <= 128);
	for (unsigned int i = 0; i < count; i++) {
		assert(!msi_fixture.allocated[virq + i]);
		msi_fixture.leaf[virq + i] = (struct irq_data){.domain = domain,
			.parent_data = &msi_fixture.parent[virq + i], .type = &msi_fixture.type[virq + i]};
	}
	mutex_lock(&domain->root->mutex);
	int error = domain->ops->alloc(domain, virq, count, argument);
	mutex_unlock(&domain->root->mutex);
	for (unsigned int i = 0; i < count; i++) {
		if (error) {
			assert(!msi_fixture.parent_allocated[virq + i] && !msi_fixture.leaf[virq + i].chip);
			msi_fixture.leaf[virq + i] = (struct irq_data){0};
		} else {
			assert(msi_fixture.parent_allocated[virq + i] && msi_fixture.leaf[virq + i].chip);
			msi_fixture.allocated[virq + i] = true; msi_fixture.descriptors++;
			domain->mapcount++; domain->parent->mapcount++;
		}
	}
	return error;
}
static void core_free(struct irq_domain *domain, unsigned int virq, unsigned int count)
{
	mutex_lock(&domain->root->mutex);
	for (unsigned int i = 0; i < count; i++) {
		unsigned int v = virq + i; assert(msi_fixture.allocated[v]);
		domain->mapcount--; domain->parent->mapcount--;
		domain->ops->free(domain, v, 1);
		assert(!msi_fixture.leaf[v].chip && !msi_fixture.parent_allocated[v]);
		msi_fixture.allocated[v] = false; msi_fixture.descriptors--;
	}
	mutex_unlock(&domain->root->mutex);
}
#endif /* N71_WLAN_MSI_NATIVE_FIXTURE_H */
