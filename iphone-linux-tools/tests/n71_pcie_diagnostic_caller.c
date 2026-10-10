/* SPDX-License-Identifier: GPL-2.0-only */
/* Real probe/action/cleanup and MMIO backend; kernel and scan dependencies are fixtures. */
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71-pcie-contract.h"
#include "n71-dart-lease.h"
#include "n71-msi-allocation-lease.h"
#include "n71-wlan-msi-config.h"
#define __iomem
#define __init
#define __exit
#define THIS_MODULE NULL
#define GFP_KERNEL 0
#define PAGE_SIZE 4096
#define IORESOURCE_MEM 0x200
#define GPIOD_OUT_HIGH 1
#define ARRAY_SIZE(a) (sizeof(a) / sizeof(*(a)))
#define IS_ERR(p) ((uintptr_t)(p) > (uintptr_t)-4096)
#define IS_ERR_OR_NULL(p) (!(p) || IS_ERR(p))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define WARN_ON(condition) assert(!(condition))
#define module_param(name, type, mode)
#define MODULE_PARM_DESC(name, text)
#define MODULE_DEVICE_TABLE(type, name)
#define MODULE_LICENSE(text)
#define MODULE_DESCRIPTION(text)
#define module_init(fn)
#define module_exit(fn)
#define module_param_cb(name, ops, arg, mode) \
	static const void *param_##name __attribute__((unused)) = (ops)
#define DEFINE_MUTEX(name) int name
static int *active_lock;
static void mutex_lock(int *lock) { assert(!*lock && !active_lock); *lock = 1; active_lock = lock; }
static void mutex_unlock(int *lock) { assert(*lock && active_lock == lock); *lock = 0; active_lock = NULL; }
static void host_lock(int *lock) { assert(active_lock && *active_lock && !*lock); *lock=1; }
static void host_unlock(int *lock) { assert(active_lock && *active_lock && *lock); *lock=0; }
#define spin_lock_irqsave(lock, flags) do { (flags)=0; host_lock(lock); } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(flags); host_unlock(lock); } while (0)
struct kernel_param { int unused; };
struct kernel_param_ops {
	int (*set)(const char *, const struct kernel_param *);
	int (*get)(char *, const struct kernel_param *);
};
struct device_node { int refs; };
struct device { struct device_node *of_node; int index, usage; bool suspended, attached; };
typedef uint64_t resource_size_t;
struct resource { resource_size_t start, end; struct resource *parent; };
static struct resource iomem_resource, foreign_resource;
struct platform_device { struct device dev; void *data; struct resource resources[11]; };
struct of_phandle_args { struct device_node *np; u32 args[2]; };
struct of_device_id { const char *compatible; };
struct platform_driver {
	int (*probe)(struct platform_device *);
	void (*remove)(struct platform_device *);
	struct { const char *name; const struct of_device_id *of_match_table; bool suppress_bind_attrs; } driver;
};
struct gpio_desc { int logical; };
/* MSI dependencies are modeled here; native callbacks have separate gates. */
struct irq_domain { unsigned int mapcount; };
struct pci_dev { bool msi_enabled; };
struct pci_host_bridge;
struct n71_wlan_msi {
	struct irq_domain *domain, *child;
	unsigned int slots;
};
struct n71_wlan_msi_host {
	struct pci_host_bridge *bridge;
	struct n71_wlan_msi native;
	bool associated;
};
struct n71_scan_host {
	struct n71_wlan_msi_host msi;
	struct n71_msi_allocation msi_allocation;
	struct n71_msi_config msi_config;
	struct { bool active; int error; } brcmfmac;
	struct pci_dev *driver_root, *driver_endpoint;
	bool driver_pm, driver_root_override, driver_endpoint_override, driver_published;
	unsigned int driver_reads;
	int lock;
	struct { struct pci_host_bridge *bridge; bool available, mapped; } dart;
	void *iommu_domain;
	unsigned int iommu_devices;
	bool bus_held, resource_attempted, resources_assigned, window_claimed;
	int held_stop_error, io_error;
	struct { bool pending, active; int error; } resources;
	struct { int error; } config;
	struct resource windows[3];
};
struct pci_host_bridge { bool alive; void *bus; struct n71_scan_host private; };
/* DART callbacks are tracked fixtures; the full module ABI uses the real provider. */
struct n71_dart_provider {
	struct n71_dart_lease lease;
	struct { void *domain, *fwnode; unsigned int irq; } interrupt;
	struct { void *regs; } mmio;
	struct platform_device *device;
	void *claimed;
};
static void *pci_host_bridge_priv(struct pci_host_bridge *bridge) { assert(bridge); return &bridge->private; }
enum n71_pcie_region { N71_PCIE_COMMON, N71_PCIE_PHY };
#define N71_PCIE_MAX_TUNABLES 512U
struct n71_pcie_tunable { u32 offset, mask, value; };
struct n71_pcie_io {
	void *context;
	int (*read32)(void *, enum n71_pcie_region, u32, u32 *);
	int (*write32)(void *, enum n71_pcie_region, u32, u32);
	void (*delay_us)(void *, unsigned int);
};
struct n71_pcie_port_io { struct n71_pcie_io common; int (*read_port)(void *, u32, u32 *); int (*write_port)(void *, u32, u32); };
struct n71_pcie_link_io {
	void *context;
	int (*read32)(void *, bool, u32, u32 *);
	int (*write32)(void *, bool, u32, u32);
	int (*reset)(void *, bool);
	void (*delay_us)(void *, unsigned int);
	int (*read_endpoint)(void *, u32, u32 *);
};
struct n71_pcie_global_config { u32 lane_config; const struct n71_pcie_tunable *phy; unsigned int phy_count; const struct n71_pcie_tunable *common; unsigned int common_count; };
struct n71_pcie_inventory_io { void *context; int (*read32)(void *, u32, u32 *); };
struct n71_pcie_inventory {
	u32 class_revision, header, subsystem, command_status, interrupt, bars[6];
	u32 express_offset, express_header, msi_offset, msi_header, msix_offset, msix_header;
	unsigned int reads, capabilities;
};
enum fault { NONE, VALIDATE, TABLE, MAP, GPIO, ALLOC, GLOBAL, PORT, ROOT,
	ENUMERATE, INVENTORY, SCAN_ERROR, SCAN_PENDING, RESET_WRITE, RESET_READ,
	RESET_VALUE, PUT_ERROR, PUT_ACTIVE, PUT_ERROR_OFF, HOLD_NO_OWNER, HOLD_NO_BUS,
	HOLD_PENDING, HOLD_STOP_REFUSED, HOLD_STOP_AND_RESTORE };
