/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
#include "n71_dart_irq_fixture.h"
#include "n71-dart-irq.h"

static unsigned int cases;
static void initialize(struct device_node *node, struct n71_dart_irq *binding, struct irq_fwspec *spec)
{
	cases++; memset(node, 0, sizeof(*node)); memset(binding, 0, sizeof(*binding));
	irq_fixture_initialize(node);
	*spec = (struct irq_fwspec){.fwnode = of_fwnode_handle(node), .param_count = 3, .param = {0, 248, 4, 0}};
}
static void release(struct device_node *node, struct n71_dart_irq *binding)
{
	assert(n71_dart_irq_release(binding) == 0);
	assert(!binding->irq && !binding->domain && !binding->fwnode && !binding->node && !binding->parent);
	irq_fixture_released(node);
}

int main(void)
{
	struct device_node node;
	struct n71_dart_irq binding;
	struct irq_fwspec spec;
	struct irq_domain_ops altered;
	unsigned int index, frees;

	/* Mutations: duplicate ownership, omit trigger, change parent identity or free an active IRQ. */
	initialize(&node, &binding, &spec);
	assert(n71_dart_irq_acquire(&binding, &spec) == 0);
	assert(binding.irq == 32 && binding.hwirq == 0x100f8 && binding.domain->mapcount == 1);
	assert(binding.domain->parent == binding.parent && node.refs == 1);
	assert(irq_fixture.state.type == 4 && irq_fixture.state.disabled && irq_fixture.state.masked);
	assert(!irq_fixture.mask_writes && !irq_fixture.unmask_writes);
	assert(n71_dart_irq_acquire(&binding, &spec) == -EBUSY && irq_fixture.named == 1);
	irq_fixture.action = true; irq_fixture.state.started = true; irq_fixture.state.disabled = false;
	irq_fixture.leaf_data.chip->irq_unmask(&irq_fixture.leaf_data);
	assert(n71_dart_irq_release(&binding) == -EBUSY && binding.irq == 32 && node.refs == 1);
	irq_fixture.action = false; irq_fixture.state.started = false; irq_fixture.state.disabled = true;
	irq_fixture.leaf_data.chip->irq_mask(&irq_fixture.leaf_data);
	release(&node, &binding);
	frees = irq_fixture.irq_frees;
	assert(frees == 1 && n71_dart_irq_release(&binding) == 0 && irq_fixture.irq_frees == frees);

	/* Mutations: ignore partial allocation failure, skip parent rollback or leak node/domain/fwnode. */
	for (index = 1; index <= 11; index++) {
		initialize(&node, &binding, &spec); irq_fixture.fail_stage = index;
		assert(n71_dart_irq_acquire(&binding, &spec) < 0);
		release(&node, &binding);
		assert(!irq_fixture.mask_writes && !irq_fixture.unmask_writes);
	}
	for (index = 0; index < 2; index++) {
		initialize(&node, &binding, &spec);
		if (!index) irq_fixture.conflict = true;
		else irq_fixture.race_conflict = true;
		assert(n71_dart_irq_acquire(&binding, &spec) == -EBUSY);
		assert(irq_fixture.conflict && !irq_fixture.parent_allocs && !irq_fixture.irq_frees);
		release(&node, &binding);
		assert(irq_fixture.conflict);
	}

	/* Mutations: omit N71 cells/hwirq/root/domain callback guards. */
	for (index = 0; index < 6; index++) {
		initialize(&node, &binding, &spec);
		if (!index) spec.param_count = 2;
		if (index == 1) spec.param[0] = 1;
		if (index == 2) spec.param[1] = 247;
		if (index == 3) spec.param[2] = 1;
		if (index == 4) spec.fwnode = NULL;
		if (index == 5) node.aic = false;
		assert(n71_dart_irq_acquire(&binding, &spec) == -EINVAL);
		assert(!binding.node && !irq_fixture.named && !irq_fixture.lookups);
		release(&node, &binding);
	}
	for (index = 0; index < 6; index++) {
		initialize(&node, &binding, &spec); altered = root_ops;
		if (!index) irq_fixture.root.parent = &irq_fixture.root;
		if (index == 1) irq_fixture.root.root = NULL;
		if (index == 2) irq_fixture.root.hierarchical = false;
		if (index == 3) altered.translate = NULL;
		if (index == 4) altered.alloc = NULL;
		if (index == 5) altered.free = NULL;
		irq_fixture.root.ops = &altered;
		assert(n71_dart_irq_acquire(&binding, &spec) == -ENODEV);
		assert(!binding.node && !irq_fixture.named);
		release(&node, &binding);
	}
	initialize(&node, &binding, &spec);
	binding.node = of_node_get(&node); binding.parent = &irq_fixture.root;
	binding.spec = spec; binding.hwirq = 0x100f8;
	binding.fwnode = irq_domain_alloc_named_fwnode("n71-dart");
	binding.domain = irq_domain_create_hierarchy(binding.parent, 0, 1, binding.fwnode, &n71_dart_irq_ops, &binding);
	irq_fixture.root.mutex.held = true;
	assert(n71_dart_irq_alloc(binding.domain, 32, 2, &binding) == -EINVAL);
	assert(n71_dart_irq_alloc(binding.domain, 32, 1, NULL) == -EINVAL);
	assert(n71_dart_irq_alloc(binding.domain, 0, 1, &binding) == -EINVAL);
	irq_fixture.root.mutex.held = false;
	assert(!irq_fixture.parent_allocs);
	release(&node, &binding);

	/* Mutations: ignore teardown identity, action, started, disabled or masked state. */
	for (index = 0; index < 4; index++) {
		initialize(&node, &binding, &spec);
		assert(n71_dart_irq_acquire(&binding, &spec) == 0);
		if (!index) irq_fixture.action = true;
		if (index == 1) irq_fixture.state.started = true;
		if (index == 2) irq_fixture.state.disabled = false;
		if (index == 3) irq_fixture.state.masked = false;
		assert(n71_dart_irq_release(&binding) == -EBUSY && binding.irq == 32 && node.refs == 1);
		assert(!irq_fixture.irq_frees);
		irq_fixture.action = false; irq_fixture.state.started = false; irq_fixture.state.disabled = true;
		irq_fixture.leaf_data.chip->irq_mask(&irq_fixture.leaf_data);
		release(&node, &binding);
	}
	for (index = 0; index < 5; index++) {
		initialize(&node, &binding, &spec);
		assert(n71_dart_irq_acquire(&binding, &spec) == 0);
		if (!index) irq_fixture.leaf_data.hwirq = 1;
		if (index == 1) irq_fixture.leaf_data.domain = &irq_fixture.root;
		if (index == 2) irq_fixture.leaf_data.parent_data = NULL;
		if (index == 3) irq_fixture.parent_data.hwirq = 248;
		if (index == 4) irq_fixture.parent_data.domain = NULL;
		assert(n71_dart_irq_release(&binding) == -EINVAL && binding.irq == 32 && node.refs == 1);
		irq_fixture.leaf_data.hwirq = 0; irq_fixture.leaf_data.domain = binding.domain;
		irq_fixture.leaf_data.parent_data = &irq_fixture.parent_data;
		irq_fixture.parent_data.hwirq = 0x100f8; irq_fixture.parent_data.domain = &irq_fixture.root;
		release(&node, &binding);
	}
	initialize(&node, &binding, &spec); irq_fixture.fail_stage = 6;
	assert(n71_dart_irq_acquire(&binding, &spec) == -ENOMEM);
	binding.domain->mapcount = 1;
	assert(n71_dart_irq_release(&binding) == -EBUSY && binding.domain && binding.fwnode && node.refs == 1);
	binding.domain->mapcount = 0;
	release(&node, &binding);
	assert(n71_dart_irq_acquire(NULL, &spec) == -EINVAL);
	assert(n71_dart_irq_acquire(&binding, NULL) == -EINVAL);
	assert(n71_dart_irq_release(NULL) == -EINVAL);
	printf("N71_DART_IRQ_OK cases=%u\n", cases);
	return 0;
}
