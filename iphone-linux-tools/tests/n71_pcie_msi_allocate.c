/* Real allocation adapter/config owner; kernel PCI/IRQ APIs are modeled. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "n71-wlan-msi-config.h"
#define N71_PCIE_RESOURCE_ASSIGN_H
#define PCI_UNKNOWN 5
#define PCI_D0 0
#define PCI_IRQ_MSI 2U
#define IRQ_TYPE_EDGE_RISING 1U
#define CONFIG_PCIEASPM 1
struct irq_chip { const char *name; };
struct irq_domain { struct irq_domain *parent; unsigned int mapcount; };
struct device { struct irq_domain *domain; };
struct pci_dev;
struct pci_bus { unsigned int number; void *sysdata; struct pci_dev *self; };
struct pci_dev {
	struct device dev;
	struct pci_bus *bus, *subordinate;
	void *driver, *link_state;
	unsigned int vendor, device, devfn, pm_cap, msi_cap, msix_cap, irq;
	int current_state;
	bool msi_enabled, msix_enabled;
};
struct pci_host_bridge { struct pci_bus *bus; };
struct irq_data {
	struct irq_domain *domain;
	struct irq_data *parent_data;
	const struct irq_chip *chip;
	void *chip_data;
	unsigned long hwirq;
	unsigned int type;
};
struct n71_wlan_msi {
	struct irq_domain *domain, *parent, *child;
	struct device *child_device;
	unsigned int slots;
};
struct n71_scan_host {
	unsigned int lock;
	struct { bool active; int error; } config;
	struct { bool pending, active; } resources;
	struct { bool prepared; } pme, target;
	struct { struct pci_host_bridge *bridge; bool associated; struct n71_wlan_msi native; } msi;
	struct { struct pci_host_bridge *bridge; bool available, mapped; } dart;
	struct n71_msi_config msi_config;
	void *iommu_domain;
	unsigned int iommu_devices;
	bool bus_held, config_pending, resources_assigned, window_claimed;
	int io_error;
};
struct n71_resource_devices { struct pci_dev *root, *endpoint; unsigned int count; int error; };
static const struct irq_chip n71_wlan_msi_chip = {"N71-MSI"}, aic_chip = {"AIC"}, foreign_chip = {"foreign"};
static struct {
	struct n71_scan_host host;
	struct pci_bus bus, sub;
	struct pci_dev root, endpoint;
	struct pci_host_bridge bridge;
	struct irq_domain domain, parent, child;
	struct irq_data own, aic, leaf;
	u32 config[2][64], baseline[2][64];
	unsigned int fault, slot, references, rescan, spins, allocs, frees, puts, powers, cases;
	unsigned int writes, drop_write, fail_read, reads, free_drift;
	bool missing, invalid_resources, extra_device, fail_restore;
} mock;
static unsigned int cases;

#define spin_lock_irqsave(lock, flags) do { (void)(lock); (flags)=0; assert(!mock.spins++); } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); assert(mock.spins-- == 1); } while (0)
static void pci_lock_rescan_remove(void) { assert(!mock.rescan++); }
static void pci_unlock_rescan_remove(void) { assert(mock.rescan-- == 1); }
static struct pci_dev *pci_get_slot(struct pci_bus *bus, unsigned int devfn)
{
	assert(mock.rescan);
	if (mock.missing) return NULL;
	struct pci_dev *dev = bus == &mock.bus && devfn == 8 ? &mock.root :
		bus == &mock.sub && !devfn ? &mock.endpoint : NULL;
	if (dev) mock.references++;
	return dev;
}
static void pci_dev_put(struct pci_dev *dev)
{
	if (dev) { assert(mock.references && mock.rescan); mock.references--; mock.puts++; }
}
static struct irq_domain *dev_get_msi_domain(struct device *dev) { return dev->domain; }
static int n71_resource_visit(struct pci_dev *dev, void *context)
{
	struct n71_resource_devices *devices = context;
	devices->count++;
	if (dev != devices->root && dev != devices->endpoint) devices->error = -ENODEV;
	return devices->error;
}
static void pci_walk_bus(struct pci_bus *bus, int (*visit)(struct pci_dev *, void *), void *context)
{
	assert(bus == &mock.bus); visit(&mock.root,context); visit(&mock.endpoint,context);
	if (mock.extra_device) { struct pci_dev extra = {0}; visit(&extra,context); }
}
/* The existing resource verifier has its own compiled integration gate. */
int n71_resource_verify(struct n71_scan_host *host, struct n71_resource_devices *devices)
{
	assert(host == &mock.host && devices->root == &mock.root && devices->endpoint == &mock.endpoint);
	return mock.invalid_resources ? -EIO : 0;
}
static int n71_scan_raw_read(void *context, bool root, u32 where, unsigned int size, u32 *value)
{
	assert(context == &mock.host && where < 256);
	if (++mock.reads == mock.fail_read) return -EIO;
	u32 raw = mock.config[root ? 0 : 1][where/4];
	*value = size == 4 ? raw : (raw >> ((where&3)*8)) & 0xffff;
	return 0;
}
static int n71_scan_raw_write(void *context, bool root, u32 where, unsigned int size, u32 value)
{
	assert(context == &mock.host && !root && (size == 2 || size == 4));
	assert(!(mock.config[0][1]&7) && !(mock.config[1][1]&7));
	u32 *raw = &mock.config[1][where/4]; unsigned int shift = (where&3)*8;
	if (++mock.writes != mock.drop_write)
		*raw = size == 4 ? value : (*raw & ~(0xffffU<<shift)) | ((value&0xffff)<<shift);
	return 0;
}
int pci_set_power_state(struct pci_dev *dev, int state)
{
	assert(dev == &mock.endpoint && state == PCI_D0 && mock.rescan && !mock.spins);
	mock.powers++;
	if (mock.fault == 1) return -ETIMEDOUT;
	if (mock.fault == 2) return 1;
	if (mock.fault != 3) dev->current_state = PCI_D0;
	if (mock.fault == 4) mock.config[1][0x4c/4] ^= 1;
	return 0;
}
static void core_write(unsigned int where, unsigned int size, u32 value)
{
	struct n71_scan_io io = {&mock.host,n71_scan_raw_read,n71_scan_raw_write};
	struct n71_msi_config_request request = {{false,where,value,size},mock.host.msi.native.slots};
	(void)n71_msi_config_write(&io,&mock.host.msi_config,&request); /* PCI core ignores errors. */
}
static int pci_alloc_irq_vectors(struct pci_dev *dev, unsigned int min, unsigned int max, unsigned int flags)
{
	assert(dev == &mock.endpoint && min == 1 && max == 1 && flags == PCI_IRQ_MSI);
	assert(mock.rescan && !mock.spins && mock.references == 2 && dev->current_state == PCI_D0);
	assert(mock.host.msi_config.phase == N71_MSI_CONFIG_ACTIVE);
	mock.allocs++;
	if (mock.fault == 5) return -ENOSPC;
	mock.host.msi.native.child = &mock.child; mock.host.msi.native.child_device = &dev->dev;
	mock.host.msi.native.slots = 1U<<mock.slot; mock.domain.mapcount = mock.child.mapcount = 1;
	mock.own = (struct irq_data){&mock.domain,&mock.aic,&n71_wlan_msi_chip,&mock.host.msi.native,mock.slot,1};
	mock.aic = (struct irq_data){&mock.parent,NULL,&aic_chip,NULL,0x10108UL+mock.slot,1};
	mock.leaf = (struct irq_data){.domain=&mock.child,.parent_data=&mock.own};
	core_write(0x5c,4,0xbffff000); core_write(0x60,4,0); core_write(0x64,2,8+mock.slot);
	core_write(4,2,0x500); core_write(0x5a,2,0x89);
	dev->msi_enabled = true; dev->irq = 320;
	if (mock.fault == 7) mock.config[1][0x64/4] ^= 1;
	if (mock.fault == 8) mock.config[1][0x58/4] &= ~0x10000U;
	if (mock.fault == 9) mock.host.msi.native.slots |= 3;
	if (mock.fault == 10) mock.aic.chip = &foreign_chip;
	if (mock.fault == 11) mock.leaf.parent_data = &mock.aic;
	if (mock.fault == 12) mock.aic.hwirq++;
	if (mock.fault == 13) mock.domain.mapcount++;
	if (mock.fault == 14) dev->msi_enabled = false;
	if (mock.fault == 16) mock.leaf.domain = &mock.parent;
	if (mock.fault == 17) mock.own.hwirq++;
	if (mock.fault == 18) mock.own.type = 0;
	if (mock.fault == 19) mock.own.chip_data = &mock;
	if (mock.fault == 20) mock.host.msi.native.domain = NULL;
	return 1;
}
static int pci_irq_vector(struct pci_dev *dev, unsigned int index)
{
	assert(dev == &mock.endpoint && !index);
	return mock.fault == 6 ? 0 : mock.fault == 15 ? -EINVAL : 320;
}
static struct irq_data *irq_domain_get_irq_data(struct irq_domain *domain, unsigned int vector)
{
	assert(vector == 320);
	return domain == &mock.domain ? &mock.own : domain == &mock.parent ? &mock.aic : NULL;
}
static struct irq_data *irq_get_irq_data(unsigned int vector) { assert(vector == 320); return &mock.leaf; }
static unsigned int irqd_get_trigger_type(struct irq_data *data) { return data->type; }
static void pci_free_irq_vectors(struct pci_dev *dev)
{
	assert(dev == &mock.endpoint && mock.rescan && !mock.spins);
	assert(mock.host.msi_config.phase == N71_MSI_CONFIG_STOPPED);
	assert((mock.config[1][0x58/4]>>16) == 0x88); /* Mutation: freeing before verified stop. */
	mock.frees++;
	if (!dev->msi_enabled) return;
	core_write(0x5a,2,0x88); core_write(4,2,0x100);
	core_write(0x5c,4,0); core_write(0x60,4,0); core_write(0x64,2,0);
	dev->msi_enabled = false; dev->irq = mock.free_drift == 2 ? 321 : 0;
	mock.host.msi.native.slots = mock.free_drift == 1 ? 1 : 0;
	mock.domain.mapcount = mock.child.mapcount = 0;
	if (mock.fail_restore) mock.fail_read = mock.reads + 1;
}
#include "n71-pcie-msi-allocate.h"