static struct {
	enum fault fault;
	int attach_fail, resume_fail, put_fail;
	bool machine, live, reset_phase;
	unsigned int refs, gets, puts, suspends, detaches, scans, enumerations, resets, registered;
	unsigned int pme_scans, held_scans;
	unsigned int msi_scans, msi_releases, bus_removals;
	int msi_acquire_error, msi_cleanup_error;
	unsigned int msi_allocations, msi_vector_releases, msi_release_calls;
	int allocation_early_error, allocation_error, vector_release_error;
	bool vector_release_stopped, vector_release_pending, allocation_child_owned;
	struct pci_dev msi_endpoint;
	char allocation_log[512];
	struct {
		unsigned int prepares, publishes, releases;
		int prepare_error, publish_error, release_error;
		bool prepare_pending, release_pending;
		char log[512];
	} runtime;
	struct irq_domain msi_domain, msi_child;
	unsigned int assignments;
	unsigned int dart_acquires, dart_releases;
	bool dart_live;
	bool prescan_dart, dart_no_owner, dart_not_running, dart_no_device;
	unsigned int iommu_scans, consumer_calls, unmaps, host_releases;
	unsigned int inventories;
	int consumer_error, unmap_error, host_release_error, iommu_scan_error;
	struct platform_device dart_device;
	int dart_acquire_error, dart_cleanup_error;
	struct n71_dart_provider dart;
	int assign_error, assign_early_error;
	struct device domains[4];
	struct gpio_desc gpio;
	struct device_node node;
	void *allocations[16];
	unsigned int allocated;
	u32 *ecam, port[4096], common[8192], phy[4096];
	struct pci_host_bridge bridge;
} mock;
static void __module_get(void *module) { (void)module; mock.refs++; }
static bool try_module_get(void *module) { if (!mock.live) return false; __module_get(module); return true; }
static void module_put(void *module) { (void)module; assert(mock.refs); mock.refs--; }
static bool sysfs_streq(const char *a, const char *b) { size_t n = strlen(b); return !strncmp(a,b,n) && (!a[n] || (a[n]=='\n' && !a[n+1])); }
static int scnprintf(char *buffer, size_t size, const char *format, ...)
{
	va_list args; int length; va_start(args,format); length=vsnprintf(buffer,size,format,args); va_end(args); return length;
}
static void dev_info(struct device *dev, const char *format, ...)
{
	va_list arguments;
	(void)dev;
	va_start(arguments,format);
	if (strstr(format,"N71_PCIE_MSI_ALLOCATION_RESULT ")==format)
		vsnprintf(mock.allocation_log,sizeof(mock.allocation_log),format,arguments);
	else if (strstr(format,"N71_PCIE_DRIVER_RESULT ")==format) {
		assert(mock.bridge.private.lock);
		vsnprintf(mock.runtime.log,sizeof(mock.runtime.log),format,arguments);
	}
	va_end(arguments);
}
static void dev_err(struct device *dev, const char *format, ...) { (void)dev; (void)format; }
static int dev_err_probe(struct device *dev, int error, const char *format, ...) { (void)dev; (void)format; return error; }
static void *devm_kcalloc(struct device *dev, size_t count, size_t bytes, int flags)
{
	void *p; (void)dev; (void)flags;
	if (mock.fault==ALLOC) return NULL;
	p=calloc(count,bytes); assert(p && mock.allocated<16); mock.allocations[mock.allocated++]=p; return p;
}
static void *devm_kzalloc(struct device *dev, size_t size, int flags) { return devm_kcalloc(dev,1,size,flags); }
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name,"apple,n71")); return mock.machine; }
static struct resource *platform_get_resource(struct platform_device *pdev, unsigned int type, unsigned int index)
{
	assert(type==IORESOURCE_MEM); return index<11 ? &pdev->resources[index] : NULL;
}
static resource_size_t resource_size(struct resource *r) { return r->end-r->start+1; }
static int of_parse_phandle_with_fixed_args(struct device_node *node, const char *name, int count, int index, struct of_phandle_args *out)
{
	(void)node; assert(!strcmp(name,"perst-gpios") && count==2 && !index);
	mock.node.refs++; *out=(struct of_phandle_args){&mock.node,{161,1}}; return 0;
}
static int of_address_to_resource(struct device_node *node, int index, struct resource *out)
{
	assert(node==&mock.node && !index); *out=(struct resource){.start=0x20f100000ULL,.end=0x20f1fffffULL}; return 0;
}
static void of_node_put(struct device_node *node) { assert(node->refs); node->refs--; }
static int of_property_count_u32_elems(struct device_node *node, const char *name) { (void)node; (void)name; return mock.fault==TABLE ? 2 : 3; }
static int of_property_read_u32_index(struct device_node *node, const char *name, unsigned int index, u32 *out)
{
	(void)node; (void)name; *out=index==0 ? 0x100 : index==1 ? 0xff : 0x25; return 0;
}
static bool n71_pcie_table_valid(const struct n71_pcie_tunable *t, unsigned int n, u32 size) { return t && n && size>=4; }
static bool n71_pcie_link_table_valid(const struct n71_pcie_tunable *t, unsigned int n, bool ecam) { (void)ecam; return t && n; }
static void *devm_platform_ioremap_resource(struct platform_device *pdev, unsigned int index)
{
	(void)pdev; if (mock.fault==MAP) return ERR_PTR(-ENOMEM);
	return index==0 ? (void *)mock.ecam : index==3 ? (void *)mock.port : index==9 ? (void *)mock.common : (void *)mock.phy;
}
static struct gpio_desc *devm_gpiod_get(struct device *dev, const char *name, int flag)
{
	(void)dev; assert(!strcmp(name,"perst") && flag==1); mock.gpio.logical=1; return mock.fault==GPIO ? ERR_PTR(-EIO) : &mock.gpio;
}
static void platform_set_drvdata(struct platform_device *pdev, void *data) { pdev->data=data; }
static void *platform_get_drvdata(struct platform_device *pdev) { return pdev->data; }
static struct device *dev_pm_domain_attach_by_name(struct device *dev, const char *name)
{
	static const char *names[]={"pcie","aux","ref","link1"}; unsigned int index; (void)dev;
	assert(mock.refs);
	for (index=0;index<4;index++) if (!strcmp(name,names[index])) break;
	assert(index<4 && !mock.domains[index].attached);
	if ((int)index==mock.attach_fail) return ERR_PTR(-ENODEV);
	mock.domains[index].attached=true; return &mock.domains[index];
}
static int pm_runtime_resume_and_get(struct device *dev)
{
	assert(dev->attached && !dev->usage && mock.refs);
	if (dev->index==mock.resume_fail) return -EIO;
	dev->usage++; dev->suspended=false; mock.gets++; return 0;
}
static int pm_runtime_put_sync_suspend(struct device *dev)
{
	assert(dev->usage==1 && mock.refs && !mock.bridge.alive && !mock.dart_live);
	dev->usage--; mock.puts++;
	if (dev->index==mock.put_fail && mock.fault==PUT_ERROR_OFF) {
		dev->suspended=true; return -ETIMEDOUT;
	}
	if (dev->index==mock.put_fail && mock.fault==PUT_ERROR) return -ETIMEDOUT;
	if (!(dev->index==mock.put_fail && mock.fault==PUT_ACTIVE)) dev->suspended=true;
	return 0;
}
static void pm_runtime_barrier(struct device *dev) { assert(!dev->usage && mock.refs); }
static int pm_runtime_suspend(struct device *dev)
{
	assert(!dev->usage && mock.refs && !mock.bridge.alive); mock.suspends++;
	if (dev->suspended) return 1;
	if (mock.fault==PUT_ERROR) return -ETIMEDOUT;
	if (mock.fault!=PUT_ACTIVE) dev->suspended=true;
	return 0;
}
static bool pm_runtime_status_suspended(struct device *dev) { return dev->suspended; }
static void dev_pm_domain_detach(struct device *dev, bool poweroff)
{
	assert(dev->attached && !dev->usage && dev->suspended && poweroff && !mock.bridge.alive && !mock.dart_live && mock.refs);
	dev->attached=false; mock.detaches++;
}
static u32 readl(const void *address) { u32 value; memcpy(&value,address,4); return value; }
static void writel(u32 value, void *address) { memcpy(address,&value,4); }
static void udelay(unsigned int delay) { (void)delay; }
static void usleep_range(unsigned int a, unsigned int b) { assert(a<b); }
static int gpiod_direction_output(struct gpio_desc *gpio, int value)
{
	assert(!mock.bridge.alive && !mock.dart_live && mock.refs);
	if (mock.reset_phase && value) {
		mock.resets++;
		if (mock.fault==RESET_WRITE) return -EIO;
	}
	gpio->logical=value; return 0;
}
static int gpiod_get_value_cansleep(struct gpio_desc *gpio)
{
	if (mock.reset_phase && gpio->logical) {
		if (mock.fault==RESET_READ) return -EIO;
		if (mock.fault==RESET_VALUE) return 0;
	}
	return gpio->logical;
}
#include "n71-pcie-mmio.h"
static int n71_pcie_initialize_global(const struct n71_pcie_io *io, const struct n71_pcie_global_config *config)
{
	assert(io->context && config->lane_config==1 && mock.refs); return mock.fault==GLOBAL ? -EIO : 0;
}
static int n71_pcie_prepare_wlan(const struct n71_pcie_port_io *io, bool a, bool b)
{
	assert(io->common.context && !a && !b); return mock.fault==PORT ? -EIO : 0;
}
static int n71_pcie_enumerate_wlan(const struct n71_pcie_link_io *io, const struct n71_pcie_tunable *a, unsigned int ac, const struct n71_pcie_tunable *b, unsigned int bc, u32 *identity)
{
	assert(a && b && ac && bc); mock.enumerations++;
	assert(io->reset(io->context,false)==0); mock.reset_phase=true; *identity=0x43a314e4;
	return mock.fault==ENUMERATE ? -ENOLINK : 0;
}
static int n71_pcie_inventory_collect(const struct n71_pcie_inventory_io *io, struct n71_pcie_inventory *out)
{
	u32 value; assert(io->read32(io->context,0,&value)==0 && value==0x43a314e4);
	mock.inventories++;
	memset(out,0,sizeof(*out)); return mock.fault==INVENTORY ? -EIO : 0;
}
static int n71_pcie_scan(struct device *dev, struct n71_diagnostic *state)
{
	(void)dev; assert(state->reset_pending && mock.refs && state->powered==4); mock.scans++;
	if (mock.fault==SCAN_PENDING) { mock.bridge.alive=true; state->scan_bridge=&mock.bridge; return -EPERM; }
	return mock.fault==SCAN_ERROR ? -EPERM : 0;
}
static int n71_pcie_scan_with_pme(struct device *dev, struct n71_diagnostic *state, bool disable_pme)
{
	assert(disable_pme);
	mock.pme_scans++;
	return n71_pcie_scan(dev,state);
}
static int n71_pcie_scan_hold(struct device *dev, struct n71_diagnostic *state)
{
	int error;
	mock.held_scans++;
	error=n71_pcie_scan_with_pme(dev,state,true);
	if (error || mock.fault==HOLD_NO_OWNER) return error;
	mock.bridge.alive=true; state->scan_bridge=&mock.bridge;
	mock.bridge.bus=mock.fault==HOLD_NO_BUS ? NULL : &mock.bridge;
	mock.bridge.private.bus_held=true;
	return 0;
}
static int n71_pcie_scan_hold_msi(struct device *dev, struct n71_diagnostic *state)
{
	struct n71_wlan_msi_host *owner=&mock.bridge.private.msi;
	int error;

	assert(active_lock && *active_lock && mock.refs==1 && state->module_retained);
	mock.msi_scans++;
	if (mock.msi_acquire_error) {
		mock.bridge.alive=true; state->scan_bridge=&mock.bridge;
		owner->bridge=&mock.bridge; owner->native.domain=&mock.msi_domain;
		return mock.msi_acquire_error;
	}
	error=n71_pcie_scan_hold(dev,state);
	if (error || !state->scan_bridge) return error;
	owner->bridge=&mock.bridge; owner->native.domain=&mock.msi_domain;
	owner->associated=true;
	return 0;
}
static int n71_pcie_scan_hold_iommu(struct device *dev, struct n71_diagnostic *state,
				   struct platform_device *provider)
{
	struct n71_scan_host *host=&mock.bridge.private;
	int error;
	assert(mock.prescan_dart && mock.dart_live && state->dart==&mock.dart);
	assert(provider==&mock.dart_device && mock.dart.lease.running && !mock.scans);
	mock.iommu_scans++;
	error=n71_pcie_scan_hold_msi(dev,state);
	if (error || !state->scan_bridge) return error;
	host->dart.bridge=&mock.bridge;
	host->dart.available=host->dart.mapped=true;
	host->iommu_domain=&mock.dart; host->iommu_devices=2;
	return mock.iommu_scan_error;
}
/* Native allocation/config tests and the real ABI probe qualify this dependency. */
static int n71_msi_allocation_error(struct n71_scan_host *host)
{
	return host->msi_config.error ? host->msi_config.error :
		host->config.error ? host->config.error : host->io_error;
}
static int n71_pcie_msi_allocate(struct pci_host_bridge *bridge, struct n71_scan_host *host,
				struct n71_msi_allocation *lease)
{
	assert(active_lock && *active_lock && mock.refs==2);
	assert(bridge==&mock.bridge && host==&bridge->private && lease==&host->msi_allocation);
	assert(mock.bridge.alive && mock.bridge.bus && !mock.puts && !mock.resets);
	if (mock.allocation_early_error) return mock.allocation_early_error;
	if (!host->resources_assigned || !host->window_claimed || host->resources.active ||
	    !host->msi.associated || !host->dart.available || !host->dart.mapped)
		return -EACCES;
	if (host->msi_config.attempts) return -EALREADY;
	mock.msi_allocations++;
	host->msi_config.attempts=1; host->msi_config.phase=N71_MSI_CONFIG_ACTIVE;
	*lease=(struct n71_msi_allocation){.endpoint=&mock.msi_endpoint,.vector=320,.default_irq=19};
	mock.msi_endpoint.msi_enabled=true;
	host->msi.native.slots=1; mock.msi_domain.mapcount=mock.msi_child.mapcount=1;
	host->msi.native.child=&mock.msi_child; mock.allocation_child_owned=true;
	host->msi_config.error=mock.allocation_error;
	return mock.allocation_error;
}
static int n71_pcie_msi_release(struct n71_scan_host *host, struct n71_msi_allocation *lease)
{
	assert(active_lock && *active_lock && mock.refs==2 && mock.bridge.alive && mock.bridge.bus);
	assert(host==&mock.bridge.private && lease==&host->msi_allocation);
	if (!lease->endpoint && !lease->vector && !lease->default_irq && host->msi_config.phase==N71_MSI_CONFIG_EMPTY)
		return 0;
	mock.msi_release_calls++;
	if (mock.vector_release_pending) return 0; /* Caller must independently conserve ownership. */
	if (!lease->endpoint) return -EBUSY;
	if (mock.vector_release_stopped) {
		host->msi_config.phase=N71_MSI_CONFIG_STOPPED;
		mock.msi_endpoint.msi_enabled=false; host->msi.native.slots=0;
		mock.msi_domain.mapcount=mock.msi_child.mapcount=0;
	}
	if (mock.vector_release_error) {
		if (!host->msi_config.error) host->msi_config.error=mock.vector_release_error;
		return mock.vector_release_error;
	}
	memset(lease,0,sizeof(*lease)); host->msi_config.phase=N71_MSI_CONFIG_EMPTY;
	mock.msi_endpoint.msi_enabled=false; host->msi.native.slots=0;
	mock.msi_domain.mapcount=mock.msi_child.mapcount=0; mock.msi_vector_releases++;
	return 0;
}

