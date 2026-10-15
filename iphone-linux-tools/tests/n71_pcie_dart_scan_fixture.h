/* SPDX-License-Identifier: GPL-2.0-only */
/* Scan is production; the separately qualified OF lease and core IOMMU are dependencies. */
#ifndef N71_PCIE_DART_SCAN_FIXTURE_H
#define N71_PCIE_DART_SCAN_FIXTURE_H
#define N71_DART_HOST_H
#define IOMMU_DOMAIN_DMA 3U
struct platform_device { struct device dev; };
struct property { unsigned int tag; };
struct iommu_domain { unsigned int type; };
struct iommu_group { int id; unsigned int refs; };
enum dma_fault {
	DMA_OK, DMA_LEGACY_ROOT, DMA_LEGACY_ENDPOINT, DMA_EMPTY_ALIAS, DMA_GROUP_ZERO,
	DMA_ROOT_BUS_NUMBER, DMA_ROOT_PARENT, DMA_ROOT_SELF, DMA_ROOT_SYSDATA,
	DMA_EP_PARENT, DMA_EP_SELF, DMA_EP_SYSDATA, DMA_ROOT_SUBORDINATE,
	DMA_ROOT_BUS_OWNER, DMA_EP_BUS_NUMBER, DMA_EP_SUBORDINATE,
	DMA_ROOT_HEADER, DMA_EP_HEADER, DMA_ROOT_TYPE, DMA_EP_TYPE, DMA_EP_NO_PCIE,
	DMA_ROOT_MULTIFUNCTION, DMA_EP_MULTIFUNCTION, DMA_ROOT_PF, DMA_EP_PF, DMA_ROOT_VF, DMA_EP_VF,
	DMA_ROOT_ALIAS, DMA_EP_ALIAS,
	DMA_ROOT_ALIAS_FLAG, DMA_EP_ALIAS_FLAG, DMA_ROOT_XLATE_FLAG, DMA_EP_XLATE_FLAG,
	DMA_ROOT_NO_ALIAS_FLAG, DMA_EP_NO_ALIAS_FLAG,
	DMA_ROOT_MASK_NULL, DMA_EP_MASK_NULL, DMA_ROOT_MASK_FOREIGN, DMA_EP_MASK_FOREIGN,
	DMA_ROOT_STREAM_ZERO, DMA_EP_STREAM_ZERO, DMA_ROOT_STREAM64, DMA_EP_STREAM64,
	DMA_ROOT_COHERENT64, DMA_EP_COHERENT64, DMA_ROOT_COHERENT_ZERO, DMA_EP_COHERENT_ZERO,
	DMA_ROOT_GROUP_NONE, DMA_EP_GROUP_NONE, DMA_ROOT_GROUP_NEGATIVE, DMA_EP_GROUP_NEGATIVE,
	DMA_EP_GROUP_FOREIGN, DMA_FAULT_COUNT
};
struct iommu_fwspec { struct fwnode_handle *iommu_fwnode; u32 flags; unsigned int num_ids; u32 ids[2]; };
struct n71_dart_host {
	struct pci_host_bridge *bridge;
	struct platform_device *provider;
	struct device_node *provider_node;
	struct device_node *master_node;
	struct property *map_property, *status_property;
	u32 phandle;
	bool available, mapped;
};
struct n71_dart_host_request { struct pci_host_bridge *bridge; struct platform_device *provider; };
static struct {
	struct platform_device provider;
	struct device_node node, foreign_node;
	struct n71_dart_host *owner;
	struct iommu_domain domain, foreign_domain;
	struct iommu_group group, foreign_group;
	unsigned int group_gets, group_ids, group_puts;
	enum dma_fault dma_fault;
	unsigned long aliases[256 / (8 * sizeof(unsigned long))];
	u64 foreign_mask;
	struct iommu_fwspec spec[2];
	struct property map_property, status_property, foreign_property;
	struct property *map_current, *status_current;
	u32 map[9];
	unsigned int map_count;
	unsigned int prepare_failure, core_fault, unmap_failure, release_failure;
	unsigned int prepares, unmaps, releases, active_consumers, held_refs;
	bool requested, registered, available, mapped, identity;
} dart_mock;

