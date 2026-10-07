/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71_dart_host_fixture.h"
#include "n71-dart-host.h"

static unsigned int cases;
static struct n71_dart_host *active_owner;
static void last_device_put(struct device *device)
{
	(void)device;
	assert(!active_owner->bridge);
}
static void setup(struct n71_dart_host *owner, struct n71_dart_host_request *request)
{
	cases++; *owner=(struct n71_dart_host){0}; memset(&dt_fixture,0,sizeof(dt_fixture));
	dt_fixture.machine=true;
	active_owner=owner; dt_fixture.last_device_put=last_device_put;
	dt_fixture.disabled=(struct property){"status",9,"disabled"};
	dt_fixture.foreign_status=(struct property){"status",5,"okay"};
	dt_fixture.foreign_map=(struct property){"iommu-map",4,"data"};
	dt_fixture.master=(struct device_node){.full_name="/soc/pcie@610000000",.refs=1};
	dt_fixture.provider=(struct device_node){.full_name="/soc/iommu@602008000",.refs=1,
		.phandle=41,.cells=1,.compatible=true,.status=&dt_fixture.disabled};
	dt_fixture.foreign_node.refs=1;
	dt_fixture.master_device=(struct device){.of_node=&dt_fixture.master,.refs=1};
	dt_fixture.driver.name="apple-dart";
	dt_fixture.provider_device=(struct platform_device){.name="n71-dart-cycle",.registered=true,.data=&dt_fixture,
		.dev={.parent=&dt_fixture.master_device,.of_node=&dt_fixture.provider,.driver=&dt_fixture.driver,.refs=1}};
	dt_fixture.foreign_device=(struct platform_device){.registered=true,.dev={.refs=1}};
	dt_fixture.provider_foreign=false; dt_fixture.foreign_device.registered=false;
	dt_fixture.bridge.dev=(struct device){.parent=&dt_fixture.master_device,.refs=1};
	*request=(struct n71_dart_host_request){&dt_fixture.bridge,&dt_fixture.provider_device};
}
static void stop_provider(void)
{
	assert(!dt_fixture.master.map && !dt_fixture.bridge.bus);
	dt_fixture.provider_device.registered=false;
	put_device(&dt_fixture.provider_device.dev);
}
static void finish(struct n71_dart_host *owner, unsigned int flag, bool dropped_bridge)
{
	assert(!owner->bridge && !owner->master && !owner->provider);
	assert(dt_fixture.master.refs==1 && dt_fixture.provider.refs==1 && dt_fixture.foreign_node.refs==1);
	assert(dt_fixture.bridge.dev.refs==(dropped_bridge ? 0U : 1U) && dt_fixture.master_device.refs==1);
	assert(dt_fixture.provider_device.dev.refs==0 && !dt_fixture.master.map);
	assert(dt_fixture.provider.status==&dt_fixture.disabled && dt_fixture.provider.flags==flag);
	assert(!dt_fixture.duplicate_devices);
	for (unsigned int i=0;i<dt_fixture.allocated_count;i++) {
		free((void *)dt_fixture.allocated[i]->name); free(dt_fixture.allocated[i]->value); free(dt_fixture.allocated[i]);
	}
}
static void map_exact(void)
{
	const u32 expected[]={8,41,0,1,0x100,41,0,1};
	struct property *map=dt_fixture.master.map;
	assert(map && map->length==32);
	for (unsigned int i=0;i<8;i++) {
		const unsigned char *p=(const unsigned char *)map->value+i*4;
		u32 v=((u32)p[0]<<24)|((u32)p[1]<<16)|((u32)p[2]<<8)|p[3];
		assert(v==expected[i]);
	}
}
int main(void)
{
#ifdef __linux__
	assert(prctl(PR_SET_DUMPABLE,0)==0);
#endif
	struct n71_dart_host owner;
	struct n71_dart_host_request request;
	/* Mutations: lose refs/owner, skip flag/association, free a live consumer/provider, or repeat revert. */
	setup(&owner,&request);
	assert(n71_dart_host_unmap(NULL)==-EINVAL && n71_dart_host_release(NULL)==-EINVAL);
	assert(n71_dart_host_prepare(NULL,&request)==-EINVAL && n71_dart_host_prepare(&owner,NULL)==-EINVAL);
	assert(n71_dart_host_unmap(&owner)==0 && n71_dart_host_release(&owner)==0);
	assert(n71_dart_host_prepare(&owner,&request)==0);
	assert(owner.bridge==&dt_fixture.bridge && owner.mapped && owner.available && owner.populated);
	assert(dt_fixture.bridge.dev.refs==2 && dt_fixture.master_device.refs==2 && dt_fixture.provider_device.dev.refs==2);
	assert(dt_fixture.master.refs==3 && dt_fixture.provider.refs==3);
	assert(dt_fixture.provider.status==owner.status_property && of_device_is_available(&dt_fixture.provider)); map_exact();
	assert(n71_dart_host_prepare(&owner,&request)==-EBUSY && dt_fixture.queue_calls==2);
	dt_fixture.bridge.bus=&dt_fixture;
	assert(n71_dart_host_unmap(&owner)==-EBUSY && n71_dart_host_release(&owner)==-EBUSY);
	assert(!dt_fixture.map_reverts && dt_fixture.master.map && owner.bridge);
	dt_fixture.bridge.bus=NULL;
	assert(n71_dart_host_unmap(&owner)==0 && !owner.mapped && !dt_fixture.master.map);
	assert(n71_dart_host_unmap(&owner)==0 && dt_fixture.map_reverts==1);
	assert(n71_dart_host_release(&owner)==-EBUSY && owner.bridge && dt_fixture.status_reverts==0);
	put_device(&dt_fixture.bridge.dev); assert(dt_fixture.bridge.dev.refs==1);
	stop_provider(); assert(dt_fixture.provider_device.dev.refs==1);
	assert(n71_dart_host_release(&owner)==0 && dt_fixture.destroys==2);
	assert(n71_dart_host_release(&owner)==0 && dt_fixture.destroys==2);
	finish(&owner,0,true);

	/* Mutations: accept invalid scope/provider/OF state, or take refs before validation. */
	for (unsigned int invalid=0;invalid<21;invalid++) {
		setup(&owner,&request); int expected=-ENODEV;
		switch(invalid) {
		case 0: request.bridge=NULL; expected=-EINVAL; break;
		case 1: request.provider=NULL; expected=-EINVAL; break;
		case 2: dt_fixture.bridge.bus=&dt_fixture; expected=-EBUSY; break;
		case 3: dt_fixture.machine=false; break;
		case 4: dt_fixture.master.full_name="/soc/other"; break;
		case 5: dt_fixture.provider.full_name="/soc/iommu@603008000"; break;
		case 6: dt_fixture.provider.compatible=false; break;
		case 7: dt_fixture.provider_device.name="foreign"; break;
		case 8: dt_fixture.driver.name="foreign"; break;
		case 9: dt_fixture.provider_device.data=NULL; break;
		case 10: dt_fixture.provider.status=&dt_fixture.foreign_status; expected=-EINVAL; break;
		case 11: dt_fixture.provider.phandle=0; expected=-EINVAL; break;
		case 12: dt_fixture.provider.phandle=0xffffffff; expected=-EINVAL; break;
		case 13: dt_fixture.provider.cells=2; expected=-EINVAL; break;
		case 14: dt_fixture.provider.flags=OF_POPULATED; expected=-EBUSY; break;
		case 15: dt_fixture.master.map=&dt_fixture.foreign_map; expected=-EBUSY; break;
		case 16: dt_fixture.master.mask=&dt_fixture.foreign_map; expected=-EBUSY; break;
		case 17: dt_fixture.master.iommus=&dt_fixture.foreign_map; expected=-EBUSY; break;
		case 18: dt_fixture.lookup_foreign=true; expected=-EINVAL; break;
		case 19: dt_fixture.provider_foreign=true; dt_fixture.foreign_device.registered=true; expected=-EBUSY; break;
		default: dt_fixture.provider_device.dev.parent=NULL; break;
		}
		assert(n71_dart_host_prepare(&owner,&request)==expected && !owner.bridge && !dt_fixture.queue_calls);
		assert(dt_fixture.master.refs==1 && dt_fixture.provider.refs==1 && dt_fixture.foreign_node.refs==1);
		assert(dt_fixture.master_device.refs==1 && dt_fixture.provider_device.dev.refs==1 && dt_fixture.bridge.dev.refs==1);
	}
	/* Mutations: lose partial ownership, ignore apply/notify error, or abandon a completed effect on retry. */
	for (unsigned int fault=0;fault<9;fault++) {
		setup(&owner,&request);
		if (fault<2) dt_fixture.queue_failure=fault+1;
		else if (fault==2) dt_fixture.flag_race=true;
		else if (fault<6) dt_fixture.status_apply_failure=fault-2;
		else dt_fixture.map_apply_failure=fault-5;
		int expected=fault<2 ? -ENOMEM : fault==2 ? -EBUSY : -EIO;
		assert(n71_dart_host_prepare(&owner,&request)==expected && owner.bridge);
		assert(n71_dart_host_unmap(&owner)==0 && !dt_fixture.master.map);
		assert(n71_dart_host_release(&owner)==-EBUSY && owner.bridge);
		stop_provider(); assert(n71_dart_host_release(&owner)==0);
		finish(&owner,fault==2 ? OF_POPULATED : 0,false);
	}
	/* Mutation: trust an apply return while a notifier changed the property identity. */
	for (unsigned int map=0;map<2;map++) {
		setup(&owner,&request);
		if (map) dt_fixture.map_apply_failure=4; else dt_fixture.status_apply_failure=4;
		assert(n71_dart_host_prepare(&owner,&request)==-EIO && owner.bridge);
		if (map) {
			assert(n71_dart_host_unmap(&owner)==-EACCES && !dt_fixture.map_reverts);
			dt_fixture.master.map=owner.map_property;
		}
		assert(n71_dart_host_unmap(&owner)==0); stop_provider();
		if (!map) {
			assert(n71_dart_host_release(&owner)==-EACCES && !dt_fixture.status_reverts);
			dt_fixture.provider.status=owner.status_property;
		}
		assert(n71_dart_host_release(&owner)==0); finish(&owner,0,false);
	}
	/* Mutations: discard pending revert or repeat a revert whose readback already restored state. */
	for (unsigned int which=0;which<2;which++) for (unsigned int fault=1;fault<=4;fault++) {
		setup(&owner,&request); assert(n71_dart_host_prepare(&owner,&request)==0);
		if (which) { assert(n71_dart_host_unmap(&owner)==0); stop_provider(); dt_fixture.status_revert_failure=fault; }
		else dt_fixture.map_revert_failure=fault;
		assert((which ? n71_dart_host_release(&owner) : n71_dart_host_unmap(&owner))==-EIO && owner.bridge);
		unsigned int calls=which ? dt_fixture.status_reverts : dt_fixture.map_reverts;
		if (fault==2) {
			assert((which ? n71_dart_host_release(&owner) : n71_dart_host_unmap(&owner))==0);
			assert((which ? dt_fixture.status_reverts : dt_fixture.map_reverts)==calls);
		} else {
			if (fault==4) {
				assert((which ? n71_dart_host_release(&owner) : n71_dart_host_unmap(&owner))==-EACCES);
				assert((which ? dt_fixture.status_reverts : dt_fixture.map_reverts)==calls);
				if (which) dt_fixture.provider.status=owner.status_property;
				else dt_fixture.master.map=owner.map_property;
			}
			dt_fixture.status_revert_failure=dt_fixture.map_revert_failure=0;
			assert((which ? n71_dart_host_release(&owner) : n71_dart_host_unmap(&owner))==0);
		}
		if (!which) { stop_provider(); assert(n71_dart_host_release(&owner)==0); }
		finish(&owner,0,false);
	}
	/* Mutations: overwrite a foreign property, ignore lost flag/refs, or remove a foreign provider. */
	for (unsigned int drift=0;drift<8;drift++) {
		setup(&owner,&request); assert(n71_dart_host_prepare(&owner,&request)==0);
		if (drift==0) dt_fixture.master.map=&dt_fixture.foreign_map;
		if (drift==1) dt_fixture.master.mask=&dt_fixture.foreign_map;
		if (drift==2) dt_fixture.master.iommus=&dt_fixture.foreign_map;
		if (drift==3) dt_fixture.provider.flags=0;
		if (drift==4) dt_fixture.provider.phandle=42;
		if (drift==5) dt_fixture.bridge.dev.parent=NULL;
		if (drift<6) {
			assert(n71_dart_host_unmap(&owner)==-EACCES && owner.bridge && !dt_fixture.destroys);
			dt_fixture.master.map=owner.map_property; dt_fixture.master.mask=dt_fixture.master.iommus=NULL;
			dt_fixture.provider.flags=OF_POPULATED; dt_fixture.provider.phandle=41;
			dt_fixture.bridge.dev.parent=&dt_fixture.master_device;
			assert(n71_dart_host_unmap(&owner)==0); stop_provider();
		} else {
			assert(n71_dart_host_unmap(&owner)==0); stop_provider();
			if (drift==6) dt_fixture.provider.status=&dt_fixture.foreign_status;
			else { dt_fixture.provider_foreign=true; dt_fixture.foreign_device.registered=true; }
			assert(n71_dart_host_release(&owner)==(drift==6 ? -EACCES : -EBUSY) && owner.bridge);
			dt_fixture.provider.status=owner.status_property; dt_fixture.provider_foreign=false;
			dt_fixture.foreign_device.registered=false;
		}
		assert(n71_dart_host_release(&owner)==0); finish(&owner,0,false);
	}
	printf("N71_DART_HOST_OK cases=%u\n",cases);
	return 0;
}