static int n71_pcie_scan_remove_consumers(struct n71_diagnostic *state)
{
	struct n71_wlan_msi_host *owner=&mock.bridge.private.msi;
	struct n71_scan_host *host=&mock.bridge.private;
	if (!state->scan_bridge) return 0;
	assert(!host->brcmfmac.active && !host->driver_root && !host->driver_endpoint && !host->driver_pm &&
	       !host->driver_root_override && !host->driver_endpoint_override);
	assert(mock.bridge.alive && mock.refs && state->powered==4 && state->attached==4);
	assert(!host->msi_allocation.endpoint && !host->msi_allocation.vector && !host->msi_allocation.default_irq &&
	       host->msi_config.phase==N71_MSI_CONFIG_EMPTY);
	mock.consumer_calls++;
	if (mock.consumer_error) return mock.consumer_error;
	if (mock.bridge.bus) {
		mock.bus_removals++;
		mock.bridge.bus=NULL;
		mock.bridge.private.bus_held=false;
		if (mock.fault==HOLD_STOP_REFUSED || mock.fault==HOLD_STOP_AND_RESTORE)
			mock.bridge.private.held_stop_error=-EPERM;
		if (mock.bridge.private.config.error && !mock.bridge.private.held_stop_error)
			mock.bridge.private.held_stop_error=mock.bridge.private.config.error;
	}
	host->iommu_domain=NULL; host->iommu_devices=0;
	if (owner->bridge) {
		owner->associated=false;
		if (mock.msi_cleanup_error) return mock.msi_cleanup_error;
		if (mock.allocation_child_owned && !owner->native.slots && !mock.msi_domain.mapcount) {
			owner->native.child=NULL; mock.allocation_child_owned=false;
		}
		if (owner->native.child || owner->native.domain->mapcount) return -EBUSY;
		*owner=(struct n71_wlan_msi_host){0}; mock.msi_releases++;
	}
	if (host->dart.mapped) {
		assert(mock.dart_live && state->dart && host->dart.available);
		if (mock.unmap_error) return mock.unmap_error;
		host->dart.mapped=false; mock.unmaps++;
	}
	return 0;
}
static int n71_pcie_scan_cleanup(struct n71_diagnostic *state)
{
	struct n71_scan_host *host=&mock.bridge.private;
	int stop_error, error;
	assert(!state->dart && !mock.dart_live);
	if (!state->scan_bridge) return 0;
	if (mock.fault==SCAN_PENDING) return -EIO;
	error=n71_pcie_scan_remove_consumers(state);
	if (error) return error;
	if (host->dart.bridge) {
		assert(!mock.bridge.bus && !host->dart.mapped);
		if (mock.host_release_error) return mock.host_release_error;
		host->dart.bridge=NULL; host->dart.available=false; mock.host_releases++;
	}
	if (mock.fault==HOLD_PENDING || mock.fault==HOLD_STOP_AND_RESTORE) return -EIO;
	stop_error=mock.bridge.private.held_stop_error;
	mock.bridge.private.resources.pending=false;
	mock.bridge.private.window_claimed=mock.bridge.private.resources_assigned=false;
	mock.bridge.private.windows[1].parent=NULL;
	mock.bridge.alive=false; state->scan_bridge=NULL; return stop_error;
}
static int n71_pcie_assign_resources(struct n71_diagnostic *state)
{
	struct n71_scan_host *host=&mock.bridge.private;
	assert(active_lock && *active_lock && mock.refs==2);
	assert(state->module_retained && state->reset_pending && state->powered==4 && state->attached==4);
	assert(!state->power_put_pending && !state->primary_error && !state->cleanup_error);
	assert(state->scan_bridge==&mock.bridge && mock.bridge.alive && mock.bridge.bus && host->bus_held);
	if (mock.assign_early_error) return mock.assign_early_error;
	if (host->resource_attempted) return host->config.error ? host->config.error : -EALREADY;
	host->resource_attempted=true; mock.assignments++;
	host->resources.pending=host->window_claimed=true;
	host->windows[1].parent=&iomem_resource;
	host->config.error=mock.assign_error;
	host->resources_assigned=!mock.assign_error;
	return mock.assign_error;
}
static int n71_pcie_size_bars(struct device *dev, struct n71_diagnostic *state, void *out) { (void)dev; (void)state; (void)out; return 0; }
static int n71_pcie_chip_id(struct device *dev, struct n71_diagnostic *state) { (void)dev; (void)state; return 0; }
static int n71_pcie_dart_observe(struct device *dev, struct n71_diagnostic *state) { (void)dev; (void)state; return 0; }
static int n71_pcie_dart_cycle(struct device *dev, struct n71_diagnostic *state) { (void)dev; (void)state; return 0; }
static int n71_pcie_dart_acquire(struct device *dev, struct n71_diagnostic *state)
{
	(void)dev;
	assert(active_lock && *active_lock);
	if (mock.prescan_dart) {
		assert(mock.refs==1 && !mock.bridge.alive && !mock.scans && mock.inventories==1);
	} else {
		assert(mock.refs==2 && mock.bridge.alive && mock.bridge.bus);
		assert(mock.bridge.private.resources_assigned && mock.bridge.private.window_claimed);
	}
	assert(state->module_retained && state->reset_pending && state->powered==4 && state->attached==4);
	assert(!state->primary_error && !state->cleanup_error && !state->power_put_pending);
	if (state->dart) return mock.dart.lease.running ? -EALREADY : -EBUSY;
	mock.dart=(struct n71_dart_provider){0};
	mock.dart.lease.captured=mock.dart.lease.attempted=true;
	mock.dart.lease.running=!mock.dart_acquire_error && !mock.dart_not_running;
	mock.dart.lease.operation_error=mock.dart_acquire_error;
	mock.dart.device=mock.dart_no_device ? NULL : &mock.dart_device;
	mock.dart.mmio.regs=mock.dart.interrupt.domain=mock.dart.interrupt.fwnode=&mock.dart;
	mock.dart.interrupt.irq=32;
	state->dart=mock.dart_no_owner ? NULL : &mock.dart;
	mock.dart_live=!mock.dart_no_owner; mock.dart_acquires++;
	return mock.dart_acquire_error;
}
static int n71_pcie_dart_cleanup(struct device *dev, struct n71_diagnostic *state)
{
	(void)dev;
	if (!state->dart) return 0;
	assert(active_lock && *active_lock && mock.refs && mock.dart_live);
	assert(state->powered==4 && state->attached==4 && state->reset_pending);
	if (!mock.prescan_dart) assert(mock.bridge.alive);
	if (mock.bridge.private.dart.bridge)
		assert(!mock.bridge.bus && !mock.bridge.private.dart.mapped && !mock.bridge.private.msi.bridge);
	mock.dart.lease.running=false;
	if (mock.dart_cleanup_error) {
		mock.dart.lease.restore_error=mock.dart_cleanup_error;
		return mock.dart_cleanup_error;
	}
	state->dart=NULL; mock.dart_live=false; mock.dart_releases++;
	return 0;
}
static int platform_driver_register(struct platform_driver *driver) { assert(driver->driver.suppress_bind_attrs); mock.registered++; return 0; }
static void platform_driver_unregister(struct platform_driver *driver) { (void)driver; assert(!mock.refs && mock.registered); mock.registered--; }
/* The adapter/config have separate real-source gates; only their effects are modeled here. */
static void runtime_owned(struct n71_scan_host *host)
{
	host->brcmfmac.active=true; host->driver_root=host->driver_endpoint=&mock.msi_endpoint;
	host->driver_pm=host->driver_root_override=host->driver_endpoint_override=true;
}
static void runtime_error(struct n71_scan_host *host, int error)
{
	if (error && error!=-EBUSY && error!=-EALREADY && !host->brcmfmac.error)
		host->brcmfmac.error=error;
}
static void runtime_dependency(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{
	assert(active_lock && *active_lock && mock.refs==2 && bridge==&mock.bridge && host==&bridge->private);
	assert(mock.bridge.alive && mock.bridge.bus && !mock.puts && !mock.resets && !host->lock);
}
static int n71_pcie_brcmfmac_prepare(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{
	runtime_dependency(bridge,host);
	if (host->brcmfmac.active || host->driver_root || host->driver_endpoint || host->driver_pm ||
	    host->driver_root_override || host->driver_endpoint_override || host->driver_published)
		return -EBUSY;
	mock.runtime.prepares++;
	if (!mock.runtime.prepare_error || mock.runtime.prepare_pending) runtime_owned(host);
	runtime_error(host,mock.runtime.prepare_error);
	return mock.runtime.prepare_error;
}
static int n71_pcie_brcmfmac_publish(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{
	runtime_dependency(bridge,host);
	if (host->driver_published) return -EALREADY;
	if (!host->brcmfmac.active) return -EACCES;
	mock.runtime.publishes++; host->driver_published=true;
	runtime_error(host,mock.runtime.publish_error);
	return mock.runtime.publish_error;
}
static int n71_pcie_brcmfmac_release(struct pci_host_bridge *bridge, struct n71_scan_host *host)
{
	runtime_dependency(bridge,host);
	if (!host->brcmfmac.active && !host->driver_root && !host->driver_endpoint && !host->driver_pm &&
	    !host->driver_root_override && !host->driver_endpoint_override) return 0;
	mock.runtime.releases++;
	if (mock.runtime.release_error || mock.runtime.release_pending) {
		runtime_error(host,mock.runtime.release_error);
		return mock.runtime.release_error;
	}
	host->brcmfmac.active=false; host->driver_root=host->driver_endpoint=NULL;
	host->driver_pm=host->driver_root_override=host->driver_endpoint_override=false;
	return 0;
}
#include "n71-pcie-diagnostic.c"

static struct platform_device setup(void)
{
	static const uint64_t addresses[]={0x610000000ULL,0x601000000ULL,0x601004000ULL,0x602000000ULL,0x602004000ULL,0x603000000ULL,0x603004000ULL,0x604000000ULL,0x604004000ULL,0x600000000ULL,0x600008000ULL};
	struct platform_device p={0}; unsigned int index;
	assert(!session && !mock.refs); memset(&mock,0,sizeof(mock));
	mock.machine=mock.live=true; mock.attach_fail=mock.resume_fail=mock.put_fail=-1;
	mock.ecam=calloc(0x1000000/4,4); assert(mock.ecam);
	mock.ecam[0x8000/4]=0x1004106b; mock.ecam[0x100000/4]=0x43a314e4; mock.port[0x88/4]=5;
	for (index=0;index<4;index++) { mock.domains[index].index=index; mock.domains[index].suspended=true; }
	for (index=0;index<11;index++) p.resources[index]=(struct resource){.start=addresses[index],.end=addresses[index]+(index==0 ? 0x1000000 : index==9 ? 0x8000 : 0x4000)-1};
	p.dev.of_node=&mock.node;
	run=enumerate=config_inventory=host_scan=true; bar_sizing=chip_id=dart_observe=dart_cycle=false;
	scan_pme_disable=scan_hold=msi_parent=iommu_parent=driver_runtime=false;
	return p;
}
static void finish(struct platform_device *p)
{
	unsigned int index;
	assert(!mock.refs && !mock.node.refs && !mock.bridge.alive && mock.puts==mock.gets);
	assert(!mock.bridge.private.msi.bridge && !mock.bridge.private.msi.native.domain);
	assert(mock.msi_scans==(msi_parent && (!mock.prescan_dart || mock.iommu_scans) ? 1U : 0U) || !mock.enumerations);
	assert(mock.pme_scans==(scan_pme_disable ? mock.scans : 0));
	for (index=0;index<4;index++) assert(!mock.domains[index].attached && !mock.domains[index].usage);
	if (session) n71_remove(p);
	assert(!session && !session_device && !session_lock);
	for (index=0;index<mock.allocated;index++) free(mock.allocations[index]);
	free(mock.ecam);
}

static struct platform_device setup_held(void)
{
	struct platform_device p=setup();
	scan_pme_disable=scan_hold=true;
	return p;
}

static unsigned int exercise_held_caller(void)
{
	const enum fault bad_proofs[]={HOLD_NO_OWNER,HOLD_NO_BUS};
	const enum fault cleanup_faults[]={HOLD_PENDING,HOLD_STOP_REFUSED,
		HOLD_STOP_AND_RESTORE,RESET_READ,PUT_ERROR};
	const int cleanup_errors[]={-EIO,-EPERM,-EIO,-EIO,-ETIMEDOUT};
	struct platform_device p;
	char status[PAGE_SIZE], held[32];
	u32 identity;
	unsigned int index,cases=0;
	int error;

	/* Mutations killed: ignore hold opt-in, clean up before return, or report a stale held flag. */
	p=setup_held();
	assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=0\n"));
	assert(n71_init()==0 && mock.registered==1 && !mock.scans);
	assert(n71_probe(&p)==0 && session && session->module_retained && mock.refs==1);
	assert(mock.bridge.alive && mock.bridge.bus && mock.held_scans==1 && mock.pme_scans==1);
	assert(session->powered==4 && session->attached==4 && session->reset_pending);
	assert(!mock.puts && !mock.detaches && !mock.resets && !session->cleanup_error && !session->primary_error);
	assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=1\n"));
	assert(n71_session_status(status,NULL)>0 && strstr(status,"retained=1 scan_pending=1") &&
	       strstr(status,"powered=4 attached=4") && !strstr(status,"held="));
	assert(n71_read_link(session,true,0,&identity)==0 && identity==0x1004106b);
	mock.bridge.private.bus_held=false;
	assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=0\n"));
	mock.bridge.private.bus_held=true;
	assert(n71_probe(&p)==-EBUSY && mock.refs==1 && mock.scans==1);
	assert(n71_cleanup_action("scan",NULL)==-EINVAL && mock.refs==1 && mock.bridge.alive);
	assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && !mock.bridge.alive);
	assert(mock.scans==1 && mock.enumerations==1 && mock.resets==1 && mock.puts==4);
	assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=0\n"));
	assert(n71_cleanup_action("cleanup",NULL)==0 && mock.puts==4);
	n71_exit(); finish(&p); cases++;
	/* Mutation killed: trust a zero backend return without a live, owned bus. */
	for (index=0;index<ARRAY_SIZE(bad_proofs);index++) {
		p=setup_held(); mock.fault=bad_proofs[index];
		assert(n71_probe(&p)==-ENODEV && !session && !mock.refs && !mock.bridge.alive);
		assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=0\n"));
		assert(mock.scans==1 && mock.puts==4); finish(&p); cases++;
	}
	/* Mutation killed: let hold overwrite a negative scan or abandon its pending owner. */
	p=setup_held(); mock.fault=SCAN_ERROR;
	assert(n71_probe(&p)==-EPERM && !session && !mock.refs); finish(&p); cases++;
	p=setup_held(); mock.fault=SCAN_PENDING;
	assert(n71_probe(&p)==0 && session->module_retained && mock.refs==1);
	assert(session->primary_error==-EPERM && session->cleanup_error==-EIO);
	assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=0\n"));
	assert(n71_cleanup_action("cleanup",NULL)==-EIO && !mock.puts && !mock.resets);
	mock.fault=NONE;
	assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && mock.scans==1);
	finish(&p); cases++;
	/* Mutations killed: free power/reset before bus cleanup, lose stop refusal, or put twice on retry. */
	for (index=0;index<ARRAY_SIZE(cleanup_faults);index++) {
		unsigned int puts;
		p=setup_held(); mock.fault=cleanup_faults[index]; mock.put_fail=3;
		assert(n71_probe(&p)==0 && session->module_retained && mock.refs==1 && mock.bridge.bus);
		assert(!mock.puts && !mock.resets);
		assert(n71_cleanup_action("cleanup",NULL)==cleanup_errors[index] && mock.refs==1);
		assert(n71_held_status(held,NULL)>0 && !strcmp(held,"held=0\n"));
		assert(session->module_retained && !session->primary_error);
		puts=mock.puts;
		if (cleanup_faults[index]!=HOLD_STOP_REFUSED)
			assert(n71_cleanup_action("cleanup",NULL)==cleanup_errors[index] && mock.refs==1 && mock.puts==puts);
		mock.fault=NONE;
		error=n71_cleanup_action("cleanup",NULL);
		if (cleanup_faults[index]==HOLD_STOP_AND_RESTORE) {
			assert(error==-EPERM && mock.refs==1 && !session->scan_bridge && !mock.puts && !mock.resets);
			error=n71_cleanup_action("cleanup",NULL);
		}
		assert(error==0 && !mock.refs && !session->module_retained && !session->scan_bridge);
		assert(mock.scans==1 && mock.held_scans==1 && mock.enumerations==1 && mock.puts==4);
		assert(n71_cleanup_action("cleanup",NULL)==0 && mock.puts==4);
		finish(&p); cases++;
	}
	/* Mutation killed: permit hold without PME or the existing N71/mode scope. */
	for (index=0;index<10;index++) {
		int expected=index>=8 ? -ENODEV : -EINVAL;
		p=setup_held();
		switch(index) {
		case 0: scan_pme_disable=false; break;
		case 1: host_scan=false; break;
		case 2: enumerate=false; break;
		case 3: config_inventory=false; break;
		case 4: bar_sizing=true; break;
		case 5: chip_id=true; break;
		case 6: dart_observe=true; break;
		case 7: dart_cycle=true; break;
		case 8: run=false; break;
		default: mock.machine=false; break;
		}
		assert(n71_init()==expected && !mock.registered && !mock.scans && !mock.refs && !mock.gets);
		finish(&p); cases++;
	}
	p=setup_held(); mock.attach_fail=0;
	assert(n71_probe(&p)==-ENODEV && !session && !mock.refs && !mock.scans);
	finish(&p); cases++;
	return cases;
}
static void expect_resources(const char *expected)
{
	char buffer[PAGE_SIZE];
	assert(resource_ops.get(buffer,NULL)>0 && !strcmp(buffer,expected));
	assert(!session_lock && !active_lock);
}

static unsigned int exercise_resource_caller(void)
{
	struct platform_device p;
	struct n71_diagnostic *state, saved_state;
	struct n71_scan_host saved_host;
	void *saved_bus;
	unsigned int index,cases=0;
	char expected[PAGE_SIZE];
	int error;

	/* Mutations killed: assign without opt-in/session, or take an unreleased temporary pin. */
	p=setup();
	expect_resources("ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=0\n");
	assert(n71_cleanup_action("assign",NULL)==-EINVAL && !mock.refs && !mock.assignments);
	scan_hold=true;
	assert(n71_cleanup_action("assign",NULL)==-ENODEV && !mock.refs && !mock.assignments);
	mock.live=false;
	assert(n71_cleanup_action("assign",NULL)==-ENODEV && !mock.refs && !mock.assignments);
	finish(&p); cases++;
	/* Mutations killed: remove any lifetime/power/error gate before the allocator's effects. */
	for (index=0;index<12;index++) {
		p=setup_held(); assert(n71_probe(&p)==0);
		state=session; saved_state=*state; saved_host=mock.bridge.private; saved_bus=mock.bridge.bus;
		error=-EBUSY;
		switch(index) {
		case 0: state->module_retained=false; break;
		case 1: state->reset_pending=false; break;
		case 2: state->powered=3; break;
		case 3: state->attached=3; break;
		case 4: state->power_put_pending=true; break;
		case 5: state->primary_error=-ETIMEDOUT; break;
		case 6: state->cleanup_error=-EIO; break;
		case 7: mock.bridge.private.bus_held=false; error=-ENODEV; break;
		case 8: mock.bridge.bus=NULL; error=-ENODEV; break;
		case 9: session=NULL; error=-ENODEV; break;
		case 10: scan_hold=false; error=-EINVAL; break;
		default: mock.live=false; error=-ENODEV; break;
		}
		assert(n71_cleanup_action("assign",NULL)==error && mock.refs==1 && !mock.assignments);
		assert(!mock.puts && !mock.resets && !mock.detaches && mock.scans==1 && !active_lock);
		*state=saved_state; session=state; mock.bridge.private=saved_host; mock.bridge.bus=saved_bus;
		scan_hold=mock.live=true;
		assert(n71_cleanup_action("cleanup",NULL)==0); finish(&p); cases++;
	}
	/* Mutations killed: dispatch to cleanup, lose EALREADY idempotency, omit mutex/pin or unpin twice. */
	p=setup_held(); assert(n71_probe(&p)==0);
	expect_resources("ready=1 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=0\n");
	assert(n71_cleanup_action("assignjunk",NULL)==-EINVAL && mock.refs==1 && !mock.assignments);
	assert(cleanup_ops.set("assign\n",NULL)==0 && mock.refs==1 && mock.assignments==1);
	assert(mock.bridge.bus && !mock.puts && !mock.resets && !mock.detaches && mock.scans==1);
	expect_resources("ready=1 attempted=1 assigned=1 pending=1 claimed=1 active=0 error=0\n");
	assert(n71_cleanup_action("assign",NULL)==-EALREADY && !session->primary_error && mock.assignments==1);
	assert(mock.refs==1 && mock.bridge.bus && !mock.puts && !mock.resets && mock.enumerations==1);
	cases++;
	/* Mutations killed: assigned from historical flags instead of live bus/window/phase/error ownership. */
	for (index=0;index<10;index++) {
		saved_state=*session; saved_host=mock.bridge.private; saved_bus=mock.bridge.bus; error=0;
		switch(index) {
		case 0: mock.bridge.bus=NULL; break;
		case 1: mock.bridge.private.bus_held=false; break;
		case 2: mock.bridge.private.resources_assigned=false; break;
		case 3: mock.bridge.private.window_claimed=false; break;
		case 4: mock.bridge.private.windows[1].parent=&foreign_resource; break;
		case 5: mock.bridge.private.resources.active=true; break;
		case 6: mock.bridge.private.config.error=error=-EACCES; break;
		case 7: mock.bridge.private.io_error=error=-ERANGE; break;
		case 8: mock.bridge.private.resources.error=error=-EIO; break;
		default: session->primary_error=error=-ENODEV; break;
		}
		snprintf(expected,sizeof(expected),"ready=1 attempted=1 assigned=0 pending=1 claimed=%u active=%u error=%d\n",
			 index==3 ? 0 : 1,index==5 ? 1 : 0,error);
		expect_resources(expected);
		*session=saved_state; mock.bridge.private=saved_host; mock.bridge.bus=saved_bus; cases++;
	}
	/* Mutation killed: a removed bus with pending rollback still reported assigned. */
	mock.fault=HOLD_PENDING;
	assert(n71_cleanup_action("cleanup",NULL)==-EIO && session->scan_bridge && mock.refs==1);
	mock.bridge.private.bus_held=true;
	expect_resources("ready=1 attempted=1 assigned=0 pending=1 claimed=1 active=0 error=0\n");
	assert(n71_cleanup_action("assign",NULL)==-ENODEV && mock.assignments==1 && mock.refs==1);
	mock.fault=NONE;
	assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && mock.puts==4 && mock.resets==1);
	expect_resources("ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=0\n");
	assert(n71_cleanup_action("assign",NULL)==-ENODEV && !mock.refs && mock.assignments==1);
	finish(&p); cases++;
	/* Mutations killed: lose assignment error, retry after failure or hide it when its bridge is freed. */
	p=setup_held(); assert(n71_probe(&p)==0); mock.assign_error=-EACCES;
	assert(n71_cleanup_action("assign",NULL)==-EACCES && session->primary_error==-EACCES && mock.refs==1);
	expect_resources("ready=1 attempted=1 assigned=0 pending=1 claimed=1 active=0 error=-13\n");
	assert(n71_cleanup_action("assign",NULL)==-EBUSY && mock.assignments==1);
	assert(n71_cleanup_action("cleanup",NULL)==-EACCES && !session->scan_bridge && mock.refs==1);
	expect_resources("ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=-13\n");
	assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && mock.scans==1 && mock.puts==4);
	assert(session->primary_error==-EACCES); finish(&p); cases++;
	/* Mutation killed: hide an early adapter refusal not copied into host config.error. */
	p=setup_held(); assert(n71_probe(&p)==0); mock.assign_early_error=-ENODEV;
	assert(n71_cleanup_action("assign",NULL)==-ENODEV && session->primary_error==-ENODEV && !mock.assignments);
	expect_resources("ready=1 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=-19\n");
	assert(n71_cleanup_action("assign",NULL)==-EBUSY && !mock.assignments && mock.refs==1);
	assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && session->primary_error==-ENODEV);
	expect_resources("ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=-19\n");
	finish(&p); cases++;
	return cases;
}

