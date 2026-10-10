/* SPDX-License-Identifier: GPL-2.0-only */
/* Real controller header; OF/clock/pin/MMIO fixtures are not device proof. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifndef EUCLEAN
#define EUCLEAN 117
#endif
typedef uint32_t u32;
typedef uint64_t u64;
#define __iomem
#define IORESOURCE_MEM 0x200U
#define IS_ERR(p) ((uintptr_t)(p) > (uintptr_t)-4096)
#define PTR_ERR(p) ((int)(intptr_t)(p))
struct device_node { int index; };
struct device { struct device_node *of_node; void *bus, *driver, *pm_domain; bool registered; };
struct resource { u64 start, end; unsigned int flags; };
struct of_phandle_args { struct device_node *np; unsigned int args_count; };
struct clk { unsigned int enables, protects, references; };
static struct device_node node, clock_node, other_node;
static struct device consumer;
static struct resource region;
static struct clk clock_handle;
static struct of_phandle_args clock_spec;
static struct resource resource_value;
static unsigned char memory[0x1000];
static u32 registers[5];
static bool claimed, mapped, region_busy, map_failure, clock_null;
static bool clock_available, clock_compatible, timeout_reset, restore_corrupt, reset_all_ones, reset_busy;
static unsigned int pin_calls, pin_fail_from, reads, writes, resets, restores, delays, node_refs;
static unsigned int unstable_at, all_ones_at, clock_cells, clock_frequency;
static int resource_error, parse_error, clock_error, protect_error, enable_error, clock_count;
static unsigned long clock_rate;
static bool device_is_registered(struct device *value) { return value->registered; }
static int of_address_to_resource(struct device_node *value, int index, struct resource *out)
{ assert(value==&node && index==0); *out=resource_value; return resource_error; }
static u64 resource_size(struct resource *value) { return value->end-value->start+1; }
static unsigned int resource_type(struct resource *value) { return value->flags; }
static int of_count_phandle_with_args(struct device_node *value, const char *name, const char *cells)
{ assert(value==&node && !strcmp(name,"clocks") && !strcmp(cells,"#clock-cells")); return clock_count; }
static int of_parse_phandle_with_args(struct device_node *value, const char *name, const char *cells,
		int index, struct of_phandle_args *out)
{
	assert(value==&node && !strcmp(name,"clocks") && !strcmp(cells,"#clock-cells") && index==0);
	if (parse_error) return parse_error;
	*out=clock_spec; node_refs++; return 0;
}
static struct device_node *of_find_node_by_path(const char *path)
{ assert(!strcmp(path,"/clock-ref")); node_refs++; return &clock_node; }
static void of_node_put(struct device_node *value) { if (value) { assert(node_refs); node_refs--; } }
static bool of_device_is_available(struct device_node *value)
{ assert(value==&clock_node); return clock_available; }
static bool of_device_is_compatible(struct device_node *value, const char *name)
{ assert(value==&clock_node && !strcmp(name,"fixed-clock")); return clock_compatible; }
static int of_property_read_u32(struct device_node *value, const char *name, u32 *out)
{
	assert(value==&clock_node);
	if (!strcmp(name,"#clock-cells")) *out=clock_cells;
	else { assert(!strcmp(name,"clock-frequency")); *out=clock_frequency; }
	return 0;
}
static struct clk *of_clk_get(struct device_node *value, int index)
{
	assert(value==&node && index==0 && !node_refs);
	if (clock_error) return (struct clk *)(intptr_t)clock_error;
	if (clock_null) return NULL;
	clock_handle.references++; return &clock_handle;
}
static int clk_rate_exclusive_get(struct clk *value)
{ assert(value==&clock_handle && value->references==1); if (!protect_error) value->protects++; return protect_error; }
static void clk_rate_exclusive_put(struct clk *value)
{ assert(value==&clock_handle && value->protects==1 && value->enables==1); value->protects--; }
static int clk_prepare_enable(struct clk *value)
{ assert(value==&clock_handle && value->protects==1 && value->enables==1); if (!enable_error) value->enables++; return enable_error; }
static void clk_disable_unprepare(struct clk *value)
{ assert(value==&clock_handle && value->enables==2 && !mapped && !claimed); value->enables--; }
static unsigned long clk_get_rate(struct clk *value) { assert(value==&clock_handle && value->enables==2); return clock_rate; }
static void clk_put(struct clk *value)
{ assert(value==&clock_handle && value->references==1 && !value->protects && value->enables==1); value->references--; }
static struct resource *request_mem_region_exclusive(u64 start, u64 size, const char *name)
{
	assert(start==0x20a111000ULL && size==0x1000);
	assert(!strcmp(name,"n71-i2c1-controller") || !strcmp(name,"n71-i2c1-inspect"));
	assert(!claimed && !mapped && clock_handle.enables==2);
	if (region_busy) return NULL;
	claimed=true; return &region;
}
static void *ioremap(u64 start, u64 size)
{
	assert(start==0x20a111000ULL && size==0x1000 && claimed && !mapped);
	if (map_failure) return NULL;
	mapped=true; return memory;
}
static unsigned int word_index(void *address)
{
	const unsigned int offsets[]={0x28,0x14,0x0c,0x18,0x1c};
	for (unsigned int i=0;i<5;i++) if (address==memory+offsets[i]) return i;
	assert(!"FIFO or unqualified register accessed"); return 0;
}
static u32 ioread32(void *address)
{
	assert(mapped && claimed && clock_handle.enables==2 && clock_handle.protects==1);
	unsigned int index=word_index(address); reads++;
	if (all_ones_at==reads) return ~0U;
	if (unstable_at==reads) return registers[index]^1U;
	return registers[index];
}
static void iowrite32(u32 value, void *address)
{
	assert(mapped && claimed && clock_handle.enables==2 && pin_calls>=2);
	unsigned int index=word_index(address);
	assert(index==3 || index==4); writes++;
	registers[index]=value;
	if (index==4 && value==0x70f) {
		resets++;
		if (timeout_reset) registers[4]=0x70e;
		if (reset_all_ones) registers[0]=~0U;
		if (reset_busy) registers[1]|=1U<<28;
	} else if (index==4) {
		assert(value==0x2a); restores++;
		if (restore_corrupt) registers[4]=0x2b;
	}
}
static void iounmap(void *address) { assert(address==memory && mapped && claimed); mapped=false; }
static void release_mem_region(u64 start, u64 size)
{ assert(start==0x20a111000ULL && size==0x1000 && claimed && !mapped); claimed=false; }
static void usleep_range(unsigned long low, unsigned long high)
{ assert(low==1000 && high==1100 && mapped && claimed); delays++; }
static int verify_pins(void *context)
{ assert(context==&consumer); pin_calls++; return pin_fail_from && pin_calls>=pin_fail_from ? -EACCES : 0; }
#include "n71-i2c-controller.h"

static void reset_fixture(void)
{
	assert(!mapped && !claimed && !clock_handle.references && !clock_handle.protects && !node_refs);
	consumer=(struct device){.of_node=&node,.registered=true};
	resource_value=(struct resource){.start=0x20a111000ULL,.end=0x20a111fffULL,.flags=IORESOURCE_MEM};
	clock_spec=(struct of_phandle_args){.np=&clock_node};
	clock_handle=(struct clk){.enables=1}; /* Preserve another consumer's reference. */
	registers[0]=2; registers[1]=0x08010100; registers[2]=0; registers[3]=0; registers[4]=0x2a;
	region_busy=map_failure=clock_null=false;
	timeout_reset=restore_corrupt=reset_all_ones=reset_busy=false;
	clock_available=clock_compatible=true;
	pin_calls=pin_fail_from=reads=writes=resets=restores=delays=node_refs=0;
	unstable_at=all_ones_at=clock_cells=0; clock_frequency=24000000;
	resource_error=parse_error=clock_error=protect_error=enable_error=0;
	clock_count=1; clock_rate=24000000;
}
static void assert_clean(const struct n71_i2c_controller *state)
{
	assert(n71_i2c_controller_clean(state) && !state->cleanup_error);
	assert(!mapped && !claimed && !clock_handle.references && !clock_handle.protects && !node_refs);
	assert(clock_handle.enables==1);
}
static void assert_pending(const struct n71_i2c_controller *state)
{
	assert(!n71_i2c_controller_clean(state) && state->restore_pending && state->cleanup_error);
	assert(mapped && claimed && clock_handle.references==1 && clock_handle.protects==1 && clock_handle.enables==2);
}
int main(void)
{
	struct n71_i2c_power_state power={.active=true,.attached=true,.usage_held=true,.cleanup_pending=true};
	struct n71_i2c_controller_request request={.consumer=&consumer,.pin_context=&consumer,.power=&power,.verify_pins=verify_pins};
	struct n71_i2c_controller state={0};
	unsigned int cases=0;
	reset_fixture();
	assert(n71_i2c_controller_acquire(NULL,&state)==-EINVAL && !reads && !writes); cases++;
	assert(n71_i2c_controller_acquire(&request,NULL)==-EINVAL && !reads && !writes); cases++;
	for (unsigned int i=0;i<4;i++) {
		struct n71_i2c_power_state invalid=power;
		if (i==0) invalid.active=false;
		if (i==1) invalid.attached=false;
		if (i==2) invalid.usage_held=false;
		if (i==3) invalid.cleanup_pending=false;
		request.power=&invalid;
		assert(n71_i2c_controller_acquire(&request,&state)==-EINVAL && !pin_calls && !writes); cases++;
	}
	request.power=&power;
	for (unsigned int i=0;i<18;i++) {
		reset_fixture();
		int expected=-ENODEV;
		if (i==0) { pin_fail_from=1; expected=-EACCES; }
		if (i==1) { resource_error=-EIO; expected=-EIO; }
		if (i==2) { resource_value.start++; resource_value.end++; }
		if (i==3) resource_value.end++;
		if (i==4) resource_value.flags=0;
		if (i==5) clock_count=2;
		if (i==6) { parse_error=-EIO; expected=-EIO; }
		if (i==7) clock_spec.np=&other_node;
		if (i==8) clock_spec.args_count=1;
		if (i==9) clock_available=false;
		if (i==10) clock_compatible=false;
		if (i==11) clock_cells=1;
		if (i==12) clock_frequency=25000000;
		if (i==13) { clock_error=-EAGAIN; expected=-EAGAIN; }
		if (i==14) clock_null=true;
		if (i==15) { protect_error=-EBUSY; expected=-EBUSY; }
		if (i==16) { enable_error=-EIO; expected=-EIO; }
		if (i==17) { clock_rate=25000000; expected=-ERANGE; }
		assert(n71_i2c_controller_acquire(&request,&state)==expected && !reads && !writes);
		assert_clean(&state); cases++;
	}
	for (unsigned int i=0;i<11;i++) {
		reset_fixture();
		int expected=-EBUSY;
		if (i==0) region_busy=true;
		if (i==1) { map_failure=true; expected=-ENOMEM; }
		if (i==2) { all_ones_at=1; expected=-ENODEV; }
		if (i==3) { unstable_at=6; expected=-EUCLEAN; }
		if (i==4) registers[0]=6;
		if (i==5) registers[1]|=1U<<28;
		if (i==6) registers[1]|=1U<<19;
		if (i==7) registers[1]&=~(1U<<16);
		if (i==8) registers[2]=1;
		if (i==9) registers[3]=1;
		if (i==10) registers[4]=0x700;
		assert(n71_i2c_controller_acquire(&request,&state)==expected && !writes);
		assert_clean(&state); cases++;
	}
	reset_fixture(); pin_fail_from=2;
	assert(n71_i2c_controller_acquire(&request,&state)==-EACCES && !writes);
	assert_clean(&state); cases++;
	reset_fixture();
	assert(n71_i2c_controller_acquire(&request,&state)==0 && state.restore_pending && resets==1 && !restores && writes==2 && pin_calls==3);
	assert(n71_i2c_controller_acquire(&request,&state)==-EBUSY && resets==1); cases++;
	assert(n71_i2c_controller_release(&request,&state)==0 && restores==1 && registers[4]==0x2a && writes==4);
	assert_clean(&state); cases++;
	assert(n71_i2c_controller_release(&request,&state)==0 && writes==4); cases++;
	reset_fixture(); timeout_reset=true;
	assert(n71_i2c_controller_acquire(&request,&state)==-ETIMEDOUT && delays==100 && restores==1);
	assert_clean(&state); cases++;
	for (unsigned int i=0;i<3;i++) {
		reset_fixture();
		if (i==0) reset_all_ones=true;
		if (i==1) reset_busy=true;
		if (i==2) pin_fail_from=3;
		assert(n71_i2c_controller_acquire(&request,&state)==(i==0 ? -ENODEV : i==1 ? -EUCLEAN : -EACCES));
		assert_pending(&state); assert(!restores);
		registers[0]=2; registers[1]=0x08010100; pin_fail_from=0;
		assert(n71_i2c_controller_release(&request,&state)==0 && restores==1);
		assert_clean(&state); cases++;
	}
	reset_fixture();
	assert(n71_i2c_controller_acquire(&request,&state)==0);
	assert(n71_i2c_controller_release(&(struct n71_i2c_controller_request){.consumer=&(struct device){0}},&state)==-EINVAL);
	assert(mapped && claimed && !restores); cases++;
	power.active=false;
	assert(n71_i2c_controller_release(&request,&state)==-EINVAL); assert_pending(&state); assert(!restores); cases++;
	power.active=true; restore_corrupt=true;
	assert(n71_i2c_controller_release(&request,&state)==-EUCLEAN); assert_pending(&state); assert(restores==1); cases++;
	restore_corrupt=false;
	assert(n71_i2c_controller_release(&request,&state)==0 && restores==2); assert_clean(&state); cases++;
	reset_fixture();
	assert(n71_i2c_controller_acquire(&request,&state)==0);
	registers[4]=0x0f; /* The restore also accepts command bits already cleared. */
	assert(n71_i2c_controller_release(&request,&state)==0); assert_clean(&state); cases++;
	reset_fixture();
	assert(n71_i2c_controller_acquire(&request,&state)==0);
	registers[4]|=1U<<11;
	assert(n71_i2c_controller_release(&request,&state)==-EBUSY && !restores); assert_pending(&state); cases++;
	registers[4]=0x0f;
	assert(n71_i2c_controller_release(&request,&state)==0); assert_clean(&state); cases++;
	printf("N71_I2C_CONTROLLER_TRANSACTION_OK cases=%u\n",cases);
	return 0;
}
