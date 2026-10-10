/* Real adapter and ECAM callbacks; PCI/driver/PM dependencies are modeled. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71-pcie-pme-control.h"
#include "n71-pcie-resource-write.h"
#include "n71-brcmfmac-config.h"
#include "n71-msi-allocation-lease.h"
#define __iomem
#define CONFIG_PCIEASPM 1
#define PCI_UNKNOWN 5
#define PCI_D0 0
#define PCIBIOS_DEVICE_NOT_FOUND 0x86
#define PCIBIOS_BAD_REGISTER_NUMBER 0x87
#define PCIBIOS_SET_FAILED 0x88
#define PCIBIOS_SUCCESSFUL 0
typedef int spinlock_t;
struct device_driver { const char *name; };
struct device { const char *override; unsigned int locks, pm; };
struct pci_dev;
struct pci_bus { void *sysdata; unsigned int number; struct pci_dev *self; };
struct pci_dev {
	struct device dev;
	struct pci_bus *bus, *subordinate;
	void *driver, *link_state;
	unsigned int vendor, device, devfn, pm_cap, msi_cap, msix_cap;
	int current_state, enable_cnt;
	bool msi_enabled, msix_enabled, dma_valid;
};
struct pci_host_bridge { struct pci_bus *bus; void *private; };
struct irq_domain { unsigned int mapcount; };
struct n71_scan_host {
	struct device *dev;
	void *ecam, *port;
	spinlock_t lock;
	struct n71_scan_config config;
	struct { bool prepared; } target;
	struct n71_pme_state pme;
	struct n71_resource_write_state resources;
	struct { struct pci_host_bridge *bridge; bool associated;
		struct { struct irq_domain *domain, *parent, *child; unsigned int slots; } native; } msi;
	struct n71_msi_config msi_config;
	struct n71_msi_allocation msi_allocation;
	struct n71_brcmfmac_config brcmfmac;
	struct pci_dev *driver_root, *driver_endpoint;
	bool driver_pm, driver_root_override, driver_endpoint_override, driver_published;
	struct { struct pci_host_bridge *bridge; bool available, mapped; } dart;
	void *iommu_domain;
	unsigned int iommu_devices;
	int iommu_group_id;
	bool config_pending, bus_held, resources_assigned, window_claimed;
	unsigned int reads, driver_reads;
	int io_error, held_stop_error;
};
struct n71_diagnostic { struct pci_host_bridge *scan_bridge; };
struct n71_resource_devices { struct pci_dev *root, *endpoint; unsigned int count; int error; };
static const int pci_bus_type;
static struct {
	struct n71_scan_host host;
	struct device device;
	struct pci_bus bus, sub;
	struct pci_dev root, endpoint, foreign;
	struct pci_host_bridge bridge;
	struct irq_domain domain, parent, child;
	u32 *ecam, port[64];
	unsigned int references, locked, writes, publishes, disables, removes, releases, unmaps;
	unsigned int override_calls, fail_override, drop_write;
	bool registered, invalid_resources, missing, publish_failure;
} mock;
static unsigned int cases;
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock)=1; (flags)=0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { assert(*(lock)==1); *(lock)=0; (void)(flags); } while (0)
static void dev_info(struct device *device, const char *format, ...) { (void)device; (void)format; }
static void *pci_host_bridge_priv(struct pci_host_bridge *bridge) { return bridge->private; }
static void pci_lock_rescan_remove(void) { assert(!mock.locked++); }
static void pci_unlock_rescan_remove(void) { assert(mock.locked-- == 1); }
static void device_lock(struct device *device) { assert(mock.locked && !device->locks++); }
static void device_unlock(struct device *device) { assert(device->locks-- == 1); }
static void pm_runtime_get_noresume(struct device *device) { assert(device->locks); device->pm++; }
static void pm_runtime_put_noidle(struct device *device) { assert(device->locks && device->pm == 1); device->pm--; }
static bool device_has_driver_override(struct device *device) { return !!device->override; }
static int device_match_driver_override(struct device *device, const struct device_driver *driver)
{ return device->override ? !strcmp(device->override, driver->name) : -1; }
static int device_set_driver_override(struct device *device, const char *name)
{
	assert(device->locks);
	if (++mock.override_calls == mock.fail_override) return -ENOMEM;
	device->override = *name ? name : NULL;
	return 0;
}
static void *driver_find(const char *name, const int *bus)
{ assert(!strcmp(name,"brcmfmac") && bus == &pci_bus_type); return mock.registered ? &mock : NULL; }
static struct pci_dev *pci_get_slot(struct pci_bus *bus, unsigned int devfn)
{
	assert(mock.locked);
	if (mock.missing) return NULL;
	struct pci_dev *device = bus == &mock.bus && devfn == 8 ? &mock.root :
		bus == &mock.sub && !devfn ? &mock.endpoint : NULL;
	if (device) mock.references++;
	return device;
}
static void pci_dev_put(struct pci_dev *device) { if (device) { assert(mock.locked && mock.references); mock.references--; } }
static bool pci_device_is_present(struct pci_dev *device) { (void)device; return !mock.publish_failure; }
static bool pci_is_enabled(struct pci_dev *device) { return device->enable_cnt > 0; }
static int atomic_read(const int *count) { return *count; }
static bool n71_scan_dma_device_valid(struct pci_dev *device, bool root) { (void)root; return device->dma_valid; }
static int n71_resource_visit(struct pci_dev *device, void *context)
{
	struct n71_resource_devices *devices = context;
	devices->count++;
	if (device != devices->root && device != devices->endpoint) devices->error = -ENODEV;
	return devices->error;
}
static void pci_walk_bus(struct pci_bus *bus, int (*visit)(struct pci_dev *, void *), void *context)
{ assert(bus == &mock.bus && mock.locked); visit(&mock.root,context); visit(&mock.endpoint,context); }
static int n71_resource_verify(struct n71_scan_host *host, struct n71_resource_devices *devices)
{
	assert(host == &mock.host && devices->count == 2 && mock.locked);
	return mock.invalid_resources ? -EIO : 0;
}
static u32 readl(const void *address) { u32 value; memcpy(&value,address,4); return value; }
static void writew(u32 value, void *address)
{
	if (++mock.writes != mock.drop_write) { uint16_t word = value; memcpy(address,&word,2); }
}
static void writel(u32 value, void *address)
{
	if (++mock.writes != mock.drop_write) memcpy(address,&value,4);
}
static void n71_scan_remove_bus(struct pci_host_bridge *bridge) { assert(mock.locked); mock.removes++; bridge->bus = NULL; }
static int n71_wlan_msi_host_release(void *owner) { (void)owner; mock.releases++; return 0; }
static int n71_dart_host_unmap(void *owner) { (void)owner; mock.unmaps++; return 0; }
static int pci_set_power_state(struct pci_dev *device, int state)
{ assert(state == PCI_D0 && device == &mock.endpoint); device->current_state = state; return 0; }
static void pci_bus_add_devices(const struct pci_bus *bus);
static void pci_disable_device(struct pci_dev *device);
#include "n71-runtime-scan-extracted.h"
#include "n71-pcie-brcmfmac.h"

static void pci_bus_add_devices(const struct pci_bus *bus)
{
	assert(bus == &mock.bus && mock.locked && mock.root.dev.pm == 1 && mock.endpoint.dev.pm == 1);
	assert(!strcmp(mock.root.dev.override,"none") && !strcmp(mock.endpoint.dev.override,"brcmfmac"));
	mock.publishes++;
	if (mock.publish_failure) return;
	assert(n71_scan_deny_enable(&mock.bridge,&mock.root) == 0);
	assert(n71_scan_deny_enable(&mock.bridge,&mock.endpoint) == 0);
	assert(n71_scan_config_write(&mock.bus,8,4,2,6) == 0);
	assert(n71_scan_config_write(&mock.sub,0,4,2,6) == 0);
	mock.root.enable_cnt = mock.endpoint.enable_cnt = 1;
}
static void pci_disable_device(struct pci_dev *device)
{
	assert(mock.locked && device->dev.locks && device->enable_cnt == 1);
	device->enable_cnt--;
	mock.disables++;
	struct pci_bus *bus = device->bus;
	u32 value;
	assert(n71_scan_config_read(bus,device->devfn,4,2,&value) == 0);
	(void)n71_scan_config_write(bus,device->devfn,4,2,value & ~4U);
}
static void fresh(void)
{
	if (mock.ecam) free(mock.ecam);
	memset(&mock,0,sizeof(mock));
	mock.ecam = calloc(0x110000/4,sizeof(u32)); assert(mock.ecam);
	mock.host.ecam = mock.ecam; mock.host.port = mock.port; mock.host.dev = &mock.device;
	mock.port[0x88/4] = 1;
	mock.ecam[0x8000/4] = 0x1004106b; mock.ecam[0x100000/4] = 0x43a314e4;
	mock.ecam[0x100058/4] = 0x00886805; mock.ecam[0x10004c/4] = 0x4008;
	mock.ecam[0x8044/4] = 8; mock.ecam[0x100080/4] = 0x18003000;
	mock.host.config.active = mock.host.config_pending = mock.host.bus_held = true;
	mock.host.resources_assigned = mock.host.resources.pending = mock.host.window_claimed = true;
	mock.host.target.prepared = mock.host.pme.prepared = true;
	mock.bus.sysdata = mock.sub.sysdata = &mock.host; mock.sub.number = 1;
	mock.root = (struct pci_dev){.bus=&mock.bus,.subordinate=&mock.sub,.vendor=0x106b,.device=0x1004,.devfn=8,.dma_valid=true};
	mock.endpoint = (struct pci_dev){.bus=&mock.sub,.vendor=0x14e4,.device=0x43a3,.pm_cap=0x48,.msi_cap=0x58,.current_state=PCI_UNKNOWN,.dma_valid=true};
	mock.foreign = (struct pci_dev){.bus=&mock.bus,.devfn=16};
	mock.sub.self = &mock.root;
	mock.bridge = (struct pci_host_bridge){&mock.bus,&mock.host};
	mock.host.msi.bridge = mock.host.dart.bridge = &mock.bridge;
	mock.host.msi.associated = mock.host.dart.available = mock.host.dart.mapped = true;
	mock.host.msi.native.domain = &mock.domain; mock.host.msi.native.parent = &mock.parent;
	mock.host.iommu_domain = &mock.host; mock.host.iommu_devices = 2;
	cases++;
}
static void prepare(void)
{
	assert(n71_pcie_brcmfmac_prepare(&mock.bridge,&mock.host) == 0);
	assert(mock.references == 2 && mock.host.brcmfmac.active && mock.host.driver_pm);
	assert(mock.root.dev.pm == 1 && mock.endpoint.dev.pm == 1 && !mock.locked);
}
static void release(void)
{
	assert(n71_pcie_brcmfmac_release(&mock.bridge,&mock.host) == 0);
	assert(!n71_brcmfmac_pending(&mock.host) && !mock.references && !mock.locked);
	assert(!mock.root.dev.pm && !mock.endpoint.dev.pm && !mock.root.dev.override && !mock.endpoint.dev.override);
	assert(!mock.root.enable_cnt && !mock.endpoint.enable_cnt);
	assert(mock.ecam[0x8004/4] == 0 && mock.ecam[0x100004/4] == 0);
	assert(mock.ecam[0x100080/4] == 0x18003000);
}
int main(void)
{
#ifdef __linux__
	assert(prctl(PR_SET_DUMPABLE,0) == 0);
#endif
	/* Mutations: enable by default, omit capture/refs, publish before ready. */
	fresh(); assert(n71_scan_deny_enable(&mock.bridge,&mock.root) == -EPERM);
	assert(n71_pcie_brcmfmac_publish(&mock.bridge,&mock.host) == -EACCES && !mock.publishes);
	prepare(); assert(n71_pcie_brcmfmac_prepare(&mock.bridge,&mock.host) == -EBUSY);
	assert(n71_scan_deny_enable(&mock.bridge,&mock.foreign) == -EPERM);
	assert(n71_pcie_brcmfmac_publish(&mock.bridge,&mock.host) == 0 && mock.publishes == 1);
	assert(n71_pcie_brcmfmac_publish(&mock.bridge,&mock.host) == -EALREADY && mock.publishes == 1);
	/* Mutation: consume the finite scan budget while running the driver. */
	unsigned int scan_reads = mock.host.reads;
	u32 value;
	for (unsigned int index=0;index<4200;index++)
		assert(n71_scan_config_read(&mock.sub,0,0x80,4,&value) == 0);
	assert(mock.host.reads == scan_reads && mock.host.driver_reads >= 4200);
	/* Mutations: remove PCI/DART with a live mode or retained references. */
	struct n71_diagnostic state = {&mock.bridge};
	assert(n71_pcie_scan_remove_consumers(&state) == -EBUSY && !mock.removes && !mock.unmaps);
	release(); assert(mock.disables == 2);
	assert(n71_pcie_scan_remove_consumers(&state) == 0 && mock.removes == 1 && mock.unmaps == 1);
	/* Mutation: ignore a PM/override-only owner during consumer removal. */
	for (unsigned int fault=0;fault<6;fault++) {
		fresh();
		if (fault==0) mock.host.brcmfmac.active=true;
		if (fault==1) mock.host.driver_root=&mock.root;
		if (fault==2) mock.host.driver_endpoint=&mock.endpoint;
		if (fault==3) mock.host.driver_pm=true;
		if (fault==4) mock.host.driver_root_override=true;
		if (fault==5) mock.host.driver_endpoint_override=true;
		assert(n71_pcie_scan_remove_consumers(&state) == -EBUSY);
		assert(!mock.removes && !mock.releases && !mock.unmaps);
	}
	/* Mutations: omit dependencies/scope or steal a preexisting override. */
	for (unsigned int fault=0;fault<10;fault++) {
		fresh();
		if (fault==0) mock.host.iommu_devices=1;
		if (fault==1) mock.host.resources_assigned=false;
		if (fault==2) mock.host.msi.associated=false;
		if (fault==3) mock.host.dart.available=false;
		if (fault==4) mock.registered=true;
		if (fault==5) mock.endpoint.vendor^=1;
		if (fault==6) mock.endpoint.dma_valid=false;
		if (fault==7) mock.host.driver_published=true;
		if (fault==8) mock.root.dev.override="foreign";
		if (fault==9) mock.root.link_state=&mock;
		assert(n71_pcie_brcmfmac_prepare(&mock.bridge,&mock.host) < 0);
		assert(!mock.references && !mock.host.brcmfmac.active && !mock.root.dev.pm && !mock.writes);
	}
	/* Mutations: drop partial override ownership, PM refs or stop after error. */
	for (unsigned int fault=1;fault<=2;fault++) {
		fresh(); mock.fail_override=fault;
		assert(n71_pcie_brcmfmac_prepare(&mock.bridge,&mock.host) == -ENOMEM);
		assert(mock.references == 2 && n71_brcmfmac_pending(&mock.host));
		assert(n71_pcie_scan_remove_consumers(&state) == -EBUSY && !mock.unmaps);
		mock.fail_override=0; release(); assert(mock.host.brcmfmac.error == -ENOMEM);
	}
	/* Mutations: release with an async module, bound driver or live vectors. */
	for (unsigned int fault=0;fault<8;fault++) {
		fresh(); prepare();
		if (fault==0) mock.registered=true;
		if (fault==1) mock.endpoint.driver=&mock;
		if (fault==2) mock.endpoint.msi_enabled=true;
		if (fault==3) mock.host.msi.native.slots=1;
		if (fault==4) mock.domain.mapcount=1;
		if (fault==5) { mock.child.mapcount=1; mock.host.msi.native.child=&mock.child; }
		if (fault==6) mock.root.enable_cnt=2;
		if (fault==7) mock.endpoint.enable_cnt=-1;
		unsigned int writes=mock.writes;
		assert(n71_pcie_brcmfmac_release(&mock.bridge,&mock.host) == -EBUSY);
		assert(mock.host.brcmfmac.active && mock.references == 2 && mock.root.dev.pm == 1 && mock.writes == writes);
	}
	/* Mutations: release after failed readback or clear someone else's override. */
	fresh(); prepare(); assert(n71_pcie_brcmfmac_publish(&mock.bridge,&mock.host) == 0);
	mock.drop_write=mock.writes+3;
	assert(n71_pcie_brcmfmac_release(&mock.bridge,&mock.host) == -EIO && mock.references == 2);
	mock.drop_write=0; release(); assert(mock.host.brcmfmac.error == -EIO);
	fresh(); prepare(); mock.endpoint.dev.override="foreign";
	assert(n71_pcie_brcmfmac_release(&mock.bridge,&mock.host) == -EAGAIN);
	assert(mock.references == 2 && mock.host.driver_pm && !mock.host.brcmfmac.active);
	assert(n71_pcie_scan_remove_consumers(&state) == -EBUSY && !mock.unmaps);
	mock.endpoint.dev.override="brcmfmac"; release();
	fresh(); prepare(); mock.publish_failure=true;
	assert(n71_pcie_brcmfmac_publish(&mock.bridge,&mock.host) == -EIO && mock.references == 2);
	release();
	printf("N71_PCIE_BRCMFMAC_OK cases=%u\n",cases);
	free(mock.ecam);
	return 0;
}
