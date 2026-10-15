/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_DART_HOST_FIXTURE_H
#define N71_DART_HOST_FIXTURE_H
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
#define OF_POPULATED 1U
struct property { const char *name; int length; void *value; };
struct device_node {
	const char *full_name;
	u32 phandle, cells;
	unsigned int refs, flags;
	bool compatible;
	struct property *status, *map, *mask, *iommus;
};
struct device_driver { const char *name; };
struct device { struct device *parent; struct device_node *of_node; struct device_driver *driver; unsigned int refs; };
struct platform_device { struct device dev; const char *name; void *data; bool registered; };
struct pci_host_bridge { struct device dev; void *bus; };
struct of_changeset_entry { struct property *prop; };
struct of_changeset {
	struct of_changeset_entry entries;
	struct device_node *node;
	struct property *before;
	bool initialized, queued, status;
};
#define list_last_entry(head, type, member) (head)
static struct {
	struct device_node master, provider, foreign_node;
	struct device master_device;
	struct platform_device provider_device, foreign_device;
	struct pci_host_bridge bridge;
	struct device_driver driver;
	struct property disabled, foreign_status, foreign_map;
	struct property *allocated[4];
	unsigned int allocated_count, queue_calls, status_applies, map_applies;
	unsigned int status_reverts, map_reverts, destroys, duplicate_devices;
	int queue_failure, status_apply_failure, map_apply_failure;
	int status_revert_failure, map_revert_failure;
	bool machine, lookup_foreign, provider_foreign, flag_race;
	unsigned int master_path_result, provider_path_result;
	void (*last_device_put)(struct device *);
} dt_fixture;

