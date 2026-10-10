/* SPDX-License-Identifier: GPL-2.0-only */
/* Compile the real caller and genpd backend; kernel API fixtures are not hardware proof. */
#include <stdarg.h>
#include "n71_i2c_genpd_fixture.c"

#define N71_PMGR_PATH "/soc/power-management@20e000000"
#define PAGE_SIZE 4096
#define __init
#define __exit
#define THIS_MODULE ((void *)1)
#define DEFINE_MUTEX(name) int name
#define MODULE_PARM_DESC(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define module_param(...)
#define module_param_cb(name, ops, arg, mode) static const void *name##_used __attribute__((unused)) = ops
#define module_init(fn) static const void *init_used __attribute__((unused)) = fn
#define module_exit(fn) static const void *exit_used __attribute__((unused)) = fn
#define scnprintf snprintf
struct kernel_param { int unused; };
struct kernel_param_ops {
	int (*set)(const char *, const struct kernel_param *);
	int (*get)(char *, const struct kernel_param *);
};
static int module_refs, root_error, root_validation_error, missing_node, unregisters;
static bool module_live;
static char last_log[1024];
static char controller_log[1024];
static void mutex_lock(int *lock) { assert(!*lock); *lock=1; }
static void mutex_unlock(int *lock) { assert(*lock); *lock=0; }
static bool try_module_get(void *module) { assert(module==THIS_MODULE); if (!module_live) return false; module_refs++; return true; }
static void __module_get(void *module) { assert(module==THIS_MODULE && module_refs>0); module_refs++; }
static void module_put(void *module) { assert(module==THIS_MODULE && module_refs>0); module_refs--; }
static bool sysfs_streq(const char *text, const char *expected)
{ size_t length=strlen(expected); return !strcmp(text,expected) || (strlen(text)==length+1 && !strncmp(text,expected,length) && text[length]=='\n'); }
static void pr_info(const char *format, ...)
{
	va_list args; va_start(args,format); vsnprintf(last_log,sizeof(last_log),format,args); va_end(args);
	if (!strncmp(last_log,"N71_I2C_CONTROLLER ",19)) strcpy(controller_log,last_log);
}
static struct device *root_device_register(const char *name)
{
	assert(!strcmp(name,"n71-i2c1-power"));
	if (root_error) return ERR_PTR(root_error);
	consumer.of_node=NULL; consumer.registered=true; consumer.refs=1;
	return &consumer;
}
static void root_device_unregister(struct device *device)
{ assert(device==&consumer && !device->of_node && device->registered && device->refs==1); unregisters++; device->registered=false; device->refs=0; }
static int n71_pmgr_root_validate(struct device_node *node)
{ assert(node==&nodes[ROOT_NODE]); return root_validation_error; }
static struct device_node *diagnostic_find_node(const char *path)
{
	int index=-1;
	if (!strcmp(path,N71_PMGR_PATH)) index=ROOT_NODE;
	else if (!strcmp(path,"/soc/i2c@20a111000")) index=CONSUMER_NODE;
	else for (unsigned int i=0;i<3;i++) if (!strcmp(path,n71_domains[i].path)) index=LEAF_NODE+(int)i;
	assert(index>=0);
	return index==missing_node ? NULL : node_get((unsigned int)index);
}
#define of_find_node_by_path diagnostic_find_node
#define __iomem
#define N71_CONTROLLER_INTEGRATION
#include "n71_i2c_controller_observe.c"
#include "n71-i2c-power-diagnostic.c"
#undef of_find_node_by_path

