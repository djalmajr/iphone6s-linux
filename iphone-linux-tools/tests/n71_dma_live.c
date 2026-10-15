/* SPDX-License-Identifier: GPL-2.0-only */
/* Real backend/helper; bound-driver/domain/MMIO APIs are fixtures. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "n71-dma-observe.h"
struct device_driver { const char *name; };
struct device { struct device_driver *driver; };
struct pci_driver { struct device_driver driver; bool driver_managed_dma; };
struct pci_bus { unsigned int number; };
struct pci_dev { struct device dev; struct pci_driver *driver; struct pci_bus *bus; unsigned int vendor,device,class,devfn; };
#define IOMMU_DOMAIN_DMA 3
struct iommu_domain { unsigned int type; struct { u64 aperture_start,aperture_end; } geometry; };
struct n71_diagnostic;
struct platform_device { int unused; };
struct n71_dart_host { bool available,mapped; struct platform_device *provider; };
struct n71_scan_host { struct { bool active; } brcmfmac; bool driver_published,driver_pm; struct pci_dev *driver_endpoint; struct n71_dart_host dart; struct iommu_domain *iommu_domain; };
struct pci_host_bridge { bool alive; struct n71_scan_host host; };
struct n71_dart_provider { struct { bool running; } lease; struct platform_device *device; struct { void *regs; struct n71_diagnostic *state; } mmio; };
struct n71_diagnostic { struct pci_host_bridge *scan_bridge; unsigned int attached,powered; bool power_put_pending,reset_pending,module_retained; struct n71_dart_provider *dart; };
static bool session_locked,endpoint_locked,refs_valid;
static unsigned int locks,unlocks,domain_queries,translations,clocks,reads,fail_after;
static u64 clock_value,physical;
static struct pci_driver driver;
static struct device_driver foreign_driver;
static struct pci_bus bus;
static struct pci_dev endpoint;
static struct iommu_domain domain,other_domain;
static struct iommu_domain *current_domain;
static struct platform_device provider_device;
static struct n71_dart_provider provider;
static struct pci_host_bridge bridge;
static struct n71_diagnostic state;
static unsigned char mmio[0x4000];
static bool n71_session_has_held_bus(struct n71_diagnostic *value)
{ assert(session_locked); return value && value->scan_bridge && value->scan_bridge->alive; }
static void *pci_host_bridge_priv(struct pci_host_bridge *value)
{ assert(session_locked && value==&bridge); return &value->host; }
static void device_lock(struct device *value)
{ assert(session_locked && !endpoint_locked && value==&endpoint.dev); endpoint_locked=true; locks++; }
static void device_unlock(struct device *value)
{ assert(session_locked && endpoint_locked && value==&endpoint.dev); endpoint_locked=false; unlocks++; }
static struct iommu_domain *iommu_get_domain_for_dev(struct device *value)
{
	assert(session_locked && endpoint_locked && value==&endpoint.dev && value->driver==&driver.driver);
	assert(endpoint.driver==&driver && !driver.driver_managed_dma); domain_queries++; return current_domain;
}
static bool n71_dart_host_refs_valid(struct n71_dart_host *value)
{ assert(session_locked && endpoint_locked && value==&bridge.host.dart); return refs_valid; }
static u64 ktime_get_boottime_ns(void)
{ assert(session_locked && endpoint_locked); clocks++; return clock_value++; }
static u64 iommu_iova_to_phys(struct iommu_domain *value, u64 iova)
{
	assert(session_locked && endpoint_locked && value==&domain && value==current_domain && iova==0x3ffff028);
	translations++; return physical;
}
static u32 readl(void *address)
{
	assert(session_locked && endpoint_locked && provider.mmio.regs==mmio);
	unsigned int index=reads%8; assert(address==mmio+n71_dma_offset(index)); reads++;
	if (fail_after && reads==fail_after) provider.lease.running=false;
	return index ? 0x1000U+index : 0;
}
#include "n71-pcie-dma-live.h"

static void reset(void)
{
	assert(!endpoint_locked);
	session_locked=refs_valid=true; locks=unlocks=domain_queries=translations=clocks=reads=fail_after=0;
	clock_value=100; physical=0x8a1234028ULL;
	driver=(struct pci_driver){.driver={.name="brcmfmac"}};
	foreign_driver=(struct device_driver){.name="other"}; bus=(struct pci_bus){.number=1};
	endpoint=(struct pci_dev){.dev={.driver=&driver.driver},.driver=&driver,.bus=&bus,.vendor=0x14e4,.device=0x43a3,.class=0x028000};
	domain=(struct iommu_domain){.type=IOMMU_DOMAIN_DMA,.geometry={0,0xffffffffULL}};
	other_domain=domain; current_domain=&domain;
	provider=(struct n71_dart_provider){.lease={.running=true},.device=&provider_device,.mmio={.regs=mmio,.state=&state}};
	bridge=(struct pci_host_bridge){.alive=true,.host={.brcmfmac={.active=true},.driver_published=true,.driver_pm=true,.driver_endpoint=&endpoint,.dart={.available=true,.mapped=true,.provider=&provider_device},.iommu_domain=&domain}};
	state=(struct n71_diagnostic){.scan_bridge=&bridge,.attached=4,.powered=4,.reset_pending=true,.module_retained=true,.dart=&provider};
}
static int capture(struct n71_dma_observation *out)
{
	int error=n71_dma_capture_locked(&state,true,0x3ffff028,out);
	assert(!endpoint_locked && locks==unlocks && out->error==error && out->iova==0x3ffff028);
	return error;
}
int main(void)
{
	struct n71_dma_observation result;
	unsigned int cases=0;
	reset(); assert(capture(&result)==0 && result.stable && result.complete==2);
	assert(locks==1 && domain_queries==1 && clocks==2 && translations==2 && reads==16);
	assert(result.samples[0].time_ns==100 && result.samples[1].time_ns==101);
	assert(result.samples[0].physical==physical && result.samples[1].valid==N71_DMA_VALID_MASK);
	assert(result.samples[1].words[7]==0x1007); cases++;
	reset(); assert(n71_dma_capture_locked(&state,true,0x3ffff028,NULL)==-EINVAL && !locks && !domain_queries); cases++;
	reset(); assert(n71_dma_capture_locked(NULL,true,0x3ffff028,&result)==-EACCES && !locks && !reads); cases++;
	reset(); assert(n71_dma_capture_locked(&state,false,0x3ffff028,&result)==-EACCES && !locks && !reads); cases++;
	for (unsigned int i=0;i<34;i++) {
		reset();
		switch (i) {
		case 0: state.scan_bridge=NULL; break;
		case 1: bridge.alive=false; break;
		case 2: bridge.host.driver_endpoint=NULL; break;
		case 3: endpoint.driver=NULL; break;
		case 4: endpoint.dev.driver=NULL; break;
		case 5: endpoint.dev.driver=&foreign_driver; break;
		case 6: driver.driver.name="foreign"; break;
		case 7: driver.driver_managed_dma=true; break;
		case 8: endpoint.vendor^=1; break;
		case 9: endpoint.device^=1; break;
		case 10: endpoint.class^=1; break;
		case 11: endpoint.bus=NULL; break;
		case 12: bus.number=0; break;
		case 13: endpoint.devfn=1; break;
		case 14: current_domain=NULL; break;
		case 15: current_domain=&other_domain; break;
		case 16: domain.type=1; break;
		case 17: state.attached=3; break;
		case 18: state.powered=3; break;
		case 19: state.power_put_pending=true; break;
		case 20: state.reset_pending=false; break;
		case 21: state.module_retained=false; break;
		case 22: state.dart=NULL; break;
		case 23: provider.lease.running=false; break;
		case 24: provider.device=NULL; break;
		case 25: provider.mmio.regs=NULL; break;
		case 26: provider.mmio.state=NULL; break;
		case 27: bridge.host.brcmfmac.active=false; break;
		case 28: bridge.host.driver_published=false; break;
		case 29: bridge.host.driver_pm=false; break;
		case 30: bridge.host.dart.available=false; break;
		case 31: bridge.host.dart.mapped=false; break;
		case 32: bridge.host.dart.provider=NULL; break;
		case 33: refs_valid=false; break;
		}
		assert(capture(&result)<0 && !reads && !translations && !clocks);
		assert(!result.complete && !result.stable && !result.samples[0].valid); cases++;
	}
	reset(); domain.geometry.aperture_start=0x40000000;
	assert(capture(&result)==-EINVAL && !reads && !translations); cases++;
	reset(); domain.geometry.aperture_end=0x100000000ULL;
	assert(capture(&result)==-EINVAL && !reads && !translations); cases++;
	reset(); domain.geometry.aperture_end=0x3ffff027;
	assert(capture(&result)==-EINVAL && !reads && !translations); cases++;
	for (unsigned int i=1;i<=16;i++) {
		reset(); fail_after=i;
		assert(capture(&result)==-EACCES && !result.stable && reads==i);
		assert(result.samples[0].valid & N71_DMA_TIME_VALID);
		assert(result.samples[0].valid & N71_DMA_TRANSLATION_VALID); cases++;
	}
	reset(); physical=0;
	assert(capture(&result)==0 && result.stable && !result.samples[0].physical && reads==16); cases++;
	printf("N71_DMA_LIVE_OK cases=%u\n",cases);
	return 0;
}