static struct device_node *of_node_get(struct device_node *node) { if (node) { assert(node->refs); node->refs++; } return node; }
static void of_node_put(struct device_node *node) { if (node) { assert(node->refs>1); node->refs--; } }
static struct device *get_device(struct device *dev) { assert(dev && dev->refs); dev->refs++; return dev; }
static void put_device(struct device *dev) { assert(dev && dev->refs); if (!--dev->refs && dt_fixture.last_device_put) dt_fixture.last_device_put(dev); }
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name,"apple,n71")); return dt_fixture.machine; }
static struct device_node *of_find_node_by_path(const char *path)
{
	bool master=!strcmp(path,"/soc/pcie@610000000");
	assert(master || !strcmp(path,"/soc/iommu@602008000"));
	unsigned int result=master ? dt_fixture.master_path_result : dt_fixture.provider_path_result;
	if (result==1) return NULL;
	struct device_node *expected=master ? &dt_fixture.master : &dt_fixture.provider;
	if (result==2) {
		dt_fixture.foreign_node.full_name=expected->full_name;
		return of_node_get(&dt_fixture.foreign_node);
	}
	return of_node_get(expected);
}
static bool of_device_is_compatible(struct device_node *node, const char *name) { assert(!strcmp(name,"apple,s8000-dart")); return node->compatible; }
static void *platform_get_drvdata(struct platform_device *dev) { return dev->data; }
static struct device_node *of_find_node_by_phandle(u32 phandle)
{
	assert(phandle==dt_fixture.provider.phandle);
	return of_node_get(dt_fixture.lookup_foreign ? &dt_fixture.foreign_node : &dt_fixture.provider);
}
static struct platform_device *of_find_device_by_node(struct device_node *node)
{
	assert(node==&dt_fixture.provider);
	struct platform_device *pdev=dt_fixture.provider_foreign ? &dt_fixture.foreign_device : &dt_fixture.provider_device;
	if (!pdev->registered) return NULL;
	get_device(&pdev->dev); return pdev;
}
static struct property *of_find_property(struct device_node *node, const char *name, int *length)
{
	struct property *prop=!strcmp(name,"status") ? node->status :
		!strcmp(name,"iommu-map") ? node->map : !strcmp(name,"iommu-map-mask") ? node->mask : node->iommus;
	if (length && prop) *length=prop->length;
	return prop;
}
static int of_property_read_u32(struct device_node *node, const char *name, u32 *value)
{
	assert(!strcmp(name,"#iommu-cells")); *value=node->cells; return 0;
}
static bool of_device_is_available(struct device_node *node)
{
	return !node->status || (node->status->value && node->status->length==5 && !memcmp(node->status->value,"okay",5));
}
static bool of_node_check_flag(struct device_node *node, unsigned int flag) { return !!(node->flags&flag); }
static bool of_node_test_and_set_flag(struct device_node *node, unsigned int flag)
{
	if (dt_fixture.flag_race) node->flags|=flag;
	bool old=of_node_check_flag(node,flag); node->flags|=flag; return old;
}
static void of_node_clear_flag(struct device_node *node, unsigned int flag) { node->flags&=~flag; }
static void of_changeset_init(struct of_changeset *set) { *set=(struct of_changeset){.initialized=true}; }
static int fixture_queue(struct of_changeset *set, struct device_node *node, const char *name, const void *value, size_t bytes)
{
	assert(set->initialized && !set->queued && node->refs>=2);
	if (++dt_fixture.queue_calls==(unsigned int)dt_fixture.queue_failure) return -ENOMEM;
	struct property *prop=calloc(1,sizeof(*prop)); assert(prop && dt_fixture.allocated_count<4);
	prop->name=strdup(name); prop->value=malloc(bytes); assert(prop->name && prop->value);
	memcpy(prop->value,value,bytes); prop->length=bytes;
	dt_fixture.allocated[dt_fixture.allocated_count++]=prop;
	set->node=of_node_get(node); set->entries.prop=prop; set->queued=true;
	set->status=!strcmp(name,"status"); set->before=set->status ? node->status : node->map;
	return 0;
}
static int of_changeset_update_prop_string(struct of_changeset *set, struct device_node *node, const char *name, const char *value)
{
	assert(node==&dt_fixture.provider && !strcmp(name,"status") && !strcmp(value,"okay"));
	return fixture_queue(set,node,name,value,strlen(value)+1);
}
static int of_changeset_add_prop_u32_array(struct of_changeset *set, struct device_node *node, const char *name, const u32 *values, size_t count)
{
	unsigned char bytes[32];
	assert(node==&dt_fixture.master && !strcmp(name,"iommu-map") && count==8);
	for (size_t i=0;i<count;i++) for (size_t b=0;b<4;b++) bytes[i*4+b]=values[i]>>(24-b*8);
	return fixture_queue(set,node,name,bytes,sizeof(bytes));
}
static int of_changeset_apply(struct of_changeset *set)
{
	assert(set->queued);
	int failure=set->status ? dt_fixture.status_apply_failure : dt_fixture.map_apply_failure;
	if (set->status) dt_fixture.status_applies++; else dt_fixture.map_applies++;
	if (failure==1) return -EIO;
	if (failure==3) return 0;
	if (set->status) {
		if (!of_node_check_flag(set->node,OF_POPULATED)) dt_fixture.duplicate_devices++;
		set->node->status=failure==4 ? &dt_fixture.foreign_status : set->entries.prop;
	} else set->node->map=failure==4 ? &dt_fixture.foreign_map : set->entries.prop;
	return failure==2 ? -EIO : 0;
}
static int of_changeset_revert(struct of_changeset *set)
{
	assert(set->queued);
	int failure=set->status ? dt_fixture.status_revert_failure : dt_fixture.map_revert_failure;
	if (set->status) {
		assert(!dt_fixture.provider_device.registered && !dt_fixture.foreign_device.registered);
		assert(set->node->status==set->entries.prop); dt_fixture.status_reverts++;
	} else { assert(!dt_fixture.bridge.bus && set->node->map==set->entries.prop); dt_fixture.map_reverts++; }
	if (failure==1) return -EIO;
	if (failure==3) return 0;
	if (set->status) set->node->status=failure==4 ? &dt_fixture.foreign_status : set->before;
	else set->node->map=failure==4 ? &dt_fixture.foreign_map : set->before;
	return failure==2 ? -EIO : 0;
}
static void of_changeset_destroy(struct of_changeset *set)
{
	assert(set->initialized);
	if (set->queued) {
		assert((set->status ? set->node->status : set->node->map)!=set->entries.prop);
		of_node_put(set->node);
	}
	set->initialized=false; dt_fixture.destroys++;
}
#endif /* N71_DART_HOST_FIXTURE_H */