static unsigned int exercise_dart_caller(void)
{
	struct platform_device p;
	struct n71_diagnostic *state, saved_state;
	struct n71_scan_host saved_host;
	void *saved_bus;
	char status[PAGE_SIZE];
	unsigned int index, cases=0;
	int error;

	/* Mutations killed: dispatch or acquire without opt-in/session, or leak the action pin. */
	p=setup();
	assert(dart_ops.get(status,NULL)>0 && strstr(status,"ready=0 acquired=0 running=0 pending=0"));
	assert(cleanup_ops.set("dart-hold",NULL)==-EINVAL && !mock.refs && !mock.dart_live);
	scan_hold=true;
	assert(cleanup_ops.set("dart-hold",NULL)==-ENODEV && !mock.refs);
	assert(cleanup_ops.set("dart-release",NULL)==-ENODEV && !mock.refs);
	finish(&p); cases++;

	/* Mutations killed: begin before assign, poison EALREADY, release other owners, or ignore DART cleanup. */
	p=setup_held(); assert(n71_probe(&p)==0);
	assert(cleanup_ops.set("dart-hold",NULL)==-EACCES && !mock.dart_acquires && mock.refs==1);
	assert(cleanup_ops.set("assign",NULL)==0);
	assert(cleanup_ops.set("dart-holdjunk",NULL)==-EINVAL && !mock.dart_acquires);
	assert(cleanup_ops.set("dart-hold\n",NULL)==0 && mock.dart_acquires==1 && mock.refs==1);
	assert(session->dart==&mock.dart && mock.bridge.bus && !mock.puts && !mock.resets);
	assert(dart_ops.get(status,NULL)>0 && strstr(status,"acquired=1 running=1 pending=1") &&
	       strstr(status,"mapping_new=1") && strstr(status,"irq_domain=1 irq_fwnode=1"));
	assert(cleanup_ops.set("dart-hold",NULL)==-EALREADY && !session->primary_error && mock.dart_acquires==1);
	mock.dart_cleanup_error=-EBUSY;
	assert(cleanup_ops.set("dart-release",NULL)==-EBUSY && session->dart && mock.refs==1);
	assert(!mock.puts && !mock.resets && mock.bridge.bus && !mock.dart_releases);
	assert(dart_ops.get(status,NULL)>0 && strstr(status,"acquired=1 running=0 pending=1") && strstr(status,"restore_error=-16"));
	mock.dart_cleanup_error=0;
	assert(cleanup_ops.set("dart-release",NULL)==0 && !session->dart && mock.dart_releases==1);
	assert(mock.bridge.bus && session->powered==4 && session->attached==4 && mock.refs==1);
	assert(cleanup_ops.set("dart-release",NULL)==0 && mock.dart_releases==1 && mock.refs==1);
	assert(cleanup_ops.set("dart-hold",NULL)==0 && mock.dart_acquires==2 && mock.scans==1);
	mock.dart_cleanup_error=-ENOLINK;
	assert(cleanup_ops.set("cleanup",NULL)==-ENOLINK && session->dart && session->module_retained);
	assert(mock.refs==1 && mock.bridge.bus && !mock.puts && !mock.resets);
	mock.dart_cleanup_error=0;
	assert(cleanup_ops.set("cleanup",NULL)==0 && !session->dart && !mock.refs && mock.dart_releases==2);
	assert(mock.scans==1 && mock.puts==4 && mock.resets==1);
	assert(dart_ops.get(status,NULL)>0 && strstr(status,"acquired=0 running=0 pending=0"));
	finish(&p); cases++;

	/* Mutations killed: omit any retained/session/resource ownership gate before acquisition. */
	for (index=0;index<19;index++) {
		p=setup_held(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
		state=session; saved_state=*state; saved_host=mock.bridge.private; saved_bus=mock.bridge.bus;
		error=index<5 || index>=17 ? -ENODEV : index<9 ? -EBUSY : -EACCES;
		switch(index) {
		case 0: state->module_retained=false; break;
		case 1: state->reset_pending=false; break;
		case 2: state->powered=3; break;
		case 3: state->attached=3; break;
		case 4: state->power_put_pending=true; break;
		case 5: state->primary_error=-EIO; break;
		case 6: state->cleanup_error=-EIO; break;
		case 7: mock.bridge.private.bus_held=false; break;
		case 8: mock.bridge.bus=NULL; break;
		case 9: mock.bridge.private.resources_assigned=false; break;
		case 10: mock.bridge.private.window_claimed=false; break;
		case 11: mock.bridge.private.windows[1].parent=&foreign_resource; break;
		case 12: mock.bridge.private.resources.active=true; break;
		case 13: mock.bridge.private.resources.error=-EIO; break;
		case 14: mock.bridge.private.config.error=-EIO; break;
		case 15: mock.bridge.private.io_error=-EIO; break;
		case 16: scan_hold=false; error=-EINVAL; break;
		case 17: session=NULL; break;
		default: mock.live=false; break;
		}
		assert(cleanup_ops.set("dart-hold",NULL)==error && mock.refs==1 && !mock.dart_live && !mock.dart_acquires);
		assert(!mock.puts && !mock.resets && !mock.detaches && mock.scans==1 && !active_lock);
		*state=saved_state; session=state; mock.bridge.private=saved_host; mock.bridge.bus=saved_bus;
		scan_hold=mock.live=true;
		assert(cleanup_ops.set("cleanup",NULL)==0); finish(&p); cases++;
	}
	/* Mutation killed: discard a partial acquire error or abandon the pending provider. */
	p=setup_held(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
	mock.dart_acquire_error=-ENOLINK;
	assert(cleanup_ops.set("dart-hold",NULL)==-ENOLINK && session->primary_error==-ENOLINK);
	assert(session->dart && mock.dart_live && mock.refs==1 && !mock.puts && !mock.resets);
	assert(cleanup_ops.set("dart-release",NULL)==0 && !session->dart && session->primary_error==-ENOLINK);
	assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && session->primary_error==-ENOLINK);
	finish(&p); cases++;
	return cases;
}

static void expect_msi(const char *expected)
{
	char buffer[PAGE_SIZE];
	assert(msi_ops.get(buffer,NULL)>0 && !strcmp(buffer,expected));
	assert(!session_lock && !active_lock);
}

static unsigned int exercise_msi_caller(void)
{
	struct platform_device p;
	struct n71_wlan_msi_host saved;
	unsigned int index, cases=0;
	char expected[PAGE_SIZE];

	/* Mutations killed: enable MSI by default or report a session/owner that does not exist. */
	p=setup_held();
	expect_msi("requested=0 ready=0 held=0 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=0\n");
	assert(n71_probe(&p)==0 && !mock.msi_scans);
	expect_msi("requested=0 ready=1 held=1 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=0\n");
	assert(cleanup_ops.set("cleanup",NULL)==0); finish(&p); cases++;
	/* Mutation killed: accept the MSI flag without the held-bus lifetime contract. */
	p=setup(); msi_parent=true;
	assert(n71_init()==-EINVAL && !mock.registered && !mock.refs && !mock.gets && !mock.scans);
	finish(&p); cases++;
	/* Mutations killed: ignore MSI selection, confuse requested with ownership, or skip the getter lock. */
	p=setup_held(); msi_parent=true;
	expect_msi("requested=1 ready=0 held=0 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=0\n");
	assert(n71_init()==0 && mock.registered==1 && !mock.msi_scans);
	assert(n71_probe(&p)==0 && mock.msi_scans==1 && mock.scans==1 && mock.refs==1);
	expect_msi("requested=1 ready=1 held=1 associated=1 owner=1 domain=1 mappings=0 child=0 session_error=0\n");
	assert(n71_probe(&p)==-EBUSY && mock.msi_scans==1);
	cases++;
	/* Mutations killed: hard-code association, owner/domain, mapping count or child presence. */
	for (index=0;index<5;index++) {
		saved=mock.bridge.private.msi;
		switch(index) {
		case 0: mock.bridge.private.msi.associated=false; break;
		case 1: mock.bridge.private.msi.bridge=NULL; break;
		case 2: mock.bridge.private.msi.native.domain=NULL; break;
		case 3: mock.msi_domain.mapcount=4; break;
		default: mock.bridge.private.msi.native.child=&mock.msi_child; break;
		}
		snprintf(expected,sizeof(expected),
			"requested=1 ready=1 held=1 associated=%u owner=%u domain=%u mappings=%u child=%u session_error=0\n",
			index==0 ? 0U : 1U,index==1 ? 0U : 1U,index==2 ? 0U : 1U,
			index==3 ? 4U : 0U,index==4 ? 1U : 0U);
		expect_msi(expected);
		mock.bridge.private.msi=saved; mock.msi_domain.mapcount=0; cases++;
	}
	assert(cleanup_ops.set("cleanup",NULL)==0 && mock.msi_releases==1 && !mock.refs);
	expect_msi("requested=1 ready=1 held=0 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=0\n");
	assert(cleanup_ops.set("cleanup",NULL)==0 && mock.msi_releases==1 && mock.scans==1);
	n71_exit(); finish(&p);
	expect_msi("requested=1 ready=0 held=0 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=0\n");
	/* Mutations killed: release pin/reset/power before MSI quiesces, abandon partial acquire, or rescan on retry. */
	for (index=0;index<4;index++) {
		unsigned int scans, removals;
		int error=index<2 ? -EBUSY : -EIO;
		p=setup_held(); msi_parent=true;
		if (index==3) { mock.msi_acquire_error=-ENOLINK; mock.msi_cleanup_error=-EIO; }
		assert(n71_probe(&p)==0 && session->module_retained && mock.refs==1);
		if (index==0) mock.bridge.private.msi.native.child=&mock.msi_child;
		if (index==1) mock.msi_domain.mapcount=1;
		if (index==2) mock.msi_cleanup_error=-EIO;
		scans=mock.scans;
		assert(cleanup_ops.set("cleanup",NULL)==error && session->scan_bridge && mock.refs==1);
		assert(!mock.bridge.bus && mock.bridge.alive && session->reset_pending);
		assert(session->powered==4 && session->attached==4 && !mock.puts && !mock.resets && !mock.detaches);
		assert(session->primary_error==(index==3 ? -ENOLINK : 0));
		snprintf(expected,sizeof(expected),
			"requested=1 ready=1 held=0 associated=0 owner=1 domain=1 mappings=%u child=%u session_error=%d\n",
			index==1 ? 1U : 0U,index==0 ? 1U : 0U,error);
		expect_msi(expected);
		removals=mock.bus_removals;
		assert(cleanup_ops.set("cleanup",NULL)==error && mock.bus_removals==removals);
		assert(cleanup_ops.set("assign",NULL)==-ENODEV && !mock.assignments && mock.refs==1);
		assert(mock.scans==scans && mock.msi_scans==1 && !mock.msi_releases && !mock.puts && !mock.resets);
		mock.bridge.private.msi.native.child=NULL; mock.msi_domain.mapcount=0; mock.msi_cleanup_error=0;
		assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && mock.msi_releases==1);
		assert(mock.scans==scans && mock.msi_scans==1 && mock.bus_removals==removals);
		assert(mock.puts==4 && mock.resets==1 && !session->scan_bridge);
		expect_msi("requested=1 ready=1 held=0 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=0\n");
		finish(&p); cases++;
	}
	/* Mutation killed: hide the session cleanup error after MSI ownership has already been released. */
	p=setup_held(); msi_parent=true;
	assert(n71_probe(&p)==0); mock.fault=RESET_READ;
	assert(cleanup_ops.set("cleanup",NULL)==-EIO && !session->scan_bridge && mock.refs==1);
	expect_msi("requested=1 ready=1 held=0 associated=0 owner=0 domain=0 mappings=0 child=0 session_error=-5\n");
	mock.fault=NONE;
	assert(cleanup_ops.set("cleanup",NULL)==0 && mock.msi_releases==1 && mock.scans==1);
	finish(&p); cases++;
	return cases;
}

