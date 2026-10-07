/* SPDX-License-Identifier: GPL-2.0-only */
/* Scan is production; the separately qualified OF lease and core IOMMU are dependencies. */
#ifndef N71_PCIE_DART_SCAN_FIXTURE_H
#define N71_PCIE_DART_SCAN_FIXTURE_H
#define N71_DART_HOST_H
#define IOMMU_DOMAIN_DMA 3U
struct platform_device { struct device dev; };
struct iommu_domain { unsigned int type; };
struct iommu_fwspec { struct fwnode_handle *iommu_fwnode; u32 flags; unsigned int num_ids; u32 ids[2]; };
struct n71_dart_host {
	struct pci_host_bridge *bridge;
	struct platform_device *provider;
	struct device_node *provider_node;
	bool available, mapped;
};
struct n71_dart_host_request { struct pci_host_bridge *bridge; struct platform_device *provider; };
static struct {
	struct platform_device provider;
	struct device_node node, foreign_node;
	struct n71_dart_host *owner;
	struct iommu_domain domain, foreign_domain;
	struct iommu_fwspec spec[2];
	unsigned int prepare_failure, core_fault, unmap_failure, release_failure;
	unsigned int prepares, unmaps, releases, active_consumers, held_refs;
	bool requested, registered, available, mapped, identity;
} dart_mock;

static void dart_fixture_initialize(void)
{
	assert(!dart_mock.owner && !dart_mock.held_refs && !dart_mock.active_consumers);
	memset(&dart_mock,0,sizeof(dart_mock));
	dart_mock.node.fwnode.node=&dart_mock.node;
	dart_mock.foreign_node.fwnode.node=&dart_mock.foreign_node;
	dart_mock.provider.dev.of_node=&dart_mock.node;
	dart_mock.registered=true; dart_mock.identity=true;
	dart_mock.domain.type=dart_mock.foreign_domain.type=IOMMU_DOMAIN_DMA;
}
static bool n71_dart_host_refs_valid(const struct n71_dart_host *owner)
{
	return dart_mock.identity && owner->bridge==mock.bridge &&
		owner->provider==&dart_mock.provider && owner->provider_node==&dart_mock.node;
}
static int n71_dart_host_prepare(struct n71_dart_host *owner, const struct n71_dart_host_request *request)
{
	assert(dart_mock.requested && mock.locked && !mock.scans && !request->bridge->bus);
	assert(!owner->bridge && request->provider==&dart_mock.provider && dart_mock.registered);
	assert(request->bridge->dev.parent==dart_mock.provider.dev.parent);
	assert(request->bridge->dev.msi_domain && (mock.ecam[0x80a0/4]&0xffff)==2);
	assert(mock.ecam[0x10004c/4]==0xabc04008);
	dart_mock.prepares++;
	if (dart_mock.prepare_failure==1) return -EINVAL;
	*owner=(struct n71_dart_host){.bridge=request->bridge,.provider=request->provider,.provider_node=&dart_mock.node};
	dart_mock.owner=owner; dart_mock.held_refs=3;
	if (dart_mock.prepare_failure==2) return -EIO;
	owner->available=dart_mock.available=true;
	if (dart_mock.prepare_failure==3) return -EIO;
	owner->mapped=dart_mock.mapped=true;
	return dart_mock.prepare_failure==4 ? -EIO : 0;
}
static int n71_dart_host_unmap(struct n71_dart_host *owner)
{
	if (!owner->bridge) return 0;
	assert(!owner->bridge->bus && !dart_mock.active_consumers);
	assert(!msi_mock.domains && !owner->bridge->dev.msi_domain);
	if (!n71_dart_host_refs_valid(owner)) return -EACCES;
	if (!dart_mock.mapped) return 0;
	dart_mock.unmaps++;
	if (dart_mock.unmap_failure==1) return -EIO;
	owner->mapped=dart_mock.mapped=false;
	return dart_mock.unmap_failure==2 ? -EIO : 0;
}
static int n71_dart_host_release(struct n71_dart_host *owner)
{
	if (!owner->bridge) return 0;
	assert(!owner->bridge->bus && !dart_mock.active_consumers && !dart_mock.mapped);
	if (dart_mock.registered) return -EBUSY;
	dart_mock.releases++;
	if (dart_mock.release_failure) return -EIO;
	owner->available=dart_mock.available=false;
	*owner=(struct n71_dart_host){0}; dart_mock.owner=NULL; dart_mock.held_refs=0;
	return 0;
}
static void dart_fixture_publish(void)
{
	if (!dart_mock.requested) { assert(!dart_mock.owner && !dart_mock.available && !dart_mock.mapped); return; }
	assert(dart_mock.owner && dart_mock.available && dart_mock.mapped && dart_mock.registered);
	dart_mock.active_consumers=2;
	for (unsigned int i=0;i<2;i++) dart_mock.spec[i]=(struct iommu_fwspec){.iommu_fwnode=&dart_mock.node.fwnode,.num_ids=1};
	if (dart_mock.core_fault==3) dart_mock.spec[0].iommu_fwnode=&dart_mock.foreign_node.fwnode;
	if (dart_mock.core_fault==4) dart_mock.spec[1].iommu_fwnode=&dart_mock.foreign_node.fwnode;
	if (dart_mock.core_fault==5) dart_mock.spec[0].ids[0]=1;
	if (dart_mock.core_fault==6) dart_mock.spec[1].ids[0]=1;
	if (dart_mock.core_fault==7) dart_mock.spec[0].num_ids=0;
	if (dart_mock.core_fault==8) dart_mock.spec[1].num_ids=2;
	if (dart_mock.core_fault==9) dart_mock.spec[0].flags=1;
	if (dart_mock.core_fault==10) dart_mock.spec[1].flags=1;
	if (dart_mock.core_fault==13) dart_mock.domain.type=4;
	if (dart_mock.core_fault==14) dart_mock.foreign_domain.type=0;
	if (dart_mock.core_fault==16) dart_mock.identity=false;
}
static unsigned int dart_fixture_index(struct device *dev)
{
	assert(dart_mock.requested && mock.locked && dart_mock.active_consumers==2 && !mock.removes);
	assert(dev==&mock.root.dev || dev==&mock.endpoint.dev);
	return dev==&mock.endpoint.dev;
}
static struct iommu_fwspec *dev_iommu_fwspec_get(struct device *dev)
{
	unsigned int i=dart_fixture_index(dev);
	return dart_mock.core_fault==i+1 ? NULL : &dart_mock.spec[i];
}
static struct iommu_domain *iommu_get_domain_for_dev(struct device *dev)
{
	unsigned int i=dart_fixture_index(dev);
	if (dart_mock.core_fault==i+11) return NULL;
	return i && (dart_mock.core_fault==14 || dart_mock.core_fault==15) ? &dart_mock.foreign_domain : &dart_mock.domain;
}
static void dart_fixture_remove(void) { dart_mock.active_consumers=0; }
static void dart_fixture_stop(void)
{
	assert(!dart_mock.active_consumers && !dart_mock.mapped && (!mock.bridge || !mock.bridge->bus));
	dart_mock.registered=false;
}
#endif /* N71_PCIE_DART_SCAN_FIXTURE_H */
