/* SPDX-License-Identifier: GPL-2.0-only */
/* Real backend with bounded kernel API fixtures; PMGR qualification has its own real-source gate. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define N71_PMGR_ACCESS_H
#define IORESOURCE_MEM 0x200U
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR_OR_NULL(p) (!(p) || IS_ERR(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
enum { RPM_SUSPENDED, RPM_ACTIVE, RPM_RESUMING };
struct device_node { int index, refs; };
struct power { int lock, usage_count, child_count, runtime_status, runtime_error, request_pending, disable_depth; };
struct device { struct device_node *of_node; void *bus, *driver, *pm_domain; int refs; bool registered; struct power power; };
struct platform_device { struct device dev; };
struct i2c_adapter { struct device dev; };
struct of_phandle_args { struct device_node *np; int args_count; };
struct resource { u64 start, end; unsigned int flags; };
struct regmap { unsigned int index; };
struct n71_pmgr_reference { unsigned int index; struct device_node *node, *pmgr; };
struct n71_pmgr_access { struct platform_device *provider; struct regmap *map; };
static const struct { unsigned int offset; } n71_domains[] = {{0x801a0}, {0x80158}, {0x80150}};
enum { ROOT_NODE, CONSUMER_NODE, LEAF_NODE, PARENT_NODE, BUS_NODE, OTHER_NODE, NODE_COUNT };
enum fault { NONE, WRONG_PATH, AVAILABLE, CHILDREN, STATUS_ERROR, STATUS_WRONG, COMPAT, FALLBACK,
             CONTROLLER, ADAPTER, RESOURCE_ERROR, RESOURCE_BASE, RESOURCE_SIZE, RESOURCE_TYPE,
             DOMAIN_COUNT, DOMAIN_PARSE, DOMAIN_WRONG, DOMAIN_ARGS, ATTACH_NULL, ATTACH_ERROR };
static enum fault fault;
static struct device_node nodes[NODE_COUNT];
static struct device consumer, virtual_device;
static struct platform_device providers[3], controller;
static struct i2c_adapter adapter;
static struct regmap maps[3];
static bool held[3], detach_fail, detach_registered, suspend_keeps_power;
static int lock_fail, resume_error, suspend_error, read_fail;
static unsigned int reads, attaches, put_calls, suspends, detaches, noidles;
static u32 samples[3][2];
static int atomic_read(const int *value) { return *value; }
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock)=1; (flags)=0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { assert(*(lock)); *(lock)=0; (void)(flags); } while (0)
static struct device_node *node_get(unsigned int index) { nodes[index].refs++; return &nodes[index]; }
static void of_node_put(struct device_node *node) { if (node) { assert(node->refs>0); node->refs--; } }
static struct device_node *of_find_node_by_path(const char *path)
{ assert(!strcmp(path,"/soc/i2c@20a111000")); return node_get(fault==WRONG_PATH ? OTHER_NODE : CONSUMER_NODE); }
static bool of_device_is_available(struct device_node *node) { assert(node==&nodes[CONSUMER_NODE]); return fault==AVAILABLE; }
static int of_get_child_count(struct device_node *node) { assert(node==&nodes[CONSUMER_NODE]); return fault==CHILDREN; }
static int of_property_read_string(struct device_node *node, const char *name, const char **value)
{ assert(node==&nodes[CONSUMER_NODE] && !strcmp(name,"status")); *value=fault==STATUS_WRONG ? "okay" : "disabled"; return fault==STATUS_ERROR ? -EIO : 0; }
static bool of_device_is_compatible(struct device_node *node, const char *value)
{ assert(node==&nodes[CONSUMER_NODE]); if (!strcmp(value,"apple,s8000-i2c")) return fault!=COMPAT; assert(!strcmp(value,"apple,i2c")); return fault!=FALLBACK; }
static struct device *get_device(struct device *device) __attribute__((unused));
static struct device *get_device(struct device *device) { assert(device && device->refs>0); device->refs++; return device; }
static void put_device(struct device *device) { assert(device && device->refs>0); device->refs--; }
static bool device_is_registered(struct device *device) { assert(device->refs>0); return device->registered; }
static struct platform_device *of_find_device_by_node(struct device_node *node)
{ assert(node==&nodes[CONSUMER_NODE]); if (fault!=CONTROLLER) return NULL; controller.dev.refs++; return &controller; }
static struct i2c_adapter *of_find_i2c_adapter_by_node(struct device_node *node)
{ assert(node==&nodes[CONSUMER_NODE]); if (fault!=ADAPTER) return NULL; adapter.dev.refs++; return &adapter; }
static int of_address_to_resource(struct device_node *node, int index, struct resource *resource)
{
	assert(node==&nodes[CONSUMER_NODE] && !index);
	resource->start=fault==RESOURCE_BASE ? 0x20a110000ULL : 0x20a111000ULL;
	resource->end=resource->start+(fault==RESOURCE_SIZE ? 0x2000 : 0x1000)-1;
	resource->flags=fault==RESOURCE_TYPE ? 0 : IORESOURCE_MEM;
	return fault==RESOURCE_ERROR ? -EIO : 0;
}
static u64 resource_size(struct resource *resource) { return resource->end-resource->start+1; }
static unsigned int resource_type(struct resource *resource) { return resource->flags; }
static int of_count_phandle_with_args(struct device_node *node, const char *name, const char *cells)
{ assert(node==&nodes[CONSUMER_NODE] && !strcmp(name,"power-domains") && !strcmp(cells,"#power-domain-cells")); return fault==DOMAIN_COUNT ? 2 : 1; }
static int of_parse_phandle_with_args(struct device_node *node, const char *name, const char *cells, int index, struct of_phandle_args *domain)
{
	assert(!index); (void)of_count_phandle_with_args(node,name,cells);
	if (fault==DOMAIN_PARSE) return -EIO;
	domain->np=node_get(fault==DOMAIN_WRONG ? OTHER_NODE : LEAF_NODE);
	domain->args_count=fault==DOMAIN_ARGS;
	return 0;
}
static int n71_pmgr_access_lock(const struct n71_pmgr_reference *reference, struct n71_pmgr_access *access)
{
	unsigned int index=reference->index;
	if (index>=3 || reference->node!=&nodes[LEAF_NODE+index] || reference->pmgr!=&nodes[ROOT_NODE]) return -ENODEV;
	if ((int)index==lock_fail) return -ENODEV;
	assert(!held[index] && !access->map && !access->provider);
	held[index]=true; access->provider=&providers[index]; access->map=&maps[index];
	return 0;
}
static void n71_pmgr_access_unlock(struct n71_pmgr_access *access)
{ if (access->provider) { unsigned int index=access->map->index; assert(held[index]); held[index]=false; access->map=NULL; access->provider=NULL; } }
static void locked(void) { for (unsigned int index=0;index<3;index++) assert(held[index]); }
static int regmap_read_bypassed(struct regmap *map, unsigned int offset, unsigned int *word)
{
	unsigned int index=map->index, sample=reads%2; locked(); assert(offset==n71_domains[index].offset);
	reads++; if ((int)reads==read_fail) return -EIO; *word=samples[index][sample]; return 0;
}
static struct device *dev_pm_domain_attach_by_id(struct device *device, unsigned int index)
{
	locked(); assert(device==&consumer && !index); attaches++;
	if (fault==ATTACH_ERROR) return ERR_PTR(-EIO);
	if (fault==ATTACH_NULL) return NULL;
	assert(!virtual_device.refs); virtual_device.refs=1; virtual_device.registered=true;
	virtual_device.of_node=device->of_node; virtual_device.pm_domain=&providers[0];
	return &virtual_device;
}
static int pm_runtime_resume_and_get(struct device *device)
{
	locked(); assert(device==&virtual_device && !device->power.usage_count);
	if (resume_error) return resume_error;
	device->power.usage_count++; device->power.runtime_status=RPM_ACTIVE;
	for (unsigned int index=0;index<3;index++) samples[index][0]=samples[index][1]=0x100000ff;
	return 0;
}
static int pm_runtime_put_sync_suspend(struct device *device)
{
	locked(); assert(device==&virtual_device && device->power.usage_count==1); put_calls++;
	device->power.usage_count--;
	if (suspend_error) return suspend_error;
	device->power.runtime_status=RPM_SUSPENDED;
	if (!suspend_keeps_power) samples[0][0]=samples[0][1]=0;
	return 0;
}
static void pm_runtime_put_noidle(struct device *device)
{ assert(device==&virtual_device); noidles++; if (device->power.usage_count) device->power.usage_count--; }
static int pm_runtime_suspend(struct device *device)
{
	locked(); assert(device==&virtual_device && !device->power.usage_count); suspends++;
	if (suspend_error) return suspend_error;
	if (device->power.disable_depth) return -EACCES;
	if (device->power.runtime_status==RPM_SUSPENDED) return 1;
	device->power.runtime_status=RPM_SUSPENDED;
	if (!suspend_keeps_power) samples[0][0]=samples[0][1]=0;
	return 0;
}
static void dev_pm_domain_detach(struct device *device, bool power_off)
{
	locked(); assert(device==&virtual_device && device->refs>0 && !power_off); detaches++;
	assert(!device->power.usage_count && device->power.runtime_status==RPM_SUSPENDED);
	device->power.disable_depth=1;
	if (detach_fail) return;
	device->pm_domain=NULL;
	if (detach_registered) return;
	device->registered=false; put_device(device);
}
#include "n71-i2c-genpd.h"

static struct n71_i2c_genpd backend;
static struct n71_i2c_power_state state;
static struct n71_i2c_power_io io;
static void reset(void)
{
	memset(&backend,0,sizeof(backend)); memset(&state,0,sizeof(state));
	memset(nodes,0,sizeof(nodes)); memset(&virtual_device,0,sizeof(virtual_device));
	memset(&consumer,0,sizeof(consumer)); memset(held,0,sizeof(held)); memset(samples,0,sizeof(samples));
	for (unsigned int index=0;index<NODE_COUNT;index++) { nodes[index].index=(int)index; nodes[index].refs=1; }
	for (unsigned int index=0;index<3;index++) { maps[index].index=index; backend.references[index]=(struct n71_pmgr_reference){index,&nodes[LEAF_NODE+index],&nodes[ROOT_NODE]}; }
	consumer.of_node=&nodes[CONSUMER_NODE]; consumer.refs=1; consumer.registered=true; backend.consumer=&consumer;
	io=n71_i2c_genpd_io(&backend); fault=NONE; lock_fail=-1; resume_error=suspend_error=read_fail=0;
	detach_fail=detach_registered=suspend_keeps_power=false; reads=attaches=put_calls=suspends=detaches=noidles=0;
}
static void balanced(void)
{
	for (unsigned int index=0;index<3;index++) assert(!held[index]);
	for (unsigned int index=0;index<NODE_COUNT;index++) assert(nodes[index].refs==1);
	assert(!controller.dev.refs && !adapter.dev.refs && !consumer.power.lock && !virtual_device.power.lock);
}
static void released(void)
{
	balanced(); assert(!backend.domain && !backend.detach_attempted && !virtual_device.refs);
	assert(!state.active && !state.attached && !state.cleanup_pending && !state.usage_held && !state.cleanup_error);
}
int main(void)
{
	unsigned int cases=0;
	/* Kills omitted consumer/resource/domain guards and failed attach cleanup. */
	for (int id=WRONG_PATH;id<=ATTACH_ERROR;id++) {
		reset(); fault=(enum fault)id; assert(n71_i2c_power_acquire(&io,&state)<0);
		assert(!backend.domain && !virtual_device.refs && !state.attached && !reads); balanced(); cases++;
	}
	for (int index=0;index<3;index++) {
		reset(); lock_fail=index; assert(n71_i2c_power_acquire(&io,&state)==-ENODEV);
		assert(!attaches && !backend.domain); balanced(); cases++;
	}
	for (int id=0;id<7;id++) {
		reset();
		switch(id) {
		case 0: consumer.of_node=NULL; break; case 1: consumer.bus=&consumer; break;
		case 2: consumer.driver=&consumer; break; case 3: consumer.pm_domain=&consumer; break;
		case 4: consumer.registered=false; break; case 5: backend.references[1].index=0; break;
		case 6: backend.references[1].pmgr=&nodes[OTHER_NODE]; break;
		}
		assert(n71_i2c_power_acquire(&io,&state)<0 && !attaches); balanced(); cases++;
	}
	reset(); assert(n71_genpd_attach(NULL)==-EINVAL); assert(n71_genpd_put_suspend(NULL)==-ENODEV);
	assert(n71_genpd_resume(&backend)==-EBUSY); assert(n71_genpd_suspend(&backend)==-ENODEV);
	balanced(); cases++;
	/* Kills missing own ref, missing verified detach and usage leaks. */
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); assert(state.active && virtual_device.refs==2);
	assert(n71_i2c_power_acquire(&io,&state)==-EBUSY && attaches==1);
	assert(n71_genpd_attach(&backend)==-EBUSY);
	assert(!n71_i2c_power_release(&io,&state)); assert(put_calls==1 && detaches==1 && !noidles);
	released(); assert(!n71_i2c_power_release(&io,&state)); cases++;
	reset(); resume_error=-EIO; assert(n71_i2c_power_acquire(&io,&state)==-EIO);
	assert(!put_calls && suspends==1 && detaches==1); released(); cases++;
	/* Runtime state and electrical samples must both agree before active or detach. */
	for (int id=0;id<7;id++) {
		reset(); assert(!n71_i2c_power_acquire(&io,&state));
		switch(id) {
		case 0: virtual_device.power.runtime_status=RPM_RESUMING; break;
		case 1: virtual_device.power.usage_count=2; break; case 2: virtual_device.power.child_count=1; break;
		case 3: virtual_device.power.runtime_error=-EIO; break; case 4: virtual_device.power.request_pending=1; break;
		case 5: virtual_device.power.disable_depth=1; break; case 6: virtual_device.pm_domain=NULL; break;
		}
		assert(n71_genpd_verify_active(&backend)==-EBUSY); balanced(); cases++;
	}
	for (unsigned int index=0;index<3;index++) for (unsigned int sample=0;sample<2;sample++) {
		const u32 bad[]={0x100000f0,0x4f,0x900000ff,0x100004ff};
		for (unsigned int id=0;id<4;id++) {
			reset(); assert(!n71_i2c_power_acquire(&io,&state)); reads=0; samples[index][sample]=bad[id];
			assert(n71_genpd_verify_active(&backend)==-EIO); balanced(); cases++;
		}
	}
	reset(); assert(!n71_i2c_power_acquire(&io,&state));
	for (unsigned int index=0;index<3;index++) samples[index][0]=samples[index][1]=0x1000004f;
	assert(!n71_genpd_verify_active(&backend)); assert(!n71_i2c_power_release(&io,&state)); released(); cases++;
	for (int sample=1;sample<=6;sample++) {
		reset(); read_fail=sample; assert(n71_i2c_power_acquire(&io,&state)==-EIO);
		released(); assert(put_calls==1); cases++;
	}
	/* A failed put consumes usage once; retry uses suspend and never detaches early. */
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); suspend_error=-EIO;
	assert(n71_i2c_power_release(&io,&state)==-EIO && !state.usage_held && state.cleanup_pending);
	assert(!virtual_device.power.usage_count && backend.domain && !detaches); balanced();
	suspend_error=0; assert(!n71_i2c_power_release(&io,&state)); assert(put_calls==1 && suspends==1); released(); cases++;
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); lock_fail=1;
	assert(n71_i2c_power_release(&io,&state)==-ENODEV && noidles==1 && !virtual_device.power.usage_count);
	assert(!put_calls && !detaches && state.cleanup_pending); balanced(); lock_fail=-1;
	assert(!n71_i2c_power_release(&io,&state)); assert(noidles==1 && suspends==1); released(); cases++;
	/* Genpd suspend can succeed while power-off fails: never hide the live leaf on retry. */
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); suspend_keeps_power=true;
	assert(n71_i2c_power_release(&io,&state)==-EBUSY && !state.usage_held && state.cleanup_pending);
	assert(virtual_device.power.runtime_status==RPM_SUSPENDED && backend.domain && !detaches);
	assert(n71_i2c_power_release(&io,&state)==-EBUSY && put_calls==1 && suspends==1);
	assert(virtual_device.refs==2 && !virtual_device.power.usage_count); balanced(); cases++;
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); virtual_device.power.usage_count=2;
	assert(n71_i2c_power_release(&io,&state)==-EBUSY && noidles==1 && !put_calls);
	assert(virtual_device.power.usage_count==1 && state.cleanup_pending && backend.domain);
	balanced(); cases++;
	/* Void detach failure retains both references; retry tolerates only its own disabled suspended state. */
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); detach_fail=true;
	assert(n71_i2c_power_release(&io,&state)==-EBUSY && backend.domain && backend.detach_attempted);
	assert(virtual_device.refs==2 && state.cleanup_pending && !state.usage_held);
	assert(n71_i2c_power_acquire(&io,&state)==-EBUSY); balanced();
	virtual_device.power.disable_depth=2;
	assert(n71_genpd_verify_quiescent(&backend)==-EBUSY);
	virtual_device.power.disable_depth=1; detach_fail=false;
	assert(!n71_i2c_power_release(&io,&state)); assert(put_calls==1 && !suspends && detaches==2); released(); cases++;
	reset(); assert(!n71_i2c_power_acquire(&io,&state)); detach_registered=true;
	assert(n71_i2c_power_release(&io,&state)==-EBUSY && backend.domain && virtual_device.refs==2);
	assert(state.cleanup_pending); balanced(); cases++;
	/* Suspended runtime status alone cannot prove an electrically idle leaf. */
	for (unsigned int sample=0;sample<2;sample++) for (unsigned int id=0;id<4;id++) {
		const u32 bad[]={0x10000000,0xf0,0xf,0x80000000};
		reset(); assert(!n71_i2c_power_acquire(&io,&state)); assert(!n71_genpd_put_suspend(&backend));
		reads=0; samples[0][sample]=bad[id]; assert(n71_genpd_detach(&backend)<0 && !detaches && backend.domain);
		balanced(); cases++;
	}
	printf("N71_I2C_GENPD_OK cases=%u\n",cases);
	return 0;
}