static void reset(struct n71_msi_allocation *lease)
{
	memset(&mock,0,sizeof(mock)); memset(lease,0,sizeof(*lease));
	mock.bus = (struct pci_bus){.sysdata=&mock.host}; mock.bridge.bus=&mock.bus;
	mock.sub = (struct pci_bus){.number=1,.sysdata=&mock.host,.self=&mock.root};
	mock.root = (struct pci_dev){.bus=&mock.bus,.subordinate=&mock.sub,.vendor=0x106b,.device=0x1004,.devfn=8};
	mock.endpoint = (struct pci_dev){.bus=&mock.sub,.vendor=0x14e4,.device=0x43a3,.pm_cap=0x48,.msi_cap=0x58,.current_state=PCI_UNKNOWN};
	mock.domain.parent=&mock.parent; mock.child.parent=&mock.domain;
	mock.root.dev.domain=mock.endpoint.dev.domain=&mock.domain;
	mock.host.config.active=mock.host.config_pending=mock.host.bus_held=true;
	mock.host.resources_assigned=mock.host.resources.pending=mock.host.window_claimed=true;
	mock.host.pme.prepared=mock.host.target.prepared=true;
	mock.host.msi.bridge=mock.host.dart.bridge=&mock.bridge;
	mock.host.msi.associated=mock.host.dart.available=mock.host.dart.mapped=true;
	mock.host.msi.native.domain=&mock.domain; mock.host.msi.native.parent=&mock.parent;
	mock.host.iommu_domain=&mock; mock.host.iommu_devices=2;
	mock.config[0][0]=0x1004106b; mock.config[1][0]=0x43a314e4;
	mock.config[1][1]=0x5a5a0100; mock.config[1][0x4c/4]=0x4008;
	mock.config[1][0x58/4]=0x00886805; mock.config[1][0x5c/4]=0x12345000;
	mock.config[1][0x60/4]=0x42; mock.config[1][0x64/4]=0xbeef0013;
	memcpy(mock.baseline,mock.config,sizeof(mock.config));
}
static int allocate(struct n71_msi_allocation *lease) { return n71_pcie_msi_allocate(&mock.bridge,&mock.host,lease); }
static void released(struct n71_msi_allocation *lease)
{
	assert(n71_pcie_msi_release(&mock.host,lease) == 0);
	assert(!lease->endpoint && !lease->vector && !mock.references && !mock.rescan && !mock.spins);
	assert(mock.host.msi_config.phase == N71_MSI_CONFIG_EMPTY);
	assert(!memcmp(mock.config,mock.baseline,sizeof(mock.config)));
}
int main(void)
{
	struct n71_msi_allocation lease;
	unsigned int i;
	const int errors[] = {0,-ETIMEDOUT,-EIO,-EIO,-EIO,-ENOSPC,-EIO,-EIO,-EIO,
		-EACCES,-EACCES,-EACCES,-EACCES,-EACCES,-EACCES,-EINVAL,
		-EACCES,-EACCES,-EACCES,-EACCES,-EACCES};
	for (i=0;i<8;i++) {
		reset(&lease); mock.slot=i; assert(allocate(&lease)==0);
		assert(lease.endpoint==&mock.endpoint && lease.vector==320 && mock.references==1);
		assert(mock.powers==1 && mock.endpoint.current_state==PCI_D0);
		assert(allocate(&lease)==-EBUSY); released(&lease);
		assert(mock.host.msi.native.child==&mock.child && mock.host.msi.native.child_device==&mock.endpoint.dev);
		assert(allocate(&lease)==-EALREADY); cases++;
	}
	for (i=1;i<=20;i++) {
		reset(&lease); mock.fault=i; assert(allocate(&lease)==errors[i]);
		assert(!mock.rescan && !mock.spins);
		if (i<=4) { assert(!lease.endpoint && !mock.references && !mock.allocs && !mock.writes); }
		else {
			assert(lease.endpoint && mock.references==1 && mock.host.msi_config.error<0);
			/* Simulate repairing software drift; no new allocation is allowed. */
			if (i==14) mock.endpoint.msi_enabled=true;
			if (i==20) mock.host.msi.native.domain=&mock.domain;
			released(&lease);
			assert(mock.host.msi_config.error==errors[i]);
			assert(allocate(&lease)==errors[i]);
		}
		cases++;
	}
	/* Each refusal must precede power, config writes and vector allocation. */
	for (i=0;i<20;i++) {
		reset(&lease);
		switch(i) {
		case 0: mock.host.bus_held=false; break;
		case 1: mock.host.resources_assigned=false; break;
		case 2: mock.host.resources.active=true; break;
		case 3: mock.host.msi.associated=false; break;
		case 4: mock.host.dart.mapped=false; break;
		case 5: mock.host.iommu_devices=1; break;
		case 6: mock.domain.mapcount=1; break;
		case 7: mock.host.msi.native.slots=1; break;
		case 8: mock.missing=true; break;
		case 9: mock.endpoint.driver=&mock; break;
		case 10: mock.endpoint.dev.domain=&mock.parent; break;
		case 11: mock.extra_device=true; break;
		case 12: mock.invalid_resources=true; break;
		case 13: mock.endpoint.pm_cap=0; break;
		case 14: mock.endpoint.current_state=3; break;
		case 15: mock.config[1][0x4c/4]=0x4108; break;
		case 16: mock.host.io_error=-EIO; break;
		case 17: mock.host.msi_config.error=-ETIMEDOUT; break;
		case 18: mock.config[1][0]=0x43b314e4; break;
		case 19: mock.root.link_state=&mock; break;
		}
		assert(allocate(&lease)<0 && !lease.endpoint && !mock.references);
		assert(!mock.powers && !mock.allocs && !mock.writes && !mock.rescan); cases++;
	}
	reset(&lease); assert(allocate(&lease)==0);
	mock.drop_write=mock.writes+1;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EIO);
	assert(mock.frees==0 && mock.references==1 && lease.vector==320);
	mock.drop_write=0; released(&lease); assert(mock.host.msi_config.error==-EIO); cases++;
	reset(&lease); assert(allocate(&lease)==0); mock.free_drift=1;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EBUSY && mock.references==1);
	mock.host.msi.native.slots=0; released(&lease); cases++;
	reset(&lease); assert(allocate(&lease)==0); mock.free_drift=2;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EIO && mock.references==1);
	mock.endpoint.irq=0; released(&lease); cases++;
	reset(&lease); assert(allocate(&lease)==0); mock.endpoint.driver=&mock;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EBUSY && !mock.frees);
	mock.endpoint.driver=NULL; released(&lease); cases++;
	reset(&lease); assert(allocate(&lease)==0); mock.fail_restore=true;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EIO && mock.references==1);
	assert(mock.host.msi_config.phase==N71_MSI_CONFIG_STOPPED && !mock.endpoint.msi_enabled);
	mock.fail_restore=false; mock.fail_read=0; released(&lease);
	assert(mock.host.msi_config.error==-EIO); cases++;
	reset(&lease); lease.vector=1;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EBUSY && !mock.frees); cases++;
	reset(&lease); lease.endpoint=&mock.endpoint; mock.references=1;
	assert(n71_pcie_msi_release(&mock.host,&lease)==-EBUSY && !mock.frees && mock.references==1); cases++;
	printf("N71_PCIE_MSI_ALLOCATE_OK cases=%u; real adapter/config, PCI and IRQ APIs modeled, no IRQ delivery\n",cases);
	return 0;
}
