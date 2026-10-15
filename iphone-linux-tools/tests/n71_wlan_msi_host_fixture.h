/* SPDX-License-Identifier: GPL-2.0-only */
/* Model PCI accessors/native lease; native callbacks have a separate real gate. */
#ifndef N71_WLAN_MSI_HOST_FIXTURE_H
#define N71_WLAN_MSI_HOST_FIXTURE_H
#define N71_WLAN_MSI_NATIVE_H
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <string.h>
struct irq_domain { unsigned int identity; };
struct device { struct irq_domain *domain; };
struct pci_host_bridge { struct device dev; void *bus; bool msi_domain; };
struct irq_fwspec { unsigned int identity; };
struct n71_wlan_msi_request { unsigned int identity; };
struct n71_wlan_msi {
	struct irq_domain *domain, *child;
	void *node, *fwnode;
};
static struct {
	struct pci_host_bridge *bridge;
	struct irq_domain domain, foreign, child;
	struct irq_fwspec spec;
	struct n71_wlan_msi_request request;
	unsigned int fail_acquire, acquire_calls, release_calls, resources;
	int release_error;
} host_fixture;
static struct irq_domain *dev_get_msi_domain(struct device *device) { return device->domain; }
static void dev_set_msi_domain(struct device *device, struct irq_domain *domain) { device->domain = domain; }
static int n71_wlan_msi_acquire(struct n71_wlan_msi *binding, const struct irq_fwspec *spec,
				const struct n71_wlan_msi_request *request)
{
	assert(spec == &host_fixture.spec && request == &host_fixture.request);
	assert(!binding->node && !binding->fwnode && !binding->domain);
	assert(!host_fixture.bridge->bus && !host_fixture.bridge->dev.domain);
	host_fixture.acquire_calls++;
	if (host_fixture.fail_acquire == 1) return -EINVAL;
	binding->node = &host_fixture; host_fixture.resources++;
	if (host_fixture.fail_acquire == 2) return -ENOMEM;
	binding->fwnode = &host_fixture.domain; host_fixture.resources++;
	if (host_fixture.fail_acquire == 3) return -ENOMEM;
	binding->domain = &host_fixture.domain; host_fixture.resources++;
	return 0;
}
static int n71_wlan_msi_release(struct n71_wlan_msi *binding)
{
	host_fixture.release_calls++;
	if (host_fixture.release_error) return host_fixture.release_error;
	if (binding->child) return -EBUSY;
	/* A parent must never be destroyed while the bridge still names it. */
	assert(!host_fixture.bridge->bus && (!binding->domain || host_fixture.bridge->dev.domain != binding->domain));
	if (binding->domain) host_fixture.resources--;
	if (binding->fwnode) host_fixture.resources--;
	if (binding->node) host_fixture.resources--;
	*binding = (struct n71_wlan_msi){0};
	return 0;
}
#endif /* N71_WLAN_MSI_HOST_FIXTURE_H */