static void dart_fixture_initialize(void)
{
	assert(!dart_mock.owner && !dart_mock.held_refs && !dart_mock.active_consumers);
	assert(!dart_mock.group.refs && !dart_mock.foreign_group.refs);
	memset(&dart_mock,0,sizeof(dart_mock));
	dart_mock.node.fwnode.node=&dart_mock.node;
	dart_mock.foreign_node.fwnode.node=&dart_mock.foreign_node;
	dart_mock.provider.dev.of_node=&dart_mock.node;
	dart_mock.registered=true; dart_mock.identity=true;
	dart_mock.map_count=8;
	dart_mock.domain.type=dart_mock.foreign_domain.type=IOMMU_DOMAIN_DMA;
	dart_mock.group.id = 7; dart_mock.foreign_group.id = 8;
	dart_mock.foreign_mask = DMA_BIT_MASK(32);
}
static bool pci_is_pcie(const struct pci_dev *dev) { return dev->pcie; }
static int pci_pcie_type(const struct pci_dev *dev) { return dev->pcie_type; }
static bool bitmap_empty(const unsigned long *mask, unsigned int bits)
{
	assert(bits == 256);
	for (unsigned int i = 0; i < bits; i++)
		if (mask[i / (8 * sizeof(*mask))] & (1UL << (i % (8 * sizeof(*mask))))) return false;
	return true;
}
static void dart_fixture_dma_fault(void)
{
	switch (dart_mock.dma_fault) {
	case DMA_OK: break;
	case DMA_LEGACY_ROOT: mock.root.pcie = false; break;
	case DMA_LEGACY_ENDPOINT: mock.endpoint.pcie_type = PCI_EXP_TYPE_LEG_END; break;
	case DMA_EMPTY_ALIAS: mock.root.dma_alias_mask = mock.endpoint.dma_alias_mask = dart_mock.aliases; break;
	case DMA_GROUP_ZERO: dart_mock.group.id = 0; break;
	case DMA_ROOT_BUS_NUMBER: mock.bridge->bus->number = 2; break;
	case DMA_ROOT_PARENT: mock.bridge->bus->parent = &mock.endpoint_bus; break;
	case DMA_ROOT_SELF: mock.bridge->bus->self = &mock.endpoint; break;
	case DMA_ROOT_SYSDATA: mock.bridge->bus->sysdata = &mock; break;
	case DMA_EP_PARENT: mock.endpoint_bus.parent = NULL; break;
	case DMA_EP_SELF: mock.endpoint_bus.self = NULL; break;
	case DMA_EP_SYSDATA: mock.endpoint_bus.sysdata = &mock; break;
	case DMA_ROOT_SUBORDINATE: mock.root.subordinate = NULL; break;
	case DMA_ROOT_BUS_OWNER: mock.root.bus = &mock.endpoint_bus; break;
	case DMA_EP_BUS_NUMBER: mock.endpoint_bus.number = 2; break;
	case DMA_EP_SUBORDINATE: mock.endpoint.subordinate = mock.bridge->bus; break;
	case DMA_ROOT_HEADER: mock.root.hdr_type = PCI_HEADER_TYPE_NORMAL; break;
	case DMA_EP_HEADER: mock.endpoint.hdr_type = PCI_HEADER_TYPE_BRIDGE; break;
	case DMA_ROOT_TYPE: mock.root.pcie_type = 5; break;
	case DMA_EP_TYPE: mock.endpoint.pcie_type = PCI_EXP_TYPE_ROOT_PORT; break;
	case DMA_EP_NO_PCIE: mock.endpoint.pcie = false; break;
	case DMA_ROOT_MULTIFUNCTION: mock.root.multifunction = true; break;
	case DMA_EP_MULTIFUNCTION: mock.endpoint.multifunction = true; break;
	case DMA_ROOT_PF: mock.root.is_physfn = true; break;
	case DMA_EP_PF: mock.endpoint.is_physfn = true; break;
	case DMA_ROOT_VF: mock.root.is_virtfn = true; break;
	case DMA_EP_VF: mock.endpoint.is_virtfn = true; break;
	case DMA_ROOT_ALIAS: mock.root.dma_alias_mask = dart_mock.aliases; dart_mock.aliases[0] = 1; break;
	case DMA_EP_ALIAS: mock.endpoint.dma_alias_mask = dart_mock.aliases; dart_mock.aliases[3] = 1; break;
	case DMA_ROOT_ALIAS_FLAG: mock.root.dev_flags = PCI_DEV_FLAG_PCIE_BRIDGE_ALIAS; break;
	case DMA_EP_ALIAS_FLAG: mock.endpoint.dev_flags = PCI_DEV_FLAG_PCIE_BRIDGE_ALIAS; break;
	case DMA_ROOT_XLATE_FLAG: mock.root.dev_flags = PCI_DEV_FLAGS_BRIDGE_XLATE_ROOT; break;
	case DMA_EP_XLATE_FLAG: mock.endpoint.dev_flags = PCI_DEV_FLAGS_BRIDGE_XLATE_ROOT; break;
	case DMA_ROOT_NO_ALIAS_FLAG: mock.root.dev_flags = PCI_DEV_FLAGS_PCI_BRIDGE_NO_ALIAS; break;
	case DMA_EP_NO_ALIAS_FLAG: mock.endpoint.dev_flags = PCI_DEV_FLAGS_PCI_BRIDGE_NO_ALIAS; break;
	case DMA_ROOT_MASK_NULL: mock.root.dev.dma_mask = NULL; break;
	case DMA_EP_MASK_NULL: mock.endpoint.dev.dma_mask = NULL; break;
	case DMA_ROOT_MASK_FOREIGN: mock.root.dev.dma_mask = &dart_mock.foreign_mask; break;
	case DMA_EP_MASK_FOREIGN: mock.endpoint.dev.dma_mask = &dart_mock.foreign_mask; break;
	case DMA_ROOT_STREAM_ZERO: mock.root.dma_mask = 0; break;
	case DMA_EP_STREAM_ZERO: mock.endpoint.dma_mask = 0; break;
	case DMA_ROOT_STREAM64: mock.root.dma_mask = ~(u64)0; break;
	case DMA_EP_STREAM64: mock.endpoint.dma_mask = ~(u64)0; break;
	case DMA_ROOT_COHERENT64: mock.root.dev.coherent_dma_mask = ~(u64)0; break;
	case DMA_EP_COHERENT64: mock.endpoint.dev.coherent_dma_mask = ~(u64)0; break;
	case DMA_ROOT_COHERENT_ZERO: mock.root.dev.coherent_dma_mask = 0; break;
	case DMA_EP_COHERENT_ZERO: mock.endpoint.dev.coherent_dma_mask = 0; break;
	case DMA_ROOT_GROUP_NEGATIVE: dart_mock.group.id = -1; break;
	case DMA_EP_GROUP_NEGATIVE: dart_mock.foreign_group.id = -1; break;
	case DMA_ROOT_GROUP_NONE: case DMA_EP_GROUP_NONE: case DMA_EP_GROUP_FOREIGN: break;
	case DMA_FAULT_COUNT: assert(false);
	}
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
	*owner=(struct n71_dart_host){.bridge=request->bridge,.provider=request->provider,.provider_node=&dart_mock.node,
		.master_node=request->bridge->dev.parent->of_node,.map_property=&dart_mock.map_property,
		.status_property=&dart_mock.status_property,.phandle=41};
	dart_mock.owner=owner; dart_mock.held_refs=3;
	if (dart_mock.prepare_failure==2) return -EIO;
	owner->available=dart_mock.available=true;
	dart_mock.status_current=&dart_mock.status_property;
	if (dart_mock.prepare_failure==3) return -EIO;
	owner->mapped=dart_mock.mapped=true;
	dart_mock.map_current=&dart_mock.map_property;
	const u32 map[8]={8,41,0,1,0x100,41,0,1};memcpy(dart_mock.map,map,sizeof(map));
	return dart_mock.prepare_failure==4 ? -EIO : 0;
}
static int n71_dart_host_unmap(struct n71_dart_host *owner)
{
	if (!owner->bridge) return 0;
	assert(!owner->bridge->bus && !dart_mock.active_consumers);
	assert(!msi_mock.domains && !owner->bridge->dev.msi_domain);
	if (!n71_dart_host_refs_valid(owner)) return -EACCES;
	if (dart_mock.map_current && dart_mock.map_current!=owner->map_property) return -EACCES;
	if (!dart_mock.mapped) return 0;
	dart_mock.unmaps++;
	if (dart_mock.unmap_failure==1) return -EIO;
	owner->mapped=dart_mock.mapped=false;
	dart_mock.map_current=NULL;
	return dart_mock.unmap_failure==2 ? -EIO : 0;
}
static int n71_dart_host_release(struct n71_dart_host *owner)
{
	if (!owner->bridge) return 0;
	assert(!owner->bridge->bus && !dart_mock.active_consumers && !dart_mock.mapped);
	if (dart_mock.registered) return -EBUSY;
	if (dart_mock.status_current && dart_mock.status_current!=owner->status_property) return -EACCES;
	dart_mock.releases++;
	if (dart_mock.release_failure) return -EIO;
	owner->available=dart_mock.available=false;
	dart_mock.status_current=NULL;
	*owner=(struct n71_dart_host){0}; dart_mock.owner=NULL; dart_mock.held_refs=0;
	return 0;
}
static void dart_fixture_publish(void)
{
	if (!dart_mock.requested) { assert(!dart_mock.owner && !dart_mock.available && !dart_mock.mapped); return; }
	assert(dart_mock.owner && dart_mock.available && dart_mock.mapped && dart_mock.registered);
	dart_mock.active_consumers=2;
	for (unsigned int i=0;i<2;i++) dart_mock.spec[i]=(struct iommu_fwspec){.iommu_fwnode=&dart_mock.node.fwnode};
	if (dart_mock.core_fault==3) dart_mock.spec[0].iommu_fwnode=&dart_mock.foreign_node.fwnode;
	if (dart_mock.core_fault==4) dart_mock.spec[1].iommu_fwnode=&dart_mock.foreign_node.fwnode;
	if (dart_mock.core_fault==5) dart_mock.map[2]=1;
	if (dart_mock.core_fault==6) dart_mock.map[6]=1;
	if (dart_mock.core_fault==7) dart_mock.spec[0].num_ids=1;
	if (dart_mock.core_fault==8) dart_mock.spec[1].num_ids=2;
	if (dart_mock.core_fault==9) dart_mock.spec[0].flags=1;
	if (dart_mock.core_fault==10) dart_mock.spec[1].flags=1;
	if (dart_mock.core_fault==13) dart_mock.domain.type=4;
	if (dart_mock.core_fault==14) dart_mock.foreign_domain.type=0;
	if (dart_mock.core_fault==16) dart_mock.identity=false;
	if (dart_mock.core_fault==17) dart_mock.map_current=&dart_mock.foreign_property;
	if (dart_mock.core_fault==18) dart_mock.status_current=&dart_mock.foreign_property;
	if (dart_mock.core_fault==19) dart_mock.map_count=9;
	if (dart_mock.core_fault==21) dart_mock.map[1]=42;
	if (dart_mock.core_fault==22) dart_mock.map[0]=9;
	if (dart_mock.core_fault==23) dart_mock.map[4]=0x101;
	if (dart_mock.core_fault==24) dart_mock.map[3]=0;
}
static struct property *of_find_property(struct device_node *node, const char *name, int *length)
{
	(void)length;
	if (!strcmp(name,"status")) { assert(node==&dart_mock.node);return dart_mock.status_current; }
	assert(dart_mock.owner && node==dart_mock.owner->master_node && !strcmp(name,"iommu-map"));return dart_mock.map_current;
}
static int of_property_count_u32_elems(struct device_node *node, const char *name)
{
	assert(dart_mock.owner && node==dart_mock.owner->master_node && !strcmp(name,"iommu-map"));return dart_mock.map_count;
}
static int of_property_read_u32_index(struct device_node *node, const char *name, unsigned int index, u32 *value)
{
	assert(dart_mock.owner && node==dart_mock.owner->master_node && !strcmp(name,"iommu-map") && index<9);
	if (index>=dart_mock.map_count) return -EINVAL;
	*value=dart_mock.map[index];return dart_mock.core_fault==20 && index==3 ? -EIO : 0;
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
	/* Drift is observed after the current device's COMMAND read, without corrupting fake MMIO. */
	if (i || (dart_mock.dma_fault != DMA_EP_SYSDATA && dart_mock.dma_fault != DMA_EP_BUS_NUMBER))
		dart_fixture_dma_fault();
	return dart_mock.core_fault==i+1 ? NULL : &dart_mock.spec[i];
}
static struct iommu_domain *iommu_get_domain_for_dev(struct device *dev)
{
	unsigned int i=dart_fixture_index(dev);
	if (dart_mock.core_fault==i+11) return NULL;
	return i && (dart_mock.core_fault==14 || dart_mock.core_fault==15) ? &dart_mock.foreign_domain : &dart_mock.domain;
}
static struct iommu_group *iommu_group_get(struct device *dev)
{
	unsigned int i = dart_fixture_index(dev);
	dart_mock.group_gets++;
	if ((!i && dart_mock.dma_fault == DMA_ROOT_GROUP_NONE) ||
	    (i && dart_mock.dma_fault == DMA_EP_GROUP_NONE)) return NULL;
	struct iommu_group *group = i && (dart_mock.dma_fault == DMA_EP_GROUP_NEGATIVE ||
		dart_mock.dma_fault == DMA_EP_GROUP_FOREIGN) ? &dart_mock.foreign_group : &dart_mock.group;
	group->refs++;
	return group;
}
static int iommu_group_id(struct iommu_group *group)
{
	assert(group && group->refs == 1); dart_mock.group_ids++;
	return group->id;
}
static void iommu_group_put(struct iommu_group *group)
{
	assert(group->refs == 1); group->refs--; dart_mock.group_puts++;
}
static void dart_fixture_remove(void)
{
	assert(!dart_mock.group.refs && !dart_mock.foreign_group.refs);
	assert(dart_mock.group_ids == dart_mock.group_puts);
	dart_mock.active_consumers=0;
}
static void dart_fixture_stop(void)
{
	assert(!dart_mock.active_consumers && !dart_mock.mapped && (!mock.bridge || !mock.bridge->bus));
	dart_mock.registered=false;
}
#endif /* N71_PCIE_DART_SCAN_FIXTURE_H */