static struct platform_device setup_iommu(void)
{
	struct platform_device p=setup_held();
	msi_parent=iommu_parent=mock.prescan_dart=true;
	return p;
}

static void expect_iommu(const char *expected)
{
	char buffer[PAGE_SIZE];
	assert(iommu_ops.get(buffer,NULL)>0 && !strcmp(buffer,expected));
	assert(!session_lock && !active_lock);
}

static unsigned int exercise_iommu_caller(void)
{
	struct platform_device p;
	struct n71_scan_host saved;
	void *bus;
	unsigned int index, cases=0;
	char expected[PAGE_SIZE];

	/* Mutations killed: enable IOMMU by default or publish an owner before probe. */
	p=setup_held();
	expect_iommu("requested=0 ready=0 held=0 owner=0 available=0 mapped=0 observed=0 map_checked=0 session_error=0\n");
	assert(n71_probe(&p)==0 && !mock.dart_acquires && !mock.iommu_scans);
	expect_iommu("requested=0 ready=1 held=1 owner=0 available=0 mapped=0 observed=0 map_checked=0 session_error=0\n");
	assert(cleanup_ops.set("cleanup",NULL)==0); finish(&p); cases++;
	/* Mutations killed: admit IOMMU without the existing MSI/held/PME/inventory contract. */
	for (index=0;index<6;index++) {
		p=setup_iommu();
		switch(index) {
		case 0: msi_parent=false; break;
		case 1: scan_hold=false; break;
		case 2: host_scan=false; break;
		case 3: scan_pme_disable=false; break;
		case 4: config_inventory=false; break;
		default: enumerate=false; break;
		}
		assert(n71_init()==-EINVAL && !mock.registered && !mock.refs && !mock.gets && !mock.dart_acquires);
		finish(&p); cases++;
	}
	/* Mutations killed: omit acquisition/selection, stop an associated provider alone, or rescan. */
	p=setup_iommu();
	expect_iommu("requested=1 ready=0 held=0 owner=0 available=0 mapped=0 observed=0 map_checked=0 session_error=0\n");
	assert(n71_init()==0 && !mock.dart_acquires);
	assert(n71_probe(&p)==0 && mock.dart_acquires==1 && mock.iommu_scans==1 && mock.refs==1);
	expect_iommu("requested=1 ready=1 held=1 owner=1 available=1 mapped=1 observed=2 map_checked=1 session_error=0\n");
	assert(cleanup_ops.set("dart-release",NULL)==-EBUSY && mock.dart.lease.running && !mock.dart_releases);
	assert(mock.bridge.bus && mock.bridge.private.dart.mapped && !mock.consumer_calls && mock.refs==1);
	assert(n71_probe(&p)==-EBUSY && mock.iommu_scans==1); cases++;
	/* Mutations killed: getter ignores ownership, partial observations, errors, or live bus loss. */
	for (index=0;index<9;index++) {
		saved=mock.bridge.private; bus=mock.bridge.bus;
		switch(index) {
		case 0: mock.bridge.private.dart.bridge=NULL; break;
		case 1: mock.bridge.private.dart.available=false; break;
		case 2: mock.bridge.private.dart.mapped=false; break;
		case 3: mock.bridge.private.iommu_domain=NULL; break;
		case 4: mock.bridge.private.iommu_devices=1; break;
		case 5: mock.bridge.private.config.error=-EIO; break;
		case 6: mock.bridge.private.io_error=-EIO; break;
		case 7: session->cleanup_error=-EAGAIN; break;
		default: mock.bridge.bus=NULL; break;
		}
		snprintf(expected,sizeof(expected),
			"requested=1 ready=1 held=%u owner=%u available=%u mapped=%u observed=%u map_checked=%u session_error=%d\n",
			index==8 ? 0U : 1U,index==0 ? 0U : 1U,index==1 ? 0U : 1U,index==2 ? 0U : 1U,
			index==4 ? 1U : 2U,index==7 ? 1U : 0U,index==7 ? -EAGAIN : 0);
		expect_iommu(expected);
		mock.bridge.private=saved; mock.bridge.bus=bus; session->cleanup_error=0; cases++;
	}
	assert(cleanup_ops.set("cleanup",NULL)==0 && mock.bus_removals==1 && mock.unmaps==1);
	assert(mock.dart_releases==1 && mock.host_releases==1 && mock.puts==4 && !mock.refs);
	expect_iommu("requested=1 ready=1 held=0 owner=0 available=0 mapped=0 observed=0 map_checked=0 session_error=0\n");
	assert(cleanup_ops.set("cleanup",NULL)==0 && mock.dart_releases==1 && mock.scans==1);
	n71_exit(); finish(&p);
	/* Mutations killed: scan with an absent, stopped or device-less successful provider. */
	for (index=0;index<4;index++) {
		p=setup_iommu();
		if (index==0) mock.dart_no_owner=true;
		if (index==1) mock.dart_not_running=true;
		if (index==2) mock.dart_no_device=true;
		if (index==3) mock.dart_acquire_error=-ENOLINK;
		assert(n71_probe(&p)==(index==3 ? -ENOLINK : -ENODEV));
		assert(!session && !mock.iommu_scans && !mock.scans && !mock.refs);
		assert(mock.dart_acquires==1 && mock.dart_releases==(index==0 ? 0U : 1U));
		finish(&p); cases++;
	}
	/* Mutations killed: advance after teardown failure, reset/power early, or lose retry ownership. */
	for (index=0;index<7;index++) {
		unsigned int removals, releases;
		p=setup_iommu(); assert(n71_probe(&p)==0);
		if (index==0) mock.consumer_error=-EIO;
		if (index==1) mock.msi_cleanup_error=-EIO;
		if (index==2) mock.unmap_error=-EIO;
		if (index==3) mock.dart_cleanup_error=-EIO;
		if (index==4) mock.host_release_error=-EIO;
		if (index==5) mock.fault=RESET_READ;
		if (index==6) { mock.fault=PUT_ERROR; mock.put_fail=3; }
		assert(cleanup_ops.set("cleanup",NULL)==(index==6 ? -ETIMEDOUT : -EIO) && mock.refs==1);
		assert(session->module_retained && session->primary_error==0 && mock.iommu_scans==1);
		if (index<4) assert(session->dart && !mock.dart_releases);
		if (index<5) assert(session->scan_bridge && !mock.resets && !mock.puts);
		if (index<3) assert(mock.dart.lease.running && mock.bridge.private.dart.mapped);
		snprintf(expected,sizeof(expected),
			"requested=1 ready=1 held=%u owner=%u available=%u mapped=%u observed=%u map_checked=%u session_error=%d\n",
			index==0 ? 1U : 0U,index<5 ? 1U : 0U,index<5 ? 1U : 0U,index<3 ? 1U : 0U,
			index==0 ? 2U : 0U,index==0 ? 1U : 0U,index==6 ? -ETIMEDOUT : -EIO);
		expect_iommu(expected);
		removals=mock.bus_removals; releases=mock.dart_releases;
		assert(cleanup_ops.set("cleanup",NULL)<0 && mock.refs==1 && mock.bus_removals==removals && mock.dart_releases==releases);
		mock.consumer_error=mock.msi_cleanup_error=mock.unmap_error=mock.dart_cleanup_error=mock.host_release_error=0;
		mock.fault=NONE;
		assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && !session->dart && !session->scan_bridge);
		assert(mock.dart_acquires==1 && mock.dart_releases==1 && mock.host_releases==1);
		assert(mock.iommu_scans==1 && mock.scans==1 && mock.bus_removals==1 && mock.unmaps==1 && mock.puts==4);
		finish(&p); cases++;
	}
	/* Mutation killed: drop the primary scan error while retaining its partial association. */
	p=setup_iommu(); mock.iommu_scan_error=-ENODEV; mock.unmap_error=-EIO;
	assert(n71_probe(&p)==0 && session->primary_error==-ENODEV && session->cleanup_error==-EIO);
	assert(session->dart && session->scan_bridge && mock.refs==1 && !mock.dart_releases && !mock.puts);
	mock.unmap_error=0;
	assert(cleanup_ops.set("cleanup",NULL)==0 && session->primary_error==-ENODEV && !mock.refs);
	finish(&p); cases++;
	return cases;
}