static void caller_reset(void)
{
	assert(!module_refs && !diagnostic_lock);
	reset(); memset(&diagnostic_backend,0,sizeof(diagnostic_backend));
	memset(&diagnostic_state,0,sizeof(diagnostic_state)); memset(&diagnostic_io,0,sizeof(diagnostic_io));
	diagnostic_pmgr=diagnostic_node=NULL; diagnostic_ready=diagnostic_retained=false;
	run=true; root_error=root_validation_error=unregisters=0; missing_node=-1; module_live=true; last_log[0]=0;
	observe_reset(); controller_log[0]=0;
}
static void caller_clean(void)
{
	assert(n71_diagnostic_clean() && !diagnostic_retained && !module_refs);
	assert(!diagnostic_lock && !virtual_device.refs); balanced();
}
static void caller_exit(void)
{
	assert(!module_refs && n71_diagnostic_clean()); n71_i2c_power_diagnostic_exit();
	assert(!diagnostic_ready && !diagnostic_backend.consumer && !diagnostic_pmgr && !diagnostic_node);
	assert(!diagnostic_lock && !module_refs && !virtual_device.refs);
	for (unsigned int i=0;i<NODE_COUNT;i++) assert(nodes[i].refs==1);
}
static void caller_init(void)
{
	assert(n71_i2c_power_diagnostic_init()==0);
	assert(diagnostic_ready && !attaches && !put_calls && !detaches && !module_refs && reads==2);
	assert(!observe_claims && !observe_reads);
	assert(nodes[ROOT_NODE].refs==2 && nodes[CONSUMER_NODE].refs==2);
	for (unsigned int i=0;i<3;i++) assert(nodes[LEAF_NODE+i].refs==2);
}
static void caller_idle(void)
{
	assert(n71_diagnostic_clean() && !diagnostic_retained && !module_refs && !virtual_device.refs);
	assert(!diagnostic_lock); for (unsigned int i=0;i<3;i++) assert(!held[i]);
	assert(!observe_region && !observe_mapping);
}
int main(void)
{
	unsigned int cases=0;
	char status[PAGE_SIZE];
	caller_reset(); assert(n71_diagnostic_action("cycle",NULL)==-ENODEV); caller_clean(); cases++;
	caller_reset(); assert(n71_diagnostic_action("cleanup",NULL)==-ENODEV); caller_clean(); cases++;
	caller_reset(); assert(n71_diagnostic_action("invalid",NULL)==-EINVAL); caller_clean(); cases++;
	caller_reset(); module_live=false; assert(n71_diagnostic_action("cycle",NULL)==-ENODEV); caller_clean(); cases++;
	caller_reset(); run=false; assert(n71_i2c_power_diagnostic_init()==-ENODEV); caller_clean(); cases++;
	for (int node=ROOT_NODE;node<=BUS_NODE;node++) {
		caller_reset(); missing_node=node; assert(n71_i2c_power_diagnostic_init()==-ENODEV);
		caller_clean(); assert(!diagnostic_backend.consumer && !diagnostic_node && !diagnostic_pmgr); cases++;
	}
	caller_reset(); root_validation_error=-EIO; assert(n71_i2c_power_diagnostic_init()==-EIO); caller_clean(); cases++;
	caller_reset(); root_error=-ENOMEM; assert(n71_i2c_power_diagnostic_init()==-ENOMEM); caller_clean(); cases++;
	for (int index=0;index<3;index++) {
		caller_reset(); lock_fail=index; assert(n71_i2c_power_diagnostic_init()==-ENODEV); caller_clean(); assert(unregisters==1); cases++;
		caller_reset(); drivers[index].suppress_bind_attrs=false; assert(n71_i2c_power_diagnostic_init()==-ENODEV); caller_clean(); cases++;
	}
	for (int id=CONTROLLER;id<=ADAPTER;id++) {
		caller_reset(); fault=(enum fault)id; assert(n71_i2c_power_diagnostic_init()==-EBUSY); caller_clean(); cases++;
	}
	caller_reset(); samples[0][0]=samples[0][1]=0x100000ff; assert(n71_i2c_power_diagnostic_init()==-EBUSY); caller_clean(); cases++;
	caller_reset(); read_fail=1; assert(n71_i2c_power_diagnostic_init()==-EIO); caller_clean(); cases++;
	caller_reset(); caller_init(); assert(n71_diagnostic_action("cleanup\n",NULL)==0 && !attaches && !put_calls); caller_idle(); cases++;
	assert(n71_diagnostic_action("cycle\n",NULL)==0); assert(attaches==1 && put_calls==1 && detaches==1); caller_idle(); cases++;
	assert(n71_diagnostic_status(status,NULL)>0); assert(!strcmp(status,"ready=1 active=0 attached=0 cleanup_pending=0 usage_held=0 module_retained=0 cleanup_error=0\n")); cases++;
	assert(n71_diagnostic_action("cycle",NULL)==0); caller_idle(); assert(put_calls==2 && detaches==2); caller_exit(); assert(unregisters==1); cases++;
	for (int id=ATTACH_NULL;id<=ATTACH_ERROR;id++) {
		caller_reset(); caller_init(); fault=(enum fault)id; assert(n71_diagnostic_action("cycle",NULL)<0); caller_idle(); caller_exit(); cases++;
	}
	caller_reset(); caller_init(); resume_error=-EIO; assert(n71_diagnostic_action("cycle",NULL)==-EIO); caller_idle(); assert(!put_calls && detaches==1); caller_exit(); cases++;
	caller_reset(); caller_init(); read_fail=3; assert(n71_diagnostic_action("cycle",NULL)==-EIO); caller_idle(); assert(put_calls==1 && detaches==1); caller_exit(); cases++;
	caller_reset(); caller_init(); suspend_error=-ETIMEDOUT; assert(n71_diagnostic_action("cycle",NULL)==-ETIMEDOUT);
	assert(module_refs==1 && diagnostic_retained && diagnostic_state.cleanup_pending && diagnostic_backend.domain);
	assert(!diagnostic_state.usage_held && !virtual_device.power.usage_count && put_calls==1 && !detaches); cases++;
	assert(n71_diagnostic_action("cycle",NULL)==-EBUSY && module_refs==1 && attaches==1 && put_calls==1); cases++;
	assert(n71_diagnostic_action("cleanup",NULL)==-ETIMEDOUT && module_refs==1 && put_calls==1); cases++;
	suspend_error=0; assert(n71_diagnostic_action("cleanup",NULL)==0); caller_idle(); assert(put_calls==1 && detaches==1); caller_exit(); cases++;
	caller_reset(); caller_init(); suspend_keeps_power=true; assert(n71_diagnostic_action("cycle",NULL)==-EBUSY);
	assert(module_refs==1 && diagnostic_retained && diagnostic_state.cleanup_pending && !virtual_device.power.usage_count && !detaches);
	assert(n71_diagnostic_status(status,NULL)>0 && strstr(status,"module_retained=1") && strstr(status,"cleanup_error=-16")); cases++;
	assert(n71_diagnostic_action("cleanup",NULL)==-EBUSY && module_refs==1 && put_calls==1 && !detaches); cases++;
	/* Fixture simulates an externally quiesced leaf; caller does not force recovery. */
	samples[0][0]=samples[0][1]=0; assert(n71_diagnostic_action("cleanup",NULL)==0); caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); detach_fail=true; assert(n71_diagnostic_action("cycle",NULL)==-EBUSY);
	assert(module_refs==1 && diagnostic_retained && diagnostic_state.cleanup_pending && virtual_device.refs==2 && detaches==1); cases++;
	detach_fail=false; assert(n71_diagnostic_action("cleanup",NULL)==0); caller_idle(); assert(detaches==2 && put_calls==1); caller_exit(); cases++;
	caller_reset(); assert(n71_diagnostic_action("inspect",NULL)==-ENODEV && !observe_claims); caller_clean(); cases++;
	caller_reset(); caller_init(); assert(n71_diagnostic_action("inspect\n",NULL)==0);
	assert(observe_reads==6 && observe_unmaps==1 && observe_releases==1 && put_calls==1 && detaches==1);
	assert(!strcmp(controller_log,"N71_I2C_CONTROLLER complete=1 stable=1 idle_status=1 error=0 rev=00000005,00000005 smsta=00010000,00010000 xfsta=00000000,00000000 controller_writes=0 charger_io=0\n"));
	caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); resume_error=-EIO; assert(n71_diagnostic_action("inspect",NULL)==-EIO && !observe_claims);
	caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); read_fail=3; assert(n71_diagnostic_action("inspect",NULL)==-EIO && !observe_claims);
	caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); observe_busy=true; assert(n71_diagnostic_action("inspect",NULL)==-EBUSY);
	assert(strstr(controller_log,"complete=0 stable=0 idle_status=0 error=-16"));
	assert(!observe_maps && !observe_reads && put_calls==1 && detaches==1); caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); observe_map_failure=true; assert(n71_diagnostic_action("inspect",NULL)==-ENOMEM);
	assert(!observe_reads && observe_releases==1 && put_calls==1 && detaches==1); caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); observe_samples[1][0]=~0U; assert(n71_diagnostic_action("inspect",NULL)==-ENODEV);
	assert(strstr(controller_log,"complete=1 stable=0 idle_status=0 error=-19"));
	assert(observe_reads==6 && observe_releases==1 && put_calls==1 && detaches==1); caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); observe_samples[1][0]++; assert(n71_diagnostic_action("inspect",NULL)==0);
	assert(observe_reads==6 && observe_releases==1 && put_calls==1 && detaches==1); caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); observe_busy=true; suspend_error=-ETIMEDOUT;
	assert(n71_diagnostic_action("inspect",NULL)==-EBUSY && diagnostic_state.cleanup_error==-ETIMEDOUT);
	assert(module_refs==1 && diagnostic_retained && !observe_region && !observe_mapping && put_calls==1 && !detaches); cases++;
	assert(n71_diagnostic_action("inspect",NULL)==-EBUSY && observe_claims==1 && module_refs==1 && put_calls==1); cases++;
	suspend_error=0; assert(n71_diagnostic_action("cleanup",NULL)==0); caller_idle(); caller_exit(); cases++;
	caller_reset(); caller_init(); suspend_error=-ETIMEDOUT; assert(n71_diagnostic_action("inspect",NULL)==-ETIMEDOUT);
	assert(observe_reads==6 && observe_releases==1 && module_refs==1 && diagnostic_retained && !detaches); cases++;
	suspend_error=0; assert(n71_diagnostic_action("cleanup",NULL)==0); caller_idle(); caller_exit(); cases++;
	printf("N71_I2C_CALLER_OK cases=%u\n",cases);
	return 0;
}
