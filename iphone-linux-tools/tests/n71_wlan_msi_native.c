/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71_wlan_msi_native_fixture.h"
#include "n71-wlan-msi-native.h"

static unsigned int cases;
static const struct n71_wlan_msi_request request = {
	.irq = {3, 32, 256, 1, 8, 8, 0}, .address_lo = 0xbffff000U,
};
static void initialize(struct device_node *node, struct n71_wlan_msi *binding, struct irq_fwspec *spec)
{
	cases++; memset(node, 0, sizeof(*node)); memset(binding, 0, sizeof(*binding));
	memset(&msi_fixture, 0, sizeof(msi_fixture));
	msi_fixture.fail_parent_after = msi_fixture.fail_leaf_after = msi_fixture.bad_parent_index = -1;
	msi_fixture.translate_index = -1; node->aic = true; node->fwnode.node = node;
	msi_fixture.root = (struct irq_domain){.ops = &root_ops, .fwnode = &node->fwnode, .hierarchical = true};
	msi_fixture.root.root = &msi_fixture.root;
	msi_fixture.device.identity = 1; msi_fixture.foreign.identity = 2;
	msi_fixture.desc.dev = &msi_fixture.device;
	*spec = (struct irq_fwspec){.fwnode = &node->fwnode, .param_count = 3, .param = {0, 264, 1, 0}};
}
static void attach(struct n71_wlan_msi *binding)
{
	msi_fixture.child = (struct irq_domain){.parent = binding->domain, .root = binding->parent};
	msi_fixture.child_ops = (struct msi_domain_ops){0};
	msi_fixture.child_info = (struct msi_domain_info){.ops = &msi_fixture.child_ops,
		.bus_token = DOMAIN_BUS_PCI_DEVICE_MSI, .flags = MSI_FLAG_MULTI_PCI_MSI};
	assert(binding->domain->msi_parent_ops->init_dev_msi_info(&msi_fixture.device,
		binding->domain, binding->domain, &msi_fixture.child_info));
	msi_fixture.argument.desc = &msi_fixture.desc; msi_fixture.argument.hwirq = 99;
	assert(msi_fixture.child_ops.msi_prepare(&msi_fixture.child, &msi_fixture.device, 16, &msi_fixture.argument) == 0);
	assert(binding->child == &msi_fixture.child && binding->child_device == &msi_fixture.device);
	assert(!msi_fixture.argument.desc && !msi_fixture.argument.hwirq);
	msi_fixture.argument.desc = &msi_fixture.desc; msi_fixture.child_present = true;
}
static void detach(struct n71_wlan_msi *binding)
{
	assert(!binding->slots && !binding->domain->mapcount && !msi_fixture.descriptors);
	msi_fixture.child_ops.msi_teardown(&msi_fixture.child, &msi_fixture.argument);
	assert(!binding->child && !binding->child_device); msi_fixture.child_present = false;
}
static void release(struct device_node *node, struct n71_wlan_msi *binding)
{
	assert(n71_wlan_msi_release(binding) == 0);
	assert(!binding->domain && !binding->parent && !binding->node && !binding->fwnode);
	assert(!node->refs && !msi_fixture.named && !msi_fixture.domains && !msi_fixture.descriptors);
	for (unsigned int i = 0; i < 128; i++) assert(!msi_fixture.parent_allocated[i]);
}
static void lifetime_and_messages(void)
{
	struct device_node node;
	struct n71_wlan_msi binding;
	struct irq_fwspec spec;
	struct msi_msg message;
	initialize(&node, &binding, &spec);
	assert(n71_wlan_msi_acquire(&binding, &spec, &request) == 0);
	assert(node.refs == 1 && msi_fixture.named == 1 && !binding.slots);
	assert(n71_wlan_msi_acquire(&binding, &spec, &request) == -EBUSY);
	assert(!(n71_wlan_msi_parent_ops.supported_flags & MSI_FLAG_PCI_MSIX));
	assert(n71_wlan_msi_parent_ops.supported_flags & MSI_FLAG_MULTI_PCI_MSI);
	assert(n71_wlan_msi_parent_ops.required_flags == (1U | 2U | (1U << 9)));
	assert(n71_wlan_msi_parent_ops.chip_flags == MSI_CHIP_FLAG_SET_EOI);
	assert(n71_wlan_msi_parent_ops.bus_select_token == DOMAIN_BUS_PCI_MSI);
	attach(&binding);
	/* Mutations: ignore a child with zero vectors, overwrite a live child, or omit its device identity. */
	assert(n71_wlan_msi_release(&binding) == -EBUSY && binding.domain && node.refs == 1);
	msi_alloc_info_t duplicate = {0};
	assert(msi_fixture.child_ops.msi_prepare(&msi_fixture.child, &msi_fixture.foreign, 16, &duplicate) == -EBUSY);
	assert(binding.child_device == &msi_fixture.device);
	assert(core_allocate(binding.domain, 32, 8, &msi_fixture.argument) == 0 && binding.slots == 255);
	for (unsigned int i = 0; i < 8; i++) {
		assert(msi_fixture.leaf[32 + i].hwirq == i && msi_fixture.type[32 + i] == 1);
		msi_fixture.leaf[32 + i].chip->irq_compose_msi_msg(&msi_fixture.leaf[32 + i], &message);
		assert(message.address_lo == 0xbffff000U && !message.address_hi && message.data == 8 + i);
	}
	assert(n71_wlan_msi_release(&binding) == -EBUSY);
	/* Mutations: free multiple vectors or foreign/out-of-range/unowned IRQ data. */
	for (unsigned int kind = 0; kind < 5; kind++) {
		cases++; struct irq_data saved = msi_fixture.leaf[32];
		if (kind == 1) msi_fixture.leaf[32].chip = &wrong_chip;
		if (kind == 2) msi_fixture.leaf[32].chip_data = NULL;
		if (kind == 3) { msi_fixture.leaf[32].hwirq = 8; binding.slots |= 256; }
		if (kind == 4) binding.slots &= ~1U;
		unsigned int warnings = msi_fixture.warnings;
		mutex_lock(&binding.parent->mutex);
		n71_wlan_msi_free(binding.domain, 32, kind ? 1 : 2);
		mutex_unlock(&binding.parent->mutex);
		assert(msi_fixture.warnings == warnings + 1 && !msi_fixture.parent_frees);
		assert(msi_fixture.parent_allocated[32] && msi_fixture.leaf[32].chip);
		msi_fixture.leaf[32] = saved; binding.slots = 255;
	}
	/* Mutations: whole-region free for a multi-MSI grant, skip parent free/reset, or message uses AIC index. */
	core_free(binding.domain, 34, 1);
	assert(binding.slots == (255U & ~(1U << 2)) && binding.domain->mapcount == 7);
	assert(core_allocate(binding.domain, 64, 1, &msi_fixture.argument) == 0);
	assert(msi_fixture.leaf[64].hwirq == 2 && binding.slots == 255);
	core_free(binding.domain, 64, 1); core_free(binding.domain, 32, 2); core_free(binding.domain, 35, 5);
	assert(!binding.slots && !binding.domain->mapcount && msi_fixture.parent_frees == 9);
	assert(n71_wlan_msi_release(&binding) == -EBUSY); /* MSI disabled still owns the child. */
	detach(&binding); release(&node, &binding);
	assert(n71_wlan_msi_release(&binding) == 0 && msi_fixture.parent_frees == 9);
}
static void allocator_properties(void)
{
	struct device_node node;
	struct n71_wlan_msi binding;
	struct irq_fwspec spec;
	/* Mutations: unaligned grant, wrong count/bounds, overlap, clobber another live region or omit rollback. */
	for (unsigned int occupied = 0; occupied < 256; occupied++) {
		for (unsigned int count = 1; count <= 8; count *= 2) {
			initialize(&node, &binding, &spec);
			assert(n71_wlan_msi_acquire(&binding, &spec, &request) == 0); attach(&binding);
			binding.slots = occupied;
			unsigned int first;
			for (first = 0; first + count <= 8; first += count)
				if (!(occupied & (((1U << count) - 1) << first))) break;
			int error = core_allocate(binding.domain, 32, count, &msi_fixture.argument);
			if (first + count > 8) assert(error == -ENOSPC && binding.slots == occupied);
			else {
				assert(error == 0 && msi_fixture.leaf[32].hwirq == first);
				assert(binding.slots == (occupied | (((1U << count) - 1) << first)));
				core_free(binding.domain, 32, count); assert(binding.slots == occupied);
			}
			binding.slots = 0; detach(&binding); release(&node, &binding);
		}
	}
}
static void rollback_and_conflicts(void)
{
	struct device_node node;
	struct n71_wlan_msi binding;
	struct irq_fwspec spec;
	/* Mutations: skip a parent conflict, partial failure leaks parents/grant, wrong parent chip/domain/hwirq. */
	for (unsigned int kind = 0; kind < 6; kind++) {
		for (unsigned int i = 0; i < 8; i++) {
			initialize(&node, &binding, &spec);
			assert(n71_wlan_msi_acquire(&binding, &spec, &request) == 0); attach(&binding);
			if (!kind) msi_fixture.foreign_mask = 1U << i;
			if (kind == 1) msi_fixture.fail_parent_after = i;
			if (kind == 2) msi_fixture.fail_leaf_after = i;
			if (kind >= 3) { msi_fixture.bad_parent_index = i; msi_fixture.bad_parent_kind = kind - 2; }
			int error = core_allocate(binding.domain, 32, 8, &msi_fixture.argument);
			assert(error == (!kind ? -EBUSY : kind <= 2 ? -EIO : -EINVAL));
			assert(!binding.slots && !binding.domain->mapcount && !msi_fixture.descriptors);
			if (!kind) assert(msi_fixture.foreign_mask == (1U << i) && !msi_fixture.parent_frees);
			if (kind == 1) assert(msi_fixture.parent_frees == i);
			if (kind >= 2) assert(msi_fixture.parent_frees == 8);
			msi_fixture.foreign_mask = 0; msi_fixture.fail_parent_after = msi_fixture.fail_leaf_after = -1;
			msi_fixture.bad_parent_index = -1;
			assert(core_allocate(binding.domain, 32, 4, &msi_fixture.argument) == 0);
			core_free(binding.domain, 32, 4); detach(&binding); release(&node, &binding);
		}
	}
}
static void refusals(void)
{
	struct device_node node;
	struct n71_wlan_msi binding;
	struct irq_fwspec spec;
	/* Mutations: omit N71 cell, request, root or translation validation; skip partial constructor cleanup. */
	for (unsigned int index = 0; index < 10; index++) {
		initialize(&node, &binding, &spec);
		struct n71_wlan_msi_request altered = request;
		if (!index) spec.param_count = 2;
		if (index == 1) spec.param[0] = 1;
		if (index == 2) spec.param[1] = 263;
		if (index == 3) spec.param[2] = 4;
		if (index == 4) spec.fwnode = NULL;
		if (index == 5) node.aic = false;
		if (index == 6) altered.irq.index = 1;
		if (index == 7) altered.address_lo++;
		if (index == 8) msi_fixture.fail_named = true;
		if (index == 9) msi_fixture.fail_domain = true;
		assert(n71_wlan_msi_acquire(&binding, &spec, &altered) == (index < 8 ? -EINVAL : -ENOMEM));
		release(&node, &binding);
	}
	for (unsigned int kind = 1; kind <= 3; kind++) for (unsigned int i = 0; i < 8; i++) {
		initialize(&node, &binding, &spec); msi_fixture.translate_index = i; msi_fixture.translate_kind = kind;
		assert(n71_wlan_msi_acquire(&binding, &spec, &request) == (kind == 1 ? -EIO : -EINVAL));
		release(&node, &binding);
	}
	for (unsigned int kind = 0; kind < 6; kind++) {
		initialize(&node, &binding, &spec); struct irq_domain_ops altered = root_ops;
		if (!kind) msi_fixture.root.parent = &msi_fixture.root;
		if (kind == 1) msi_fixture.root.root = NULL;
		if (kind == 2) msi_fixture.root.hierarchical = false;
		if (kind == 3) altered.translate = NULL;
		if (kind == 4) altered.alloc = NULL;
		if (kind == 5) altered.free = NULL;
		msi_fixture.root.ops = &altered;
		assert(n71_wlan_msi_acquire(&binding, &spec, &request) == -ENODEV);
		release(&node, &binding);
	}
	initialize(&node, &binding, &spec); assert(n71_wlan_msi_acquire(&binding, &spec, &request) == 0);
	msi_fixture.child_info = (struct msi_domain_info){.ops = &msi_fixture.child_ops, .bus_token = DOMAIN_BUS_PCI_DEVICE_MSIX};
	assert(!n71_wlan_msi_init_child(&msi_fixture.device, binding.domain, binding.domain, &msi_fixture.child_info));
	msi_fixture.child_info.bus_token = DOMAIN_BUS_PCI_DEVICE_MSI; msi_fixture.child_info.flags = MSI_FLAG_PCI_MSIX;
	assert(!n71_wlan_msi_init_child(&msi_fixture.device, binding.domain, binding.domain, &msi_fixture.child_info));
	msi_fixture.child_info.flags = 0; msi_fixture.fail_library = true;
	assert(!n71_wlan_msi_init_child(&msi_fixture.device, binding.domain, binding.domain, &msi_fixture.child_info));
	msi_fixture.fail_library = false; attach(&binding);
	for (unsigned int count = 0; count <= 16; count++) if (count != 1 && count != 2 && count != 4 && count != 8) {
		cases++; assert(core_allocate(binding.domain, 32, count, &msi_fixture.argument) == -EINVAL);
	}
	msi_fixture.desc.dev = &msi_fixture.foreign;
	assert(core_allocate(binding.domain, 32, 1, &msi_fixture.argument) == -EINVAL);
	msi_fixture.desc.dev = &msi_fixture.device;
	assert(core_allocate(binding.domain, 32, 1, NULL) == -EINVAL);
	assert(core_allocate(binding.domain, 0, 1, &msi_fixture.argument) == -EINVAL);
	msi_fixture.argument.desc = NULL;
	assert(core_allocate(binding.domain, 32, 1, &msi_fixture.argument) == -EINVAL);
	msi_fixture.argument.desc = &msi_fixture.desc;
	assert(msi_fixture.child_ops.msi_prepare(&msi_fixture.child, NULL, 16, &msi_fixture.argument) == -EINVAL);
	assert(msi_fixture.child_ops.msi_prepare(&msi_fixture.child, &msi_fixture.device, 0, &msi_fixture.argument) == -EINVAL);
	struct msi_msg message = {1, 1, 1}; struct irq_data invalid = {.domain = binding.domain, .chip_data = &binding, .hwirq = 8};
	n71_wlan_msi_compose(&invalid, &message); assert(!message.address_lo && !message.address_hi && !message.data);
	invalid.hwirq = 0; message = (struct msi_msg){1, 1, 1};
	n71_wlan_msi_compose(&invalid, &message); assert(!message.address_lo && !message.address_hi && !message.data);
	invalid.domain = &msi_fixture.root; binding.slots = 1; message = (struct msi_msg){1, 1, 1};
	n71_wlan_msi_compose(&invalid, &message); assert(!message.address_lo && !message.address_hi && !message.data);
	binding.slots = 0; detach(&binding);
	binding.slots = 1;
	assert(n71_wlan_msi_release(&binding) == -EBUSY && binding.domain); binding.slots = 0;
	binding.domain->mapcount = 1;
	assert(n71_wlan_msi_release(&binding) == -EBUSY && binding.domain); binding.domain->mapcount = 0;
	binding.domain->host_data = NULL;
	assert(n71_wlan_msi_release(&binding) == -EINVAL && binding.domain); binding.domain->host_data = &binding;
	release(&node, &binding);
	assert(n71_wlan_msi_acquire(NULL, &spec, &request) == -EINVAL);
	assert(n71_wlan_msi_release(NULL) == -EINVAL);
}
int main(void)
{
#ifdef __linux__
	assert(prctl(PR_SET_DUMPABLE, 0) == 0);
#endif
	lifetime_and_messages(); allocator_properties(); rollback_and_conflicts(); refusals();
	printf("N71_WLAN_MSI_NATIVE_OK cases=%u\n", cases);
	return 0;
}
