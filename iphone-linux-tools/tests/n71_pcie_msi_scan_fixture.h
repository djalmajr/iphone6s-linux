/* SPDX-License-Identifier: GPL-2.0-only */
/* PCI scan uses the real host lease; native MSI dependencies are tracked here. */
#ifndef N71_PCIE_MSI_SCAN_FIXTURE_H
#define N71_PCIE_MSI_SCAN_FIXTURE_H
#define N71_WLAN_MSI_NATIVE_H
#define IRQ_TYPE_EDGE_RISING 1U
#include "n71-wlan-msi-message.h"
struct device_node;
struct fwnode_handle { struct device_node *node; };
struct device_node { unsigned int refs; struct fwnode_handle fwnode; };
struct irq_domain { unsigned int mapcount; };
struct irq_fwspec { struct fwnode_handle *fwnode; unsigned int param_count, param[3]; };
struct n71_wlan_msi {
	struct device_node *node;
	struct fwnode_handle *fwnode;
	struct irq_domain *domain, *child;
	unsigned int slots;
};
static struct {
	struct device_node node;
	struct fwnode_handle named;
	struct irq_domain domain, foreign, child;
	unsigned int failure, acquire_calls, release_calls, domains, names;
	unsigned int drift;
	bool missing_parent, requested;
	int release_error;
} msi_mock;

static void msi_fixture_initialize(void)
{
	memset(&msi_mock, 0, sizeof(msi_mock)); msi_mock.node.fwnode.node = &msi_mock.node;
}
static struct device_node *of_irq_find_parent(struct device_node *node)
{
	if (!node || msi_mock.missing_parent) return NULL;
	assert(node == &msi_mock.node); node->refs++; return node;
}
static struct fwnode_handle *of_fwnode_handle(struct device_node *node) { return &node->fwnode; }
static void of_node_put(struct device_node *node) { assert(node->refs); node->refs--; }
static struct irq_domain *dev_get_msi_domain(struct device *device) { return device->msi_domain; }
static void dev_set_msi_domain(struct device *device, struct irq_domain *domain) { device->msi_domain = domain; }
static int n71_wlan_msi_acquire(struct n71_wlan_msi *binding, const struct irq_fwspec *spec,
				const struct n71_wlan_msi_request *request)
{
	struct n71_wlan_msi_reference reference;
	assert(!mock.scans && !binding->domain && !binding->node);
	assert(spec->fwnode == &msi_mock.node.fwnode && spec->param_count == 3);
	assert(spec->param[0] == 0 && spec->param[1] == 264 && spec->param[2] == 1);
	assert(n71_wlan_msi_message(request, &reference) == 0 && reference.message[2] == 8);
	msi_mock.acquire_calls++;
	if (msi_mock.failure == 1) return -EINVAL;
	binding->node = &msi_mock.node; binding->node->refs++;
	if (msi_mock.failure == 2) return -ENOMEM;
	binding->fwnode = &msi_mock.named; msi_mock.names++;
	if (msi_mock.failure == 3) return -ENOMEM;
	binding->domain = &msi_mock.domain; msi_mock.domains++;
	return 0;
}
static int n71_wlan_msi_release(struct n71_wlan_msi *binding)
{
	msi_mock.release_calls++;
	if (msi_mock.release_error) return msi_mock.release_error;
	if (binding->child) return -EBUSY;
	assert(!mock.scans || mock.removes == 1);
	assert(!binding->domain || !mock.bridge || mock.bridge->dev.msi_domain != binding->domain);
	if (binding->domain) { assert(msi_mock.domains == 1); msi_mock.domains--; }
	if (binding->fwnode) { assert(msi_mock.names == 1); msi_mock.names--; }
	if (binding->node) of_node_put(binding->node);
	*binding = (struct n71_wlan_msi){0};
	return 0;
}
static void msi_fixture_inherit(struct pci_host_bridge *bridge)
{
	struct irq_domain *domain = dev_get_msi_domain(&bridge->dev);
	assert(msi_mock.requested == !!domain && (!domain || bridge->msi_domain));
	bridge->bus->dev.msi_domain = domain;
	mock.root.dev.msi_domain = domain;
	mock.endpoint_bus.dev.msi_domain = mock.root.dev.msi_domain;
	mock.endpoint.dev.msi_domain = mock.endpoint_bus.dev.msi_domain;
	if (msi_mock.drift == 1) bridge->dev.msi_domain = &msi_mock.foreign;
	if (msi_mock.drift == 2) bridge->bus->dev.msi_domain = &msi_mock.foreign;
	if (msi_mock.drift == 3) mock.root.dev.msi_domain = &msi_mock.foreign;
	if (msi_mock.drift == 4) mock.endpoint_bus.dev.msi_domain = &msi_mock.foreign;
	if (msi_mock.drift == 5) mock.endpoint.dev.msi_domain = &msi_mock.foreign;
}
#endif /* N71_PCIE_MSI_SCAN_FIXTURE_H */
