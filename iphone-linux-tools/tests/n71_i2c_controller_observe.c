/* SPDX-License-Identifier: GPL-2.0-only */
/* Actual observer, constrained kernel API fixtures; never hardware evidence. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifndef N71_CONTROLLER_INTEGRATION
typedef uint32_t u32;
typedef uint64_t u64;
#define __iomem
#define IORESOURCE_MEM 0x200U
struct device_node { int unused; };
struct device { struct device_node *of_node; void *bus, *driver, *pm_domain; bool registered; };
struct resource { u64 start, end; unsigned int flags; };
static struct device_node observe_node;
static struct device observe_consumer;
static struct resource observe_resource;
static int observe_resource_error;
static bool device_is_registered(struct device *device) { return device->registered; }
static int of_address_to_resource(struct device_node *node, int index, struct resource *result)
{ assert(node==&observe_node && !index); *result=observe_resource; return observe_resource_error; }
static u64 resource_size(struct resource *resource) { return resource->end-resource->start+1; }
static unsigned int resource_type(struct resource *resource) __attribute__((unused));
static unsigned int resource_type(struct resource *resource) { return resource->flags; }
#endif
static bool observe_region, observe_mapping, observe_busy, observe_map_failure;
static unsigned int observe_claims, observe_maps, observe_reads, observe_unmaps, observe_releases;
static unsigned char observe_memory[0x1000];
static u32 observe_samples[2][3];
static struct resource observe_region_handle;
static struct resource *request_mem_region_exclusive(u64 start, u64 size, const char *name)
{
	assert(start==0x20a111000ULL && size==0x1000 && !strcmp(name,"n71-i2c1-inspect"));
	assert(!observe_region && !observe_mapping); observe_claims++;
	if (observe_busy) return NULL;
	observe_region=true; return &observe_region_handle;
}
static void *ioremap(u64 start, u64 size)
{
	assert(observe_region && !observe_mapping && start==0x20a111000ULL && size==0x1000);
	observe_maps++; if (observe_map_failure) return NULL;
	observe_mapping=true; return observe_memory;
}
static u32 ioread32(void *address)
{
	static const unsigned int allowed[]={0x28,0x14,0x0c};
	assert(observe_region && observe_mapping && observe_reads<6);
	assert(address==observe_memory+allowed[observe_reads%3]);
	u32 value=observe_samples[observe_reads/3][observe_reads%3]; observe_reads++; return value;
}
static void iounmap(void *address)
{ assert(observe_region && observe_mapping && address==observe_memory && observe_reads==6); observe_mapping=false; observe_unmaps++; }
static void release_mem_region(u64 start, u64 size)
{ assert(observe_region && !observe_mapping && start==0x20a111000ULL && size==0x1000); observe_region=false; observe_releases++; }
static void observe_reset(void)
{
	assert(!observe_region && !observe_mapping);
	observe_busy=observe_map_failure=false;
	observe_claims=observe_maps=observe_reads=observe_unmaps=observe_releases=0;
	for (unsigned int i=0;i<2;i++) { observe_samples[i][0]=5; observe_samples[i][1]=1U<<16; observe_samples[i][2]=0; }
#ifndef N71_CONTROLLER_INTEGRATION
	observe_consumer=(struct device){.of_node=&observe_node,.registered=true};
	observe_resource=(struct resource){.start=0x20a111000ULL,.end=0x20a111fffULL,.flags=IORESOURCE_MEM};
	observe_resource_error=0;
#endif
}
#include "n71-i2c-controller-observe.h"
#ifndef N71_CONTROLLER_INTEGRATION
static void observe_clean(unsigned int reads)
{
	assert(!observe_region && !observe_mapping && observe_reads==reads);
	assert(observe_claims==1 && observe_maps==1 && observe_releases==1);
	assert(observe_unmaps==(reads==6));
}
int main(void)
{
	struct n71_i2c_power_state power={.active=true,.attached=true,.cleanup_pending=true,.usage_held=true};
	struct n71_i2c_controller_observation result;
	unsigned int cases=0;
	observe_reset(); assert(n71_i2c_controller_observe(NULL,&power,&result)==-EINVAL && !observe_claims); cases++;
	observe_reset(); assert(n71_i2c_controller_observe(&observe_consumer,NULL,&result)==-EINVAL && !observe_claims); cases++;
	observe_reset(); assert(n71_i2c_controller_observe(&observe_consumer,&power,NULL)==-EINVAL && !observe_claims); cases++;
	for (unsigned int i=0;i<4;i++) {
		struct n71_i2c_power_state invalid=power;
		if (i==0) invalid.active=false;
		if (i==1) invalid.attached=false;
		if (i==2) invalid.usage_held=false;
		if (i==3) invalid.cleanup_pending=false;
		observe_reset(); memset(&result,0xff,sizeof(result));
		assert(n71_i2c_controller_observe(&observe_consumer,&invalid,&result)==-EINVAL);
		assert(!observe_claims && !observe_reads && !result.complete && !result.idle_status); cases++;
	}
	for (unsigned int i=0;i<5;i++) {
		observe_reset();
		if (i==0) observe_consumer.of_node=NULL;
		if (i==1) observe_consumer.registered=false;
		if (i==2) observe_consumer.bus=&power;
		if (i==3) observe_consumer.driver=&power;
		if (i==4) observe_consumer.pm_domain=&power;
		assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==(i==0 ? -EINVAL : -ENODEV));
		assert(!observe_claims && !observe_reads && !result.complete); cases++;
	}
	for (unsigned int i=0;i<4;i++) {
		observe_reset();
		if (i==0) observe_resource_error=-EIO;
		if (i==1) { observe_resource.start--; observe_resource.end--; }
		if (i==2) observe_resource.end++;
		if (i==3) observe_resource.flags=0;
		assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==(i==0 ? -EIO : -ENODEV));
		assert(!observe_claims && !observe_reads); cases++;
	}
	observe_reset(); observe_busy=true;
	assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==-EBUSY);
	assert(observe_claims==1 && !observe_maps && !observe_reads && !observe_releases); cases++;
	observe_reset(); observe_map_failure=true;
	assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==-ENOMEM); observe_clean(0); cases++;
	observe_reset(); assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==0);
	assert(result.complete && result.stable && result.idle_status && !memcmp(result.words,observe_samples,sizeof(result.words)));
	observe_clean(6); cases++;
	for (unsigned int sample=0;sample<2;sample++) for (unsigned int word=0;word<3;word++) {
		observe_reset(); observe_samples[sample][word]=~0U;
		assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==-ENODEV);
		assert(result.complete && !result.idle_status); observe_clean(6); cases++;
	}
	for (unsigned int word=0;word<3;word++) {
		observe_reset(); observe_samples[1][word]^=1;
		assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==0);
		assert(result.complete && !result.stable && !result.idle_status); observe_clean(6); cases++;
	}
	const unsigned int busy_bits[]={28,25,24,23,22,21,19,6};
	for (unsigned int i=0;i<sizeof(busy_bits)/sizeof(busy_bits[0]);i++) {
		observe_reset(); observe_samples[0][1]|=1U<<busy_bits[i]; observe_samples[1][1]=observe_samples[0][1];
		assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==0);
		assert(result.complete && result.stable && !result.idle_status); observe_clean(6); cases++;
	}
	observe_reset(); observe_samples[0][1]=observe_samples[1][1]=0;
	assert(n71_i2c_controller_observe(&observe_consumer,&power,&result)==0 && !result.idle_status); observe_clean(6); cases++;
	printf("N71_I2C_CONTROLLER_OK cases=%u\n",cases);
	return 0;
}
#endif
