/* SPDX-License-Identifier: GPL-2.0-only */
/* Actual owner headers; kernel APIs and register effects are fixtures. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef EUCLEAN
#define EUCLEAN 117
#endif
typedef uint32_t u32;
typedef uint64_t u64;
#define IORESOURCE_MEM 0x200U
#define GFP_KERNEL 0
#define GPIOD_ASIS 0
#define GPIO_LOOKUP_FLAGS_DEFAULT 0
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define struct_size(p, member, n) (sizeof(*(p))+(n)*sizeof((p)->member[0]))
struct device_node { int id, refs; };
struct device_driver { const char *name; bool suppress_bind_attrs; };
struct device { struct device_node *of_node; struct device_driver *driver; void *bus, *pm_domain; bool registered; int refs, locked; };
struct platform_device { struct device dev; };
struct resource { u64 start,end; unsigned int flags; };
struct regmap { int unused; };
struct gpio_device { int refs; };
struct gpio_desc { unsigned int pin; bool owned; struct gpio_device *gdev; };
struct pinctrl { int refs; bool selected; };
struct pinctrl_state { int unused; };
struct gpiod_lookup { const char *key; unsigned int chip_hwnum; const char *con_id; unsigned int idx,flags; };
struct gpiod_lookup_table { const char *dev_id; struct gpiod_lookup table[]; };
#define GPIO_LOOKUP_IDX(k,p,c,i,f) ((struct gpiod_lookup){k,p,c,i,f})
enum fault {
 NONE, BOARD, WRONG_CONSUMER, MISSING_GPIO, NAMES_COUNT, NAMES_VALUE, EXTRA_STATE,
 GPIO_OVERRIDE, PHANDLE_COUNT, WRONG_GROUP, WRONG_PARENT, CELL_COUNT, CELL0, CELL1,
 GPIO_OFF, NPINS, RESOURCE_ERROR, RESOURCE_BASE, RESOURCE_SIZE, NO_PROVIDER, DRIVER,
 UNSUPPRESSED, NO_MAP, MAP_STRIDE, NO_GDEV, BAD_LABEL, WRONG_LABEL_DEVICE, ALLOC,
 REQUEST0, REQUEST1, WRONG_DESCRIPTOR, OFFSET, PINCTRL_GET, PINCTRL_LOOKUP, PINCTRL_SELECT,
 FAULT_COUNT
};
static enum fault selected_fault;
static struct device_node nodes[4];
static struct device_driver driver;
static struct device consumer;
static struct platform_device provider;
static struct regmap register_map;
static struct gpio_device gdev,other_gdev;
static struct gpio_desc descriptors[3];
static struct pinctrl control;
static struct pinctrl_state default_state;
static struct gpiod_lookup_table *lookup;
static unsigned int reads,requests,releases,release_order[4],pinctrl_puts;
static unsigned int read_failure,read_phase;
static u32 words[2];
static bool allocated,persistent_read_failure,replace_gdev,drift_on_put;
static bool device_is_registered(struct device *value) { return value->registered; }
static bool of_machine_is_compatible(const char *value)
{ assert(!strcmp(value,"apple,n71")); return selected_fault!=BOARD; }
static struct device_node *of_find_node_by_path(const char *path)
{
 unsigned int index;
 if (!strcmp(path,"/soc/i2c@20a111000")) index=0;
 else if (!strcmp(path,"/soc/pinctrl@20f100000")) { if (selected_fault==MISSING_GPIO) return NULL; index=1; }
 else { assert(!strcmp(path,"/soc/pinctrl@20f100000/i2c1-pins")); index=2; }
 nodes[index].refs++; return &nodes[index];
}
static void of_node_put(struct device_node *node) { if (node) { assert(node->refs>0); node->refs--; } }
static int of_property_count_strings(struct device_node *node,const char *name)
{ assert(node==&nodes[0] && !strcmp(name,"pinctrl-names")); return selected_fault==NAMES_COUNT ? 2 : 1; }
static int of_property_read_string(struct device_node *node,const char *name,const char **out)
{ assert(node==&nodes[0] && !strcmp(name,"pinctrl-names")); *out=selected_fault==NAMES_VALUE ? "idle" : "default"; return 0; }
static void *of_find_property(struct device_node *node,const char *name,int *size)
{
 assert(node==&nodes[0] && !size);
 return (selected_fault==EXTRA_STATE && !strcmp(name,"pinctrl-1")) ||
        (selected_fault==GPIO_OVERRIDE && !strcmp(name,"pins-gpios")) ? &nodes[0] : NULL;
}
static int of_count_phandle_with_args(struct device_node *node,const char *name,const char *cells)
{ assert(node==&nodes[0] && !strcmp(name,"pinctrl-0") && !cells); return selected_fault==PHANDLE_COUNT ? 2 : 1; }
static struct device_node *of_parse_phandle(struct device_node *node,const char *name,int index)
{ assert(node==&nodes[0] && !strcmp(name,"pinctrl-0") && !index); node=&nodes[selected_fault==WRONG_GROUP ? 3 : 2]; node->refs++; return node; }
static struct device_node *of_get_parent(struct device_node *node)
{ assert(node==&nodes[2] || node==&nodes[3]); node=&nodes[selected_fault==WRONG_PARENT ? 3 : 1]; node->refs++; return node; }
static int of_property_count_u32_elems(struct device_node *node,const char *name)
{ assert(node==&nodes[2] && !strcmp(name,"pinmux")); return selected_fault==CELL_COUNT ? 1 : 2; }
static int of_property_read_u32_array(struct device_node *node,const char *name,u32 *out,unsigned int count)
{ assert(node==&nodes[2] && !strcmp(name,"pinmux") && count==2); out[0]=0x10073+(selected_fault==CELL0); out[1]=0x10072+(selected_fault==CELL1); return 0; }
static bool of_device_is_available(struct device_node *node)
{ assert(node==&nodes[1]); return selected_fault!=GPIO_OFF; }
static bool of_device_is_compatible(struct device_node *node,const char *name)
{ assert(node==&nodes[1] && !strcmp(name,"apple,pinctrl")); return true; }
static int of_property_read_u32(struct device_node *node,const char *name,u32 *out)
{ assert(node==&nodes[1] && !strcmp(name,"apple,npins")); *out=selected_fault==NPINS ? 209 : 208; return 0; }
static int of_address_to_resource(struct device_node *node,int index,struct resource *out)
{
 assert(node==&nodes[1] && !index);
 out->start=0x20f100000ULL+(selected_fault==RESOURCE_BASE ? 4 : 0);
 out->end=out->start+0xfffff+(selected_fault==RESOURCE_SIZE ? 4 : 0); out->flags=IORESOURCE_MEM;
 return selected_fault==RESOURCE_ERROR ? -EIO : 0;
}
static u64 resource_size(struct resource *value) { return value->end-value->start+1; }
static unsigned int resource_type(struct resource *value) { return value->flags; }
static struct platform_device *of_find_device_by_node(struct device_node *node)
{ assert(node==&nodes[1]); if (selected_fault==NO_PROVIDER) return NULL; provider.dev.refs++; return &provider; }
static void put_device(struct device *device) { assert(device==&provider.dev && device->refs==1 && !device->locked); device->refs--; }
static void device_lock(struct device *device) { assert(device==&provider.dev && device->refs==1 && !device->locked); device->locked=1; }
static void device_unlock(struct device *device) { assert(device==&provider.dev && device->locked); device->locked=0; }
static struct regmap *dev_get_regmap(struct device *device,const char *name)
{ assert(device==&provider.dev && device->locked && !name); return selected_fault==NO_MAP ? NULL : &register_map; }
static int regmap_get_val_bytes(struct regmap *map) { assert(map==&register_map && provider.dev.locked); return 4; }
static int regmap_get_reg_stride(struct regmap *map) { assert(map==&register_map && provider.dev.locked); return selected_fault==MAP_STRIDE ? 8 : 4; }
static int read_word(struct regmap *map,unsigned int offset,unsigned int *out,bool bypass)
{
 assert(map==&register_map && provider.dev.locked && (offset==460 || offset==456));
 assert(bypass==(read_phase%4==1 || read_phase%4==2)); reads++;
 if (persistent_read_failure || reads==read_failure) { read_phase=0; return -EIO; }
 read_phase=(read_phase+1)%8;
 *out=words[offset==456]; return 0;
}
static int regmap_read(struct regmap *map,unsigned int offset,unsigned int *out) { return read_word(map,offset,out,false); }
static int regmap_read_bypassed(struct regmap *map,unsigned int offset,unsigned int *out) { return read_word(map,offset,out,true); }
static struct device_node *of_fwnode_handle(struct device_node *node) { return node; }
static struct gpio_device *gpio_device_find_by_fwnode(struct device_node *node)
{
 assert(node==&nodes[1] && provider.dev.locked);
 if (selected_fault==NO_GDEV) return NULL;
 struct gpio_device *out=replace_gdev ? &other_gdev : &gdev; out->refs++; return out;
}
static const char *gpio_device_get_label(struct gpio_device *device)
{ assert(device==&gdev && device->refs>0 && provider.dev.locked); return selected_fault==BAD_LABEL ? "other" : "20f100000.pinctrl"; }
static const char *dev_name(struct device *device)
{ assert(device==&consumer || device==&provider.dev); return device==&consumer ? "n71-i2c1-power" : "20f100000.pinctrl"; }
static struct gpio_device *gpio_device_find_by_label(const char *label)
{ assert(!strcmp(label,"20f100000.pinctrl") && provider.dev.locked); struct gpio_device *out=selected_fault==WRONG_LABEL_DEVICE ? &other_gdev : &gdev; out->refs++; return out; }
static void gpio_device_put(struct gpio_device *device) { assert(device->refs>0); device->refs--; }
static void *kzalloc(size_t size,int flags)
{ assert(flags==GFP_KERNEL && size==sizeof(struct gpiod_lookup_table)+3*sizeof(struct gpiod_lookup) && !allocated); if (selected_fault==ALLOC) return NULL; allocated=true; return calloc(1,size); }
static void kfree(void *value) { assert(allocated && !lookup); allocated=false; free(value); }
static void gpiod_add_lookup_table(struct gpiod_lookup_table *table)
{
 assert(!lookup && allocated && provider.dev.locked && !strcmp(table->dev_id,"n71-i2c1-power") && !table->table[2].key);
 for (unsigned int i=0;i<2;i++) assert(table->table[i].chip_hwnum==115-i && !strcmp(table->table[i].key,"20f100000.pinctrl") && !strcmp(table->table[i].con_id,"pins") && table->table[i].idx==i && !table->table[i].flags);
 lookup=table;
}
static void gpiod_remove_lookup_table(struct gpiod_lookup_table *table)
{ assert(lookup==table && !descriptors[0].owned && !descriptors[1].owned && !descriptors[2].owned); lookup=NULL; }
static struct gpio_desc *gpio_device_get_desc(struct gpio_device *device,unsigned int pin)
{ assert(device==&gdev && device->refs>0 && provider.dev.locked && (pin==115 || pin==114)); return &descriptors[115-pin]; }
static struct gpio_desc *gpiod_get_index(struct device *device,const char *name,unsigned int index,int flags)
{
 assert(device==&consumer && !strcmp(name,"pins") && index<2 && flags==GPIOD_ASIS && lookup && provider.dev.locked);
 requests++;
 if ((selected_fault==REQUEST0 && !index) || (selected_fault==REQUEST1 && index)) return ERR_PTR(-EBUSY);
 struct gpio_desc *out=&descriptors[selected_fault==WRONG_DESCRIPTOR ? 2 : index];
 assert(!out->owned); out->owned=true; out->gdev->refs++; return out;
}
static unsigned int gpiod_hwgpio(struct gpio_desc *descriptor)
{ assert(descriptor->owned && provider.dev.locked); return descriptor->pin+(selected_fault==OFFSET); }
static void gpiod_put(struct gpio_desc *descriptor)
{ assert(descriptor->owned && provider.dev.locked && releases<4); descriptor->owned=false; descriptor->gdev->refs--; release_order[releases++]=descriptor->pin; }
static struct pinctrl *pinctrl_get(struct device *device)
{
 assert(device==&consumer && descriptors[0].owned && descriptors[1].owned && provider.dev.locked && !control.refs);
 if (selected_fault==PINCTRL_GET) return ERR_PTR(-ENXIO);
 control.refs=1; nodes[0].refs++; return &control;
}
static struct pinctrl_state *pinctrl_lookup_state(struct pinctrl *value,const char *name)
{ assert(value==&control && control.refs==1 && !strcmp(name,"default") && provider.dev.locked); return selected_fault==PINCTRL_LOOKUP ? ERR_PTR(-ENOENT) : &default_state; }
static int pinctrl_select_state(struct pinctrl *value,struct pinctrl_state *state)
{ assert(value==&control && state==&default_state && provider.dev.locked && descriptors[0].owned && descriptors[1].owned); control.selected=true; return selected_fault==PINCTRL_SELECT ? -ENXIO : 0; }
static void pinctrl_put(struct pinctrl *value)
{ assert(value==&control && control.refs==1 && provider.dev.locked); control.refs=0; control.selected=false; nodes[0].refs--; pinctrl_puts++; if (drift_on_put) words[0]^=1U<<20; }
#include "n71-i2c-pin-owner.h"

static void reset_fixture(enum fault fault)
{
 assert(!provider.dev.refs && !provider.dev.locked && !gdev.refs && !other_gdev.refs && !control.refs && !lookup && !allocated);
 selected_fault=fault;
 for (unsigned int i=0;i<4;i++) nodes[i]=(struct device_node){.id=(int)i};
 nodes[0].refs=1;
 consumer=(struct device){.of_node=&nodes[fault==WRONG_CONSUMER ? 3 : 0],.registered=true};
 driver=(struct device_driver){.name=fault==DRIVER ? "other" : "apple-gpio-pinctrl",.suppress_bind_attrs=fault!=UNSUPPRESSED};
 provider.dev=(struct device){.of_node=&nodes[1],.driver=&driver};
 descriptors[0]=(struct gpio_desc){.pin=115,.gdev=&gdev};
 descriptors[1]=(struct gpio_desc){.pin=114,.gdev=&gdev};
 descriptors[2]=(struct gpio_desc){.pin=115,.gdev=&other_gdev};
 reads=requests=releases=pinctrl_puts=read_failure=read_phase=0;
 words[0]=words[1]=0x76221;
 persistent_read_failure=replace_gdev=drift_on_put=false;
}
static void assert_clean(const struct n71_i2c_pin_owner *owner)
{
 assert(n71_i2c_pin_owner_clean(owner) && !owner->cleanup_error && !provider.dev.refs && !provider.dev.locked);
 assert(!gdev.refs && !other_gdev.refs && !control.refs && !lookup && !allocated && nodes[0].refs==1);
 for (unsigned int i=1;i<4;i++) assert(!nodes[i].refs);
 for (unsigned int i=0;i<3;i++) assert(!descriptors[i].owned);
}
int main(void)
{
 struct n71_i2c_pin_owner owner={0}; unsigned int cases=0;
 for (enum fault f=BOARD;f<FAULT_COUNT;f++) {
  reset_fixture(f); assert(n71_i2c_pin_owner_acquire(&consumer,&owner)<0); assert_clean(&owner); cases++;
 }
 /* Mutations captured: ignoring sample errors before/after pinctrl selection leaks handles. */
 for (unsigned int position=1;position<=16;position++) {
  reset_fixture(NONE); read_failure=position;
  assert(n71_i2c_pin_owner_acquire(&consumer,&owner)==-EIO); assert_clean(&owner); cases++;
 }
 /* Mutations captured: default/descriptor scope, retained ownership and reverse release. */
 reset_fixture(NONE); assert(n71_i2c_pin_owner_acquire(&consumer,&owner)==0);
 assert(owner.selected && owner.cleanup_pending && gdev.refs==3 && control.refs==1 && control.selected && lookup && !provider.dev.locked);
 assert(n71_i2c_pin_owner_verify(&owner)==0 && n71_i2c_pin_owner_verify(&owner)==0);
 assert(n71_i2c_pin_owner_acquire(&consumer,&owner)==-EBUSY && requests==2); cases++;
 assert(n71_i2c_pin_owner_release(&owner)==0 && releases==2 && release_order[0]==114 && release_order[1]==115 && pinctrl_puts==1); assert_clean(&owner); cases++;
 assert(n71_i2c_pin_owner_release(&owner)==0 && releases==2); assert_clean(&owner); cases++;
 /* Mutations captured: losing refs on provider/readback failure or accepting replacement. */
 for (unsigned int mode=0;mode<4;mode++) {
  reset_fixture(NONE); assert(n71_i2c_pin_owner_acquire(&consumer,&owner)==0);
  if (mode==0) driver.suppress_bind_attrs=false;
  if (mode==1) replace_gdev=true;
  if (mode==2) persistent_read_failure=true;
  if (mode==3) words[0]^=1U<<20;
  assert(n71_i2c_pin_owner_verify(&owner)<0);
  assert(n71_i2c_pin_owner_release(&owner)<0 && owner.cleanup_error && owner.cleanup_pending && !releases && control.refs==1 && !provider.dev.locked); cases++;
  driver.suppress_bind_attrs=true; replace_gdev=persistent_read_failure=false; words[0]=0x76221;
  assert(n71_i2c_pin_owner_release(&owner)==0); assert_clean(&owner); cases++;
 }
 reset_fixture(NONE); assert(n71_i2c_pin_owner_acquire(&consumer,&owner)==0); drift_on_put=true;
 assert(n71_i2c_pin_owner_release(&owner)==-EUCLEAN && owner.cleanup_pending && !owner.pinctrl && !owner.descriptors[0] && !owner.lookup && !provider.dev.locked);
 assert(gdev.refs==1 && provider.dev.refs==1 && n71_i2c_pin_owner_verify(&owner)==-EINVAL); cases++;
 drift_on_put=false; words[0]=0x76221;
 assert(n71_i2c_pin_owner_release(&owner)==0); assert_clean(&owner); cases++;
 for (unsigned int bit=0;bit<4;bit++) {
  reset_fixture(NONE); words[0]^=1U<<(bit==0 ? 4 : bit==1 ? 5 : bit==2 ? 6 : 9);
  assert(n71_i2c_pin_owner_acquire(&consumer,&owner)==-EUCLEAN && !requests); assert_clean(&owner); cases++;
 }
 printf("N71_I2C_PIN_OWNER_OK cases=%u\n",cases); return 0;
}