#include "n71_pcie_diagnostic_allocation.h"
#include "n71_pcie_diagnostic_runtime.h"

int main(void)
{
	struct platform_device p; char status[PAGE_SIZE]; unsigned int index, cases=0;
	/* Mutation: static runtime flag enables activation by default. */
	assert(!driver_runtime);
#ifdef __linux__
	/* RLIMIT_CORE does not suppress piped crash handlers; isolate each mutant. */
	assert(prctl(PR_SET_DUMPABLE, 0UL, 0UL, 0UL, 0UL)==0);
#endif
	p=setup(); assert(n71_cleanup_action("cleanup",NULL)==-ENODEV && !mock.refs); cases++;
	assert(n71_cleanup_action("scan",NULL)==-EINVAL); cases++;
	mock.live=false; assert(n71_cleanup_action("cleanup",NULL)==-ENODEV); mock.live=true; cases++;
	assert(n71_session_status(status,NULL)>0 && !strcmp(status,"ready=0 retained=0\n")); cases++;
	assert(n71_init()==0 && mock.registered==1); n71_exit(); finish(&p); cases++;
	for (index=VALIDATE;index<=SCAN_ERROR;index++) {
		int expected=-EIO;
		p=setup(); mock.fault=index;
		if (index==VALIDATE) { p.resources[0].start++; p.resources[0].end++; expected=-EINVAL; }
		if (index==TABLE) expected=-EINVAL;
		if (index==MAP) expected=-ENODEV;
		if (index==ALLOC) expected=-ENOMEM;
		if (index==ROOT) { mock.ecam[0x8000/4]=0; expected=-ENODEV; }
		if (index==ENUMERATE) expected=-ENOLINK;
		if (index==SCAN_ERROR) expected=-EPERM;
		assert(n71_probe(&p)==expected && !session && !mock.refs); finish(&p); cases++;
	}
	p=setup(); assert(n71_probe(&p)==0 && session && !session->module_retained && !mock.refs); cases++;
	assert(n71_cleanup_action("cleanup\n",NULL)==0 && mock.scans==1 && mock.enumerations==1); cases++;
	assert(n71_probe(&p)==-EBUSY); cases++;
	assert(n71_session_status(status,NULL)>0 && strstr(status,"retained=0") && strstr(status,"cleanup_error=0")); finish(&p); cases++;
	for (index=SCAN_PENDING;index<=PUT_ACTIVE;index++) {
		unsigned int puts, scans;
		p=setup(); mock.fault=index; mock.put_fail=3;
		assert(n71_probe(&p)==0 && session && session->module_retained && mock.refs==1); cases++;
		assert(session->cleanup_error==(index==PUT_ERROR ? -ETIMEDOUT : index==PUT_ACTIVE ? -EBUSY : -EIO));
		puts=mock.puts; scans=mock.scans;
		if (index<=RESET_VALUE) assert(!puts && !mock.detaches && session->powered==4);
		assert(n71_cleanup_action("cleanup",NULL)<0 && mock.refs==1 && mock.puts==puts && mock.scans==scans); cases++;
		assert(n71_session_status(status,NULL)>0 && strstr(status,"retained=1")); cases++;
		if (index==SCAN_PENDING) assert(session->primary_error==-EPERM && session->cleanup_error==-EIO);
		mock.fault=NONE;
		assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && mock.scans==scans);
		assert(!session->module_retained && !session->scan_bridge && !session->reset_pending && !session->power_put_pending); cases++;
		assert(n71_cleanup_action("cleanup",NULL)==0 && mock.scans==scans); finish(&p); cases++;
	}
	for (index=0;index<4;index++) {
		p=setup(); mock.attach_fail=index; assert(n71_probe(&p)==-ENODEV); finish(&p); cases++;
		p=setup(); mock.resume_fail=index; assert(n71_probe(&p)==-EIO); finish(&p); cases++;
		p=setup(); mock.put_fail=index; mock.fault=PUT_ERROR; assert(n71_probe(&p)==0 && session->module_retained);
		assert(mock.puts==4-index); mock.fault=NONE; assert(n71_cleanup_action("cleanup",NULL)==0 && mock.puts==4); finish(&p); cases++;
	}
	/* A negative put may already have suspended hardware; preserve its error and usage accounting. */
	p=setup(); mock.fault=PUT_ERROR_OFF; mock.put_fail=3;
	assert(n71_probe(&p)==0 && session->module_retained && session->cleanup_error==-ETIMEDOUT && mock.puts==1);
	assert(n71_cleanup_action("cleanup",NULL)==0 && mock.puts==4 && !mock.refs); finish(&p); cases++;
	p=setup(); run=false; assert(n71_init()==-ENODEV); finish(&p); cases++;
	p=setup(); enumerate=false; assert(n71_init()==-EINVAL); finish(&p); cases++;
	p=setup(); config_inventory=false; assert(n71_init()==-EINVAL); finish(&p); cases++;
	p=setup(); chip_id=true; assert(n71_init()==-EINVAL); finish(&p); cases++;
	/* PME is an explicit caller mode; registration alone never scans hardware. */
	p=setup(); scan_pme_disable=true;
	assert(n71_init()==0 && mock.registered==1 && !mock.scans);
	assert(n71_probe(&p)==0 && mock.pme_scans==1 && mock.enumerations==1);
	assert(n71_cleanup_action("cleanup",NULL)==0 && mock.pme_scans==1);
	n71_exit(); finish(&p); cases++;
	p=setup(); scan_pme_disable=true; host_scan=false;
	assert(n71_init()==-EINVAL && !mock.registered && !mock.scans); finish(&p); cases++;
	p=setup(); scan_pme_disable=true; enumerate=false;
	assert(n71_init()==-EINVAL && !mock.registered && !mock.scans); finish(&p); cases++;
	p=setup(); scan_pme_disable=true; config_inventory=false;
	assert(n71_init()==-EINVAL && !mock.registered && !mock.scans); finish(&p); cases++;
	p=setup(); scan_pme_disable=true; bar_sizing=true;
	assert(n71_init()==-EINVAL && !mock.registered && !mock.scans); finish(&p); cases++;
	p=setup(); scan_pme_disable=true; mock.fault=SCAN_PENDING;
	assert(n71_probe(&p)==0 && session->module_retained && mock.refs==1 && mock.bridge.alive);
	assert(session->primary_error==-EPERM && session->cleanup_error==-EIO && !mock.puts);
	assert(n71_cleanup_action("cleanup",NULL)==-EIO && mock.refs==1 && mock.pme_scans==1);
	assert(mock.enumerations==1 && !mock.resets && !mock.puts);
	mock.fault=NONE;
	assert(n71_cleanup_action("cleanup",NULL)==0 && !mock.refs && mock.pme_scans==1);
	assert(mock.enumerations==1 && mock.resets==1 && mock.puts==4); finish(&p); cases++;
	printf("N71_PCIE_CALLER_OK cases=%u\n",cases);
	assert(exercise_held_caller()==21);
	puts("N71_PCIE_HELD_CALLER_OK cases=21");
	assert(exercise_resource_caller()==27);
	puts("N71_PCIE_RESOURCE_CALLER_OK cases=27");
	assert(exercise_dart_caller()==22);
	puts("N71_DART_CALLER_OK cases=22");
	assert(exercise_msi_caller()==13);
	puts("N71_MSI_CALLER_OK cases=13");
	assert(exercise_iommu_caller()==29);
	puts("N71_IOMMU_CALLER_OK cases=29");
	printf("N71_MSI_ALLOCATION_CALLER_OK cases=%u\n",exercise_allocation_caller());
	printf("N71_DRIVER_CALLER_OK cases=%u\n",exercise_runtime_caller());
	return 0;
}
